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
# Yahan apne FastAPI server ka URL daalein (Jaise: https://aapka-app.railway.app)
API_URL = "https://kiru-bot.up.railway.app" 

def get_clean_id(link: str) -> Optional[str]:
    if "v=" in link:
        return link.split('v=')[-1].split('&')[0]
    elif "youtu.be/" in link:
        return link.split('youtu.be/')[-1].split('?')[0]
    return link if 5 <= len(link) <= 15 else None

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="

    async def details(self, query: str):
        try:
            search = VideosSearch(query, limit=1)
            resp = await search.next()
            res = resp.get("result", [])
            if not res:
                return None
            
            video = res[0]
            thumb = video["thumbnails"][0]["url"].split("?")[0] if video.get("thumbnails") else "https://telegra.ph/file/default_thumb.png"
            
            return (
                video.get("title", "Unknown"),
                video.get("duration", "00:00"),
                int(time_to_seconds(video.get("duration", "00:00"))),
                thumb,
                video.get("id")
            )
        except Exception as e:
            LOGGER.error(f"Details Error: {e}")
            return None

    async def track(self, query: str):
        det = await self.details(query)
        if not det:
            # NoneType Error fix karne ke liye default values
            return {
                "title": "Song Not Found",
                "link": self.base,
                "vidid": "None",
                "duration_min": "00:00",
                "thumb": "https://i.ibb.co/d44s0cZR/x.jpg",
            }, None
        
        return {
            "title": det[0],
            "link": self.base + det[4],
            "vidid": det[4],
            "duration_min": det[1],
            "thumb": det[3],
        }, det[4]

    async def download(self, link: str, video: bool = False):
        video_id = get_clean_id(link)
        m_type = "video" if video else "audio"
        
        # 1. Pehle API se stream link mangiye
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_URL}/download", params={"url": video_id, "type": m_type}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        token = data.get("download_token")
                        if token:
                            # Direct aapke server ka link return hoga
                            return f"{API_URL}/stream/{video_id}?type={m_type}&token={token}", True
        except Exception as e:
            LOGGER.warning(f"API Connection Failed: {e}")

        # 2. Fallback: Agar API kaam na kare toh yt-dlp
        try:
            ydl_opts = {"format": "bestaudio/best", "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, link, download=False)
                return info['url'], True
        except Exception:
            return None, False

YouTube = YouTubeAPI()
