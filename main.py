# main.py - Cleaned & working Sachu ScencesPacks bot
# Requirements: pyrogram, pymongo, rapidfuzz, flask (flask optional but keepalive included)
# Env vars required: API_ID, API_HASH, BOT_TOKEN, MONGO_URI
# Optional env var: ADMINS (comma separated list)

import os
import json
import re
import tempfile
from threading import Thread
from urllib.parse import quote_plus, unquote_plus
from datetime import datetime
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pymongo import MongoClient
from rapidfuzz import fuzz
from urllib.parse import quote_plus
from asyncio import sleep

# ---------------- Environment / Config ----------------
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
MONGO_URI = os.environ["MONGO_URI"]
ADMINS = [int(x.strip()) for x in (os.environ["ADMINS"]).split(",") if x.strip().isdigit()]
ADMIN_ID = ADMINS[0] if ADMINS else None

if not (API_ID and API_HASH and BOT_TOKEN and MONGO_URI):
    raise RuntimeError("Missing one of API_ID/API_HASH/BOT_TOKEN/MONGO_URI env vars")

# ---------------- Keepalive (Flask) ----------------
app = Flask("keepalive")

@app.route("/")
def home():
    return "✅ Sachuscencespacks Bot is running!"

def _run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=_run_web, daemon=True).start()

# ---------------- MongoDB ----------------
mongo = MongoClient(MONGO_URI, tls=True)
db = mongo["Sachuscencespacks_db"]
filters_col = db["filters"]
connections_col = db["connections"]
user_conn_col = db["user_conn"]
requests_col = db["requests"]
sync_col = db["sync"]

# ---------------- Pyrogram client ----------------
client = Client("Sachuscencespacks", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
# ---------------- Helpers ----------------

def parse_buttons_from_text(text: str):
    """
    Parse occurrences like [Label](buttonurl:URL) anywhere in text.
    Returns (clean_description, list_of_button_rows).
    """
    if not text:
        return "", []
    # pattern finds multiple occurrences in a line
    pattern = re.compile(r'\[([^\]]+)\]\(buttonurl:([^)]+)\)')
    lines = text.splitlines()
    desc_lines = []
    buttons = []
    for line in lines:
        matches = pattern.findall(line)
        if matches:
            row = []
            for label, url in matches:
                row.append({"text": label.strip(), "url": url.strip()})
            if row:
                buttons.append(row)
        else:
            desc_lines.append(line)
    return "\n".join(desc_lines).strip(), buttons

def build_reply_markup_from_db(button_rows):
    if not button_rows:
        return None
    rows = []
    for row in button_rows:
        btns = []
        for b in row:
            if isinstance(b, dict) and b.get("text") and b.get("url"):
                btns.append(InlineKeyboardButton(b["text"], url=b["url"]))
        if btns:
            rows.append(btns)
    return InlineKeyboardMarkup(rows) if rows else None

def encode_cb(*parts):
    return "|".join(quote_plus(str(p)) for p in parts)

def decode_cb(data):
    return [unquote_plus(p) for p in data.split("|")]

PER_PAGE = 10
FUZZY_THRESHOLD = 80  # match threshold

# ---------------- Commands & Handlers ----------------

async def handle_delete_message(client, message, remove_msg="", seconds=10):
    chat_id = message.chat.id
    user_msg_id = message.id

    reply_message = await client.send_message(
        chat_id=chat_id,
        text=remove_msg,
        reply_to_message_id=user_msg_id
    )
    bot_msg_id = reply_message.id

    await sleep(seconds)

    try:
        await client.delete_messages(chat_id=chat_id, message_ids=bot_msg_id)
    except Exception as e:
        print(e)
        return


@client.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    name = (message.from_user.first_name or "Friend")
    await message.reply_text(
        f"👋 Hi {name}!\n\n"
        "Welcome to Sachu ScenesPacks 🎬\n"
        "Type a movie name in the group to check available scenepack filters.\n\n"
        "Use `/filters` to see available filters (in group for members, in private for admins).\n\n"
        "🔥 Created for Namakaga ❤️",
        quote=True
    )

# ---------------- /connect (admin private) - manual group id ----------------
@client.on_message(filters.private & filters.command("connect"))
async def connect_group(client, message: Message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        return await message.reply_text("❌ You are not authorized to use this command.", quote=True)

    parts = message.text.strip().split(maxsplit=1)

    if len(parts) < 2:
        await message.reply_text("⚙️ Usage: /connect <group_id>")
    group_id_str = parts[1].strip()
    try:
        group_id = int(group_id_str)
    except:
        return await message.reply_text("❌ Invalid Group ID format.", quote=True)

    group_name = "Unknown Group"
    try:
        chat = await client.get_chat(group_id)
        group_name = chat.title or group_name
    except:
        pass

    connections_col.update_one(
        {"admin_id": user_id, "group_id": group_id},
        {"$set": {"admin_id": user_id, "group_id": group_id, "group_name": group_name}},
        upsert=True
    )
    user_conn_col.update_one(
        {"user_id": user_id},
        {"$set": {"active_group": group_id}, "$addToSet": {"groups": {"id": group_id, "name": group_name}}},
        upsert=True
    )

    await message.reply_text(f"✅ Connected to **{group_name}** (`{group_id}`) successfully!", quote=True)

# ---------------- /connections (admin private) ----------------
@client.on_message(filters.private & filters.command("connections"))
async def show_connections(client, message: Message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        return await message.reply_text("❌ Admins only.", quote=True)

    conns = list(connections_col.find({"admin_id": user_id}))
    if not conns:
        return await message.reply_text("🔗 No connected groups found.", quote=True)

    buttons = []
    for c in conns:
        gid = c.get("group_id")
        gname = c.get("group_name") or str(gid)
        buttons.append([InlineKeyboardButton(gname, callback_data=encode_cb("conn_group", gid))])

    await message.reply_text("🔗 Your connected groups:", reply_markup=InlineKeyboardMarkup(buttons), quote=True)

@client.on_callback_query(filters.regex(r"^conn_group\|"))
async def conn_group_cb(client, cq):
    try:
        _, gid_str = decode_cb(cq.data)
        gid = int(gid_str)
    except:
        return await cq.answer("Invalid data", show_alert=True)

    conn = connections_col.find_one({"group_id": gid})
    gname = conn.get("group_name") if conn else "Unknown Group"

    buttons = [
        [InlineKeyboardButton("📶 Status", callback_data=encode_cb("conn_status", gid))],
        [InlineKeyboardButton("🔗 Connect", callback_data=encode_cb("conn_connect", gid))],
        [InlineKeyboardButton("❌ Disconnect", callback_data=encode_cb("conn_disconnect", gid))],
        [InlineKeyboardButton("🗑 Delete", callback_data=encode_cb("conn_delete", gid))],
        [InlineKeyboardButton("🔙 Back", callback_data=encode_cb("conn_back", cq.from_user.id))]
    ]
    await cq.message.edit_text(f"⚙️ Manage: {gname}\nID: `{gid}`", reply_markup=InlineKeyboardMarkup(buttons))

@client.on_callback_query(filters.regex(r"^conn_"))
async def conn_actions_cb(client, cq):
    data = cq.data
    user_id = cq.from_user.id

    if user_id not in ADMINS:
        return await cq.answer("Not allowed", show_alert=True)

    if data.startswith("conn_status|"):
        _, gid_str = decode_cb(data)
        gid = int(gid_str)
        conn = connections_col.find_one({"group_id": gid})
        await cq.answer("✅ Connected" if conn else "❌ Not connected", show_alert=True)

    elif data.startswith("conn_connect|"):
        _, gid_str = decode_cb(data)
        gid = int(gid_str)
        if connections_col.find_one({"group_id": gid}):
            return await cq.answer("Already connected", show_alert=True)
        connections_col.insert_one({"admin_id": user_id, "group_id": gid, "group_name": "Unknown Group"})
        await cq.answer("Connected", show_alert=True)

    elif data.startswith("conn_disconnect|"):
        _, gid_str = decode_cb(data)
        gid = int(gid_str)
        connections_col.delete_one({"group_id": gid})
        await cq.answer("Disconnected", show_alert=True)

    elif data.startswith("conn_delete|"):
        _, gid_str = decode_cb(data)
        gid = int(gid_str)
        connections_col.delete_one({"group_id": gid})
        await cq.answer("Deleted", show_alert=True)

    elif data.startswith("conn_back|"):
        _, admin_id_str = decode_cb(data)
        admin_id = int(admin_id_str)
        conns = list(connections_col.find({"admin_id": admin_id}))
        if not conns:
            return await cq.message.edit_text("🔗 No connected groups found.")
        buttons = [[InlineKeyboardButton(c.get("group_name","Unknown"), callback_data=encode_cb("conn_group", c["group_id"]))] for c in conns]
        await cq.message.edit_text("🔗 Your connected groups:", reply_markup=InlineKeyboardMarkup(buttons))

# ---------------- /filter add (private admin) ----------------
@client.on_message(filters.private & filters.photo & filters.caption)
async def create_filter_from_caption(client, message: Message):
    user_id = message.from_user.id

    if user_id not in ADMINS:
        return await message.reply_text("⚠️ Only admins can add filters here.")

    # Check if caption contains a /filter command
    if "/filter" not in message.caption:
        return  # Ignore normal photos

    # Active group check
    user_data = user_conn_col.find_one({"user_id": user_id})
    if not user_data or not user_data.get("active_group"):
        return await message.reply_text("❗ No active group connected. Use /connect <group_id> first.")

    group_id = int(user_data["active_group"])

    import re

    # Extract keyword
    match = re.search(r'/filter\s+"([^"]+)"', message.caption)
    if not match:
        return await message.reply_text("⚙️ Usage: /filter \"keyword\" inside caption.")

    keyword = match.group(1).strip().lower()

    # Remove the /filter command from caption
    text_content = re.sub(r'/filter\s+"[^"]+"', '', message.caption).strip()
    file_id = message.photo.file_id
    msg_type = "photo"

    # --- Parse buttonurl lines ---
    button_pattern = re.compile(
        r"\[([^\]]+)\]\(buttonurl:\s*<?([^>\s)]+)>?\)",
        re.IGNORECASE
    )
    buttons = []
    matches = button_pattern.findall(text_content)
    if matches:
        for btn_text, btn_url in matches:
            buttons.append({"text": btn_text.strip(), "url": btn_url.strip()})
        text_content = button_pattern.sub("", text_content).strip()

    # Prepare data for DB
    data = {
        "chat_id": group_id,
        "keyword": keyword,
        "type": msg_type,
        "text": text_content,
        "file_id": file_id,
        "buttons": buttons
    }

    filters_col.update_one(
        {"chat_id": group_id, "keyword": keyword},
        {"$set": data},
        upsert=True
    )

    await message.reply_text(f"✅ Filter '{keyword}' added successfully with photo.")

# ---------------- /filters (group plain + admin private inline) ----------------
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from rapidfuzz import fuzz
from pyrogram.enums import ChatType  # add this import at top if not already


MAX_LEN = 4000   # safe limit

def split_message(text):
    chunks = []
    while len(text) > MAX_LEN:
        # find the last newline before the limit
        split_at = text.rfind("\n", 0, MAX_LEN)

        if split_at == -1:  # no newline found
            split_at = MAX_LEN

        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()

    chunks.append(text)
    return chunks


@client.on_message(filters.command("filters"))
async def list_filters(client, message: Message):
    # Normalize chat_type (supports both enum and string)
    chat_type = getattr(message.chat, "type", None)
    chat_type_str = str(chat_type).replace("ChatType.", "").lower()
    user_id = message.from_user.id

    # ---------- GROUP CHAT ----------
    if chat_type_str in ("group", "supergroup"):
        group_id = message.chat.id
        filters_list = list(filters_col.find({"chat_id": group_id}).sort("keyword", 1))

        if not filters_list:
            msg = (
                        "📦 No filters found in this group yet.\n"
                        "Type the movie name to check scenepacks or use `/request <Movie Name>`."
                    )
            return await handle_delete_message(client, message, remove_msg=msg)

        text = f"🎬 Filters in this group ({len(filters_list)}):\n\n"
        for idx, f in enumerate(filters_list, start=1):
            keyword = f.get("keyword", "❓")
            text += f"{idx}. {keyword}\n"

        parts = split_message(text)

        for part in parts:
            await message.reply_text(part, quote=True)
        # await message.reply_text(text, quote=True)
        return

    # ---------- PRIVATE CHAT (ADMINS ONLY) ----------
    if chat_type_str == "private" or message.chat.id == user_id:
        if user_id not in ADMINS:
            return await message.reply_text("⚠️ Only admins can use this command in private chat.", quote=True)

        user_data = user_conn_col.find_one({"user_id": user_id})
        if not user_data or not user_data.get("active_group"):
            return await message.reply_text("❗ No active group connected. Use /connect <group_id> first.", quote=True)

        group_id = int(user_data["active_group"])
        filters_list = list(filters_col.find({"chat_id": group_id}).sort("keyword", 1))

        if not filters_list:
            return await message.reply_text("📦 No filters found in the connected group.", quote=True)

        text = f"🎬 Filters in connected group ({len(filters_list)}):\n\n"
        for idx, f in enumerate(filters_list, start=1):
            keyword = f.get("keyword", "❓")
            text += f"{idx}. {keyword}\n"

        parts = split_message(text)

        for part in parts:
            await message.reply_text(part, quote=True)
        # await message.reply_text(text, quote=True)
        return

    # ---------- DEFAULT FALLBACK ----------
    await message.reply_text(
        f"⚠️ Unhandled chat type ({chat_type_str}). Use this in a group or private chat.",
        quote=True
    )

async def send_filters_page_private(client, message_or_cq, gid, all_filters, page=1):
    total = len(all_filters)
    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    page = max(1, min(page, total_pages))
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    chunk = all_filters[start:end]

    group_name = str(gid)
    try:
        chat = await client.get_chat(gid)
        group_name = chat.title or group_name
    except:
        pass

    text = f"🎬 Filters for {group_name}\n📄 Page {page}/{total_pages}\n\nSelect a filter:"
    buttons = []
    for f in chunk:
        kw = f.get("keyword", "❓")
        buttons.append([InlineKeyboardButton(kw, callback_data=encode_cb("filters_view", gid, kw))])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=encode_cb("filters_page", gid, page-1)))
    if end < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=encode_cb("filters_page", gid, page+1)))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Close", callback_data=encode_cb("filters_close", gid))])
    markup = InlineKeyboardMarkup(buttons)

    if hasattr(message_or_cq, "reply_text"):
        await message_or_cq.reply_text(text, reply_markup=markup, quote=True)
    else:
        await message_or_cq.message.edit_text(text, reply_markup=markup)

# pagination callback
@client.on_callback_query()
async def filters_callback(client, callback_query):
    user_id = callback_query.from_user.id

    if user_id not in ADMINS:
        return await callback_query.answer("⚠️ Only admins can use this.", show_alert=True)

    data = callback_query.data

    # Pagination handler
    if data.startswith("filters_page:"):
        page = int(data.split(":")[1])
        # Get active group
        user_data = user_conn_col.find_one({"user_id": user_id})
        if not user_data or not user_data.get("active_group"):
            return await callback_query.answer("❗ No active group connected.", show_alert=True)

        group_id = int(user_data["active_group"])
        filters_list = list(filters_col.find({"chat_id": group_id}).sort("keyword", 1))
        keyboard = build_filters_buttons(filters_list, page=page)
        await callback_query.message.edit_text(
            f"📜 Filters in group ({len(filters_list)}):",
            reply_markup=keyboard
        )
        return

    # Filter actions
    if data.startswith("filter:"):
        keyword = data.split(":")[1]
        # Show action buttons: View / Delete / Copy / Back
        buttons = [
            [InlineKeyboardButton("📄 View", callback_data=f"view:{keyword}")],
            [InlineKeyboardButton("🗑 Delete", callback_data=f"del:{keyword}")],
            [InlineKeyboardButton("📤 Copy", callback_data=f"copy:{keyword}")],
            [InlineKeyboardButton("🔙 Back", callback_data="filters_page:0")]
        ]
        await callback_query.message.edit_text(
            f"⚡ Actions for filter: {keyword}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    # View filter
    if data.startswith("view:"):
        keyword = data.split(":")[1]
        user_data = user_conn_col.find_one({"user_id": user_id})
        if not user_data or not user_data.get("active_group"):
            return await callback_query.answer("❗ No active group connected.", show_alert=True)

        group_id = int(user_data["active_group"])
        fdata = filters_col.find_one({"chat_id": group_id, "keyword": keyword})
        if not fdata:
            return await callback_query.answer("❌ Filter not found.", show_alert=True)

        # Send photo if exists
        if fdata.get("file_id"):
            await callback_query.message.reply_photo(
                fdata["file_id"],
                caption=fdata.get("text",""),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(b["text"], url=b["url"]) for b in fdata.get("buttons",[])]]
                ) if fdata.get("buttons") else None
            )
        else:
            await callback_query.message.reply_text(fdata.get("text","No text found"))
        await callback_query.answer()
        return

    # Delete filter
    if data.startswith("del:"):
        keyword = data.split(":")[1]
        # Ask confirmation Yes / No
        buttons = [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"del_confirm:{keyword}"),
                InlineKeyboardButton("❌ No", callback_data="filters_page:0")
            ]
        ]
        await callback_query.message.edit_text(
            f"⚠️ Are you sure you want to delete filter: {keyword}?",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if data.startswith("del_confirm:"):
        keyword = data.split(":")[1]
        user_data = user_conn_col.find_one({"user_id": user_id})
        if not user_data or not user_data.get("active_group"):
            return await callback_query.answer("❗ No active group connected.", show_alert=True)

        group_id = int(user_data["active_group"])
        filters_col.delete_one({"chat_id": group_id, "keyword": keyword})
        await callback_query.message.edit_text(f"✅ Filter '{keyword}' deleted successfully.")
        return

    # Copy filter
    if data.startswith("copy:"):
        keyword = data.split(":")[1]
        # List all connected groups except active group
        user_data = user_conn_col.find_one({"user_id": user_id})
        if not user_data or not user_data.get("active_group"):
            return await callback_query.answer("❗ No active group connected.", show_alert=True)

        active_group = int(user_data["active_group"])
        connected_groups = connections_col.find({"user_id": user_id, "chat_id": {"$ne": active_group}})
        buttons = [
            [InlineKeyboardButton(g.get("name","Unknown"), callback_data=f"copyto:{keyword}:{g['chat_id']}")]
            for g in connected_groups
        ]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="filters_page:0")])
        await callback_query.message.edit_text("📤 Choose group to copy filter:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("copyto:"):
        _, keyword, target_group = data.split(":")
        target_group = int(target_group)
        user_data = user_conn_col.find_one({"user_id": user_id})
        if not user_data or not user_data.get("active_group"):
            return await callback_query.answer("❗ No active group connected.", show_alert=True)

        active_group = int(user_data["active_group"])
        fdata = filters_col.find_one({"chat_id": active_group, "keyword": keyword})
        if not fdata:
            return await callback_query.answer("❌ Filter not found.", show_alert=True)

        # Insert copy
        new_filter = fdata.copy()
        new_filter["chat_id"] = target_group
        new_filter.pop("_id", None)
        filters_col.insert_one(new_filter)
        await callback_query.message.edit_text(f"✅ Filter '{keyword}' copied to group successfully.")
        return
# ---------------- quick del/delall commands (admin private) ----------
@client.on_message(filters.private & filters.command("del"))
async def del_private(client, message: Message):
    if message.from_user.id not in ADMINS:
        return await message.reply_text("⚠️ Admin only.", quote=True)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply_text("Usage: /del <keyword>", quote=True)
    keyword = parts[1].strip().lower()
    ud = user_conn_col.find_one({"user_id": message.from_user.id}) or {}
    active = ud.get("active_group")
    if not active:
        return await message.reply_text("❗ No active group.", quote=True)
    gid = int(active)
    res = filters_col.delete_one({"chat_id": gid, "keyword": keyword})
    if res.deleted_count:
        await message.reply_text(f"🗑️ '{keyword}' deleted from `{gid}`.", quote=True)
    else:
        await message.reply_text("❌ Not found.", quote=True)

@client.on_message(filters.private & filters.command("delall"))
async def delall_private(client, message: Message):
    if message.from_user.id not in ADMINS:
        return await message.reply_text("⚠️ Admin only.", quote=True)
    ud = user_conn_col.find_one({"user_id": message.from_user.id}) or {}
    active = ud.get("active_group")
    if not active:
        return await message.reply_text("❗ No active group.", quote=True)
    gid = int(active)
    count = filters_col.delete_many({"chat_id": gid}).deleted_count
    await message.reply_text(f"🧹 Deleted {count} filters from `{gid}`.", quote=True)

# ---------------- /view private admin ----------------
@client.on_message(filters.private & filters.command("view"))
async def view_filter(client, message: Message):
    user_id = message.from_user.id

    # Admin only
    if user_id not in ADMINS:
        return await message.reply_text("⚠️ Only admins can use this command.")

    parts = message.text.split('"')
    if len(parts) < 2:
        return await message.reply_text("⚙️ Usage: /view \"keyword\"")

    keyword = parts[1].strip().lower()

    user_data = user_conn_col.find_one({"user_id": user_id})
    if not user_data or not user_data.get("active_group"):
        return await message.reply_text("❗ No active group connected. Use /connect <group_id> first.")

    group_id = int(user_data["active_group"])

    # Get filter from DB
    f = filters_col.find_one({"chat_id": group_id, "keyword": keyword})
    if not f:
        return await message.reply_text(f"⚠️ Filter '{keyword}' not found in group `{group_id}`.")

    text_content = f.get("text", "")
    buttons = []

    # If buttons exist in DB, rebuild InlineKeyboard
    for b in f.get("buttons", []):
        if b.get("text") and b.get("url"):
            buttons.append([InlineKeyboardButton(b["text"], url=b["url"])])

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

    # Send photo or text
    if f.get("type") == "photo" and f.get("file_id"):
        await message.reply_photo(
            photo=f["file_id"],
            caption=text_content,
            reply_markup=reply_markup
        )
    else:
        await message.reply_text(
            text_content,
            reply_markup=reply_markup
        )

# ---------------- /request ----------------
@client.on_message(filters.command("request") & (filters.private | filters.group))
async def request_command(client, message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply_text("Usage: /request <Movie Name>", quote=True)
    movie = parts[1].strip()
    requests_col.insert_one({"movie": movie, "from": message.from_user.id, "chat": message.chat.id, "time": datetime.utcnow()})
    for admin in ADMINS:
        try:
            await client.send_message(admin, f"📩 Request from `{message.from_user.id}` in `{message.chat.id}`:\n\n{movie}")
        except:
            pass
    await message.reply_text("📩 Request received. Admin will check soon. Thanks!", quote=True)

# ---------------- /status (admin placeholder: backup/import/clear) ----------------
@client.on_message(filters.private & filters.command("status"))
async def status_command(client, message: Message):
    if message.from_user.id not in ADMINS:
        return await message.reply_text("⚠️ Admin only.", quote=True)
    try:
        stats = mongo.admin.command("dbstats")
        storage_mb = round(stats.get("storageSize",0) / (1024*1024), 2)
    except:
        storage_mb = "N/A"
    total_filters = filters_col.count_documents({})
    try:
        total_groups = len(filters_col.distinct("chat_id"))
    except:
        total_groups = "N/A"
    text = f"📊 Database Status\n\n• Filters total: {total_filters}\n• Groups with filters: {total_groups}\n• Storage used: {storage_mb} MB"
    buttons = [
        [InlineKeyboardButton("💾 Backup DB", callback_data=encode_cb("status","backup"))],
        [InlineKeyboardButton("📥 Import DB", callback_data=encode_cb("status","import"))],
        [InlineKeyboardButton("📋 Copy Filters", callback_data=encode_cb("status","copy"))],
        [InlineKeyboardButton("🧹 Clear DB", callback_data=encode_cb("status","clear"))],
        [InlineKeyboardButton("🔙 Back", callback_data=encode_cb("status","back"))]
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), quote=True)

@client.on_callback_query(filters.regex(r"^status\|"))
async def status_cb(client, cq):
    if cq.from_user.id not in ADMINS:
        return await cq.answer("Admin only", show_alert=True)
    parts = decode_cb(cq.data)
    if len(parts) < 2:
        return await cq.answer("Invalid", show_alert=True)
    action = parts[1]
    if action == "backup":
        ud = user_conn_col.find_one({"user_id": cq.from_user.id}) or {}
        if not ud.get("active_group"):
            return await cq.answer("No active group", show_alert=True)
        gid = int(ud["active_group"])
        docs = list(filters_col.find({"chat_id": gid}, {"_id":0}))
        if not docs:
            return await cq.answer("No filters", show_alert=True)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        tmp.write(json.dumps(docs, ensure_ascii=False, indent=2).encode("utf-8"))
        tmp.flush(); tmp.close()
        await client.send_document(chat_id=cq.from_user.id, document=tmp.name, caption=f"Backup for group {gid}")
        await cq.answer("Backup sent", show_alert=True)
    elif action == "import":
        await cq.message.edit_text("📥 Please send the backup JSON file (as document) to this chat now.")
        user_conn_col.update_one({"user_id": cq.from_user.id}, {"$set": {"pending_import": True}}, upsert=True)
    elif action == "clear":
        await cq.message.edit_text("⚠️ Send admin password to confirm clear.")
        user_conn_col.update_one({"user_id": cq.from_user.id}, {"$set": {"awaiting_clear_password": True}}, upsert=True)
    else:
        await cq.answer("Unknown action", show_alert=True)

@client.on_message(filters.private & filters.document)
async def handle_document_import(client, message: Message):
    ud = user_conn_col.find_one({"user_id": message.from_user.id}) or {}
    if ud.get("pending_import") and ud.get("active_group"):
        tmp_path = await message.download()
        try:
            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            gid = int(ud["active_group"])
            imported = 0
            for item in data:
                item.pop("_id", None)
                item["chat_id"] = gid
                item["keyword"] = item.get("keyword","").lower()
                item["buttons"] = item.get("buttons", [])
                filters_col.update_one({"chat_id": gid, "keyword": item["keyword"]}, {"$set": item}, upsert=True)
                imported += 1
            await message.reply_text(f"✅ Imported {imported} filters into group `{gid}`.", quote=True)
        except Exception as e:
            await message.reply_text(f"❌ Import failed: {e}", quote=True)
        finally:
            user_conn_col.update_one({"user_id": message.from_user.id}, {"$unset": {"pending_import": ""}})
            try: os.remove(tmp_path)
            except: pass
        return
    await message.reply_text("No import pending. Use /status -> Import DB first.", quote=True)

@client.on_message(filters.private & filters.text)
async def admin_text_handlers(client, message: Message):
    ud = user_conn_col.find_one({"user_id": message.from_user.id}) or {}
    if ud.get("awaiting_clear_password"):
        pwd = message.text.strip()
        if pwd == "04042726":
            if not ud.get("active_group"):
                await message.reply_text("❗ No active group set.", quote=True)
            else:
                gid = int(ud["active_group"])
                count = filters_col.delete_many({"chat_id": gid}).deleted_count
                await message.reply_text(f"🧹 Cleared {count} filters from `{gid}`.", quote=True)
        else:
            await message.reply_text("❌ Wrong password.", quote=True)
        user_conn_col.update_one({"user_id": message.from_user.id}, {"$unset": {"awaiting_clear_password": ""}})
        return

# ---------------- Auto fuzzy reply in groups ----------------
from rapidfuzz import fuzz
from pyrogram.enums import ChatType

from rapidfuzz import fuzz
from pyrogram.enums import ChatType
import re

@client.on_message(filters.text)
async def filter_auto_reply(client, message: Message):
    # Skip bot/self messages only (not admins)
    if not message.from_user or message.from_user.is_bot:
        return

    # Detect chat type safely
    chat_type = getattr(message.chat, "type", None)
    chat_type_str = str(chat_type).replace("ChatType.", "").lower()

    # Only respond in groups or supergroups
    if chat_type_str not in ("group", "supergroup"):
        return

    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Fetch all filters for this group
    all_filters = list(filters_col.find({"chat_id": chat_id}))
    if not all_filters:
        if user_id not in ADMINS:
            await message.reply_text(
                "🎞️ Indha scenepack enkita ila...\n"
                "Soon naan upload pandren Nanba/Nanbi ❤️\n"
                "Unga request ah naan Sachin ku send panidren!",
                quote=True
            )
            # Notify admins
            for admin in ADMINS:
                try:
                    await client.send_message(
                        admin,
                        f"📩 *Request:* `{text}`\n👤 From: {message.from_user.first_name} (`{user_id}`)\n💬 In: `{chat_id}`"
                    )
                except Exception as e:
                    print("Admin notify error:", e)
        return

    # Find best fuzzy match
    best_filter = None
    best_score = 0
    for f in all_filters:
        keyword = f.get("keyword", "").lower()
        score = fuzz.ratio(keyword, text.lower())
        if score > best_score:
            best_score = score
            best_filter = f

    # Minimum similarity threshold
    if not best_filter or best_score < 80:
        if user_id not in ADMINS:
            msg = """🎞️ Indha scenepack enkita ila...
Soon naan upload pandren Nanba/Nanbi ❤️
Unga request ah naan Sachin ku send panidren sariyaa byeee 👋 """
            
            await handle_delete_message(client, message, remove_msg=msg)

            for admin in ADMINS:
                try:
                    await client.send_message(
                        admin,
                        f"📩 *Request:* `{text}`\n👤 From: {message.from_user.first_name} (`{user_id}`)\n💬 In: `{chat_id}`"
                    )
                except Exception as e:
                    print("Admin notify error:", e)
        return

    # --- FOUND MATCH: send filter ---
    text_content = best_filter.get("text", "")
    buttons = []

    # Regex for buttons in format:
    # [Text](buttonurl:<https://link>)  or  [Text](buttonurl: https://link)
    button_pattern = re.compile(
        r"\[([^\]]+)\]\(buttonurl:\s*(?:<)?(https?://[^\s>]+)(?:>)?\)",
        re.IGNORECASE
    )

    matches = button_pattern.findall(text_content)

    if matches:
        for btn_text, btn_url in matches:
            buttons.append([InlineKeyboardButton(btn_text.strip(), url=btn_url.strip())])
        # Remove buttonurl markup from caption
        text_content = button_pattern.sub("", text_content).strip()

    # Add extra buttons from DB (if any)
    for b in best_filter.get("buttons", []):
        if isinstance(b, dict) and b.get("text") and b.get("url"):
            buttons.append([InlineKeyboardButton(b["text"], url=b["url"])])

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

    try:
        if best_filter.get("type") == "photo" and best_filter.get("file_id"):
            await message.reply_photo(
                photo=best_filter["file_id"],
                caption=text_content,
                reply_markup=reply_markup
            )
        else:
            await message.reply_text(
                text_content,
                reply_markup=reply_markup
            )
    except Exception as e:
        print("❌ Error sending filter:", e)
# ---------------- Start client ----------------
if __name__ == "__main__":
    print("Starting Sachu scencespacks Bot...")
    client.run()