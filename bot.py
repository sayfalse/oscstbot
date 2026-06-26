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

# Commands
@bot.message_handler(commands=['start', 'help'])
@check_auth
def send_welcome(message):
    help_text = (
        "🌿 *MINT OSINT & Media Command Center Bot* 🌿\n\n"
        "Welcome! You can run OSINT scans and media downloads directly from this chat.\n\n"
        "*Available Commands:*\n"
        "• `/sherlock <username>` ─ Scan 300+ platforms for a username\n"
        "• `/holehe <email>` ─ Check registration status of an email address\n"
        "• `/toutatis <username>` ─ Extract metadata from an Instagram username\n"
        "• `/download <url>` ─ Download photos/videos from Instagram, TikTok, Facebook, or X\n"
        "• `/status` ─ Check bot status and container health\n\n"
        "_Note: All inputs are sanitized. Access is restricted to whitelisted users._"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['status'])
@check_auth
def send_status(message):
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
    bot.reply_to(message, status_text, parse_mode="Markdown")

@bot.message_handler(commands=['sherlock'])
@check_auth
def run_sherlock_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ *Usage:* `/sherlock <username>`", parse_mode="Markdown")
        return

    username = args[1].strip()
    if not is_safe_username(username):
        bot.reply_to(message, "❌ *Error:* Invalid or unsafe username format. Alphanumerics, periods, underscores, hyphens, and @ only.", parse_mode="Markdown")
        return

    sherlock_dir = get_tool_path("sherlock")
    if not sherlock_dir:
        bot.reply_to(message, "❌ *Error:* Sherlock path is not configured on this host/container.", parse_mode="Markdown")
        return

    # Sherlock entrypoint detection
    sherlock_py = os.path.join(sherlock_dir, "sherlock", "sherlock.py")
    if not os.path.exists(sherlock_py):
        sherlock_py = os.path.join(sherlock_dir, "sherlock.py")

    status_msg = bot.reply_to(message, f"🔍 *Sherlock:* Querying 300+ platforms for `{username}`...\n_This may take up to a minute._", parse_mode="Markdown")

    try:
        # Run Sherlock safely (shell=False)
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
        
        # Clean up output file generated by sherlock if any
        local_report = os.path.join(os.getcwd(), f"{username}.txt")
        if not os.path.exists(local_report):
            local_report = os.path.join(sherlock_dir, f"{username}.txt")

        # Send output
        if not output:
            bot.edit_message_text("❌ *Error:* No output received from Sherlock.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
        elif len(output) > 4000:
            bot.edit_message_text("📄 *Scan complete.* Result exceeds message limit, sending as file...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            # Write to temp file and upload
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write(output)
                temp_name = f.name
            with open(temp_name, "rb") as report:
                bot.send_document(message.chat.id, report, visible_file_name=f"sherlock_{username}.txt", reply_to_message_id=message.message_id)
            os.remove(temp_name)
        else:
            formatted_output = f"📋 *Sherlock Results for {username}:*\n\n```\n{output}\n```"
            bot.edit_message_text(formatted_output, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            
        # Clean up sherlock report file to save space
        if os.path.exists(local_report):
            try:
                os.remove(local_report)
            except:
                pass
                
    except subprocess.TimeoutExpired:
        bot.edit_message_text("⏱️ *Error:* Sherlock process timed out (exceeded 120s).", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ *Error executing Sherlock:* `{str(e)}`", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")

@bot.message_handler(commands=['holehe'])
@check_auth
def run_holehe_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ *Usage:* `/holehe <email>`", parse_mode="Markdown")
        return

    email = args[1].strip()
    if not is_safe_email(email):
        bot.reply_to(message, "❌ *Error:* Invalid or unsafe email address format.", parse_mode="Markdown")
        return

    holehe_dir = get_tool_path("holehe")
    if not holehe_dir:
        bot.reply_to(message, "❌ *Error:* Holehe path is not configured on this host/container.", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, f"🔮 *Holehe:* Querying registration endpoints for `{email}`...\n_This may take up to a minute._", parse_mode="Markdown")

    try:
        # Run Holehe safely (shell=False)
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
        
        # Strip long introductory headers / non-essential information
        lines = output.split("\n")
        clean_lines = []
        for line in lines:
            if "[+]" in line or "[-]" in line or "[!]" in line:
                clean_lines.append(line)
        
        clean_output = "\n".join(clean_lines).strip()
        if not clean_output:
            clean_output = output # Fallback to raw if filtering empty

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

@bot.message_handler(commands=['toutatis'])
@check_auth
def run_toutatis_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ *Usage:* `/toutatis <username>`", parse_mode="Markdown")
        return

    username = args[1].strip()
    if not is_safe_username(username):
        bot.reply_to(message, "❌ *Error:* Invalid or unsafe username format.", parse_mode="Markdown")
        return

    toutatis_dir = get_tool_path("toutatis")
    if not toutatis_dir:
        bot.reply_to(message, "❌ *Error:* Toutatis path is not configured on this host/container.", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, f"📸 *Toutatis:* Extracting Instagram profile metadata for `{username}`...", parse_mode="Markdown")

    try:
        # Run Toutatis safely (shell=False)
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

@bot.message_handler(commands=['download'])
@check_auth
def run_download_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ *Usage:* `/download <url>`", parse_mode="Markdown")
        return

    url = args[1].strip()
    if not is_safe_url(url):
        bot.reply_to(message, "❌ *Error:* Invalid or unsafe URL format.", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, "📥 *Media Downloader:* Initializing download connection...\n_Downloading and packaging files, please wait..._", parse_mode="Markdown")

    # Create temporary directory for downloads
    temp_dir = tempfile.mkdtemp(prefix="mint_bot_")
    
    try:
        # Determine platform to optimize tool selection
        is_gallery_dl_candidate = any(domain in url.lower() for domain in ["instagram.com", "tiktok.com", "facebook.com", "x.com", "twitter.com"])
        
        download_success = False
        
        # 1. Attempt Gallery-DL first if it's a social profile/post
        if is_gallery_dl_candidate:
            logger.info(f"Attempting download via gallery-dl for URL: {url}")
            cmd_gdl = ["gallery-dl", "-D", temp_dir, url]
            process_gdl = subprocess.run(
                cmd_gdl,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180
            )
            if process_gdl.returncode == 0:
                download_success = True
                logger.info("gallery-dl downloaded media successfully.")
        
        # 2. Fallback or primary run with yt-dlp
        if not download_success:
            logger.info(f"Attempting download via yt-dlp for URL: {url}")
            # Ensure output template puts everything flat in temp_dir
            cmd_ytd = ["yt-dlp", "-o", os.path.join(temp_dir, "%(title)s.%(ext)s"), "--no-playlist", url]
            process_ytd = subprocess.run(
                cmd_ytd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180
            )
            if process_ytd.returncode == 0:
                download_success = True
                logger.info("yt-dlp downloaded media successfully.")

        # Gather downloaded files recursively
        downloaded_files = []
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Ignore zero-byte or helper files (like archive.txt)
                if os.path.getsize(file_path) > 0 and file != "archive.txt":
                    downloaded_files.append(file_path)

        if not download_success or not downloaded_files:
            bot.edit_message_text("❌ *Error:* Failed to download media. The link may be private, expired, or unsupported.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
            return

        bot.edit_message_text(f"📤 *Download Complete.* Uploading {len(downloaded_files)} files to Telegram...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
        
        # Upload each file
        for idx, file_path in enumerate(downloaded_files):
            file_size = os.path.getsize(file_path)
            # Telegram Bot API limits uploads to 50MB
            if file_size > 50 * 1024 * 1024:
                bot.send_message(message.chat.id, f"⚠️ File `{os.path.basename(file_path)}` exceeds Telegram's 50MB limit ({file_size // (1024*1024)}MB) and cannot be sent.")
                continue
                
            ext = os.path.splitext(file_path)[1].lower()
            logger.info(f"Uploading: {file_path} (Size: {file_size} bytes)")
            
            with open(file_path, "rb") as f:
                if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                    try:
                        bot.send_photo(message.chat.id, f, reply_to_message_id=message.message_id)
                    except Exception as e:
                        # Fallback to document
                        f.seek(0)
                        bot.send_document(message.chat.id, f, reply_to_message_id=message.message_id)
                elif ext in [".mp4", ".mov", ".webm", ".m4v"]:
                    try:
                        bot.send_video(message.chat.id, f, reply_to_message_id=message.message_id)
                    except Exception as e:
                        # Fallback to document
                        f.seek(0)
                        bot.send_document(message.chat.id, f, reply_to_message_id=message.message_id)
                else:
                    bot.send_document(message.chat.id, f, reply_to_message_id=message.message_id)
                    
            # Brief sleep to prevent flooding limits
            time.sleep(0.5)
            
        bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)

    except subprocess.TimeoutExpired:
        bot.edit_message_text("⏱️ *Error:* Download process timed out (exceeded 180s).", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error during media download: {e}")
        bot.edit_message_text(f"❌ *Error executing download:* `{str(e)}`", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
    finally:
        # Clean up temporary directory completely
        try:
            shutil.rmtree(temp_dir)
            logger.info("Cleaned up temporary download directory.")
        except Exception as e:
            logger.error(f"Failed to delete temp dir: {e}")

# Catch-all text handler (Ignore command triggers, reply to plain texts)
@bot.message_handler(func=lambda message: True)
@check_auth
def handle_plain_text(message):
    # Only reply if it doesn't start with a slash
    if not message.text.startswith("/"):
        bot.reply_to(
            message, 
            "💡 *Tip:* Send one of the commands below to perform an action:\n\n"
            "• `/sherlock <username>` ─ Scan profiles\n"
            "• `/holehe <email>` ─ Check email registration\n"
            "• `/toutatis <username>` ─ Extract Instagram metadata\n"
            "• `/download <url>` ─ Download media post\n"
            "• `/help` ─ View command usage guide",
            parse_mode="Markdown"
        )

# Start long polling
if __name__ == "__main__":
    logger.info("Starting MINT Telegram Bot polling service...")
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except KeyboardInterrupt:
        logger.info("Stopping bot polling...")
        sys.exit(0)
