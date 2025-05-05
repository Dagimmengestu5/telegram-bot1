import os
import re
import csv
import pytz
import random
from datetime import datetime, timezone

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, ApplicationBuilder, ContextTypes, filters
from telegram.request import HTTPXRequest

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from pydrive2.auth import GoogleAuth


# === Telegram Config ====
TOKEN = "7945188969:AAGqv31lZK0YaRjVTDqBXgTiCJyt1hyICnc"
BOT_PASSWORD = ["dagi", "Dagi", "droga"]
main_folders = ["መሰረተ ትምሕርት", "ቤተ ዜማ", "ሥርዓተ ቅዳሴ"]
WEEKDAY_ORDER = [
    "የዘወትር ፀሎት",
    "ውዳሴ ማርያም",
    "አንቀፀ ብርሃን",
    "መልክዐ ማርያም",
    "መልክዐ ኢየሰስ",
    "መዝሙረ ዳዊት"
]

# === File System Setup ===
os.makedirs("መሰረተ ትምሕርት", exist_ok=True)
for day in WEEKDAY_ORDER:
    os.makedirs(os.path.join("መሰረተ ትምሕርት", day), exist_ok=True)
os.makedirs("ቤተ ዜማ", exist_ok=True)
os.makedirs("ሥርዓተ ቅዳሴ", exist_ok=True)

# === Google Drive Setup ===
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

gauth = GoogleAuth()
gauth.LoadServiceConfigFile("client_secrets.json")
drive = GoogleDrive(gauth)

# gauth = GoogleAuth()
# gauth.LocalWebserverAuth()
# drive = GoogleDrive(gauth)
FOLDER_ID = "1ZyYKgKcQSrrTTMDuNY8zYafGBjMWSKH6"  # Replace this

def upload_csv_to_drive(filename, folder_id):
    try:
        file_list = drive.ListFile({'q': f"'{folder_id}' in parents and title='{filename}' and trashed=false"}).GetList()
        if file_list:
            file_drive = file_list[0]
            file_drive.SetContentFile(filename)
            file_drive.Upload()
        else:
            file_drive = drive.CreateFile({'title': filename, 'parents': [{'id': folder_id}]})
            file_drive.SetContentFile(filename)
            file_drive.Upload()
    except Exception as e:
        print(f"❌ Failed to upload to Google Drive: {e}")

# === Utility ===
def natural_key(text):
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', text)]

def pad_text(text, width):
    return text + ("\u2003" * (width - len(text)))

# === Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔒 Please enter the password to access the bot:")
    context.user_data["auth_step"] = "awaiting_password"

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name
    username = user.username or "-"
    user_id = user.id
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    # Log to CSV and upload
    file_exists = os.path.isfile("users.csv")
    with open("users.csv", "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["User ID", "Name", "Username", "Timestamp"])
        writer.writerow([user_id, name, username, timestamp])
    upload_csv_to_drive("users.csv", FOLDER_ID)

    label_map = {}
    keyboard = []
    for folder in main_folders:
        label_map[folder] = folder
        keyboard.append([folder])

    context.user_data["path_map"] = label_map
    context.user_data["current_path"] = None
    context.user_data["authenticated"] = True

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"✅ Access granted.\n\n📂 Welcome {name}! Please choose a folder:", reply_markup=reply_markup)

async def list_directory(update: Update, context: ContextTypes.DEFAULT_TYPE, path):
    if not os.path.exists(path):
        await update.message.reply_text("❌ Path does not exist.")
        return

    items = os.listdir(path)
    if path == "መሰረተ ትምሕርት":
        ordered = [i for i in WEEKDAY_ORDER if i in items]
        extras = sorted([i for i in items if i not in WEEKDAY_ORDER], key=natural_key)
        items = ordered + extras
    else:
        items.sort(key=natural_key)

    if not items:
        await update.message.reply_text("📂 This folder is empty.")
        return

    max_len = max(len(item) for item in items)
    keyboard = [["Main Menu", "Back"]]
    label_map = {}

    for item in items:
        emoji = "📁" if os.path.isdir(os.path.join(path, item)) else "📄"
        padded = pad_text(item, max_len)
        label = f"{emoji} {padded}"
        keyboard.append([label])
        label_map[label] = item

    context.user_data["path_map"] = label_map
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"📂 Select from `{path}`:", reply_markup=reply_markup)

async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    print(text)
    if context.user_data.get("auth_step") == "awaiting_password":
        if text in BOT_PASSWORD:
            context.user_data["auth_step"] = None
            await show_main_menu(update, context)
        else:
            await update.message.reply_text("❌ Incorrect password. Try again.")
        return

    if text == "Main Menu":
        await show_main_menu(update, context)
        return

    if text == "Back":
        current = context.user_data.get("current_path")
        if current:
            parent = os.path.dirname(current)
            if current in main_folders or parent in ["", ".", None]:
                await show_main_menu(update, context)
            else:
                context.user_data["current_path"] = parent
                await list_directory(update, context, parent)
        else:
            await update.message.reply_text("📂 You're already at the top.")
        return

    if not context.user_data.get("current_path"):
        label_map = context.user_data.get("path_map", {})
        selected = label_map.get(text)
        if selected and selected in main_folders:
            path = selected
            context.user_data["current_path"] = path
            await list_directory(update, context, path)
        else:
            await update.message.reply_text("❌ Please select a valid main folder or write '/start'.")
        return

    path = context.user_data["current_path"]
    label_map = context.user_data.get("path_map", {})
    selected = label_map.get(text)

    if selected:
        next_path = os.path.join(path, selected)
        if os.path.isdir(next_path):
            context.user_data["current_path"] = next_path
            await list_directory(update, context, next_path)
        elif os.path.isfile(next_path):
            try:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=open(next_path, "rb"))

                user = update.effective_user
                username = user.username or "-"
                user_id = user.id
                file_name = os.path.basename(next_path)
                folder_path = os.path.dirname(next_path)
                timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

                file_exists = os.path.isfile("downloads.csv")
                with open("downloads.csv", mode="a", newline='', encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["User ID", "Username", "File Name", "Folder", "Timestamp"])
                    writer.writerow([str(user_id), username, file_name, folder_path, timestamp])
                upload_csv_to_drive("downloads.csv", FOLDER_ID)

            except Exception as e:
                print(f"❌ Failed to send or log file: {e}")
        else:
            await update.message.reply_text("❌ Invalid option.")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "current_path" not in context.user_data:
        await update.message.reply_text("📤 Please select a folder first.")
        return

    file = update.message.document or update.message.photo[-1]
    file_id = file.file_id
    file_name = file.file_name if hasattr(file, "file_name") else f"{random.randint(0, 99999)}.jpg"
    current_path = context.user_data["current_path"]
    file_path = os.path.join(current_path, file_name)

    await update.message.reply_text("⏫ Uploading file...")
    new_file = await context.bot.get_file(file_id)
    await new_file.download_to_drive(custom_path=file_path)
    await update.message.reply_text(f"✅ File saved to `{file_path}`.")

# === App Runner ===
if __name__ == '__main__':
    request = HTTPXRequest(connect_timeout=300.0, read_timeout=300.0)
    app = ApplicationBuilder().token(TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_buttons))

    print("Bot is running...")
    app.run_polling()
