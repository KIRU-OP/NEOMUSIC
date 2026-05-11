import asyncio
import glob
import os
import re
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from RishuMusic.utils.database import is_on_off
from RishuMusic.utils.formatters import time_to_seconds

# ══════════════════════════════════════════════════════════════════
#  Optional (aur bhi strong ban protection):
#    pip install yt-dlp-youtube-oauth2
#    yt-dlp --username oauth2 --password "" https://t.me/about_kiru_op
#    → Ek baar browser mein login karo, token hamesha ke liye save
# ══════════════════════════════════════════════════════════════════

OAUTH2_TOKEN = os.path.expanduser("~/.cache/yt-dlp/youtube-oauth2.token")

# Android YouTube app ka User-Agent
ANDROID_UA = (
    "com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip"
)


async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        decoded = errorz.decode("utf-8")
        if "unavailable videos are hidden" in decoded.lower():
            return out.decode("utf-8")
        return decoded
    return out.decode("utf-8")


def _ydl_opts(extra: dict = None) -> dict:
    """
    Anti-ban optimized yt-dlp options.

    Android player_client = YouTube mobile simulate karta hai.
    Bot detection automatically bypass — cookies ki zaroorat nahi.
    """
    opts = {
        # ── Core anti-ban: Android/iOS client ──────────────────────
        "extractor_args": {
            "youtube": {
                # android pehle try hoga, fail hone par ios, phir web
                "player_client": ["android", "ios", "web"],
            }
        },
        "http_headers": {"User-Agent": ANDROID_UA},

        # ── Rate limit se bachao ────────────────────────────────────
        "sleep_interval": 1,
        "max_sleep_interval": 4,
        "sleep_interval_requests": 1,

        # ── Retry with exponential backoff ──────────────────────────
        "retries": 6,
        "fragment_retries": 6,
        "retry_sleep_functions": {"http": lambda n: min(2 ** n, 30)},

        # ── General ─────────────────────────────────────────────────
        "geo_bypass": True,
        "nocheckcertificate": True,
        "quiet": True,
        "no_warnings": True,
    }

    # Agar OAuth2 plugin se pehle login kiya hai to auto-use karo
    if os.path.exists(OAUTH2_TOKEN):
        opts["username"] = "oauth2"
        opts["password"] = ""

    if extra:
        opts.update(extra)
    return opts


def _clean(link: str, videoid=None, base=None) -> str:
    if videoid and base:
        link = base + link
    return link.split("&")[0] if "&" in link else link


async def _get_stream_url(link: str, fmt: str) -> str:
    """
    yt-dlp -g se direct stream URL fetch karo — kuch bhi download nahi hoga.

    Returns:
        str: Direct playable stream URL
    Raises:
        ValueError: Agar URL fetch fail ho jaye
    """
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", "-g",
        "-f", fmt,
        "--extractor-args", "youtube:player_client=android,ios,web",
        "--no-warnings",
        link,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if stdout:
        # Pehli line = stream URL (video+audio alag hone par dono lines aati hain)
        return stdout.decode().strip().split("\n")[0]
    raise ValueError(f"Stream URL fetch failed: {stderr.decode().strip()}")


class YouTubeAPI:
    def __init__(self):
        self.base     = "https://www.youtube.com/watch?v="
        self.regex    = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        self.reg      = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def _l(self, link, videoid=None):
        return _clean(link, videoid, self.base)

    # ── exists ────────────────────────────────────────────────────────────────

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    # ── url ───────────────────────────────────────────────────────────────────

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for msg in messages:
            if msg.entities:
                for ent in msg.entities:
                    if ent.type == MessageEntityType.URL:
                        text = msg.text or msg.caption
                        return text[ent.offset: ent.offset + ent.length]
            if msg.caption_entities:
                for ent in msg.caption_entities:
                    if ent.type == MessageEntityType.TEXT_LINK:
                        return ent.url
        return None

    # ── details / title / duration / thumbnail ────────────────────────────────

    async def details(self, link: str, videoid: Union[bool, str] = None):
        link = self._l(link, videoid)
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]:
            dur_min = r["duration"]
            dur_sec = 0 if not dur_min else int(time_to_seconds(dur_min))
            return r["title"], dur_min, dur_sec, r["thumbnails"][0]["url"].split("?")[0], r["id"]

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._l(link, videoid)
        for r in (await (VideosSearch(link, limit=1)).next())["result"]:
            return r["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._l(link, videoid)
        for r in (await (VideosSearch(link, limit=1)).next())["result"]:
            return r["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._l(link, videoid)
        for r in (await (VideosSearch(link, limit=1)).next())["result"]:
            return r["thumbnails"][0]["url"].split("?")[0]

    # ── video (streaming URL) ─────────────────────────────────────────────────

    async def video(self, link: str, videoid: Union[bool, str] = None):
        link = self._l(link, videoid)
        try:
            stream_url = await _get_stream_url(
                link, "best[height<=?720][width<=?1280]"
            )
            return 1, stream_url
        except ValueError as e:
            return 0, str(e)

    # ── playlist ──────────────────────────────────────────────────────────────

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        raw = await shell_cmd(
            f'yt-dlp -i --get-id --flat-playlist --playlist-end {limit} '
            f'--extractor-args "youtube:player_client=android,ios" '
            f'--skip-download "{link}"'
        )
        return [v for v in raw.split("\n") if v.strip()]

    # ── track ─────────────────────────────────────────────────────────────────

    async def track(self, link: str, videoid: Union[bool, str] = None):
        link = self._l(link, videoid)
        for r in (await (VideosSearch(link, limit=1)).next())["result"]:
            return {
                "title": r["title"],
                "link": r["link"],
                "vidid": r["id"],
                "duration_min": r["duration"],
                "thumb": r["thumbnails"][0]["url"].split("?")[0],
            }, r["id"]

    # ── formats ───────────────────────────────────────────────────────────────

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        link = self._l(link, videoid)
        out = []
        with yt_dlp.YoutubeDL(_ydl_opts()) as ydl:
            info = ydl.extract_info(link, download=False)
            for fmt in info.get("formats", []):
                fmt_str = str(fmt.get("format", ""))
                if not fmt_str or "dash" in fmt_str.lower():
                    continue
                if not all(k in fmt for k in ("filesize", "format_id", "ext", "format_note")):
                    continue
                out.append({
                    "format":      fmt_str,
                    "filesize":    fmt["filesize"],
                    "format_id":   fmt["format_id"],
                    "ext":         fmt["ext"],
                    "format_note": fmt["format_note"],
                    "yturl":       link,
                })
        return out, link

    # ── slider ────────────────────────────────────────────────────────────────

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        link = self._l(link, videoid)
        result = (await (VideosSearch(link, limit=10)).next()).get("result", [])
        item = result[query_type]
        return item["title"], item["duration"], item["thumbnails"][0]["url"].split("?")[0], item["id"]

    # ── download ──────────────────────────────────────────────────────────────

    async def download(
        self,
        link: str,
        mystic,
        video:      Union[bool, str] = None,
        videoid:    Union[bool, str] = None,
        songaudio:  Union[bool, str] = None,
        songvideo:  Union[bool, str] = None,
        format_id:  Union[bool, str] = None,
        title:      Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link

        loop = asyncio.get_running_loop()

        def _find(vid_id: str):
            """Downloaded file glob se dhundo — ext vary kar sakti hai."""
            matches = glob.glob(os.path.join("downloads", f"{vid_id}.*"))
            return matches[0] if matches else None

        # ── 1. Song Video → Direct Stream URL (no download) ───────────────────
        # songvideo = specific format_id chahiye, isliye -g ke saath format pass karo
        if songvideo:
            stream_url = await _get_stream_url(
                link, f"{format_id}+140"  # video + audio stream
            )
            return stream_url, None  # None = streamed, file nahi

        # ── 2. Song Audio → Direct Stream URL (no download) ───────────────────
        if songaudio:
            stream_url = await _get_stream_url(link, format_id)
            return stream_url, None  # None = streamed, file nahi

        # ── 3. Video → Stream ya Download (is_on_off flag se decide) ──────────
        if video:
            if await is_on_off(1):
                # Download mode: file disk par save karo
                def video_dl() -> str:
                    with yt_dlp.YoutubeDL(_ydl_opts({
                        "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                        "outtmpl": "downloads/%(id)s.%(ext)s",
                    })) as ydl:
                        info   = ydl.extract_info(link, download=False)
                        vid_id = info["id"]
                        cached = _find(vid_id)
                        if cached:
                            return cached
                        ydl.download([link])
                        return _find(vid_id) or f"downloads/{vid_id}.mp4"

                return await loop.run_in_executor(None, video_dl), True
            else:
                # Stream mode: sirf URL fetch karo, kuch download mat karo
                stream_url = await _get_stream_url(
                    link, "best[height<=?720][width<=?1280]"
                )
                return stream_url, None

        # ── 4. Audio (default) → Direct Stream URL (no download) ──────────────
        # Seedha bestaudio ka stream URL lo — disk touch nahi hogi
        stream_url = await _get_stream_url(link, "bestaudio/best")
        return stream_url, None
