
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import asyncio
import ssl

TOKEN = ""

# Get admins ID

async def admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    admins = await context.bot.get_chat_administrators(chat_id)

    text = "Admins:\n"
    for admin in admins:
        text += f"{admin.user.first_name} — {admin.user.id}\n"

    print(text)
    await update.message.reply_text(text)

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("admins", admins))

app.run_polling()


# Get group ID

# async def handler(update, context):
#     chat_id = update.effective_chat.id
#     print("Chat ID:", chat_id)

#     # reply something (optional)
#     await update.message.reply_text(f"Your Group ID: `{chat_id}`", parse_mode="Markdown")
    
# def main():
#     app = ApplicationBuilder().token(TOKEN).build()

#     # receive all messages
#     app.add_handler(MessageHandler(filters.ALL, handler))

#     print("Bot is running...")
#     app.run_polling()

# if __name__ == "__main__":
#     main()


# from pymongo.mongo_client import MongoClient
# from pymongo.server_api import ServerApi

# uri = "mongodb+srv://sachindb:KrKbIbsbCBiCvGGa@cluster05.ukejys6.mongodb.net/?appName=Cluster05"
# # uri = "mongodb+srv://sachindb:KrKbIbsbCBiCvGGa@cluster05.mongodb.net/?retryWrites=true&w=majority&tls=true"

# # Create a new client and connect to the server
# client = MongoClient(uri, tls=True)
# # Send a ping to confirm a successful connection
# try:
#     client.admin.command('ping')
#     print("Pinged your deployment. You successfully connected to MongoDB!")
# except Exception as e:
#     print(e)