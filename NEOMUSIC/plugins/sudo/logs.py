from datetime import datetime
from pytz import timezone
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import ChatAdminRequired
from NEOMUSIC import app
from config import LOGGER_ID


def get_time():
    ist = timezone("Asia/Kolkata")
    return datetime.now(ist).strftime("%d-%b-%Y | %I:%M %p")


async def send_message_with_button(chat_id, text, buttons=None):
    try:
        msg = await app.send_message(
            chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
            disable_web_page_preview=True
        )
        try:
            await msg.pin(disable_notification=True)
        except ChatAdminRequired:
            pass
        except Exception:
            pass
    except Exception:
        pass


@app.on_message(filters.new_chat_members, group=0)
async def join_watcher(_, message: Message):
    chat = message.chat
    current_time = get_time()
    bot_user = await app.get_me()

    for member in message.new_chat_members:
        if member.id == bot_user.id:
            try:
                count = await app.get_chat_members_count(chat.id)
            except Exception:
                count = "Unavailable"

            try:
                link = await app.export_chat_invite_link(chat.id)
            except Exception:
                link = "𝖭𝗈𝗍 𝖠𝗏𝖺𝗂𝗅𝖺𝖻𝗅𝖾"

            msg = (
                f"🪘 <b>ʙᴏᴛ ᴀᴅᴅᴇᴅ ᴛᴏ ᴀ ɴᴇᴡ ɢʀᴏᴜᴘ</b> 🪘\n\n"
                f"🏷️ <b>ɢʀᴏᴜᴘ ɴᴀᴍᴇ :</b> {chat.title}\n"
                f"🆔 <b>ᴄʜᴀᴛ ɪᴅ :</b> <code>{chat.id}</code>\n"
                f"🔗 <b>ɢʀᴏᴜᴘ ʟɪɴᴋ :</b> {link}\n"
                f"👥 <b>ᴛᴏᴛᴀʟ ᴍᴇᴍʙᴇʀs :</b> {count}\n"
                f"🕰️ <b>ᴛɪᴍᴇ|ᴅᴀᴛᴇ :</b> {current_time}\n"
                f"👤 <b>ᴀᴅᴅᴇᴅ ʙʏ :</b> {message.from_user.mention if message.from_user else 'Unknown'}"
            )
            buttons = [[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]]
            await send_message_with_button(LOGGER_ID, msg, buttons)


@app.on_message(filters.left_chat_member)
async def on_left_chat_member(_, message: Message):
    bot_user = await app.get_me()
    if message.left_chat_member.id == bot_user.id:
        remover = message.from_user.mention if message.from_user else "Unknown"
        chat = message.chat
        current_time = get_time()

        msg = (
            f"🪘 <b>ʙᴏᴛ ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ᴀ ɢʀᴏᴜᴘ</b> 🪘\n\n"
            f"🏷️ <b>ɢʀᴏᴜᴘ ɴᴀᴍᴇ :</b> {chat.title}\n"
            f"🆔 <b>ᴄʜᴀᴛ ɪᴅ :</b> <code>{chat.id}</code>\n"
            f"🕰️ <b>ᴛɪᴍᴇ|ᴅᴀᴛᴇ :</b> {current_time}\n"
            f"👢 <b>ʀᴇᴍᴏᴠᴇᴅ ʙʏ :</b> {remover}"
        )
        buttons = [[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]]
        await send_message_with_button(LOGGER_ID, msg, buttons)
