import time
import re
import random
import asyncio

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import (
    ChannelPrivate, 
    SlowmodeWait, 
    PeerIdInvalid, 
    UserNotParticipant, 
    ChatAdminRequired, 
    FloodWait,
    WebpageCurlFailed,
    MediaEmpty
)
from youtubesearchpython.__future__ import VideosSearch

import config
from NEOMUSIC import app
from NEOMUSIC.misc import _boot_
from NEOMUSIC.plugins.sudo.sudoers import sudoers_list
from NEOMUSIC.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
    blacklist_chat,
)
from NEOMUSIC.utils.decorators.language import LanguageStart
from NEOMUSIC.utils.formatters import get_readable_time
from NEOMUSIC.utils.inline import help_pannel, private_panel, start_panel
from config import BANNED_USERS, LOGGER_ID
from strings import get_string

# Agar config mein image na ho toh ye use hogi
FALLBACK_IMG = "https://i.ibb.co/mF9Rw4dW/x.jpg"

@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    await add_served_user(message.from_user.id)
    
    # Image check
    img = config.START_IMG_URL if config.START_IMG_URL else FALLBACK_IMG

    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]
        if name[0:4] == "help":
            keyboard = help_pannel(_)
            try:
                return await message.reply_photo(
                    photo=img,
                    has_spoiler=True,
                    caption=_["help_1"].format(config.SUPPORT_CHAT),
                    reply_markup=keyboard,
                )
            except Exception:
                return await message.reply_text(
                    text=_["help_1"].format(config.SUPPORT_CHAT),
                    reply_markup=keyboard,
                )

        if name[0:3] == "sud":
            await sudoers_list(client=client, message=message, _=_)
            if await is_on_off(2):
                try:
                    await app.send_message(
                        chat_id=config.LOGGER_ID,
                        text=f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>sᴜᴅᴏʟɪsᴛ</b>.\n\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n<b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{message.from_user.username}",
                    )
                except:
                    pass
            return

        if name[0:3] == "inf":
            m = await message.reply_text("🔎 🔎 🔎")
            query = (str(name)).replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query}"
            
            try:
                results = VideosSearch(query, limit=1)
                search_result = (await results.next())["result"]
                if not search_result:
                    await m.edit_text("No details found for this track.")
                    return
                
                result = search_result[0]
                title = result.get("title", "N/A")
                duration = result.get("duration", "N/A")
                views = result.get("viewCount", {}).get("short", "N/A")
                thumbnail = result.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
                if not thumbnail:
                    thumbnail = img
                
                channellink = result.get("channel", {}).get("link", "N/A")
                channel = result.get("channel", {}).get("name", "N/A")
                link = result.get("link", "N/A")
                published = result.get("publishedTime", "N/A")
                
                searched_text = _["start_6"].format(
                    title, duration, views, published, channellink, channel, app.mention
                )
                key = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(text=_["S_B_8"], url=link),
                            InlineKeyboardButton(text=_["S_B_9"], url=config.SUPPORT_CHAT),
                        ],
                    ]
                )
                await m.delete()
                try:
                    await app.send_photo(
                        chat_id=message.chat.id,
                        photo=thumbnail,
                        has_spoiler=True,
                        caption=searched_text,
                        reply_markup=key,
                    )
                except Exception:
                    await app.send_message(
                        chat_id=message.chat.id,
                        text=searched_text,
                        reply_markup=key
                    )

                if await is_on_off(2):
                    try:
                        await app.send_message(
                            chat_id=config.LOGGER_ID,
                            text=f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>ᴛʀᴀᴄᴋ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b>.",
                        )
                    except:
                        pass
            except Exception as e:
                await m.edit_text(f"Error: {e}")
    else:
        out = private_panel(_)
        try:
            await message.reply_photo(
                photo=img,
                has_spoiler=True,
                caption=_["start_2"].format(message.from_user.mention, app.mention),
                reply_markup=InlineKeyboardMarkup(out),
            )
        except Exception:
            await message.reply_text(
                text=_["start_2"].format(message.from_user.mention, app.mention),
                reply_markup=InlineKeyboardMarkup(out),
            )
            
        if await is_on_off(2):
            try:
                await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ.\n\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>",
                )
            except:
                pass


@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    uptime = int(time.time() - _boot_)
    img = config.START_IMG_URL if config.START_IMG_URL else FALLBACK_IMG
    try:
        await message.reply_photo(
            photo=img,
            has_spoiler=True,
            caption=_["start_1"].format(app.mention, get_readable_time(uptime)),
            reply_markup=InlineKeyboardMarkup(out),
        )
        await add_served_chat(message.chat.id)
    except Exception as e:
        print(f"Error in start_gp: {e}")
        try:
            await message.reply_text(
                text=_["start_1"].format(app.mention, get_readable_time(uptime)),
                reply_markup=InlineKeyboardMarkup(out),
            )
        except:
            pass


@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
            img = config.START_IMG_URL if config.START_IMG_URL else FALLBACK_IMG
            
            if await is_banned_user(member.id):
                try:
                    await message.chat.ban_member(member.id)
                except:
                    pass
            
            if member.id == app.id:
                if message.chat.type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_4"])
                    return await app.leave_chat(message.chat.id)
                
                if message.chat.id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_5"].format(
                            app.mention,
                            f"https://t.me/{app.username}?start=sudolist",
                            config.SUPPORT_CHAT,
                        ),
                        disable_web_page_preview=True,
                    )
                    return await app.leave_chat(message.chat.id)
                
                try:
                    ch = await app.get_chat(message.chat.id)
                    if (ch.title and re.search(r'[\u1000-\u109F]', ch.title)) or \
                       (ch.description and re.search(r'[\u1000-\u109F]', ch.description)):
                        await blacklist_chat(message.chat.id)
                        await message.reply_text("Unsupported characters detected in chat info. Group Blacklisted.")
                        return await app.leave_chat(message.chat.id)
                except:
                    pass
                    
                out = start_panel(_)
                try:
                    await message.reply_photo(
                        photo=img,
                        has_spoiler=True,
                        caption=_["start_3"].format(
                            message.from_user.first_name if message.from_user else "User",
                            app.mention,
                            message.chat.title,
                            app.mention,
                        ),
                        reply_markup=InlineKeyboardMarkup(out),
                    )
                except Exception:
                    await message.reply_text(
                         text=_["start_3"].format(
                            message.from_user.first_name if message.from_user else "User",
                            app.mention,
                            message.chat.title,
                            app.mention,
                        ),
                        reply_markup=InlineKeyboardMarkup(out),
                    )
                await add_served_chat(message.chat.id)
                await message.stop_propagation()
        except Exception as ex:
            print(f"Welcome error: {ex}")
