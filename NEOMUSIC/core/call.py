import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import ConnectionNotFound, TelegramServerError
from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

import config
from NEOMUSIC import LOGGER, YouTube, app
from NEOMUSIC.misc import db
from NEOMUSIC.utils.database import (add_active_chat, add_active_video_chat,
                                       get_lang, get_loop, group_assistant,
                                       is_autoend, music_on,
                                       remove_active_chat,
                                       remove_active_video_chat, set_loop)
from NEOMUSIC.utils.exceptions import AssistantErr
from NEOMUSIC.utils.formatters import check_duration, seconds_to_min, speed_converter
from NEOMUSIC.utils.inline.play import stream_markup
from NEOMUSIC.utils.stream.autoclear import auto_clean
from NEOMUSIC.utils.thumbnails import gen_thumb as get_thumb
from strings import get_string


async def delete_old_message(chat_id: int):
    try:
        old = db.get(chat_id, [{}])[0].get("mystic")
        if old:
            await old.delete()
    except:
        pass


autoend = {}
counter = {}


async def _clear_(chat_id: int):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)


class Call:
    def __init__(self):
        PyTgCallsSession.notice_displayed = True

        self.userbot1 = Client(
            name="AloneMusic1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(self.userbot1, cache_duration=100)

        self.userbot2 = Client(
            name="AloneMusic2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(self.userbot2, cache_duration=100)

        self.userbot3 = Client(
            name="AloneMusic3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(self.userbot3, cache_duration=100)

        self.userbot4 = Client(
            name="AloneMusic4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(self.userbot4, cache_duration=100)

        self.userbot5 = Client(
            name="AloneMusic5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(self.userbot5, cache_duration=100)

    def _build_stream(
        self,
        source: str,
        video: bool,
        ffmpeg: str | None = None,
    ) -> types.MediaStream:
        return types.MediaStream(
            media_path=source,
            audio_parameters=types.AudioQuality.HIGH,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if video
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=ffmpeg,
        )

    async def _play_on_assistant(
        self,
        client: PyTgCalls,
        chat_id: int,
        stream: types.MediaStream,
    ):
        try:
            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=False),
            )
        except exceptions.NoActiveGroupCall:
            raise
        except exceptions.NoAudioSourceFound:
            raise
        except (ConnectionNotFound, TelegramServerError):
            raise
        except Exception:
            raise

    
    async def pause_stream(self, chat_id: int):
        await delete_old_message(chat_id)
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

  
    async def resume_stream(self, chat_id: int):
        await delete_old_message(chat_id)
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    
    async def stop_stream(self, chat_id: int):
        await delete_old_message(chat_id)
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            await assistant.leave_call(chat_id, close=False)
        except Exception:
            pass


    async def stop_stream_force(self, chat_id: int):
        for string, client in [
            (config.STRING1, self.one),
            (config.STRING2, self.two),
            (config.STRING3, self.three),
            (config.STRING4, self.four),
            (config.STRING5, self.five),
        ]:
            if not string:
                continue
            try:
                await client.leave_call(chat_id, close=False)
            except Exception:
                pass
        try:
            await _clear_(chat_id)
        except Exception:
            pass

  
    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                if str(speed) == "0.5":
                    vs = 2.0
                elif str(speed) == "0.75":
                    vs = 1.35
                elif str(speed) == "1.5":
                    vs = 0.68
                elif str(speed) == "2.0":
                    vs = 0.5
                else:
                    vs = 1.0
                proc = await asyncio.create_subprocess_shell(
                    cmd=(
                        "ffmpeg "
                        "-i "
                        f"{file_path} "
                        "-filter:v "
                        f"setpts={vs}*PTS "
                        "-filter:a "
                        f"atempo={speed} "
                        f"{out}"
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path
        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        xx = f"-ss {played} -to {duration}"
        video_mode = playing[0]["streamtype"] == "video"
        stream = self._build_stream(out, video=video_mode, ffmpeg=xx)
        if str(db[chat_id][0]["file"]) == str(file_path):
            await self._play_on_assistant(assistant, chat_id, stream)
        else:
            raise AssistantErr("Umm")
        if str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    # ─────────────────────────────────────────────
    # FEATURE 1: Volume Control
    # ─────────────────────────────────────────────
    async def change_volume(self, chat_id: int, volume: int) -> bool:
        """
        Stream ka volume badlo (0-200 ke beech).
        200 = double volume, 100 = normal, 0 = mute.
        """
        if not (0 <= volume <= 200):
            raise AssistantErr("Volume 0 se 200 ke beech hona chahiye.")
        assistant = await group_assistant(self, chat_id)
        try:
            await assistant.change_volume_call(chat_id, volume)
            if db.get(chat_id):
                db[chat_id][0]["volume"] = volume
            return True
        except Exception:
            return False

    # ─────────────────────────────────────────────
    # FEATURE 2: Mute / Unmute Assistant
    # ─────────────────────────────────────────────
    async def mute_stream(self, chat_id: int):
        """Assistant ko voice call mein mute karo."""
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    async def unmute_stream(self, chat_id: int):
        """Assistant ko voice call mein unmute karo."""
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    # ─────────────────────────────────────────────
    # FEATURE 3: Queue Statistics
    # ─────────────────────────────────────────────
    def get_queue_stats(self, chat_id: int) -> dict:
        """
        Queue ki puri stats return karo:
        - total songs kitne hain
        - total duration (seconds mein)
        - currently playing song info
        """
        queue = db.get(chat_id, [])
        if not queue:
            return {"total_songs": 0, "total_duration": 0, "current": None}

        total_seconds = 0
        for item in queue:
            try:
                raw = item.get("seconds") or item.get("dur", "00:00")
                if isinstance(raw, int):
                    total_seconds += raw
                elif isinstance(raw, str) and ":" in raw:
                    parts = raw.split(":")
                    total_seconds += int(parts[0]) * 60 + int(parts[1])
            except Exception:
                pass

        current = queue[0] if queue else None
        return {
            "total_songs": len(queue),
            "total_duration": total_seconds,          # seconds
            "current": current,
        }

    # ─────────────────────────────────────────────
    # FEATURE 4: Auto-Reconnect with Retry Logic
    # ─────────────────────────────────────────────
    async def join_call_with_retry(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video=None,
        image=None,
        retries: int = 3,
        delay: float = 2.0,
    ):
        """
        join_call ko retry logic ke saath call karo.
        Agar pehli baar fail ho, toh `retries` baar dobara try karega.
        """
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                await self.join_call(chat_id, original_chat_id, link, video, image)
                return  # success
            except AssistantErr:
                raise  # user-facing errors ko seedha raise karo
            except Exception as e:
                last_err = e
                LOGGER(__name__).warning(
                    f"join_call attempt {attempt}/{retries} failed for {chat_id}: {e}"
                )
                if attempt < retries:
                    await asyncio.sleep(delay)
        raise AssistantErr(f"Call join nahi hua {retries} tries ke baad: {last_err}")

    # ─────────────────────────────────────────────
    # FEATURE 5: Active Calls Monitor
    # ─────────────────────────────────────────────
    async def get_active_calls_count(self) -> dict:
        """
        Har assistant ke active calls ka count return karo.
        Useful for /stats ya admin panel mein dikhane ke liye.
        """
        result = {}
        pairs = [
            ("Assistant 1", config.STRING1, self.one),
            ("Assistant 2", config.STRING2, self.two),
            ("Assistant 3", config.STRING3, self.three),
            ("Assistant 4", config.STRING4, self.four),
            ("Assistant 5", config.STRING5, self.five),
        ]
        for name, string, client in pairs:
            if not string:
                continue
            try:
                calls = await client.calls
                result[name] = len(calls)
            except Exception:
                result[name] = 0
        return result

    async def force_stop_stream(self, chat_id: int):
        await delete_old_message(chat_id)
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            check.pop(0)
        except Exception:
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try:
            await assistant.leave_call(chat_id, close=False)
        except Exception:
            pass

  
    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        stream = self._build_stream(link, video=bool(video))
        await self._play_on_assistant(assistant, chat_id, stream)

  
    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        ffmpeg = f"-ss {to_seek} -to {duration}"
        video_mode = mode == "video"
        stream = self._build_stream(
            file_path,
            video=video_mode,
            ffmpeg=ffmpeg,
        )
        await self._play_on_assistant(assistant, chat_id, stream)

    
    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        stream = self._build_stream(link, video=True)
        await self._play_on_assistant(assistant, config.LOGGER_ID, stream)
        await asyncio.sleep(0.2)
        try:
            await assistant.leave_call(config.LOGGER_ID, close=False)
        except Exception:
            pass

    
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)
        stream = self._build_stream(link, video=bool(video))
        try:
            await self._play_on_assistant(assistant, chat_id, stream)
        except exceptions.NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except exceptions.NoAudioSourceFound:
            raise AssistantErr(_["call_10"])
        except (ConnectionNotFound, TelegramServerError):
            raise AssistantErr(_["call_10"])
        except Exception:
            raise AssistantErr(_["call_10"])
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)

  
    async def change_stream(self, client: PyTgCalls, chat_id: int):
        await delete_old_message(chat_id)
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                await _clear_(chat_id)
                try:
                    buttons = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "✙ ʌᴅᴅ ϻє вᴧʙʏ ✙",
                                    url=f"https://t.me/{app.username}?startgroup=true",
                                ),
                                InlineKeyboardButton(
                                    "⋞ ᴄʟᴏsє ⋟", callback_data="close_message"
                                ),
                            ]
                        ]
                    )
                    await app.send_message(
                        chat_id,
                        "**🎵 𝐓ʜᴇ 𝐐ᴜᴇᴜᴇ 𝐇ᴀs 𝐅ɪɴɪsʜᴇᴅ. 𝐔sᴇ /play 𝐓ᴏ 𝐀ᴅᴅ 𝐌ᴏʀᴇ 𝐒ᴏɴɢs!!**",
                        reply_markup=buttons,
                    )
                except:
                    pass
                return await client.leave_call(chat_id, close=False)
        except Exception:
            try:
                await _clear_(chat_id)
                try:
                    buttons = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "✙ ʌᴅᴅ ϻє вᴧʙʏ ✙",
                                    url=f"https://t.me/{app.username}?startgroup=true",
                                ),
                                InlineKeyboardButton(
                                    "⋞ ᴄʟᴏsє ⋟", callback_data="close_message"
                                ),
                            ]
                        ]
                    )
                    await app.send_message(
                        chat_id,
                        "🎵 𝐓ʜᴇ 𝐐ᴜᴇᴜᴇ 𝐇ᴀs 𝐅ɪɴɪsʜᴇᴅ. 𝐔sᴇ /play 𝐓ᴏ 𝐀ᴅᴅ 𝐌ᴏʀᴇ 𝐒ᴏɴɢs!!",
                        reply_markup=buttons,
                    )
                except:
                    pass
                return await client.leave_call(chat_id, close=False)
            except Exception:
                return
        queued = check[0]["file"]
        language = await get_lang(chat_id)
        _ = get_string(language)
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        db[chat_id][0]["played"] = 0
        exis = (check[0]).get("old_dur")
        if exis:
            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0
        video = True if str(streamtype) == "video" else False
        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            stream = self._build_stream(link, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            img = await get_thumb(videoid)
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                has_spoiler=True,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
        elif "vid_" in queued:
            mystic = await app.send_message(original_chat_id, _["call_7"])
            try:
                file_path, direct = await YouTube.download(
                    videoid,
                    mystic,
                    videoid=True,
                    video=video,
                )
            except Exception:
                return await mystic.edit_text(
                    _["call_6"], disable_web_page_preview=True
                )

Anony = Call()
