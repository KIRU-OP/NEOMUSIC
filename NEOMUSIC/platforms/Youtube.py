import asyncio
import re
import aiohttp
from typing import Union, Optional, Tuple
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

# External libraries for YouTube Search
try:
    from py_yt import VideosSearch
except ImportError:
    from youtubesearchpython.__future__ import VideosSearch

# Try to import project-specific utilities, otherwise fallback to defaults
try:
    from SONALI import LOGGER
    from SONALI.utils.formatters import time_to_seconds
except ImportError:
    import logging
    LOGGER = logging.getLogger(__name__)
    def time_to_seconds(time_str: str) -> int:
        try:
            parts = list(map(int, time_str.split(':')))
            return sum(x * 60**i for i, x in enumerate(reversed(parts)))
        except:
            return 0

API_URL = "https://kiru-bot.up.railway.app"

async def fetch_stream_link(link: str, mode: str = "audio") -> Optional[str]:
    """
    Fetches the direct streaming URL from the API.
    Does not download the file to the local server.
    """
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link
    if not video_id or len(video_id) < 3:
        return None

    try:
        # We use a short timeout because we only need the URL metadata, not the file
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Step 1: Request Download Token
            params = {"url": video_id, "type": mode}
            async with session.get(f"{API_URL}/download", params=params) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                token = data.get("download_token")
                if not token:
                    return None

            # Step 2: Construct the Stream URL
            stream_url = f"{API_URL}/stream/{video_id}?type={mode}&token={token}"
            
            # Step 3: Get the Final Redirected URL (Direct Link)
            async with session.get(stream_url, allow_redirects=False) as redirect_res:
                if redirect_res.status in [301, 302]:
                    # This is the direct CDN/Google link
                    return redirect_res.headers.get('Location')
                
                # If no redirect, the stream_url itself is the source
                return stream_url

    except Exception as e:
        LOGGER.error(f"Error fetching stream link: {e}")
        return None

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Optional[str]:
        """Extracts URL from a Pyrogram message or its reply."""
        messages = [message]
        if message.reply_to_message:
            messages.append(message.reply_to_message)
        
        for m in messages:
            content = m.text or m.caption
            if not content:
                continue
            if m.entities:
                for entity in m.entities:
                    if entity.type == MessageEntityType.URL:
                        return content[entity.offset : entity.offset + entity.length]
            if m.caption_entities:
                for entity in m.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        search = VideosSearch(link, limit=1)
        resp = await search.next()
        if not resp.get("result"):
            return None
        
        res = resp["result"][0]
        title = res.get("title")
        duration_min = res.get("duration")
        duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        thumbnail = res["thumbnails"][0]["url"].split("?")[0]
        vidid = res.get("id")
        return title, duration_min, duration_sec, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic=None,
        video: bool = False,
        videoid: Union[bool, str] = None,
        **kwargs
    ) -> Tuple[Optional[str], bool]:
        """
        Returns the Direct Streaming Link instead of downloading the file.
        Used by the bot to play audio/video via URL.
        """
        if videoid:
            link = self.base + link
        
        mode = "video" if video else "audio"
        direct_link = await fetch_stream_link(link, mode=mode)
        
        if direct_link:
            return direct_link, True
        return None, False

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        search = VideosSearch(link, limit=1)
        resp = await search.next()
        if not resp.get("result"):
            return None, None
        
        res = resp["result"][0]
        track_details = {
            "title": res["title"],
            "link": res["link"],
            "vidid": res["id"],
            "duration_min": res["duration"],
            "thumb": res["thumbnails"][0]["url"].split("?")[0],
        }
        return track_details, res["id"]

    async def playlist(self, link: str, limit: int, user_id: int, videoid: Union[bool, str] = None):
        """Extracts Video IDs from a playlist using yt-dlp."""
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
            
        cmd = f"yt-dlp -i --get-id --flat-playlist --playlist-end {limit} --skip-download {link}"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            return [key for key in stdout.decode().split("\n") if key]
        return []
