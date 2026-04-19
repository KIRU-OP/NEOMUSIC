import time
import asyncio
from typing import Union

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import Message, User, Chat

from NEOMUSIC import app
from NEOMUSIC.misc import SUDOERS
from NEOMUSIC.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_served_chats,
    get_served_users,
)
from NEOMUSIC.utils.formatters import alpha_to_int
from config import adminlist

class BroadcastStatus:
    def __init__(self):
        self.active = False
        self.sent = 0
        self.failed = 0
        self.total = 0
        self.start_time = 0
        self.users = 0
        self.chats = 0
        self.mode = ""
        self.sent_users = 0
        self.sent_chats = 0
        self.failed_targets = []
        self.current_batch = 0

    def reset(self):
        self.__init__()

    def update_status(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def get_progress(self):
        processed = self.sent + self.failed
        percent = round(processed / self.total * 100, 2) if self.total else 0
        elapsed = time.time() - self.start_time
        eta = (elapsed / max(processed, 1)) * (self.total - processed) if processed else 0
        return {
            "percent": percent,
            "elapsed": round(elapsed),
            "eta": eta,
            "processed": processed,
        }

broadcast_status = BroadcastStatus()

def generate_progress_bar(percent):
    filled = '■' * int(percent // 5)
    empty = '□' * (20 - len(filled))
    return f"[{filled}{empty}]"

@app.on_message(filters.command("broadcast") & SUDOERS)
async def broadcast_command(client, message: Message):
    global broadcast_status

    if broadcast_status.active:
        return await message.reply("🚫 ᴀɴᴏᴛʜᴇʀ ʙʀᴏᴀᴅᴄᴀsᴛ ɪs ᴀʟʀᴇᴀᴅʏ ɪɴ ᴘʀᴏɢʀᴇss.")

    command = message.text.lower()
    mode = "forward" if "-forward" in command else "copy"

    # Determine recipients
    try:
        if "-all" in command:
            users = await get_served_users()
            chats = await get_served_chats()
            target_users = [u["user_id"] for u in users]
            target_chats = [c["chat_id"] for c in chats]
        elif "-users" in command:
            users = await get_served_users()
            target_users = [u["user_id"] for u in users]
            target_chats = []
        elif "-chats" in command:
            chats = await get_served_chats()
            target_chats = [c["chat_id"] for c in chats]
            target_users = []
        else:
            return await message.reply("⚙️ ᴜsᴀɢᴇ :\n/broadcast -all/-users/-chats [-forward]")
    except Exception as e:
        print(f"Error getting targets: {e}")
        return await message.reply("🚫 ᴇʀʀᴏʀ ғᴇᴛᴄʜɪɴɢ ʀᴇᴄɪᴘɪᴇɴᴛ ʟɪsᴛ.")

    if not target_users and not target_chats:
        return await message.reply("🚫 ɴᴏ ʀᴇᴄɪᴘɪᴇɴᴛs ғᴏᴜɴᴅ.")

    # Get content
    if message.reply_to_message:
        content = message.reply_to_message
    else:
        text = message.text
        for kw in ["/broadcast", "-forward", "-all", "-users", "-chats"]:
            text = text.replace(kw, "")
        text = text.strip()
        if not text:
            return await message.reply("📝 ᴘʀᴏᴠɪᴅᴇ ᴀ ᴍᴇssᴀɢᴇ ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴏɴᴇ.")
        content = text

    # Initialize broadcast
    targets = target_users + target_chats
    broadcast_status.reset()
    broadcast_status.update_status(
        active=True,
        total=len(targets),
        start_time=time.time(),
        users=len(target_users),
        chats=len(target_chats),
        mode=mode,
        current_batch=0,
    )

    status_msg = await message.reply("📡 ʙʀᴏᴀᴅᴄᴀsᴛ ɪɴɪᴛɪᴀʟɪᴢᴀᴛɪᴏɴ ᴄᴏᴍᴘʟᴇᴛᴇ. sᴛᴀʀᴛɪɴɢ...")

    async def deliver(chat_id: Union[int, str]):
        try:
            if isinstance(content, str):
                await app.send_message(chat_id, content)
            elif mode == "forward":
                await app.forward_messages(chat_id, message.chat.id, [content.id])
            else:
                await content.copy(chat_id)

            broadcast_status.sent += 1
            if chat_id in target_users:
                broadcast_status.sent_users += 1
            else:
                broadcast_status.sent_chats += 1
            return True
        except FloodWait as e:
            wait_time = min(e.value, 60)
            await asyncio.sleep(wait_time)
            return await deliver(chat_id)
        except RPCError as e:
            broadcast_status.failed += 1
            broadcast_status.failed_targets.append((chat_id, str(e)))
            print(f"ғᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ᴛᴏ {chat_id}: {e}")
            return False
        except Exception as e:
            broadcast_status.failed += 1
            broadcast_status.failed_targets.append((chat_id, str(e)))
            print(f"ᴜɴᴇxᴘᴇᴄᴛᴇᴅ ᴇʀʀᴏʀ ғᴏʀ {chat_id}: {e}")
            return False

    BATCH_SIZE = 100
    total_batches = (len(targets) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num in range(total_batches):
        if not broadcast_status.active:
            break

        batch_start = batch_num * BATCH_SIZE
        batch = targets[batch_start:batch_start + BATCH_SIZE]
        broadcast_status.current_batch = batch_num + 1

        tasks = [deliver(chat_id) for chat_id in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        progress = broadcast_status.get_progress()
        progress_bar = generate_progress_bar(progress["percent"])
        eta_fmt = f"{int(progress['eta'] // 60)}m {int(progress['eta'] % 60)}s"

        await status_msg.edit_text(
            f"📣 <b>ʙʀᴏᴀᴅᴄᴀsᴛ ᴘʀᴏɢʀᴇss :</b>\n\n"
            f"{progress_bar} <code>{progress['percent']}%</code>\n"
            f"📦 ʙᴀᴛᴄʜ : <code>{broadcast_status.current_batch}/{total_batches}</code>\n"
            f"✅ sᴇɴᴛ : <code>{broadcast_status.sent}</code>\n"
            f"🚫 ғᴀɪʟᴇᴅ : <code>{broadcast_status.failed}</code>\n"
            f"⏱ ᴇᴛᴀ : <code>{eta_fmt}</code>\n"
            f"🕒 ᴇʟᴀᴘsᴇᴅ : <code>{progress['elapsed']}s</code>\n\n"
            f"<b>⚙️ ɪғ ʏᴏᴜ ᴡᴀɴᴛ ᴄᴀɴᴄᴇʟ ʙʀᴏᴀᴅᴄᴀsᴛ : /cancel_gcast</b>"
        )

        if batch_num < total_batches - 1:
            await asyncio.sleep(1.5)

    broadcast_status.active = False
    elapsed = time.time() - broadcast_status.start_time

    result_message = (
        f"✅ <b>ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇ ! </b>\n\n"
        f"🔘 ᴍᴏᴅᴇ : <code>{broadcast_status.mode}</code>\n"
        f"📦 ᴛᴏᴛᴀʟ ᴛᴀʀɢᴇᴛs : <code>{broadcast_status.total}</code>\n"
        f"📬 ᴅᴇʟɪᴠᴇʀᴇᴅ : <code>{broadcast_status.sent}</code>\n"
        f"    ├ ᴜsᴇʀs : <code>{broadcast_status.sent_users}</code>\n"
        f"    └ ᴄʜᴀᴛs : <code>{broadcast_status.sent_chats}</code>\n"
        f"🚫 ғᴀɪʟᴇᴅ : <code>{broadcast_status.failed}</code>\n"
        f"⏰ ᴛɪᴍᴇ ᴛᴀᴋᴇɴ : <code>{round(elapsed)}s</code>"
    )

    if broadcast_status.failed > 0:
        result_message += "\n\n⚙️ sᴏᴍᴇ ᴛᴀʀɢᴇᴛs ғᴀɪʟᴇᴅ. ᴜsᴇ [ ᴅᴏɴ'ᴛ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ] ᴛᴏ sᴇᴇ ᴅᴇᴛᴀɪʟs."

    await status_msg.edit_text(result_message)

@app.on_message(filters.command("status") & SUDOERS)
async def broadcast_status_cmd(client, message: Message):
    if not broadcast_status.active:
        return await message.reply("📡 ɴᴏ ᴀᴄᴛɪᴠᴇ ᴀɴʏ ʙʀᴏᴀᴅᴄᴀsᴛ.")

    progress = broadcast_status.get_progress()
    progress_bar = generate_progress_bar(progress["percent"])
    eta_fmt = f"{int(progress['eta'] // 60)}m {int(progress['eta'] % 60)}s"

    await message.reply(
        f"📊 <b>ʙʀᴏᴀᴅᴄᴀsᴛ sᴛᴀᴛᴜs :</b>\n\n"
        f"{progress_bar} <code>{progress['percent']}%</code>\n"
        f"📦 ʙᴀᴛᴄʜ : <code>{broadcast_status.current_batch}/{((broadcast_status.total + 99) // 100)}</code>\n"
        f"✅ sᴇɴᴛ : <code>{broadcast_status.sent}</code>\n"
        f"🚫 ғᴀɪʟᴇᴅ : <code>{broadcast_status.failed}</code>\n"
        f"⏱ ᴇᴛᴀ : <code>{eta_fmt}</code>\n"
        f"🕒 ᴇʟᴀᴘsᴇᴅ : <code>{progress['elapsed']}s</code>"
    )

@app.on_message(filters.command("cancel_gcast") & SUDOERS)
async def cancel_broadcast(client, message: Message):
    global broadcast_status

    if not broadcast_status.active:
        return await message.reply("ℹ️ ɴᴏ ᴀᴄᴛɪᴠᴇ ʙʀᴏᴀᴅᴄᴀsᴛ ᴛᴏ ᴄᴀɴᴄᴇʟ.")

    broadcast_status.active = False
    await message.reply("🛑 ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ.")

@app.on_message(filters.command("cehckfailed") & SUDOERS)
async def show_failed_targets(client, message: Message):
    if not broadcast_status.failed_targets:
        return await message.reply("✅ ɴᴏ ғᴀɪʟᴇᴅ ᴛᴀʀɢᴇᴛs ɪɴ ᴛʜᴇ ʟᴀsᴛ ʙʀᴏᴀᴅᴄᴀsᴛ.")

    failed_list = "\n".join(
        f"• <code>{target[0]}</code>: {target[1]}"
        for target in broadcast_status.failed_targets[:50]
    )

    if len(broadcast_status.failed_targets) > 50:
        failed_list += "\n\n... and {} more".format(len(broadcast_status.failed_targets) - 50)

    await message.reply(
        f"🚫 <b>ғᴀɪʟᴇᴅ ᴛᴀʀɢᴇᴛs ({len(broadcast_status.failed_targets)})</b>\n\n{failed_list}"
    )

async def auto_clean():
    while True:
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        if user.privileges.can_manage_video_chats:
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except Exception as e:
            print(f"Error in auto_clean: {e}")
        finally:
            await asyncio.sleep(300)

asyncio.create_task(auto_clean())
