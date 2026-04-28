import asyncio
import os
import re
from typing import Union, List, Dict
import yt_dlp
from innertube import InnerTube
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

# Android client use kar rahe hain kyunki ye sabse fast aur stable hai
it_client = InnerTube("ANDROID")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(r"(?:youtube\.com|youtu\.be)")
        self.listbase = "https://youtube.com/playlist?list="
        
        # Download directory setup
        if not os.path.exists("downloads"):
            os.makedirs("downloads")

    def _extract_id(self, link: str) -> str:
        """Link se Video ID nikalne ke liye optimized helper."""
        if "youtu.be/" in link:
            return link.split("youtu.be/")[1].split("?")[0].split("&")[0]
        elif "youtube.com/watch" in link:
            match = re.search(r"v=([a-zA-Z0-9_-]+)", link)
            if match: return match.group(1)
        elif "youtube.com/shorts/" in link:
            return link.split("shorts/")[1].split("?")[0].split("&")[0]
        return link

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(self.regex.search(link))

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
        """InnerTube ka use karke details nikalna (No IP Ban risk)"""
        video_id = link if videoid else self._extract_id(link)
        loop = asyncio.get_running_loop()
        
        # Player API call (fastest)
        data = await loop.run_in_executor(None, lambda: it_client.player(video_id))
        
        v_details = data.get('videoDetails', {})
        title = v_details.get('title', 'Unknown Title')
        duration_sec = int(v_details.get('lengthSeconds', 0))
        duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
        thumbnail = v_details.get('thumbnail', {}).get('thumbnails', [{}])[-1].get('url', "")
        vidid = v_details.get('videoId', video_id)
        
        return title, duration_min, duration_sec, thumbnail, vidid

    async def playlist(self, link: str, limit: int, user_id: int, videoid: bool = None):
        """InnerTube Browse API for super fast playlist extraction."""
        p_id = link if videoid else link.split("list=")[1].split("&")[0]
        loop = asyncio.get_running_loop()
        
        data = await loop.run_in_executor(None, lambda: it_client.browse(p_id))
        
        ids = []
        try:
            # Android Internal API structure parsing
            section = data['contents']['singleColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content']['sectionListRenderer']['contents'][0]
            items = section['itemSectionRenderer']['contents'][0]['playlistVideoListRenderer']['contents']
            for item in items[:limit]:
                if 'playlistVideoRenderer' in item:
                    ids.append(item['playlistVideoRenderer']['videoId'])
        except Exception:
            pass
        return ids

    async def video(self, link: str, videoid: Union[bool, str] = None):
        """Direct stream link extraction via yt-dlp."""
        if videoid: link = self.base + link
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "-g", "-f", "best[height<=720]", link,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().strip()
        return 0, stderr.decode()

    async def download(
        self,
        link: str,
        mystic, # Progress message placeholder
        video: bool = False,
        videoid: bool = False,
        songaudio: bool = False,
        songvideo: bool = False,
        format_id: str = None,
        title: str = "track",
    ):
        if videoid: link = self.base + link
        loop = asyncio.get_running_loop()
        
        # Standardize title for filename
        clean_title = re.sub(r'[^\w\s-]', '', title).strip()
        save_path = f"downloads/{clean_title}"

        def _dl():
            # YDL Options based on request type
            if songvideo:
                opts = {
                    "format": f"{format_id}+140/bestvideo+bestaudio",
                    "outtmpl": f"{save_path}.mp4",
                    "merge_output_format": "mp4"
                }
            elif songaudio:
                opts = {
                    "format": format_id or "bestaudio/best",
                    "outtmpl": f"{save_path}.%(ext)s",
                    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
                }
            elif video:
                opts = {
                    "format": "bestvideo[height<=720]+bestaudio/best",
                    "outtmpl": f"{save_path}.mp4"
                }
            else: # Standard audio
                opts = {
                    "format": "bestaudio/best",
                    "outtmpl": f"{save_path}.%(ext)s",
                    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
                }

            common_opts = {
                "quiet": True, "no_warnings": True, "geo_bypass": True, 
                "nocheckcertificate": True, "noprogress": True
            }
            
            with yt_dlp.YoutubeDL({**common_opts, **opts}) as ydl:
                info = ydl.extract_info(link, download=True)
                return ydl.prepare_filename(info)

        file_path = await loop.run_in_executor(None, _dl)
        
        # Audio post-processor extension check
        if songaudio or not video:
            file_path = f"{save_path}.mp3"
            
        return file_path, True

    async def slider(self, link: str, query_type: int, videoid: bool = None):
        """InnerTube search based slider."""
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, lambda: it_client.search(link))
        
        results = []
        try:
            items = data['contents']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']
            for item in items:
                if 'videoRenderer' in item:
                    v = item['videoRenderer']
                    results.append({
                        "title": v['title']['runs'][0]['text'],
                        "id": v['videoId'],
                        "duration": v.get('lengthText', {}).get('simpleText', "0:00"),
                        "thumb": v['thumbnail']['thumbnails'][-1]['url']
                    })
        except: pass
        
        res = results[query_type]
        return res['title'], res['duration'], res['thumb'], res['id']
