# Powered by: Kiru_Op
# Pure Streaming Version - Anti-Ban - No Download

import asyncio
import os
import re
import random
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

# Library handling for YouTube Search
try:
    from ytSearch import VideosSearch, Playlist
except ImportError:
    try:
        from youtubesearchpython.__future__ import VideosSearch, Playlist
    except ImportError:
        from youtubearchpython import VideosSearch, Playlist

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        
        # Identity rotation taaki YouTube ko pata na chale bot hai
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]

    def get_random_ip(self):
        """Har request ke liye random IP generate karta hai (Header Spoofing)"""
        return ".".join(map(str, (random.randint(1, 254) for _ in range(4))))

    def get_ytdl_opts(self):
        """Streaming optimized settings without Cookies"""
        return {
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "source_address": "0.0.0.0", # IPv4 use karega (VPS ban se bachne ke liye)
            "headers": {
                "X-Forwarded-For": self.get_random_ip(),
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": random.choice(self.user_agents),
            },
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web"],
                    "skip": ["dash", "hls"]
                }
            }
        }

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset : entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        try:
            search = VideosSearch(link, limit=1)
            import inspect
            if inspect.iscoroutinefunction(search.next):
                result = (await search.next())["result"]
            else:
                result = search.result()["result"]
                
            if not result:
                return "Unknown", "00:00", 0, "https://telegra.ph/file/default.jpg", "None"
            
            res = result[0]
            title = res.get("title", "Unknown")
            duration = res.get("duration", "00:00")
            thumb = res["thumbnails"][0]["url"].split("?")[0]
            vidid = res.get("id", "None")
            
            # Duration to Seconds
            seconds = 0
            if duration:
                try:
                    parts = duration.split(':')
                    for i, part in enumerate(reversed(parts)):
                        seconds += int(part) * (60 ** i)
                except: seconds = 0
            
            return title, duration, seconds, thumb, vidid
        except Exception:
            return "Unknown", "00:00", 0, "https://telegra.ph/file/default.jpg", "None"

    async def title(self, link: str, videoid: Union[bool, str] = None):
        res = await self.details(link, videoid)
        return res[0]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        res = await self.details(link, videoid)
        return res[1]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        res = await self.details(link, videoid)
        return res[3]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        """Direct Video Stream Link"""
        if videoid:
            link = self.base + link
        opts = self.get_ytdl_opts()
        opts["format"] = "best[height<=720]"
        
        try:
            loop = asyncio.get_running_loop()
            def extract():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(link, download=False)['url']
            url = await loop.run_in_executor(None, extract)
            return 1, url
        except Exception as e:
            return 0, str(e)

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        try:
            playlist = Playlist(link)
            return [v['id'] for v in playlist.videos[:limit]]
        except:
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        det = await self.details(link, videoid)
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
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = "track",
    ) -> str:
        """
        No Download Process. 
        Only returns direct streaming URL to save disk space.
        """
        if videoid:
            link = self.base + link
        
        loop = asyncio.get_running_loop()

        def _get_stream():
            opts = self.get_ytdl_opts()
            # Direct streaming format select
            if video or songvideo:
                opts["format"] = "best[height<=720]"
            else:
                opts["format"] = "bestaudio/best"

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                return info['url']

        try:
            # Direct link extracted from YouTube
            stream_url = await loop.run_in_executor(None, _get_stream)
            # return (url, direct) 
            # direct=None batata hai ki ye ek live stream link hai
            return stream_url, None
        except Exception as e:
            return str(e), False
