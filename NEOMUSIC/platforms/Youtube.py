import asyncio
import os
import re
import logging
import aiohttp
import yt_dlp
from typing import Union, Optional, Tuple, List
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from NEOMUSIC.utils.formatters import time_to_seconds
from NEOMUSIC import LOGGER

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

API_URL = "https://kiru-bot.up.railway.app"

def get_clean_id(link: str) -> Optional[str]:
    if "v=" in link:
        video_id = link.split('v=')[-1].split('&')[0]
    elif "youtu.be/" in link:
        video_id = link.split('youtu.be/')[-1].split('?')[0]
    else:
        video_id = link
    clean_id = re.sub(r'[^a-zA-Z0-9_-]', '', video_id)
    return clean_id if 5 <= len(clean_id) <= 15 else None

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "source_address": "0.0.0.0",
        }

    async def exists(self, link: str):
        return bool(re.search(self.regex, link))

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid: 
            link = self.base + link
        
        # Method 1: Try with youtubesearchpython
        try:
            results = VideosSearch(link, limit=1)
            res_data = await results.next()
            res = res_data.get("result", [])
            if res:
                video = res[0]
                return (
                    video["title"],
                    video.get("duration", "00:00"),
                    int(time_to_seconds(video.get("duration", "00:00"))),
                    video["thumbnails"][0]["url"].split("?")[0],
                    video["id"]
                )
        except Exception as e:
            LOGGER.warning(f"Search API failed, trying yt-dlp: {e}")

        # Method 2: Fallback to yt-dlp (Stronger for direct URLs)
        try:
            info = await asyncio.to_thread(self._extract_info, link, {"quiet": True, "noplaylist": True})
            if info:
                return (
                    info.get("title", "Unknown"),
                    "00:00", # yt-dlp duration formatting is complex, keeping simple
                    int(info.get("duration", 0)),
                    info.get("thumbnail", ""),
                    info.get("id")
                )
        except Exception as e:
            LOGGER.error(f"yt-dlp details error: {e}")
        
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

    def _extract_info(self, link, opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(link, download=False)

    async def download(self, link: str, video: bool = False, videoid: Union[bool, str] = None) -> Tuple[Optional[str], bool]:
        if videoid: link = self.base + link
        m_type = "video" if video else "audio"
        
        # 1. API Method
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                vid_id = get_clean_id(link)
                async with session.get(f"{API_URL}/download", params={"url": vid_id, "type": m_type}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        token = data.get("download_token")
                        if token:
                            return f"{API_URL}/stream/{vid_id}?type={m_type}&token={token}", True
        except:
            pass

        # 2. Fallback: Direct yt-dlp
        try:
            info = await asyncio.to_thread(self._extract_info, link, self.ydl_opts)
            return info['url'], True
        except Exception as e:
            LOGGER.error(f"Download error: {e}")
            return None, False

YouTube = YouTubeAPI()
