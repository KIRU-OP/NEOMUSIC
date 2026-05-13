import asyncio
import os
import re
import logging
import aiohttp
import yt_dlp
from typing import Union, Optional, Tuple, List
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch, Playlist
from NEOMUSIC.utils.formatters import time_to_seconds
from NEOMUSIC import LOGGER

# --- CONFIGURATION ---
try:
    from config import API_ID, BOT_TOKEN, MONGO_DB_URI
except ImportError:
    LOGGER.error("Config file not found!")

# --- SECURITY FILTER ---
class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        msg = str(record.msg)
        patterns = [r"\d{8,10}:[a-zA-Z0-9_-]{35,}", r"mongodb\+srv://\S+"]
        for pattern in patterns:
            msg = re.sub(pattern, "[PROTECTED]", msg)
        record.msg = msg
        return True

logging.getLogger().addFilter(SensitiveDataFilter())

API_URL = "kiru-bots.up.railway.app"

# --- UTILS ---
def get_clean_id(link: str) -> Optional[str]:
    """Extracts and sanitizes YouTube Video ID"""
    if "v=" in link:
        video_id = link.split('v=')[-1].split('&')[0]
    elif "youtu.be/" in link:
        video_id = link.split('youtu.be/')[-1].split('?')[0]
    else:
        video_id = link
    clean_id = re.sub(r'[^a-zA-Z0-9_-]', '', video_id)
    return clean_id if 5 <= len(clean_id) <= 15 else None


async def get_direct_stream_link(link: str, media_type: str) -> Optional[str]:
    """Generates direct streamable URL via API"""
    video_id = get_clean_id(link)
    if not video_id:
        return None
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout
        ) as session:
            async with session.get(
                f"{API_URL}/download",
                params={"url": video_id, "type": media_type}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    token = data.get("download_token")
                    if token:
                        return f"{API_URL}/stream/{video_id}?type={media_type}&token={token}"
    except Exception:
        pass  # Fallback to yt-dlp
    return None


def extract_url_from_info(info: dict, prefer_video: bool = False) -> Optional[str]:
    """
    Safely extracts a playable URL from yt-dlp info dict.
    Handles merged formats, single formats, and formats list.
    
    - prefer_video=False  → pick audio stream (for music bots)
    - prefer_video=True   → pick video stream
    """

    # Case 1: Merged format (e.g. bestvideo+bestaudio) — URLs are inside requested_formats
    requested = info.get("requested_formats")
    if requested:
        if not prefer_video:
            # Audio-only stream
            for fmt in requested:
                if fmt.get("acodec", "none") != "none" and fmt.get("url"):
                    return fmt["url"]
        else:
            # Video stream (with audio if available, else video-only)
            for fmt in requested:
                if fmt.get("vcodec", "none") != "none" and fmt.get("url"):
                    return fmt["url"]

    # Case 2: Single format — direct URL on info dict
    if info.get("url"):
        return info["url"]

    # Case 3: Formats list — last entry is usually best quality
    formats = info.get("formats", [])
    if formats:
        if not prefer_video:
            # Pick best audio-only format
            audio_formats = [
                f for f in formats
                if f.get("acodec", "none") != "none"
                and f.get("vcodec", "none") == "none"
                and f.get("url")
            ]
            if audio_formats:
                return audio_formats[-1]["url"]
        # Fallback: last format in list
        for fmt in reversed(formats):
            if fmt.get("url"):
                return fmt["url"]

    return None


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Optional[str]:
        """Extracts URL from message or replied message"""
        messages = [message, message.reply_to_message]
        for msg in messages:
            if not msg:
                continue
            text = msg.text or msg.caption
            if not text:
                continue
            if msg.entities:
                for entity in msg.entities:
                    if entity.type == MessageEntityType.URL:
                        return text[entity.offset: entity.offset + entity.length]
            urls = re.findall(r'(https?://\S+)', text)
            if urls:
                return urls[0]
        return None

    async def search(self, query: str, limit: int = 1):
        """Search videos using youtubesearchpython"""
        try:
            search = VideosSearch(query, limit=limit)
            resp = await search.next()
            return resp.get("result", [])
        except Exception as e:
            LOGGER.error(f"Search Error: {e}")
            return []

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        try:
            if not await self.exists(link):
                res = await self.search(link, limit=1)
            else:
                link = link.split("&")[0]
                results = VideosSearch(link, limit=1)
                res_data = await results.next()
                res = res_data.get("result", [])

            if not res:
                return None
            video = res[0]
            return (
                video["title"],
                video.get("duration", "00:00"),
                int(time_to_seconds(video.get("duration", "00:00"))),
                video["thumbnails"][0]["url"].split("?")[0],
                video["id"],
            )
        except Exception as e:
            LOGGER.error(f"Details Error: {e}")
            return None

    async def track(self, query: str, videoid: Union[bool, str] = None):
        det = await self.details(query, videoid)
        if not det:
            return None, None
        track_details = {
            "title": det[0],
            "link": self.base + det[4],
            "vidid": det[4],
            "duration_min": det[1],
            "thumb": det[3],
        }
        return track_details, det[4]

    async def download(
        self,
        link: str,
        mystic=None,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        **kwargs,
    ) -> Tuple[Optional[str], bool]:
        """
        Returns (streamable_url, True) or (None, False).

        Fix for WebpageMediaEmpty:
        - yt-dlp bestvideo+bestaudio format stores URLs inside
          `requested_formats`, NOT at the top-level `info['url']`.
        - extract_url_from_info() handles all three cases correctly.
        """
        if videoid:
            link = self.base + link

        m_type = "video" if video else "audio"

        # --- Step 1: Try fast API stream ---
        stream_link = await get_direct_stream_link(link, m_type)
        if stream_link:
            return stream_link, True

        # --- Step 2: yt-dlp fallback ---
        try:
            if not video:
                # Audio: single-stream format, always has top-level URL
                fmt = "bestaudio/best"
            else:
                # Video: prefer mp4 container to avoid remux issues
                fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

            ydl_opts = {
                "format": fmt,
                "quiet": True,
                "no_warnings": True,
                "geo_bypass": True,
                "nocheckcertificate": True,
                # Do NOT merge — we want direct stream URLs, not a local file
                "noplaylist": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(
                    ydl.extract_info, link, download=False
                )

            url = extract_url_from_info(info, prefer_video=bool(video))
            if url:
                return url, True

            LOGGER.warning(f"yt-dlp returned no URL for: {link}")

        except yt_dlp.utils.DownloadError as e:
            LOGGER.error(f"yt-dlp DownloadError: {e}")
        except Exception as e:
            LOGGER.error(f"yt-dlp unexpected error: {e}")

        return None, False


# Initialize
YouTube = YouTubeAPI()
