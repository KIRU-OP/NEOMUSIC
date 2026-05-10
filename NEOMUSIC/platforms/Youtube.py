import asyncio
import re
import logging
import aiohttp
import yt_dlp
from typing import Union, Optional, Tuple

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch, Playlist

from NEOMUSIC.utils.formatters import time_to_seconds
from NEOMUSIC import LOGGER
from config import YOUTUBE_IMG_URL

# ============================================================
#  SECURITY FILTER  –  token / mongo URI ko logs se hata do
# ============================================================
class SensitiveDataFilter(logging.Filter):
    _PATTERNS = [
        r"\d{8,10}:[a-zA-Z0-9_-]{35,}",   # Bot token
        r"mongodb\+srv://\S+",              # Mongo URI
    ]

    def filter(self, record):
        msg = str(record.msg)
        for pattern in self._PATTERNS:
            msg = re.sub(pattern, "[PROTECTED]", msg)
        record.msg = msg
        return True

logging.getLogger().addFilter(SensitiveDataFilter())

# ============================================================
#  CONSTANTS
# ============================================================
API_URL = "http://kiru-bot.up.railway.app"

YT_WATCH   = "https://www.youtube.com/watch?v="
YT_PLAYLIST = "https://youtube.com/playlist?list="

# ============================================================
#  HELPERS
# ============================================================

def get_video_id(link: str) -> Optional[str]:
    """
    Kisi bhi YouTube link format se 11-char video ID nikalta hai.
    Supported: ?v=, youtu.be/, /embed/, /shorts/, ya raw ID.
    """
    patterns = [
        r"(?:v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, link)
        if m:
            return m.group(1)
    # Agar already raw ID diya ho
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", link)
    if len(clean) == 11:
        return clean
    return None


def is_youtube_link(link: str) -> bool:
    return bool(re.search(r"(?:youtube\.com|youtu\.be)", link))


def sec_to_min(seconds: int) -> str:
    """Seconds ko MM:SS format mein convert karta hai."""
    if not seconds:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def get_ydl_opts(video: bool = False) -> dict:
    """
    Anti-bot hardened yt-dlp options.
    Android client use karta hai YouTube ke bot-detection se bachne ke liye.
    """
    fmt = (
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        if video else
        "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
    )
    return {
        "format": fmt,
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "retries": 3,
        "fragment_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
        # Android + Web client — YouTube bot-detection se bachaata hai
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },
    }


def extract_url_from_info(info: dict, prefer_video: bool = False) -> Optional[str]:
    """yt-dlp extracted info se best stream URL nikalta hai."""

    # 1. Merged/requested formats (highest priority)
    requested = info.get("requested_formats", [])
    for fmt in requested:
        if prefer_video:
            if fmt.get("vcodec", "none") != "none" and fmt.get("url"):
                return fmt["url"]
        else:
            if fmt.get("acodec", "none") != "none" and fmt.get("url"):
                return fmt["url"]

    # 2. Top-level URL
    if info.get("url"):
        return info["url"]

    # 3. formats list
    formats = info.get("formats", [])
    if formats:
        if not prefer_video:
            audio_fmts = [
                f for f in formats
                if f.get("acodec", "none") != "none"
                and f.get("vcodec", "none") == "none"
                and f.get("url")
            ]
            if audio_fmts:
                return audio_fmts[-1]["url"]
        for fmt in reversed(formats):
            if fmt.get("url"):
                return fmt["url"]

    return None


async def get_direct_stream_link(video_id: str, media_type: str) -> Optional[str]:
    """
    External API se direct stream link lene ki koshish karta hai.
    Fail hone par None return karta hai (silently).
    """
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout
        ) as session:
            async with session.get(
                f"{API_URL}/download",
                params={"url": video_id, "type": media_type},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    token = data.get("download_token")
                    if token:
                        return (
                            f"{API_URL}/stream/{video_id}"
                            f"?type={media_type}&token={token}"
                        )
    except Exception as e:
        LOGGER.warning(f"[YouTubeAPI] External API failed ({media_type}): {e}")
    return None


# ============================================================
#  MAIN CLASS
# ============================================================

class YouTubeAPI:
    def __init__(self):
        self.base = YT_WATCH
        self.listbase = YT_PLAYLIST

    # ----------------------------------------------------------
    #  exists  –  kya ye link YouTube ka hai?
    # ----------------------------------------------------------
    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return is_youtube_link(link)

    # ----------------------------------------------------------
    #  url  –  message/reply se YouTube link dhundho
    # ----------------------------------------------------------
    async def url(self, message: Message) -> Optional[str]:
        messages = [message, message.reply_to_message]
        for msg in messages:
            if not msg:
                continue
            text = msg.text or msg.caption
            if not text:
                continue
            if msg.entities:
                for entity in msg.entities:
                    if entity.type == MessageEntityType.URL:
                        return text[entity.offset: entity.offset + entity.length]
            urls = re.findall(r"(https?://\S+)", text)
            if urls:
                return urls[0]
        return None

    # ----------------------------------------------------------
    #  search  –  YouTube par search karo
    # ----------------------------------------------------------
    async def search(self, query: str, limit: int = 1):
        try:
            results = VideosSearch(query, limit=limit)
            resp = await results.next()
            return resp.get("result", [])
        except Exception as e:
            LOGGER.error(f"[YouTubeAPI] Search error: {e}")
            return []

    # ----------------------------------------------------------
    #  details  –  title, duration, thumbnail, video_id nikalo
    #
    #  Returns: (title, duration_str, duration_sec, thumb, video_id)
    #           ya None agar kuch fail ho
    # ----------------------------------------------------------
    async def details(
        self, link: str, videoid: Union[bool, str] = None
    ) -> Optional[Tuple]:
        if videoid:
            link = self.base + link

        # ── YouTube direct link ──────────────────────────────
        if is_youtube_link(link):
            try:
                clean_link = link.split("&")[0]   # playlist params hata do
                ydl_opts = {**get_ydl_opts(), "skip_download": True}

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = await asyncio.to_thread(
                        ydl.extract_info, clean_link, download=False
                    )

                if not info:
                    LOGGER.error("[YouTubeAPI] yt-dlp returned empty info")
                    return None

                duration_sec = info.get("duration") or 0
                duration_str = sec_to_min(duration_sec)

                # Best thumbnail
                thumbnail = info.get("thumbnail")
                if not thumbnail:
                    thumbs = info.get("thumbnails", [])
                    if thumbs:
                        thumbnail = thumbs[-1].get("url")
                thumbnail = thumbnail or YOUTUBE_IMG_URL

                return (
                    info.get("title", "Unknown Title"),
                    duration_str,
                    int(duration_sec),
                    thumbnail,
                    info.get("id"),
                )

            except yt_dlp.utils.DownloadError as e:
                LOGGER.error(f"[YouTubeAPI] yt-dlp DownloadError in details: {e}")
                return None
            except Exception as e:
                LOGGER.error(f"[YouTubeAPI] details error: {e}")
                return None

        # ── Search query ─────────────────────────────────────
        res = await self.search(link, limit=1)
        if not res:
            return None

        video = res[0]
        thumbnail = YOUTUBE_IMG_URL
        try:
            t = video["thumbnails"][0]["url"].split("?")[0]
            if t.startswith("http"):
                thumbnail = t
        except Exception:
            pass

        raw_duration = video.get("duration") or "0:00"
        try:
            duration_sec = int(time_to_seconds(raw_duration))
        except Exception:
            duration_sec = 0

        return (
            video.get("title", "Unknown Title"),
            raw_duration,
            duration_sec,
            thumbnail,
            video.get("id"),
        )

    # ----------------------------------------------------------
    #  track  –  player ke liye dict banao
    # ----------------------------------------------------------
    async def track(
        self, query: str, videoid: Union[bool, str] = None
    ):
        det = await self.details(query, videoid)
        if not det:
            return None, None

        track_details = {
            "title":        det[0],
            "link":         self.base + det[4] if det[4] else query,
            "vidid":        det[4],
            "duration_min": det[1],
            "thumb":        det[3] or YOUTUBE_IMG_URL,
        }
        return track_details, det[4]

    # ----------------------------------------------------------
    #  download  –  stream URL do (API → yt-dlp fallback)
    # ----------------------------------------------------------
    async def download(
        self,
        link: str,
        mystic=None,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        **kwargs,
    ) -> Tuple[Optional[str], bool]:

        if videoid:
            link = self.base + link

        m_type = "video" if video else "audio"

        # 1️⃣  External API (fast path)
        vid_id = get_video_id(link)
        if vid_id:
            stream_link = await get_direct_stream_link(vid_id, m_type)
            if stream_link:
                LOGGER.info(f"[YouTubeAPI] Stream via external API: {vid_id}")
                return stream_link, True

        # 2️⃣  yt-dlp fallback
        try:
            ydl_opts = get_ydl_opts(video=bool(video))
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(
                    ydl.extract_info, link, download=False
                )

            url = extract_url_from_info(info, prefer_video=bool(video))
            if url and len(url) > 10:
                LOGGER.info(f"[YouTubeAPI] Stream via yt-dlp: {link}")
                return url, True

        except yt_dlp.utils.DownloadError as e:
            LOGGER.error(f"[YouTubeAPI] yt-dlp DownloadError in download: {e}")
        except Exception as e:
            LOGGER.error(f"[YouTubeAPI] download unexpected error: {e}")

        LOGGER.warning(f"[YouTubeAPI] All methods failed for: {link}")
        return None, False

    # ----------------------------------------------------------
    #  playlist  –  playlist ke saare videos ki list
    # ----------------------------------------------------------
    async def playlist(
        self, link: str, limit: int = 0, user_id=None, videoid: Union[bool, str] = None
    ):
        if videoid:
            link = self.listbase + link
        try:
            playlist = await Playlist.getVideos(link)
            videos = playlist.get("videos", [])
            if limit and len(videos) > limit:
                videos = videos[:limit]
            return videos
        except Exception as e:
            LOGGER.error(f"[YouTubeAPI] Playlist error: {e}")
            return []

    # ----------------------------------------------------------
    #  formats  –  available formats list (admin use)
    # ----------------------------------------------------------
    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        try:
            ydl_opts = {**get_ydl_opts(), "listformats": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(
                    ydl.extract_info, link, download=False
                )
            return info.get("formats", [])
        except Exception as e:
            LOGGER.error(f"[YouTubeAPI] formats error: {e}")
            return []

    # ----------------------------------------------------------
    #  thumbnail  –  sirf thumbnail URL chahiye
    # ----------------------------------------------------------
    async def thumbnail(self, videoid: str) -> str:
        link = self.base + videoid
        det = await self.details(link)
        if det and det[3]:
            return det[3]
        return YOUTUBE_IMG_URL


# ============================================================
#  GLOBAL INSTANCE
# ============================================================
YouTube = YouTubeAPI()
