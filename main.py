# import os
# import re
# import pytz
# import random
# from datetime import datetime

# from telegram import Update, ReplyKeyboardMarkup
# from telegram.ext import CommandHandler, MessageHandler, ApplicationBuilder, ContextTypes, filters
# from telegram.request import HTTPXRequest

# import gspread
# from google.oauth2.service_account import Credentials

# === Config ===
TOKEN = "7945188969:AAGqv31lZK0YaRjVTDqBXgTiCJyt1hyICnc"
ETHIOPIA_TZ = pytz.timezone("Africa/Addis_Ababa")
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

# === Google Sheets ===
def get_worksheet(name):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("google_key.json", scopes=scope)
        client = gspread.authorize(creds)
        print(f"✅ Connected to Google Sheet: {name}")
        return client.open("Telegram Users").worksheet(name)
    except Exception as e:
        print(f"❌ Google Sheets Error: {e}")
        return None

# === Helpers ===
def natural_key(text):
    return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', text)]

def pad_text(text, width):
    return text + ("\u2003" * (width - len(text)))

# === Handlers ====-
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name
    username = user.username or "-"
    user_id = user.id
    timestamp = datetime.now(ETHIOPIA_TZ).strftime('%Y-%m-%d %H:%M:%S')

    sheet = get_worksheet("Sheet1")
    if sheet:
        try:
            sheet.append_row([user_id, name, username, timestamp])
            print("✅ Row added for user.")
        except Exception as e:
            print(f"❌ Failed to write user to sheet: {e}")

    keyboard = [[folder] for folder in main_folders]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"📂 hey {username} welcome to abenet Education:", reply_markup=reply_markup)

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
    context.user_data["current_path"] = path

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"📂 Select from `{path}`:", reply_markup=reply_markup)

async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Main Menu":
        context.user_data.clear()
        keyboard = [[folder] for folder in main_folders]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("📂 Please select a folder to begin:", reply_markup=reply_markup)
        return

    if text == "Back":
        current = context.user_data.get("current_path")
        if current:
            parent = os.path.dirname(current)
            if parent in ["", ".", None]:
                context.user_data.clear()
                keyboard = [[folder] for folder in main_folders]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text("📂 Please select a folder to begin:", reply_markup=reply_markup)
            else:
                context.user_data["current_path"] = parent
                await list_directory(update, context, parent)
        else:
            await update.message.reply_text("📂 You're already at the top.")
        return

    if "current_path" not in context.user_data:
        if text in main_folders:
            context.user_data["current_path"] = text
            await list_directory(update, context, text)
        else:
            keyboard = [[folder] for folder in main_folders]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("📂 Please select a folder to begin:", reply_markup=reply_markup)
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

                # Log download to Google Sheet
                sheet = get_worksheet("Download Log")
                if sheet:
                    user = update.effective_user
                    username = user.username or "-"
                    user_id = user.id
                    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

                    file_name = os.path.basename(next_path)
                    folder_path = os.path.dirname(next_path)
                    sheet.append_row([str(user_id), username, file_name, folder_path, timestamp])
                    print("✅ Download logged.")
            except Exception as e:
                print(f"❌ Failed to send or log file: {e}")
        else:
            await update.message.reply_text("❌ Not a valid path.")
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
