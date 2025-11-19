from telegram import Update, error
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, Defaults, ContextTypes, MessageHandler, filters
from zoneinfo import ZoneInfo
from asyncio import sleep
import logging
import time
import uuid
import sys
import re
# import pytz

from db import Messages, MoviesList, collection, movie_collection
import logger


TOKEN = ""
BOT_NAME = ""

# target_timezone = pytz.timezone("Asia/Kolkata")
target_timezone = ZoneInfo("Asia/Kolkata")
defaults = Defaults(tzinfo=target_timezone)


async def handle_delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE, remove_msg="", seconds=6):
    chat_id = update.message.chat_id
    user_msg_id = update.message.message_id    

    # Send bot reply
    reply = await context.bot.send_message(
        chat_id=chat_id,
        text=remove_msg,
        reply_to_message_id=user_msg_id
    )

    bot_msg_id = reply.message_id

    await sleep(seconds)

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=user_msg_id)
        await context.bot.delete_message(chat_id=chat_id, message_id=bot_msg_id)
    except Exception as e:
        logging.error(f"Could not delete message: {e}")



async def get_movie(id:str):
    return collection.find_one({"_id": id, "enabled": 1}) or None


async def get_request_movie_text(text:str):

    match = re.search(r'"([^"]+)"', text)
    if match:
        movie_name = match.group(1)
        return movie_name
    else:
        return


async def check_movie_exists(request_movie, update, context, enabled:int=1):
    print("request_movie :" + request_movie)
    movie_doc = movie_collection.find_one({"name": request_movie, "enabled": enabled})
    print(movie_doc)
    print("###################")
    message = "Not available"

    if not movie_doc:
        await handle_delete_message(update, context, remove_msg=message, seconds=4)
    else:
        return movie_doc


async def send_movie_link(request_movie:str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        movie_doc = await check_movie_exists(request_movie, update, context)
               
        if movie_doc and ("message_id" in movie_doc):
            # db_message = Messages(movie_doc["message_id"]).collection
            db_message = collection.find_one({"_id": movie_doc["message_id"], "enabled": 1})
            if db_message:
                print(db_message)
                buttons = [
                        [InlineKeyboardButton(text=b["text"], url=b["url"])]
                        for b in db_message["button"]
                    ]
                keyboard = InlineKeyboardMarkup(buttons)
                await update.message.reply_photo(
                        photo=db_message["file_id"],
                        caption=db_message["text"],
                        reply_markup=keyboard
                    )
            else:
                return
        else:
            # await update.message.reply_text("movie Not added")
            return
    except Exception as err:
        print(err)
        logging.info(err)
        logging.exception("Get movie crashed!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message_type = update.effective_chat.type
        text: str = str(update.message.text).lower()
        caption: str = str(update.message.caption)
        msg = update.message
        response = None

        print(message_type)
        print("text :" + str(text))
        print("caption :" + str(caption))

        print(str(sys._getframe().f_lineno) + "\n")

        if message_type in ["supergroup"]:
            print(str(sys._getframe().f_lineno) + "\n")
            response: str = await send_movie_link(text, update, context)

        elif message_type == "private":
            chat_id = str(update.effective_chat.id)

            if caption:
                print(str(sys._getframe().f_lineno) + "\n")
                pattern = r"\[(.*?)\]\(buttonurl:(.*?)\)"
                matches = re.findall(pattern, caption)

                buttons = []
                for m in matches:
                    if m:
                        buttons.append({"text": m[0].strip(), "url": m[1].strip()})
                # buttons = [{"text": m[0].strip(), "url": m[1].strip()} for m in matches]

                movie_pattern = r"𝗠𝗼𝘃𝗶𝗲\s*:\s*(.*)"
                movie_match = re.search(movie_pattern, caption)
                movie_name = movie_match.group(1).strip().lower() if movie_match else ""
                movie_name = movie_name.strip()

                msg_text = re.sub(pattern, "", caption).strip()
                
                print(str(sys._getframe().f_lineno) + "\n")
                print(movie_name)
                print(msg_text)
                print(buttons)
                if movie_name and msg_text != "None" and buttons:
                    random_id = uuid.uuid4().hex[:24]
                    db_movielist = MoviesList(random_id)
                    db_movie = db_movielist.collection
                    db_movie["name"] = movie_name
                    db_movie["enabled"] = 0
                    db_movie["timestamp"] = int(time.time())

                    random_id = uuid.uuid4().hex[:24]
                    db_movie["message_id"] = random_id

                    print(str(sys._getframe().f_lineno) + "\n")
                    print(db_movie)

                    db_base = Messages(random_id)
                    db_data = db_base.collection

                    # --- Photos ---
                    print(str(sys._getframe().f_lineno) + "\n")
                    if msg.photo:
                        print(str(sys._getframe().f_lineno) + "\n")
                        # msg.photo is a list of PhotoSize objects (different resolutions)
                        
                        print(str(sys._getframe().f_lineno) + "\n")
                        # To download the largest photo:
                        largest = msg.photo[-1]
                        if largest.file_id:
                            db_data["file_id"] = largest.file_id
                        print("Photo file_id:", largest.file_id)
                        # file = await context.bot.get_file(largest.file_id)
                        # # await file.download_to_drive(f"downloads/{largest.file_id}.jpg")
                        # print(f"downloads/{largest.file_id}.jpg")
                        # print("Photo downloaded!")

                            # bot_msg = Messages(count)

                    print(str(sys._getframe().f_lineno) + "\n")

                    db_data["text"] = msg_text
                    db_data["button"] = buttons
                    db_data["enabled"] = 0
                    db_data["timestamp"] = int(time.time())
                    db_data["movie_name"] = movie_name if movie_name else ""
                    print(db_data)
                    print(str(sys._getframe().f_lineno) + "\n")

                    if movie_name:
                        response = f'Request accepted, now add movie filters\n/filter "{movie_name}"'
                    else:
                        response = f'Request accepted, now add movie filters\n/filter "<movie_name>"'
            else:
                print(str(sys._getframe().f_lineno) + "\n")
                print("erorr")

        if response:
            print(str(sys._getframe().f_lineno) + "\n")
            await update.message.reply_text(response)
        else:
            return
            # file_id = "AgACAgUAAxkBAAOpaRjglcoNIVtx4Q_Z2MjD9aZWOoAAhIMaxtddclU2dvA2q3HdkcBAAMCAANzAAM2BA"
            # await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file_id)
            # await update.message.reply_text("Error nanba...")
    except Exception as err:
        print(err)
        logging.info(err)
        logging.exception("Bot crashed!")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.from_user.first_name or "Friend")

    await update.message.reply_text(
        f'''👋 Hi {name}!
        Welcome to Sachu ScencePacks 🎬\n
        Type a movie name in the group to check available scenepack filters.\n
        Use `/filters` to see available filters (in group for members, in private for admins).\n
        Use `/request <movie_name>` to request a movie, it will uploaded soon!\n
        🔥 Created for Namakaga ❤️'''
    )

async def add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_type = str(update.effective_chat.type)

    if message_type == "private":
        text = await get_request_movie_text(str(update.message.text).lower())

        if text:
            movie_doc = await check_movie_exists(text, update, context, enabled=0)

            if movie_doc and ("message_id" in movie_doc):
                db_movielist = movie_collection.update_one({"message_id": movie_doc["message_id"]}, {"$set": {"enabled": 1}})
                db_message = collection.update_one({"_id": movie_doc["message_id"]}, {"$set": {"enabled": 1}})

                if (db_movielist.modified_count > 0) and (db_message.modified_count > 0):
                    success_message = f"'{text}' movie added to filters ✅."
                    await update.message.reply_text(success_message)

                    print("Added: " + text)

    else:
        await update.message.reply_text("Only Admins has the access")
    

async def show_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):

    docs = movie_collection.find({"enabled": 1}).sort("name", 1)
    movies = [doc["name"] for doc in docs if "name" in doc]

    movie_list = f"🎬 Filters in this group ({len(movies)}):\n\n"
    for i, name in enumerate(movies, start=1):
        movie_list += f"{i}. {name}\n"

    await update.message.reply_text(movie_list)


async def add_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #TODO: add request to DB
    movie_name = await get_request_movie_text(str(update.message.text).lower())

    message = (
        "Soon naan upload pandren Nanba Nanbi 💚😊\n\n"
        "Unga request ah naan Sachin ku send pandren"
        )
    
    await handle_delete_message(update, context, remove_msg=message)
    # await update.message.reply_text("Unga request ah naan Sachin ku send pandren")


async def del_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_type = str(update.effective_chat.type)

    if message_type == "private":
        del_movie = await get_request_movie_text(str(update.message.text).lower())
        
        print(del_movie)
        movie_doc = await check_movie_exists(del_movie, update, context)

        if movie_doc and ("message_id" in movie_doc):
            # db_movielist = movie_collection.delete_one({"message_id": movie_doc["message_id"], "enabled": 1})
            # db_message = collection.delete_one({"_id": movie_doc["message_id"], "enabled": 1})

            # if (db_movielist.deleted_count == 1) and (db_message.deleted_count == 1):
            
            db_movielist = movie_collection.update_one({"message_id": movie_doc["message_id"]}, {"$set": {"enabled": 0}})
            db_message = collection.update_one({"_id": movie_doc["message_id"]}, {"$set": {"enabled": 0}})

            if (db_movielist.modified_count > 0) and (db_message.modified_count > 0):
                success_message = f"'{del_movie}' movie deleted from filters ✅."
                await update.message.reply_text(success_message)
            else:
                return
        else:
            return
    else:
        await update.message.reply_text("Only Admins has the access")


async def delall_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_type = str(update.effective_chat.type)

    if message_type == "private":
        del_allmovies: str = str(update.message.text).lower()

        if del_allmovies == "/delall":
            db_movielist = movie_collection.update_many({}, {"$set": {"enabled": 0}})
            db_message = collection.update_many({}, {"$set": {"enabled": 0}})

            if (db_movielist.modified_count > 0) and (db_message.modified_count > 0):
                success_message = f"All movies deleted from filters ✅."
                await update.message.reply_text(success_message)
            else:
                return
        else:
            return
    else:
        await update.message.reply_text("Only Admins has the access")


def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .defaults(defaults)
        .build()
    )

    logging.info("Bot is running...")

    #Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("filter", add_filter))
    app.add_handler(CommandHandler("filters", show_filters))
    app.add_handler(CommandHandler("request", add_request))
    app.add_handler(CommandHandler("del", del_filter))
    app.add_handler(CommandHandler("delall", delall_filter))

    #Messages
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))

    #Error
    # app.add_error_handler(error)
    # app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message))

    app.run_polling(poll_interval=3)


if __name__ == '__main__':
    try:
        main()
    except Exception as err:
        logging.exception("Bot crashed!")
        logging.info(err)


# user_id = message.from_user.id

#     if user_id not in ADMINS:
#         return await message.reply_text("⚠️ Only admins can add filters here.")