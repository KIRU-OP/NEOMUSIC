# Powered by: Kiru_Op
# Anti-Ban & IP-Shifter Version

import asyncio
import os
import re
import random
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

# Purane library name ke hisaab se imports
try:
    from ytSearch import VideosSearch, Playlist
except ImportError:
    from youtubearchpython import VideosSearch, Playlist

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        
        # Modern User-Agents rotation
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]

    def get_random_ip(self):
        """IP Shifting logic"""
        return ".".join(map(str, (random.randint(1, 254) for _ in range(4))))

    def get_ytdl_opts(self):
        """Dynamic headers for each request"""
        return {
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "source_address": "0.0.0.0", # Force IPv4 to avoid ban
            "headers": {
                "X-Forwarded-For": self.get_random_ip(),
                "User-Agent": random.choice(self.user_agents),
            },
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web", "ios"],
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
        
        # Isko async handle karne ke liye (Aapki library ke according)
        search = VideosSearch(link, limit=1)
        result = search.result()["result"]
        if not result:
            return None
        
        res = result[0]
        title = res["title"]
        duration_min = res["duration"]
        thumbnail = res["thumbnails"][0]["url"].split("?")[0]
        vidid = res["id"]
        
        seconds = 0
        if duration_min:
            try:
                parts = duration_min.split(':')
                for i, part in enumerate(reversed(parts)):
                    seconds += int(part) * (60 ** i)
            except:
                seconds = 0
        
        return title, duration_min, seconds, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        res = await self.details(link, videoid)
        return res[0] if res else None

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        res = await self.details(link, videoid)
        return res[1] if res else None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        res = await self.details(link, videoid)
        return res[3] if res else None

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        opts = self.get_ytdl_opts()
        opts["format"] = "best[height<=720]"
        
        loop = asyncio.get_running_loop()
        def extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                return info['url']
        
        try:
            url = await loop.run_in_executor(None, extract)
            return 1, url
        except Exception as e:
            return 0, str(e)

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        playlist = Playlist(link)
        # Playlist fetch logic as per ytSearch
        return [v['id'] for v in playlist.videos[:limit]]

    async def track(self, link: str, videoid: Union[bool, str] = None):
        det = await self.details(link, videoid)
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
        if videoid:
            link = self.base + link
        opts = self.get_ytdl_opts()
        
        loop = asyncio.get_running_loop()
        def get_fmt():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(link, download=False)

        info = await loop.run_in_executor(None, get_fmt)
        formats_available = []
        for f in info.get("formats", []):
            if f.get("filesize") and f.get("format_id"):
                formats_available.append({
                    "format": f.get("format"),
                    "filesize": f["filesize"],
                    "format_id": f["format_id"],
                    "ext": f["ext"],
                    "format_note": f.get("format_note", "N/A"),
                    "yturl": link,
                })
        return formats_available, link

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
        if videoid:
            link = self.base + link
        
        loop = asyncio.get_running_loop()

        def _dl():
            opts = self.get_ytdl_opts()
            
            if songvideo:
                opts.update({
                    "format": f"{format_id}+140/bestvideo+bestaudio",
                    "outtmpl": f"downloads/{title}.mp4",
                    "merge_output_format": "mp4",
                })
            elif songaudio:
                opts.update({
                    "format": format_id if format_id else "bestaudio",
                    "outtmpl": f"downloads/{title}.%(ext)s",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }],
                })
            elif video:
                opts.update({
                    "format": "best[height<=720]",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                })
            else:
                opts.update({
                    "format": "bestaudio/best",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                })

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=True)
                filename = ydl.prepare_filename(info)
                if songaudio:
                    filename = os.path.splitext(filename)[0] + ".mp3"
                return filename

        downloaded_file = await loop.run_in_executor(None, _dl)
        return downloaded_file, True
