import asyncio
import glob
import os
import re
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from NEOMUSIC.utils.database import is_on_off
from NEOMUSIC.utils.formatters import time_to_seconds

# ══════════════════════════════════════════════════════════════════
#  FIXED VERSION — Anti-ban + Proper stream URL fetch
#  Changes:
#    1. player_client mein "mweb" aur "tv_embedded" add kiya
#    2. _get_stream_url mein proper fallback chain
#    3. PO Token support (agar set ho)
#    4. yt-dlp latest version check reminder
#    5. Cookies file support (optional but recommended)
#
#  IMPORTANT: Pehle yeh run karo:
#    pip install -U yt-dlp
#    yt-dlp -U
# ══════════════════════════════════════════════════════════════════

# Optional: Agar cookies.txt hai to yahan path do (Netscape format)
# Browser se export karo: https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp
COOKIES_FILE = os.environ.get("YTDLP_COOKIES", "")  # e.g. "/app/cookies.txt"

# OAuth2 token (yt-dlp-youtube-oauth2 plugin se)
OAUTH2_TOKEN = os.path.expanduser("~/.cache/yt-dlp/youtube-oauth2.token")

# Android YouTube app ka User-Agent
ANDROID_UA = (
    "com.google.android.youtube/19.09.37 (Linux; U; Android 13; GB) gzip"
)

# Player clients — priority order mein (sabse reliable pehle)
# "mweb" = mobile web, YouTube ke nayi bot detection se bachata hai
# "tv_embedded" = Smart TV client, bahut kam flagged hota hai
PLAYER_CLIENTS = ["mweb", "tv_embedded", "android", "ios", "web"]


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
    mweb + tv_embedded = best current bypass combination.
    """
    opts = {
        # ── Core anti-ban ────────────────────────────────────────────
        "extractor_args": {
            "youtube": {
                "player_client": PLAYER_CLIENTS,
                # po_token set karna chahte ho to:
                # "po_token": ["web+YOUR_PO_TOKEN_HERE"],
            }
        },
        "http_headers": {
            "User-Agent": ANDROID_UA,
            "Accept-Language": "en-US,en;q=0.9",
        },

        # ── Rate limit protection ────────────────────────────────────
        "sleep_interval": 2,
        "max_sleep_interval": 5,
        "sleep_interval_requests": 1,

        # ── Retry with exponential backoff ───────────────────────────
        "retries": 8,
        "fragment_retries": 8,
        "retry_sleep_functions": {"http": lambda n: min(2 ** n, 60)},

        # ── General ──────────────────────────────────────────────────
        "geo_bypass": True,
        "nocheckcertificate": True,
        "quiet": True,
        "no_warnings": True,

        # ── Format fallback ──────────────────────────────────────────
        "ignoreerrors": False,
    }

    # Cookies file use karo agar available hai
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE

    # OAuth2 plugin se pehle login kiya hai to auto-use karo
    elif os.path.exists(OAUTH2_TOKEN):
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
    yt-dlp se direct stream URL fetch karo with full fallback chain.
    
    Strategy:
      1. Pehle mweb + tv_embedded try karo (most reliable)
      2. Fail hone par android + ios
      3. Last resort: web client
      
    Returns:
        str: Direct playable stream URL
    Raises:
        ValueError: Agar sab clients fail kar dein
    """
    
    # Build base args
    base_args = [
        "yt-dlp", "-g",
        "-f", fmt,
        "--no-warnings",
        "--geo-bypass",
        "--no-check-certificates",
        "--retries", "5",
    ]
    
    # Cookies add karo agar available hai
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        base_args += ["--cookies", COOKIES_FILE]
    elif os.path.exists(OAUTH2_TOKEN):
        base_args += ["--username", "oauth2", "--password", ""]

    # Try karo different client combinations
    client_combos = [
        "mweb,tv_embedded",      # Best: modern clients
        "android,ios",           # Fallback 1
        "android_embedded,ios",  # Fallback 2  
        "web",                   # Last resort
    ]

    last_error = None
    for clients in client_combos:
        args = base_args + [
            "--extractor-args", f"youtube:player_client={clients}",
            link,
        ]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if stdout:
            url = stdout.decode().strip().split("\n")[0]
            if url.startswith("http"):
                return url

        err = stderr.decode().strip()
        last_error = err

        # Agar "Sign in" ya "bot" error aaye to cookies ki zaroorat hai
        if any(kw in err.lower() for kw in ["sign in", "confirm", "bot", "captcha", "private"]):
            # Cookies nahi hain to seedha fail karo — retry useless hai
            raise ValueError(
                f"YouTube authentication chahiye. Cookies file set karo.\n"
                f"Guide: https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp\n"
                f"Error: {err}"
            )

    raise ValueError(f"Sab clients fail kar gaye. Last error: {last_error}")


async def _search_yt(query: str, limit: int = 1):
    """Safe YouTube search with error handling."""
    try:
        results = VideosSearch(query, limit=limit)
        data = await results.next()
        return data.get("result", [])
    except Exception:
        return []


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
        results = await _search_yt(link, limit=1)
        for r in results:
            dur_min = r.get("duration") or "0:00"
            dur_sec = 0 if not dur_min else int(time_to_seconds(dur_min))
            thumb = (r.get("thumbnails") or [{}])[0].get("url", "").split("?")[0]
            return r["title"], dur_min, dur_sec, thumb, r["id"]

    async def title(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._l(link, videoid)
        for r in await _search_yt(link, limit=1):
            return r["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._l(link, videoid)
        for r in await _search_yt(link, limit=1):
            return r.get("duration", "0:00")

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None) -> str:
        link = self._l(link, videoid)
        for r in await _search_yt(link, limit=1):
            return (r.get("thumbnails") or [{}])[0].get("url", "").split("?")[0]

    # ── video (streaming URL) ─────────────────────────────────────────────────

    async def video(self, link: str, videoid: Union[bool, str] = None):
        link = self._l(link, videoid)
        try:
            stream_url = await _get_stream_url(
                link,
                # Best video+audio combined stream, 720p max
                "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
                "/best[height<=720]"
                "/bestvideo[height<=720]+bestaudio"
                "/best"
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

        # Build cookies arg agar available
        cookie_arg = ""
        if COOKIES_FILE and os.path.exists(COOKIES_FILE):
            cookie_arg = f'--cookies "{COOKIES_FILE}"'

        raw = await shell_cmd(
            f'yt-dlp -i --get-id --flat-playlist --playlist-end {limit} '
            f'--extractor-args "youtube:player_client=mweb,tv_embedded,android" '
            f'--skip-download {cookie_arg} "{link}"'
        )
        return [v for v in raw.split("\n") if v.strip()]

    # ── track ─────────────────────────────────────────────────────────────────

    async def track(self, link: str, videoid: Union[bool, str] = None):
        link = self._l(link, videoid)
        for r in await _search_yt(link, limit=1):
            thumb = (r.get("thumbnails") or [{}])[0].get("url", "").split("?")[0]
            return {
                "title":        r["title"],
                "link":         r["link"],
                "vidid":        r["id"],
                "duration_min": r.get("duration", "0:00"),
                "thumb":        thumb,
            }, r["id"]

    # ── formats ───────────────────────────────────────────────────────────────

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        link = self._l(link, videoid)
        out = []
        loop = asyncio.get_running_loop()

        def _extract():
            with yt_dlp.YoutubeDL(_ydl_opts()) as ydl:
                return ydl.extract_info(link, download=False)

        try:
            info = await loop.run_in_executor(None, _extract)
        except Exception as e:
            return [], link

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
        result = await _search_yt(link, limit=10)
        item = result[query_type]
        thumb = (item.get("thumbnails") or [{}])[0].get("url", "").split("?")[0]
        return item["title"], item.get("duration", "0:00"), thumb, item["id"]

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
            matches = glob.glob(os.path.join("downloads", f"{vid_id}.*"))
            return matches[0] if matches else None

        # ── 1. Song Video → Direct Stream URL ────────────────────────────────
        if songvideo:
            try:
                stream_url = await _get_stream_url(link, f"{format_id}+140")
                return stream_url, None
            except ValueError as e:
                raise Exception(f"Song video stream failed: {e}")

        # ── 2. Song Audio → Direct Stream URL ────────────────────────────────
        if songaudio:
            try:
                stream_url = await _get_stream_url(link, format_id)
                return stream_url, None
            except ValueError as e:
                raise Exception(f"Song audio stream failed: {e}")

        # ── 3. Video → Download or Stream ────────────────────────────────────
        if video:
            if await is_on_off(1):
                # Download mode
                def video_dl() -> str:
                    with yt_dlp.YoutubeDL(_ydl_opts({
                        "format": (
                            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
                            "/bestvideo[height<=720]+bestaudio"
                            "/best[height<=720]"
                            "/best"
                        ),
                        "outtmpl": "downloads/%(id)s.%(ext)s",
                        "merge_output_format": "mp4",
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
                # Stream mode
                try:
                    stream_url = await _get_stream_url(
                        link,
                        "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
                        "/best[height<=720]"
                        "/best"
                    )
                    return stream_url, None
                except ValueError as e:
                    raise Exception(f"Video stream failed: {e}")

        # ── 4. Audio (default) → Direct Stream URL ────────────────────────────
        try:
            stream_url = await _get_stream_url(
                link,
                "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
            )
            return stream_url, None
        except ValueError as e:
            raise Exception(f"Audio stream failed: {e}")
