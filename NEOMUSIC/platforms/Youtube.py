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

# API URL
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

    # --- YE METHOD MISSING THA (ISSUE FIX) ---
    async def url(self, message: Message) -> Optional[str]:
        """Extracts URL from message or replied message"""
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
        if videoid: 
            link = self.base + link
        
        is_url = await self.exists(link)
        if is_url:
            try:
                info = await asyncio.to_thread(self._extract_info, link, {"quiet": True, "noplaylist": True, "skip_download": True})
                if info:
                    return (
                        info.get("title", "Unknown Title"),
                        "00:00",
                        int(info.get("duration", 0)),
                        info.get("thumbnail", ""),
                        info.get("id")
                    )
            except Exception as e:
                LOGGER.warning(f"yt-dlp details failed: {e}")

        try:
            search = VideosSearch(link, limit=1)
            res_data = await search.next()
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
            LOGGER.error(f"Search Error: {e}")
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

        try:
            info = await asyncio.to_thread(self._extract_info, link, self.ydl_opts)
            return info['url'], True
        except Exception as e:
            LOGGER.error(f"Download error: {e}")
            return None, False

YouTube = YouTubeAPI()
