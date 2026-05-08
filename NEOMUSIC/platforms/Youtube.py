import asyncio
import re
import logging
import aiohttp
import yt_dlp
from typing import Union, Optional, Tuple
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from NEOMUSIC.utils.formatters import time_to_seconds
from NEOMUSIC import LOGGER

# --- CONFIG ---
# Agar aapka FastAPI server chal raha hai toh uska URL yahan dalein
# Agar nahi chal raha toh ye automatic yt-dlp use karega
API_URL = "http://kiru-bot.up.railway.app" 

def get_clean_id(link: str) -> Optional[str]:
    """YouTube ID extract karne ke liye"""
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

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + str(link)
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Optional[str]:
        """EXTRACT URL FROM MESSAGE (Fixes AttributeError)"""
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

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + str(link)
        try:
            # Check if it's a direct URL or a search query
            if not await self.exists(link):
                search = VideosSearch(link, limit=1)
                resp = await search.next()
                res = resp.get("result", [])
            else:
                link = link.split("&")[0]
                results = VideosSearch(link, limit=1)
                res_data = await results.next()
                res = res_data.get("result", [])

            if not res: return None
            video = res[0]
            thumb = video["thumbnails"][0]["url"].split("?")[0] if video.get("thumbnails") else "https://i.ibb.co/d44s0cZR/x.jpg"
            
            return (
                video.get("title", "Unknown Title"),
                video.get("duration", "00:00"),
                int(time_to_seconds(video.get("duration", "00:00"))),
                thumb,
                video.get("id")
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
        """Returns streamable URL."""
        if videoid: link = self.base + str(link)
        m_type = "video" if video else "audio"
        video_id = get_clean_id(link)

        # 1. Try API first (Fastest)
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{API_URL}/download", params={"url": video_id, "type": m_type}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        token = data.get("download_token")
                        if token:
                            return f"{API_URL}/stream/{video_id}?type={m_type}&token={token}", True
        except:
            pass

        # 2. Fallback: yt-dlp (Strongest)
        try:
            ydl_opts = {
                "format": "bestaudio/best" if not video else "bestvideo+bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "geo_bypass": True,
                "nocheckcertificate": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, link, download=False)
                if info and 'url' in info:
                    return info['url'], True
        except Exception as e:
            LOGGER.error(f"Download Error: {e}")
            
        return None, False

# Initialize
YouTube = YouTubeAPI()
