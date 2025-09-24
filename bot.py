from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import os

# Load config from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

app = Client("vote_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

conn = sqlite3.connect("votes.db", check_same_thread=False)
cursor = conn.cursor()

# Create tables
cursor.execute("""CREATE TABLE IF NOT EXISTS votes (
    chat_id INTEGER, user_id INTEGER, username TEXT, vote_count INTEGER DEFAULT 0, UNIQUE(chat_id, user_id)
)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS vote_sessions (
    chat_id INTEGER PRIMARY KEY, created_by INTEGER
)""")
conn.commit()

@app.on_message(filters.command("vote") & filters.private)
def create_vote(client, message):
    if len(message.command) != 2:
        message.reply("Usage: /vote <chat_id>")
        return
    chat_id = int(message.command[1])
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO vote_sessions(chat_id, created_by) VALUES (?, ?)", (chat_id, user_id))
    conn.commit()
    link = f"https://t.me/{app.username}?start=vote_{chat_id}"
    message.reply(f"Voting created! Share this link to participate:\n{link}")

@app.on_message(filters.private & filters.command("start"))
def start(client, message):
    if not message.command[1].startswith("vote_"):
        return
    chat_id = int(message.command[1].split("_")[1])
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    cursor.execute("SELECT * FROM votes WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    if cursor.fetchone():
        message.reply("You already voted in this chat.")
        return
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Vote ✅", callback_data=f"vote_{chat_id}_{user_id}")]])
    message.reply("Click the button to cast your vote:", reply_markup=keyboard)

@app.on_callback_query(filters.regex(r"vote_\d+_\d+"))
def vote_callback(client, callback_query):
    chat_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.first_name
    cursor.execute("SELECT * FROM votes WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    if cursor.fetchone():
        callback_query.answer("You already voted!", show_alert=True)
        return
    cursor.execute("INSERT INTO votes(chat_id, user_id, username, vote_count) VALUES (?, ?, ?, ?)", (chat_id, user_id, username, 1))
    conn.commit()
    callback_query.answer("Vote recorded!", show_alert=True)
    callback_query.message.edit("Thanks for voting!")

@app.on_message(filters.command("result") & filters.private)
def result(client, message):
    chat_id = int(message.command[1])
    cursor.execute("SELECT username, vote_count FROM votes WHERE chat_id=? ORDER BY vote_count DESC LIMIT 10", (chat_id,))
    top_users = cursor.fetchall()
    if not top_users:
        message.reply("No votes yet.")
        return
    result_text = "🏆 Top 10 voters:\n\n"
    for i, (username, count) in enumerate(top_users, start=1):
        result_text += f"{i}. {username} - {count} vote(s)\n"
    message.reply(result_text)

app.run()
