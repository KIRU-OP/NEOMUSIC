import asyncio
import os
import re
from typing import Union, List
import yt_dlp
from innertube import InnerTube
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

# WEB client search ke liye zyada stable hota hai
it_client = InnerTube("WEB")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(r"(?:youtube\.com|youtu\.be)")
        self.listbase = "https://youtube.com/playlist?list="
        
        if not os.path.exists("downloads"):
            os.makedirs("downloads")

    def _extract_id(self, link: str) -> str:
        if "youtu.be/" in link:
            return link.split("youtu.be/")[1].split("?")[0].split("&")[0]
        elif "youtube.com/watch" in link:
            match = re.search(r"v=([a-zA-Z0-9_-]+)", link)
            if match: return match.group(1)
        return link

    async def details(self, link: str, videoid: Union[bool, str] = None):
        video_id = link if videoid else self._extract_id(link)
        loop = asyncio.get_running_loop()
        
        try:
            # InnerTube Player Call
            data = await loop.run_in_executor(None, lambda: it_client.player(video_id))
            v_details = data.get('videoDetails', {})
            
            title = v_details.get('title', 'Unknown Title')
            duration_sec = int(v_details.get('lengthSeconds', 0))
            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            thumbnail = v_details.get('thumbnail', {}).get('thumbnails', [{}])[-1].get('url', "")
            vidid = v_details.get('videoId', video_id)
            
            return title, duration_min, duration_sec, thumbnail, vidid
        except Exception as e:
            # Fallback to yt-dlp if InnerTube fails
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(link, download=False))
                return info['title'], f"{info['duration']//60}:{info['duration']%60:02d}", info['duration'], info['thumbnail'], info['id']

    async def playlist(self, link: str, limit: int, user_id: int, videoid: bool = None):
        p_id = link if videoid else link.split("list=")[1].split("&")[0]
        # Playlist ke liye yt-dlp hi use karte hain kyunki ye zyada stable hai
        cmd = f"yt-dlp -i --get-id --flat-playlist --playlist-end {limit} --skip-download https://www.youtube.com/playlist?list={p_id}"
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        return [id for id in stdout.decode().split("\n") if id]

    async def slider(self, link: str, query_type: int, videoid: bool = None):
        """Search query slider with better parsing."""
        loop = asyncio.get_running_loop()
        try:
            data = await loop.run_in_executor(None, lambda: it_client.search(link))
            results = []
            # Parsing WEB search results
            contents = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']
            
            for item in contents:
                if 'videoRenderer' in item:
                    v = item['videoRenderer']
                    results.append({
                        "title": v['title']['runs'][0]['text'],
                        "id": v['videoId'],
                        "duration": v.get('lengthText', {}).get('simpleText', "0:00"),
                        "thumb": v['thumbnail']['thumbnails'][-1]['url']
                    })
                if len(results) > query_type + 1: break
            
            res = results[query_type]
            return res['title'], res['duration'], res['thumb'], res['id']
        except Exception:
            # Agar InnerTube search fail ho toh basic return
            return "Unknown", "00:00", "", ""

    async def download(self, link: str, mystic, video=False, videoid=False, songaudio=False, songvideo=False, format_id=None, title="track"):
        if videoid: link = self.base + link
        loop = asyncio.get_running_loop()
        clean_title = re.sub(r'[^\w\s-]', '', title).strip() or "track"
        save_path = f"downloads/{clean_title}"

        def _dl():
            opts = {
                "quiet": True,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "outtmpl": f"{save_path}.%(ext)s",
            }
            if songvideo or video:
                opts["format"] = f"{format_id}+140/best" if format_id else "bestvideo[height<=720]+bestaudio/best"
                opts["merge_output_format"] = "mp4"
            else:
                opts["format"] = "bestaudio/best"
                opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=True)
                return ydl.prepare_filename(info)

        file_path = await loop.run_in_executor(None, _dl)
        if not video and not songvideo:
            file_path = f"{save_path}.mp3"
        return file_path, True

    # Puraane functions for compatibility
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        return bool(self.regex.search(link))

    async def url(self, message: Message) -> Union[str, None]:
        m = message.reply_to_message or message
        if m.entities:
            for e in m.entities:
                if e.type == MessageEntityType.URL:
                    return (m.text or m.caption)[e.offset : e.offset + e.length]
        return None
