from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from config import BOT_TOKEN, API_ID, API_HASH, MONGO_URL

# ------------------- Initialize Bot -------------------
app = Client(
    ":memory:",  # in-memory session avoids BadMsgNotification
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="./"  # optional for Heroku dyno
)

# ------------------- MongoDB Setup -------------------
mongo_client = MongoClient(MONGO_URL)
db = mongo_client["vote_bot_db"]
votes_col = db["votes"]
sessions_col = db["vote_sessions"]

# ------------------- /start Command -------------------
@app.on_message(filters.private & filters.command("start"))
def start(client, message):
    if len(message.command) > 1 and message.command[1].startswith("vote_"):
        chat_id = int(message.command[1].split("_")[1])
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        if votes_col.find_one({"chat_id": chat_id, "user_id": user_id}):
            message.reply("❌ You already voted in this chat.")
            return

        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Vote ✅", callback_data=f"vote_{chat_id}_{user_id}")]]
        )
        message.reply("Click the button to cast your vote:", reply_markup=keyboard)
    else:
        message.reply(
            f"👋 Hi {message.from_user.first_name}!\n\n"
            "I am Vote Bot 🤖. I can help you create inline voting in your groups or channels.\n\n"
            "Use /help to see available commands."
        )

# ------------------- /help Command -------------------
@app.on_message(filters.private & filters.command("help"))
def help_command(client, message):
    message.reply(
        "📌 *Vote Bot Usage Guide*\n\n"
        "/vote <chat_id> - Create a new vote. Make me admin in your group/channel first.\n"
        "/result <chat_id> - Show top 10 users with highest votes.\n"
        "/help - Show this guide.\n\n"
        "Steps to create a vote:\n"
        "1️⃣ Make the bot an admin in your group/channel.\n"
        "2️⃣ Send /vote <chat_id> (get chat ID with -100xxxx format).\n"
        "3️⃣ Share the generated link for participants."
    )

# ------------------- /vote Command -------------------
@app.on_message(filters.private & filters.command("vote"))
def create_vote(client, message):
    if len(message.command) != 2:
        message.reply("Usage: /vote <chat_id>")
        return

    chat_id = int(message.command[1])
    user_id = message.from_user.id

    message.reply(
        "⚠️ Please make me an admin in your group/channel first, then send the chat ID using this command.\n"
        f"Example: /vote {chat_id}"
    )

    sessions_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"created_by": user_id}},
        upsert=True
    )

    link = f"https://t.me/{app.username}?start=vote_{chat_id}"
    message.reply(f"✅ Voting created!\nShare this link to participate:\n{link}")

# ------------------- Voting Callback -------------------
@app.on_callback_query(filters.regex(r"vote_\d+_\d+"))
def vote_callback(client, callback_query):
    chat_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or callback_query.from_user.first_name

    if votes_col.find_one({"chat_id": chat_id, "user_id": user_id}):
        callback_query.answer("❌ You already voted!", show_alert=True)
        return

    votes_col.insert_one({
        "chat_id": chat_id,
        "user_id": user_id,
        "username": username,
        "vote_count": 1
    })
    callback_query.answer("✅ Vote recorded!", show_alert=True)
    callback_query.message.edit("Thanks for voting!")

# ------------------- /result Command -------------------
@app.on_message(filters.private & filters.command("result"))
def result(client, message):
    if len(message.command) != 2:
        message.reply("Usage: /result <chat_id>")
        return

    chat_id = int(message.command[1])
    top_users = list(votes_col.find({"chat_id": chat_id}).sort("vote_count", -1).limit(10))

    if not top_users:
        message.reply("No votes yet.")
        return

    result_text = "🏆 Top 10 voters:\n\n"
    for i, user in enumerate(top_users, start=1):
        result_text += f"{i}. {user['username']} - {user['vote_count']} vote(s)\n"

    message.reply(result_text)

# ------------------- Run Bot -------------------
if __name__ == "__main__":
    app.start()
    print("Bot started successfully ✅")
    app.idle()  # keep bot running
    app.stop()
