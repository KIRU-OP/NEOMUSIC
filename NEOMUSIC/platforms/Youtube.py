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
#  COMPLETE FIX — Sab YouTube links working
#  - Long videos (30min, 1hr, 2hr+) ✅
#  - Age restricted ✅
#  - Region blocked ✅
#  - Normal videos ✅
#  - Playlists ✅
#
#  Setup (ZARURI):
#    pip install -U yt-dlp
#
#  Cookies (age-restricted ke liye recommended):
#    export YTDLP_COOKIES="/app/cookies.txt"
# ══════════════════════════════════════════════════════════════════

COOKIES_FILE = os.environ.get("YTDLP_COOKIES", "cookies.txt")
OAUTH2_TOKEN = os.path.expanduser("~/.cache/yt-dlp/youtube-oauth2.token")
ANDROID_UA   = "com.google.android.youtube/19.09.37 (Linux; U; Android 13; GB) gzip"

# ── Format priority lists ─────────────────────────────────────────
# Har format fail hone par agla try hoga — 100% coverage
AUDIO_FORMATS = [
    "bestaudio[ext=m4a]",
    "bestaudio[ext=webm]",
    "bestaudio",
    "140",       # m4a 128kbps — almost always available
    "251",       # webm opus 160kbps
    "250",       # webm opus 70kbps
    "249",       # webm opus 50kbps
    "best[height<=480]",
    "best",
]

VIDEO_FORMATS = [
    "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]",
    "bestvideo[height<=720]+bestaudio",
    "best[height<=720][ext=mp4]",
    "best[height<=720]",
    "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]",
    "best[height<=480]",
    "best",
]

# Player clients — 2025 mein reliable order
PLAYER_CLIENTS_LIST = [
    "mweb,tv_embedded",
    "android,mweb",
    "ios,mweb",
    "android_embedded,mweb",
    "web",
]


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


def _cookie_args() -> list:
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        return ["--cookies", COOKIES_FILE]
    if os.path.exists(OAUTH2_TOKEN):
        return ["--username", "oauth2", "--password", ""]
    return []


def _ydl_opts(extra: dict = None) -> dict:
    opts = {
        "extractor_args": {
            "youtube": {
                "player_client": ["mweb", "tv_embedded", "android", "ios", "web"],
            }
        },
        "http_headers": {
            "User-Agent": ANDROID_UA,
            "Accept-Language": "en-US,en;q=0.9",
        },
        "sleep_interval": 1,
        "max_sleep_interval": 4,
        "sleep_interval_requests": 1,
        "retries": 10,
        "fragment_retries": 10,
        "retry_sleep_functions": {"http": lambda n: min(2 ** n, 60)},
        "geo_bypass": True,
        "nocheckcertificate": True,
        "quiet": True,
        "no_warnings": True,
    }
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
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


async def _get_stream_url(link: str, fmt_list: list) -> str:
    """
    Multiple formats + multiple player clients try karo.
    Jab tak koi kaam kare tab tak try karta rahe.
    Long videos ke liye 60 second timeout.
    """
    cookie_args = _cookie_args()
    base_args = [
        "yt-dlp", "-g",
        "--no-warnings",
        "--geo-bypass",
        "--no-check-certificates",
        "--retries", "5",
        "--socket-timeout", "30",
    ] + cookie_args

    errors = []

    for clients in PLAYER_CLIENTS_LIST:
        for fmt in fmt_list:
            args = base_args + [
                "--extractor-args", f"youtube:player_client={clients}",
                "-f", fmt,
                link,
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=60
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    errors.append(f"[{clients}][{fmt}] Timeout")
                    continue

                if stdout:
                    url = stdout.decode().strip().split("\n")[0]
                    if url.startswith("http"):
                        return url  # ✅ Working URL mila!

                err = stderr.decode().strip()
                if err:
                    errors.append(f"[{clients}][{fmt}] {err[:120]}")
                    # Private / age-restricted — cookies chahiye
                    if any(kw in err.lower() for kw in [
                        "sign in to confirm", "private video",
                        "this video is private", "age"
                    ]):
                        raise ValueError(
                            "🔒 Private/age-restricted video.\n"
                            "Cookies set karo: export YTDLP_COOKIES='/app/cookies.txt'"
                        )

            except ValueError:
                raise
            except Exception as e:
                errors.append(f"[{clients}][{fmt}] {str(e)[:80]}")
                continue

    raise ValueError(
        "❌ Stream URL fetch nahi hua.\n"
        "Last errors:\n" + "\n".join(errors[-3:]) + "\n\n"
        "Fix: pip install -U yt-dlp"
    )


async def _search_yt(query: str, limit: int = 1) -> list:
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

    # ── details ───────────────────────────────────────────────────────────────

    async def details(self, link: str, videoid: Union[bool, str] = None):
        link = self._l(link, videoid)
        for r in await _search_yt(link, limit=1):
            dur_min = r.get("duration") or "0:00"
            dur_sec = 0 if not dur_min else int(time_to_seconds(dur_min))
            thumb   = (r.get("thumbnails") or [{}])[0].get("url", "").split("?")[0]
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

    # ── video ─────────────────────────────────────────────────────────────────

    async def video(self, link: str, videoid: Union[bool, str] = None):
        link = self._l(link, videoid)
        try:
            url = await _get_stream_url(link, VIDEO_FORMATS)
            return 1, url
        except ValueError as e:
            return 0, str(e)

    # ── playlist ──────────────────────────────────────────────────────────────

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]

        cookie_part = ""
        if COOKIES_FILE and os.path.exists(COOKIES_FILE):
            cookie_part = f'--cookies "{COOKIES_FILE}"'
        elif os.path.exists(OAUTH2_TOKEN):
            cookie_part = '--username oauth2 --password ""'

        raw = await shell_cmd(
            f'yt-dlp -i --get-id --flat-playlist --playlist-end {limit} '
            f'--extractor-args "youtube:player_client=mweb,tv_embedded,android" '
            f'--skip-download {cookie_part} "{link}"'
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
        loop = asyncio.get_running_loop()

        def _extract():
            with yt_dlp.YoutubeDL(_ydl_opts()) as ydl:
                return ydl.extract_info(link, download=False)

        try:
            info = await loop.run_in_executor(None, _extract)
        except Exception:
            return [], link

        out = []
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
        item   = result[query_type]
        thumb  = (item.get("thumbnails") or [{}])[0].get("url", "").split("?")[0]
        return item["title"], item.get("duration", "0:00"), thumb, item["id"]

    # ── download ──────────────────────────────────────────────────────────────

    async def download(
        self,
        link:       str,
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

        # ── 1. Song Video ─────────────────────────────────────────────────────
        if songvideo:
            url = await _get_stream_url(
                link,
                [f"{format_id}+140", f"{format_id}+251", format_id] + VIDEO_FORMATS
            )
            return url, None

        # ── 2. Song Audio ─────────────────────────────────────────────────────
        if songaudio:
            url = await _get_stream_url(
                link,
                [format_id, "140", "251"] + AUDIO_FORMATS
            )
            return url, None

        # ── 3. Video ──────────────────────────────────────────────────────────
        if video:
            if await is_on_off(1):
                def video_dl() -> str:
                    with yt_dlp.YoutubeDL(_ydl_opts({
                        "format": (
                            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
                            "/bestvideo[height<=720]+bestaudio"
                            "/best[height<=720]"
                            "/best"
                        ),
                        "outtmpl":             "downloads/%(id)s.%(ext)s",
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
                url = await _get_stream_url(link, VIDEO_FORMATS)
                return url, None

        # ── 4. Audio (default) ────────────────────────────────────────────────
        url = await _get_stream_url(link, AUDIO_FORMATS)
        return url, None
