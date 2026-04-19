import asyncio
import random

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.raw.functions.messages import DeleteHistory

from NEOMUSIC import userbot as us, app
from NEOMUSIC.core.userbot import assistants

@app.on_message(filters.command("sg"))
async def sg(client: Client, message: Message):
    if len(message.text.split()) < 1 and not message.reply_to_message:
        return await message.reply("❖ sɢ ᴜsᴇʀɴᴀᴍᴇ-ɪᴅ-ʀᴇᴘʟʏ")
    
    if message.reply_to_message:
        args = message.reply_to_message.from_user.id
    else:
        args = message.text.split()[1]

    lol = await message.reply("🧡")

    if args:
        try:
            user = await client.get_users(f"{args}")
        except Exception:
            return await lol.edit("<code>❖ ᴘʟᴇᴀsᴇ sᴘᴇᴄɪғʏ ᴀ ᴠᴀʟɪᴅ ᴜsᴇʀ !</code>")

    bo = ["sangmata_bot", "sangmata_beta_bot"]
    sg = random.choice(bo)

    if 1 in assistants:
        ubot = us.one

    try:
        a = await ubot.send_message(sg, str(user.id))
        await a.delete()
    except Exception as e:
        return await lol.edit(str(e))

    await asyncio.sleep(2)

    sent = False
    try:
        async for stalk in ubot.search_messages(sg):
            if not stalk or not stalk.text:
                continue
            
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]]
            )
            await client.send_message(
                chat_id=message.chat.id,
                text=stalk.text,
                reply_to_message_id=message.id,
                reply_markup=keyboard
            )
            sent = True
            break
    except Exception:
        pass

    if not sent:
        await message.reply("❖ ɴᴏ ʜɪsᴛᴏʀʏ ғᴏᴜɴᴅ ᴏʀ ʙᴏᴛ ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ.")

    try:
        user_info = await ubot.resolve_peer(sg)
        await ubot.send(DeleteHistory(peer=user_info, max_id=0, revoke=True))
    except Exception:
        pass

    await lol.delete()
