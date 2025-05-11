import os
import re
import pytz
import random
import csv
import json
from datetime import datetime, timezone
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ApplicationBuilder,
    ContextTypes,
    ConversationHandler,
)
from telegram.request import HTTPXRequest

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()

# === Bot Config ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
BOT_PASSWORD = ["dagi", "Dagi", "droga"]
ETHIOPIA_TZ = pytz.timezone("Africa/Addis_Ababa")

main_folders = ["መሰረተ ትምሕርት", "ቤተ ዜማ", "ሥርዓተ ቅዳሴ"]
WEEKDAY_ORDER = ["የዘወትር ፀሎት", "ውዳሴ ማርያም", "አንቀፀ ብርሃን", "መልክዐ ማርያም", "መልክዐ ኢየሰስ", "መዝሙረ ዳዊት"]

# === Setup file system folders ===
os.makedirs("መሰረተ ትምሕርት", exist_ok=True)
for day in WEEKDAY_ORDER:
    os.makedirs(os.path.join("መሰረተ ትምሕርት", day), exist_ok=True)
os.makedirs("ቤተ ዜማ", exist_ok=True)
os.makedirs("ሥርዓተ ቅዳሴ", exist_ok=True)

# === Google Sheets Setup ===
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

def get_worksheet(sheet_name):
    try:
        GOOGLE_KEY_JSON = os.getenv("GOOGLE_KEY_JSON")

        if not GOOGLE_KEY_JSON:
            print("❌ GOOGLE_KEY_JSON environment variable is missing or empty.")
            return None

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GOOGLE_KEY_JSON)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        return client.open("Telegram Users").worksheet(sheet_name)

    except Exception as e:
        print(f"❌ Google Sheets Error: {e}")
        return None


# def log_registration(user, phone_number):
#     try:
#         worksheet = get_worksheet("Registrations")
#         if worksheet is None:
#             print("❌ Google Sheets Logging Error: Worksheet not found")
#             return
#
#         user_id = user.id
#         full_name = f"{user.first_name} {user.last_name or ''}".strip()
#         username = user.username or "N/A"
#         now = datetime.now(pytz.timezone("Africa/Addis_Ababa"))
#         date = now.strftime("%Y-%m-%d")
#         time = now.strftime("%H:%M:%S")
#
#         worksheet.append_row([str(user_id), full_name, username, phone_number, date, time])
#         print("✅ Registration logged to Google Sheets.")
#     except Exception as e:
#         print(f"❌ Google Sheets Logging Error: {e}")

def log_registration_to_sheets(user, name, phone):
    try:
        sheet = get_worksheet("Registrations")
        if sheet is None:
            print("❌ Google Sheets Logging Error: Worksheet not found")
            return

        username = user.username or "N/A"
        now = datetime.now(pytz.timezone("Africa/Addis_Ababa"))
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")

        sheet.append_row([str(user.id), name, phone, username, date, time])
        print("✅ Registration logged to Google Sheets.")
    except Exception as e:
        print(f"❌ Google Sheets Logging Error: {e}")

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler
from datetime import datetime
import pytz

REGISTER_NAME, REGISTER_PHONE = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_user_registered(user_id):
        await update.message.reply_text("🔒 Please enter the password to access the bot:")
        context.user_data["auth_step"] = "awaiting_password"
        return
    await update.message.reply_text("📝 Please enter your full name to register:")
    return REGISTER_NAME

async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["reg_name"] = update.message.text
    keyboard = [[KeyboardButton("📱 Share Phone Number", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("📞 Please share your phone number:", reply_markup=reply_markup)
    return REGISTER_PHONE

async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    phone_number = contact.phone_number if contact else update.message.text
    user = update.effective_user
    log_registration_to_sheets(user, context.user_data["reg_name"], phone_number)
    await update.message.reply_text("✅ Registration complete. Please enter the password to access the bot:", reply_markup=ReplyKeyboardRemove())
    context.user_data["auth_step"] = "awaiting_password"
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Registration cancelled.")
    return ConversationHandler.END

def is_user_registered(user_id):
    try:
        sheet = get_worksheet("Registrations")
        if sheet is None:
            return False
        users = sheet.col_values(1)  # Get all user IDs from column 1
        return str(user_id) in users  # Check if the user ID is in the list
    except Exception as e:
        print(f"❌ Error checking registration: {e}")
        return False

# === Helpers ===
def natural_key(text):
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', text)]

def pad_text(text, width):
    return text + ("\u2003" * (width - len(text)))

# === Folder Navigation and File Handlers ===
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name
    username = user.username or "-"
    user_id = user.id
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    try:
        file_exists = os.path.isfile("users.csv")
        with open("users.csv", "a", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["User ID", "Name", "Username", "Timestamp"])
            writer.writerow([user_id, name, username, timestamp])
    except Exception as e:
        print(f"❌ Failed to log to CSV: {e}")

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
        context.user_data.clear()
        label_map = {}
        keyboard = []
        for folder in main_folders:
            label_map[folder] = folder
            keyboard.append([folder])
        context.user_data["path_map"] = label_map
        context.user_data["current_path"] = None
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("📂 Please select a folder to begin:", reply_markup=reply_markup)
        return

    if text == "Back":
        current = context.user_data.get("current_path")
        if current:
            parent = os.path.dirname(current)
            if current in main_folders or parent in ["", ".", None]:
                context.user_data.clear()
                label_map = {}
                keyboard = []
                for folder in main_folders:
                    label_map[folder] = folder
                    keyboard.append([folder])
                context.user_data["path_map"] = label_map
                context.user_data["current_path"] = None
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text("📂 Back to main menu. Please select a folder:", reply_markup=reply_markup)
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
                file_name = os.path.basename(next_path)
                folder_path = os.path.dirname(next_path)
                timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                file_exists = os.path.isfile("downloads.csv")
                with open("downloads.csv", "a", newline='', encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["User ID", "Username", "File Name", "Folder", "Timestamp"])
                    writer.writerow([str(user.id), username, file_name, folder_path, timestamp])
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

    # Download the file
    await update.message.reply_text("⏫ Uploading file...")
    new_file = await context.bot.get_file(file_id)
    await new_file.download_to_drive(custom_path=file_path)
    await update.message.reply_text(f"✅ File saved to `{file_path}`.")

    # Logging the download
    user = update.effective_user
    username = user.username or "-"
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    folder_path = os.path.dirname(file_path)

    print(f"Logging file download: {user.id}, {username}, {file_name}, {folder_path}, {timestamp}")

    try:
        # Log the download to "Download Log" sheet
        sheet = get_worksheet("Download Log")
        if sheet is not None:
            # Attempting to log the download to the sheet
            sheet.append_row([str(user.id), username, file_name, folder_path, timestamp])
            print(f"✅ Download logged: {file_name} by {username}")
        else:
            print("❌ Failed to log download - worksheet not found.")
    except Exception as e:
        print(f"❌ Google Sheets Logging Error: {e}")


# === App Runner ===
if __name__ == '__main__':
    request = HTTPXRequest(connect_timeout=300.0, read_timeout=300.0)
    app = ApplicationBuilder().token(TOKEN).request(request).build()

    registration_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REGISTER_NAME: [MessageHandler(filters.TEXT & (~filters.COMMAND), register_name)],
            REGISTER_PHONE: [MessageHandler(filters.CONTACT, register_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(registration_handler)
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_buttons))

    print("Bot is running...")
    app.run_polling()
