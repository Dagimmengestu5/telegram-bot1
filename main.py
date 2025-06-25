import os
import re
import pytz
import random
import csv
import json
import threading
import time
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
TOKEN = "7945188969:AAFIhUOfG8tv6l1NUIid5aBY"
BOT_PASSWORD = ["dagi", "Dagi", "mekane heywet", "mekaneheywet", "Mekane heywet", "Mekane Heywet", "Mekane hiwot", "Mekanehiwot", "mekane hiwot", "MEKANE HIWOT"
                "MEKANE HEYWET", "መካነ ሕይወት", "መካነ ህይወት", "መካነህይወት", "መካነሕይወት", "መካነ ኅይወት", "2017"]
ETHIOPIA_TZ = pytz.timezone("Africa/Addis_Ababa")

main_folders = ["መሰረተ ትምሕርት", "ቤተ ዜማ", "ሥርዓተ ቅዳሴ"]
WEEKDAY_ORDER = ["የዘወትር ፀሎት", "ውዳሴ ማርያም", "አንቀፀ ብርሃን", "መልክዐ ማርያም", "መልክዐ ኢየሰስ", "መዝሙረ ዳዊት"]

# === Setup file system folders ====
os.makedirs("መሰረተ ትምሕርት", exist_ok=True)
for day in WEEKDAY_ORDER:
    os.makedirs(os.path.join("መሰረተ ትምሕርት", day), exist_ok=True)
os.makedirs("ቤተ ዜማ", exist_ok=True)
os.makedirs("ሥርዓተ ቅዳሴ", exist_ok=True)

# === Google Sheets Setup ===
def get_worksheet(sheet_name):
    json_path = "goggle json file"
    if not json_path:
        json_path = ""google json file"
    try:
        if not json_path:
            print("❌ GOOGLE_KEY_JSON environment variable is missing or empty.")
            return None

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(json_path)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Telegram Users").worksheet(sheet_name)
    except Exception as e:
        print(f"❌ Google Sheets Error: {e}")
        return None


def log_registration(user, phone_number):
    try:
        worksheet = get_worksheet("Registrations")
        if worksheet is None:
            print("❌ Google Sheets Logging Error: Worksheet not found")
            return

        user_id = user.id
        full_name = f"{user.first_name} {user.last_name or ''}".strip()
        username = user.username or "N/A"
        now = datetime.now(pytz.timezone("Africa/Addis_Ababa"))
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")

        worksheet.append_row([str(user_id), full_name, username, phone_number, date, time])
        print("✅ Registration logged to Google Sheets.")
    except Exception as e:
        print(f"❌ Google Sheets Logging Error: {e}")


def log_download_to_sheets(user, file_name, folder_path):
    try:
        sheet = get_worksheet("Downloads")
        if sheet is None:
            print("❌ Google Sheets Logging Error: Worksheet not found")
            return

        username = user.username or "N/A"
        now = datetime.now(pytz.timezone("Africa/Addis_Ababa"))
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")

        sheet.append_row([str(user.id), username, file_name, folder_path, date, time])
        print("✅ Download logged to Google Sheets.")
    except Exception as e:
        print(f"❌ Google Sheets Logging Error: {e}")


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


def is_user_registered(user_id):
    try:
        sheet = get_worksheet("Registrations")
        if sheet is None:
            print("❌ Google Sheets Logging Error: Worksheet not found")
            return False
        users = sheet.col_values(1)
        return str(user_id) in users
    except Exception as e:
        print(f"❌ Error checking registration: {e}")
        return False


# === Registration States ===
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
    await update.message.reply_text("✅ Registration complete. Please enter the password to access the bot:",
                                    reply_markup=ReplyKeyboardRemove())
    context.user_data["auth_step"] = "awaiting_password"
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Registration cancelled.")
    return ConversationHandler.END


# === Helpers ====
def natural_key(text):
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', text)]


def pad_text(text, width):
    return text + ("\u2003" * (width - len(text)))

def clean_label(label):
    """Removes emojis and padding from a label for comparison."""
    # Remove emoji characters
    cleaned = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', '', label)
    # Remove the padding character
    cleaned = cleaned.replace("\u2003", "").strip()
    return cleaned

# === Folder Navigation and File Handlers ====
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
        label_map[folder] = folder # Store actual folder name
        keyboard.append([folder])

    context.user_data["path_map"] = {clean_label(label).lower(): original_value for label, original_value in label_map.items()}
    context.user_data["display_path_map"] = label_map # Keep original for display
    context.user_data["current_path"] = None
    context.user_data["authenticated"] = True

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"✅ Access granted.\n\n📂 Welcome {name}! Please choose a folder:",
                                    reply_markup=reply_markup)


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

    max_len = max(len(item) for item in items) if items else 0
    keyboard = [["Main Menu", "Back"]]
    label_map = {} # This will store clean_label.lower() -> actual_item_name
    display_label_map = {} # This will store full_display_label -> actual_item_name

    for item in items:
        emoji = "📁" if os.path.isdir(os.path.join(path, item)) else "📄"
        padded = pad_text(item, max_len)
        label = f"{emoji} {padded}"
        keyboard.append([label])
        label_map[clean_label(label).lower()] = item
        display_label_map[label] = item

    context.user_data["path_map"] = label_map
    context.user_data["display_path_map"] = display_label_map
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"📂 Select from {path}:", reply_markup=reply_markup)


async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    print(f"Received text: '{text}'")

    if context.user_data.get("auth_step") == "awaiting_password":
        if text in BOT_PASSWORD:
            context.user_data["auth_step"] = None
            await show_main_menu(update, context)
        else:
            await update.message.reply_text("❌ Incorrect password. Try again.")
        return

    # Normalize user input for comparison
    normalized_text = clean_label(text).lower()

    if normalized_text == "main menu":
        context.user_data.clear()
        label_map = {}
        keyboard = []
        for folder in main_folders:
            label_map[folder] = folder
            keyboard.append([folder])
        context.user_data["path_map"] = {clean_label(label).lower(): original_value for label, original_value in label_map.items()}
        context.user_data["display_path_map"] = label_map
        context.user_data["current_path"] = None
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("📂 Please select a folder to begin:", reply_markup=reply_markup)
        return

    if normalized_text == "back":
        current = context.user_data.get("current_path")
        if current:
            parent = os.path.dirname(current)
            # Check if parent is an empty string (meaning we're at a top-level folder)
            if current in main_folders or not parent: # If parent is empty, current is a main folder
                context.user_data.clear()
                label_map = {}
                keyboard = []
                for folder in main_folders:
                    label_map[folder] = folder
                    keyboard.append([folder])
                context.user_data["path_map"] = {clean_label(label).lower(): original_value for label, original_value in label_map.items()}
                context.user_data["display_path_map"] = label_map
                context.user_data["current_path"] = None
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text("📂 Back to main menu. Please select a folder:",
                                                reply_markup=reply_markup)
            else:
                context.user_data["current_path"] = parent
                await list_directory(update, context, parent)
        else:
            await update.message.reply_text("📂 You're already at the top.")
        return

    # Handle folder/file selection
    path_map = context.user_data.get("path_map", {})
    selected_item_name = path_map.get(normalized_text)

    if not context.user_data.get("current_path"):
        # If no current_path, user is selecting a main folder
        if selected_item_name and selected_item_name in main_folders:
            path = selected_item_name
            context.user_data["current_path"] = path
            await list_directory(update, context, path)
        else:
            await update.message.reply_text("❌ Please select a valid main folder from the provided options or type '/start'.")
        return

    # If current_path exists, user is navigating within a subfolder or selecting a file
    current_path = context.user_data["current_path"]
    if selected_item_name:
        next_path = os.path.join(current_path, selected_item_name)
        if os.path.isdir(next_path):
            context.user_data["current_path"] = next_path
            await list_directory(update, context, next_path)
        elif os.path.isfile(next_path):
            try:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=open(next_path, "rb"))
                user = update.effective_user
                file_name = os.path.basename(next_path)
                folder_path = os.path.dirname(next_path)
                log_download_to_sheets(user, file_name, folder_path)
                # Also log to local CSV for redundancy if Google Sheets fails
                username = user.username or "-"
                timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                file_exists = os.path.isfile("downloads.csv")
                with open("downloads.csv", "a", newline='', encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["User ID", "Username", "File Name", "Folder", "Timestamp"])
                    writer.writerow([str(user.id), username, file_name, folder_path, timestamp])
            except Exception as e:
                print(f"❌ Failed to send or log file: {e}")
                await update.message.reply_text(f"❌ Error sending file: {e}")
        else:
            await update.message.reply_text("❌ The selected item is neither a folder nor a file.")
    else:
        # If `selected_item_name` is None, it means the normalized_text didn't match any key in path_map.
        # This is where the "Invalid option" usually comes from.
        await update.message.reply_text("❌ Invalid option. Please select an option from the keyboard or type it exactly as shown (case-insensitive).")


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ensure user is authenticated before allowing file uploads
    if not context.user_data.get("authenticated"):
        await update.message.reply_text("🔒 You need to be authenticated to upload files. Please use /start.")
        return

    if "current_path" not in context.user_data or context.user_data["current_path"] is None:
        await update.message.reply_text("📤 Please select a folder where you want to upload the file first.")
        return

    file = update.message.document or update.message.photo[-1]
    file_id = file.file_id
    file_name = file.file_name if hasattr(file, "file_name") else f"{random.randint(0, 99999)}.jpg"
    current_path = context.user_data["current_path"]
    file_path = os.path.join(current_path, file_name)

    try:
        await update.message.reply_text("⏫ Uploading file...")
        new_file = await context.bot.get_file(file_id)
        await new_file.download_to_drive(custom_path=file_path)
        await update.message.reply_text(f"✅ File saved to {file_path}.")
        # Optionally log file uploads as well
        # log_upload_to_sheets(update.effective_user, file_name, current_path)
    except Exception as e:
        print(f"❌ Failed to save file: {e}")
        await update.message.reply_text(f"❌ Failed to upload file: {e}")


# === Timeout Mechanism ===
def shutdown_bot(application, timeout):
    """Shutdown the bot after specified timeout"""
    time.sleep(timeout)
    print(f"\n🛑 Timeout reached ({timeout} seconds). Stopping bot...")
    application.stop()
    print("✅ Bot stopped successfully")


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

    # Set timeout duration (in seconds - 8 hours = 28800 seconds)
    TIMEOUT_DURATION = 28800

    # Start timeout thread
    timeout_thread = threading.Thread(
        target=shutdown_bot,
        args=(app, TIMEOUT_DURATION),
        daemon=True
    )
    timeout_thread.start()

    print(f"⏱ Bot is running with {TIMEOUT_DURATION} second timeout...")
    app.run_polling()
    print("👋 Bot shutdown complete")
