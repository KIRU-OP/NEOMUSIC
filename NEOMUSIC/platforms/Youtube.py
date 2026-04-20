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
    LOGGER.error("Config file not found! Ensure API_ID, BOT_TOKEN and MONGO_DB_URI are set.")

# --- SECURITY FILTER ---
class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        msg = str(record.msg)
        patterns = [
            r"\d{8,10}:[a-zA-Z0-9_-]{35,}",  # Telegram Bot Token
            r"mongodb\+srv://\S+",           # Mongo DB URI
        ]
        for pattern in patterns:
            msg = re.sub(pattern, "[PROTECTED]", msg)
        record.msg = msg
        return True

logging.getLogger().addFilter(SensitiveDataFilter())

API_URL = "http://kiru-bot.up.railway.app"

# --- UTILS ---
def get_clean_id(link: str) -> Optional[str]:
    """Video ID extract aur sanitize karne ke liye"""
    if "v=" in link:
        video_id = link.split('v=')[-1].split('&')[0]
    elif "youtu.be/" in link:
        video_id = link.split('youtu.be/')[-1].split('?')[0]
    else:
        video_id = link
    clean_id = re.sub(r'[^a-zA-Z0-9_-]', '', video_id)
    return clean_id if 5 <= len(clean_id) <= 15 else None

async def get_direct_stream_link(link: str, media_type: str) -> Optional[str]:
    """Direct streamable URL generate karne ke liye"""
    video_id = get_clean_id(link)
    if not video_id:
        return None

    try:
        timeout = aiohttp.ClientTimeout(total=30) 
        async with aiohttp.ClientSession(headers={"User-Agent": "ShrutiMusicBot/1.0"}, timeout=timeout) as session:
            async with session.get(f"{API_URL}/download", params={"url": video_id, "type": media_type}) as resp:
                if resp.status != 200: return None
                data = await resp.json()
                token = data.get("download_token")
                if not token: return None

            return f"{API_URL}/stream/{video_id}?type={media_type}&token={token}"
    except Exception as e:
        LOGGER.error(f"Streaming API Error: {e}")
    return None

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Optional[str]:
        """Message se URL extract karne ke liye (Ye function error fix karega)"""
        for msg in [message, message.reply_to_message]:
            if not msg: continue
            text = msg.text or msg.caption
            if not text: continue
            
            if msg.entities:
                for entity in msg.entities:
                    if entity.type == MessageEntityType.URL:
                        return text[entity.offset : entity.offset + entity.length]
            if msg.caption_entities:
                for entity in msg.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
            
            # Regex fallback
            urls = re.findall(r'(https?://\S+)', text)
            if urls: return urls[0]
        return None

    async def search(self, query: str, limit: int = 1):
        try:
            search = VideosSearch(query, limit=limit)
            resp = await search.next()
            return resp.get("result", [])
        except Exception as e:
            LOGGER.error(f"Search Error: {e}")
            return []

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        is_url = await self.exists(link)
        try:
            if is_url:
                link = link.split("&")[0]
                results = VideosSearch(link, limit=1)
                res_data = await results.next()
                res = res_data["result"]
            else:
                res = await self.search(link, limit=1)

            if not res: return None
            video = res[0]
            return (
                video["title"],
                video["duration"],
                int(time_to_seconds(video["duration"])),
                video["thumbnails"][0]["url"].split("?")[0],
                video["id"]
            )
        except Exception:
            return None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        det = await self.details(link, videoid)
        return det[0] if det else "Unknown Title"

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        stream_link = await get_direct_stream_link(link, "video")
        return (1, stream_link) if stream_link else (0, "Stream Failed")

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid: link = self.listbase + link
        try:
            plist = await Playlist.get(link)
            return [v["id"] for v in plist.get("videos", [])[:limit] if v.get("id")]
        except:
            return []

    async def track(self, query: str, videoid: Union[bool, str] = None):
        det = await self.details(query, videoid)
        if not det: return None, None
        track_details = {
            "title": det[0],
            "link": self.base + det[4],
            "vidid": det[4],
            "duration_min": det[1],
            "thumb": det[3],
        }
        return track_details, det[4]

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        ytdl_opts = {"quiet": True, "no_warnings": True}
        try:
            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, link, download=False)
            return info.get("formats", []), link
        except:
            return [], link

    async def download(
        self,
        link: str,
        mystic=None,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        **kwargs
    ) -> Tuple[Optional[str], bool]:
        """Direct stream link return karta hai fast playback ke liye"""
        if videoid: link = self.base + link
        m_type = "video" if video else "audio"
        
        # API se stream link lene ki koshish
        stream_link = await get_direct_stream_link(link, m_type)
        if stream_link:
            return stream_link, True
        
        # Fallback: yt-dlp direct extract
        try:
            ydl_opts = {"format": "bestaudio/best" if not video else "best", "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, link, download=False)
                return info['url'], True
        except:
            return None, False

# Initialize Instance
YouTube = YouTubeAPI()
