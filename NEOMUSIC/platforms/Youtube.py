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

API_URL = "http://kiru-bot.up.railway.app"

# --- UTILS ---
def get_clean_id(link: str) -> Optional[str]:
    if "v=" in link:
        video_id = link.split('v=')[-1].split('&')[0]
    elif "youtu.be/" in link:
        video_id = link.split('youtu.be/')[-1].split('?')[0]
    else:
        video_id = link
    clean_id = re.sub(r'[^a-zA-Z0-9_-]', '', video_id)
    return clean_id if 5 <= len(clean_id) <= 15 else None

async def get_direct_stream_link(link: str, media_type: str) -> Optional[str]:
    video_id = get_clean_id(link)
    if not video_id:
        return None
    try:
        timeout = aiohttp.ClientTimeout(total=10) 
        async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout) as session:
            async with session.get(f"{API_URL}/download", params={"url": video_id, "type": media_type}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    token = data.get("download_token")
                    if token:
                        return f"{API_URL}/stream/{video_id}?type={media_type}&token={token}"
    except:
        pass
    return None

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"

    async def exists(self, link: str):
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Optional[str]:
        messages = [message, message.reply_to_message]
        for msg in messages:
            if not msg: continue
            text = msg.text or msg.caption
            if not text: continue
            if msg.entities:
                for entity in msg.entities:
                    if entity.type == MessageEntityType.URL:
                        return text[entity.offset : entity.offset + entity.length]
            urls = re.findall(r'(https?://\S+)', text)
            if urls: return urls[0]
        return None

    async def details(self, query: str, videoid: Union[bool, str] = None):
        if videoid: 
            query = self.base + query
        try:
            search = VideosSearch(query, limit=1)
            resp = await search.next()
            res = resp.get("result", [])
            if not res:
                return None
            
            video = res[0]
            return (
                video["title"],
                video.get("duration", "00:00"),
                int(time_to_seconds(video.get("duration", "00:00"))),
                video["thumbnails"][0]["url"].split("?")[0],
                video["id"]
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
        **kwargs
    ) -> Tuple[Optional[str], bool]:
        if videoid: 
            link = self.base + link
        
        m_type = "video" if video else "audio"
        
        # 1. Try External API (Fastest)
        stream_link = await get_direct_stream_link(link, m_type)
        if stream_link:
            return stream_link, True
        
        # 2. Fallback: yt-dlp with specific headers to prevent WebpageMediaEmpty
        try:
            ydl_opts = {
                "format": "bestaudio/best" if not video else "bestvideo[height<=720]+bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            
            # Use cookies if available (Recommended to prevent 403 errors)
            if os.path.exists("cookies.txt"):
                ydl_opts["cookiefile"] = "cookies.txt"

            def extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(link, download=False)

            info = await asyncio.to_thread(extract)
            
            # Attempt to get the direct URL
            if "url" in info:
                return info["url"], True
            elif "formats" in info:
                # Fallback to the first available format if 'url' is missing
                return info["formats"][0]["url"], True
                
        except Exception as e:
            LOGGER.error(f"yt-dlp Error: {e}")
            
        return None, False

YouTube = YouTubeAPI()
