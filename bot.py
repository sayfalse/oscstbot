import os
import sys
import re
import time
import shutil
import tempfile
import subprocess
import json
import logging
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MINT_Bot")

# Load configuration
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("Error: TELEGRAM_BOT_TOKEN environment variable is not set.")
    sys.exit(1)

# Configure allowed users whitelist
ALLOWED_USERS = set()
allowed_users_env = os.environ.get("ALLOWED_USERS")
if allowed_users_env:
    for token in allowed_users_env.split(","):
        token = token.strip()
        if token.isdigit():
            ALLOWED_USERS.add(int(token))
    logger.info(f"Access Control Enabled. Whitelisted User IDs: {ALLOWED_USERS}")
else:
    logger.warning("Access Control Disabled. The bot is PUBLIC. (Specify ALLOWED_USERS to secure it)")

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# User states for interactive wizard (chat_id -> state_string)
USER_STATES = {}

# Helper: Check user authorization
def is_authorized(user_id):
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS

# Decorator to enforce access control
def check_auth(func):
    def wrapper(message, *args, **kwargs):
        if not is_authorized(message.from_user.id):
            bot.reply_to(message, "⚠️ *Access Denied.*\nYou are not authorized to use this MINT Bot instance.", parse_mode="Markdown")
            logger.warning(f"Unauthorized access attempt by User ID: {message.from_user.id} ({message.from_user.username})")
            return
        return func(message, *args, **kwargs)
    return wrapper

# Utility: Strip ANSI escape sequences (color codes) from output
def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# Input Whitelist Regexes
def is_safe_username(username):
    if not username:
        return False
    return bool(re.match(r'^[a-zA-Z0-9._\-@]+$', username))

def is_safe_email(email):
    if not email:
        return False
    return bool(re.match(r'^[a-zA-Z0-9._\-@+]+$', email))

def is_safe_url(url):
    if not url:
        return False
    if any(char in url for char in [';', '|', '$', '`', '<', '>', '"', "'", '\\', ' ']):
        return False
    return bool(re.match(r'^[a-zA-Z0-9.:/?&=\-_+@%,]+$', url))

# Load MINT path configuration
user_home = os.path.expanduser("~")
config_path = os.path.join(user_home, ".mint", "config.json")
MINT_CONFIG = {}

if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            MINT_CONFIG = json.load(f)
        logger.info("MINT Path Configuration loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load MINT config.json: {e}")
else:
    logger.warning("config.json not found. OSINT command execution will use path fallbacks.")

# Resolve OSINT tool paths
def get_tool_path(tool_key):
    path = MINT_CONFIG.get(f"{tool_key}_path")
    if path and os.path.exists(path):
        return path
    # Container default fallbacks
    container_path = f"/app/mint/MINT_Tools/{tool_key}"
    if os.path.exists(container_path):
        return container_path
    return None

# Send Main Menu Markup
def send_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 Sherlock Scan", callback_data="menu_sherlock"),
        InlineKeyboardButton("🔮 Holehe Check", callback_data="menu_holehe"),
        InlineKeyboardButton("📸 Toutatis Instagram", callback_data="menu_toutatis"),
        InlineKeyboardButton("📥 Media Downloader", callback_data="menu_download"),
        InlineKeyboardButton("📊 Bot Status", callback_data="menu_status")
    )
    bot.send_message(
        chat_id,
        "🌿 *MINT OSINT & Media Command Center Bot* 🌿\n\n"
        "Select a tool from the interactive menu below to begin:",
        parse_mode="Markdown",
        reply_markup=markup
    )

# Core Logic: Sherlock
def run_sherlock_logic(message, username):
    if not is_safe_username(username):
        bot.reply_to(message, "❌ *Error:* Invalid or unsafe username format. Alphanumerics, periods, underscores, hyphens, and @ only.", parse_mode="Markdown")
        return

    sherlock_dir = get_tool_path("sherlock")
    if not sherlock_dir:
        bot.reply_to(message, "❌ *Error:* Sherlock path is not configured on this host/container.", parse_mode="Markdown")
        return

    sherlock_py = os.path.join(sherlock_dir, "sherlock", "sherlock.py")
    if not os.path.exists(sherlock_py):
        sherlock_py = os.path.join(sherlock_dir, "sherlock.py")

    status_msg = bot.reply_to(message, f"🔍 *Sherlock:* Querying 300+ platforms for `{username}`...\n_This may take up to a minute._", parse_mode="Markdown")

    try:
        cmd = [sys.executable, sherlock_py, "--timeout", "10", username]
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            cwd=sherlock_dir
        )
        
        output = strip_ansi(process.stdout + "\n" + process.stderr).strip()
        local_report = os.path.join(os.getcwd(), f"{username}.txt")
        if not os.path.exists(local_report):
            local_report = os.path.join(sherlock_dir, f"{username}.txt")

        if not output:
            bot.edit_message_text("❌ *Error:* No output received from Sherlock.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
        elif len(output) > 4000:
            bot.edit_message_text("📄 *Scan complete.* Result exceeds message limit, sending as file...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write(output)
                temp_name = f.name
            with open(temp_name, "rb") as report:
                bot.send_document(message.chat.id, report, visible_file_name=f"sherlock_{username}.txt", reply_to_message_id=message.message_id)
            os.remove(temp_name)
        else:
            formatted_output = f"📋 *Sherlock Results for {username}:*\n\n```\n{output}\n```"
            bot.edit_message_text(formatted_output, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            
        if os.path.exists(local_report):
            try: os.remove(local_report)
            except: pass
                
    except subprocess.TimeoutExpired:
        bot.edit_message_text("⏱️ *Error:* Sherlock process timed out (exceeded 120s).", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ *Error executing Sherlock:* `{str(e)}`", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")

# Core Logic: Holehe
def run_holehe_logic(message, email):
    if not is_safe_email(email):
        bot.reply_to(message, "❌ *Error:* Invalid or unsafe email address format.", parse_mode="Markdown")
        return

    holehe_dir = get_tool_path("holehe")
    if not holehe_dir:
        bot.reply_to(message, "❌ *Error:* Holehe path is not configured on this host/container.", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, f"🔮 *Holehe:* Querying registration endpoints for `{email}`...\n_This may take up to a minute._", parse_mode="Markdown")

    try:
        cmd = [sys.executable, "-m", "holehe.cli", email]
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            cwd=holehe_dir
        )
        
        output = strip_ansi(process.stdout + "\n" + process.stderr).strip()
        
        lines = output.split("\n")
        clean_lines = []
        for line in lines:
            if "[+]" in line or "[-]" in line or "[!]" in line:
                clean_lines.append(line)
        
        clean_output = "\n".join(clean_lines).strip()
        if not clean_output:
            clean_output = output

        if not clean_output:
            bot.edit_message_text("❌ *Error:* No output received from Holehe.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
        elif len(clean_output) > 4000:
            bot.edit_message_text("📄 *Scan complete.* Result exceeds message limit, sending as file...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write(output)
                temp_name = f.name
            with open(temp_name, "rb") as report:
                bot.send_document(message.chat.id, report, visible_file_name=f"holehe_{email}.txt", reply_to_message_id=message.message_id)
            os.remove(temp_name)
        else:
            formatted_output = f"📋 *Holehe Results for {email}:*\n\n```\n{clean_output}\n```"
            bot.edit_message_text(formatted_output, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            
    except subprocess.TimeoutExpired:
        bot.edit_message_text("⏱️ *Error:* Holehe process timed out (exceeded 120s).", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ *Error executing Holehe:* `{str(e)}`", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")

# Core Logic: Toutatis
def run_toutatis_logic(message, username):
    if not is_safe_username(username):
        bot.reply_to(message, "❌ *Error:* Invalid or unsafe username format.", parse_mode="Markdown")
        return

    toutatis_dir = get_tool_path("toutatis")
    if not toutatis_dir:
        bot.reply_to(message, "❌ *Error:* Toutatis path is not configured on this host/container.", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, f"📸 *Toutatis:* Extracting Instagram profile metadata for `{username}`...", parse_mode="Markdown")

    try:
        cmd = [sys.executable, "-m", "toutatis", "-u", username]
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=90,
            cwd=toutatis_dir
        )
        
        output = strip_ansi(process.stdout + "\n" + process.stderr).strip()

        if not output:
            bot.edit_message_text("❌ *Error:* No output received from Toutatis.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
        elif len(output) > 4000:
            bot.edit_message_text("📄 *Scan complete.* Result exceeds message limit, sending as file...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write(output)
                temp_name = f.name
            with open(temp_name, "rb") as report:
                bot.send_document(message.chat.id, report, visible_file_name=f"toutatis_{username}.txt", reply_to_message_id=message.message_id)
            os.remove(temp_name)
        else:
            formatted_output = f"📋 *Toutatis Instagram Metadata for {username}:*\n\n```\n{output}\n```"
            bot.edit_message_text(formatted_output, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            
    except subprocess.TimeoutExpired:
        bot.edit_message_text("⏱️ *Error:* Toutatis process timed out (exceeded 90s).", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ *Error executing Toutatis:* `{str(e)}`", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")

# Core Logic: Downloader
def run_download_logic(message, url):
    if not is_safe_url(url):
        bot.reply_to(message, "❌ *Error:* Invalid or unsafe URL format.", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, "📥 *Media Downloader:* Initializing download connection...\n_Downloading and packaging files, please wait..._", parse_mode="Markdown")
    temp_dir = tempfile.mkdtemp(prefix="mint_bot_")
    
    try:
        is_gallery_dl_candidate = any(domain in url.lower() for domain in ["instagram.com", "tiktok.com", "facebook.com", "x.com", "twitter.com"])
        download_success = False
        
        if is_gallery_dl_candidate:
            logger.info(f"Attempting download via gallery-dl for URL: {url}")
            cmd_gdl = ["gallery-dl", "-D", temp_dir, url]
            process_gdl = subprocess.run(cmd_gdl, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            if process_gdl.returncode == 0:
                download_success = True
                logger.info("gallery-dl downloaded media successfully.")
        
        if not download_success:
            logger.info(f"Attempting download via yt-dlp for URL: {url}")
            cmd_ytd = ["yt-dlp", "-o", os.path.join(temp_dir, "%(title)s.%(ext)s"), "--no-playlist", url]
            process_ytd = subprocess.run(cmd_ytd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            if process_ytd.returncode == 0:
                download_success = True
                logger.info("yt-dlp downloaded media successfully.")

        downloaded_files = []
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.getsize(file_path) > 0 and file != "archive.txt":
                    downloaded_files.append(file_path)

        if not download_success or not downloaded_files:
            bot.edit_message_text("❌ *Error:* Failed to download media. The link may be private, expired, or unsupported.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            return

        bot.edit_message_text(f"📤 *Download Complete.* Uploading {len(downloaded_files)} files to Telegram...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
        
        for idx, file_path in enumerate(downloaded_files):
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:
                bot.send_message(message.chat.id, f"⚠️ File `{os.path.basename(file_path)}` exceeds Telegram's 50MB limit ({file_size // (1024*1024)}MB) and cannot be sent.")
                continue
                
            ext = os.path.splitext(file_path)[1].lower()
            logger.info(f"Uploading: {file_path} (Size: {file_size} bytes)")
            
            with open(file_path, "rb") as f:
                if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                    try: bot.send_photo(message.chat.id, f, reply_to_message_id=message.message_id)
                    except:
                        f.seek(0)
                        bot.send_document(message.chat.id, f, reply_to_message_id=message.message_id)
                elif ext in [".mp4", ".mov", ".webm", ".m4v"]:
                    try: bot.send_video(message.chat.id, f, reply_to_message_id=message.message_id)
                    except:
                        f.seek(0)
                        bot.send_document(message.chat.id, f, reply_to_message_id=message.message_id)
                else:
                    bot.send_document(message.chat.id, f, reply_to_message_id=message.message_id)
            time.sleep(0.5)
            
        bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)

    except subprocess.TimeoutExpired:
        bot.edit_message_text("⏱️ *Error:* Download process timed out (exceeded 180s).", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error during media download: {e}")
        bot.edit_message_text(f"❌ *Error executing download:* `{str(e)}`", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
    finally:
        try:
            shutil.rmtree(temp_dir)
            logger.info("Cleaned up temporary download directory.")
        except Exception as e:
            logger.error(f"Failed to delete temp dir: {e}")

# Helper: Show Status Directly
def send_status_direct(chat_id):
    total, used, free = shutil.disk_usage("/")
    status_text = (
        "📊 *MINT Bot Status*\n\n"
        f"• *Platform:* `{sys.platform.upper()}`\n"
        f"• *Python Version:* `{sys.version.split()[0]}`\n"
        f"• *Disk Usage:* `{used // (2**30)}GB` / `{total // (2**30)}GB` used ({free // (2**30)}GB free)\n"
        f"• *Access Control:* `{'ENABLED' if ALLOWED_USERS else 'DISABLED (PUBLIC)'}`\n"
        f"• *Sherlock Path:* `{get_tool_path('sherlock') is not None}`\n"
        f"• *Holehe Path:* `{get_tool_path('holehe') is not None}`\n"
        f"• *Toutatis Path:* `{get_tool_path('toutatis') is not None}`\n"
    )
    bot.send_message(chat_id, status_text, parse_mode="Markdown")

# Callback Query Handler for Inline Keyboard Buttons
@bot.callback_query_handler(func=lambda call: True)
def handle_menu_click(call):
    if not is_authorized(call.from_user.id):
        bot.answer_callback_query(call.id, "⚠️ Access Denied", show_alert=True)
        return
        
    chat_id = call.message.chat.id
    action = call.data
    
    if action == "menu_sherlock":
        USER_STATES[chat_id] = "awaiting_sherlock"
        bot.send_message(chat_id, "🔍 *Sherlock:* Please enter the target username to scan:")
    elif action == "menu_holehe":
        USER_STATES[chat_id] = "awaiting_holehe"
        bot.send_message(chat_id, "🔮 *Holehe:* Please enter the target email address to check:")
    elif action == "menu_toutatis":
        USER_STATES[chat_id] = "awaiting_toutatis"
        bot.send_message(chat_id, "📸 *Toutatis:* Please enter the target Instagram username to extract:")
    elif action == "menu_download":
        USER_STATES[chat_id] = "awaiting_download"
        bot.send_message(chat_id, "📥 *Downloader:* Please enter the social media post URL to download:")
    elif action == "menu_status":
        send_status_direct(chat_id)
        
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

# Command Handlers (Fallback/Direct triggers)
@bot.message_handler(commands=['start', 'help'])
@check_auth
def send_welcome(message):
    send_main_menu(message.chat.id)

@bot.message_handler(commands=['status'])
@check_auth
def run_status_command(message):
    send_status_direct(message.chat.id)

@bot.message_handler(commands=['sherlock'])
@check_auth
def run_sherlock_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ *Usage:* `/sherlock <username>`", parse_mode="Markdown")
        return
    run_sherlock_logic(message, args[1].strip())

@bot.message_handler(commands=['holehe'])
@check_auth
def run_holehe_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ *Usage:* `/holehe <email>`", parse_mode="Markdown")
        return
    run_holehe_logic(message, args[1].strip())

@bot.message_handler(commands=['toutatis'])
@check_auth
def run_toutatis_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ *Usage:* `/toutatis <username>`", parse_mode="Markdown")
        return
    run_toutatis_logic(message, args[1].strip())

@bot.message_handler(commands=['download'])
@check_auth
def run_download_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ *Usage:* `/download <url>`", parse_mode="Markdown")
        return
    run_download_logic(message, args[1].strip())

# Message Handler: Handles text input and interactive wizard states
@bot.message_handler(func=lambda message: True)
@check_auth
def handle_user_message(message):
    chat_id = message.chat.id
    state = USER_STATES.get(chat_id)
    
    if state == "awaiting_sherlock":
        USER_STATES.pop(chat_id, None)
        run_sherlock_logic(message, message.text.strip())
    elif state == "awaiting_holehe":
        USER_STATES.pop(chat_id, None)
        run_holehe_logic(message, message.text.strip())
    elif state == "awaiting_toutatis":
        USER_STATES.pop(chat_id, None)
        run_toutatis_logic(message, message.text.strip())
    elif state == "awaiting_download":
        USER_STATES.pop(chat_id, None)
        run_download_logic(message, message.text.strip())
    else:
        # Standard behavior: show interactive menu
        send_main_menu(chat_id)

# Start long polling
if __name__ == "__main__":
    logger.info("Starting MINT Telegram Bot polling service...")
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except KeyboardInterrupt:
        logger.info("Stopping bot polling...")
        sys.exit(0)
