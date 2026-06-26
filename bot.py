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

# Constants
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
PHOTO_FILTER = "extension in ('jpg','jpeg','png','gif','webp','bmp','jfif','heic','avif','tiff','svg')"
VIDEO_FILTER = "extension in ('mp4','webm','mkv','mov','avi','m4v','flv','wmv','3gp','mpeg','mpg','ts','f4v','mts','m2ts')"

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

# Resolve MINT Social Base Directory
def get_social_dir():
    path = MINT_CONFIG.get("social_dir")
    if path and os.path.exists(path):
        return path
    container_path = "/app/mint/mint-social"
    if os.path.exists(container_path):
        return container_path
    return os.path.join(user_home, "mint-social")

# Helper: Get cookies argument for gallery-dl / yt-dlp
def get_cookies_arg(platform):
    social_dir = get_social_dir()
    cookies_dir = os.path.join(social_dir, "cookies")
    possible_names = [
        f"{platform}.com_cookies.txt",
        f"{platform}_cookies.txt"
    ]
    for name in possible_names:
        path = os.path.join(cookies_dir, name)
        if os.path.exists(path):
            return path
    return None

# Parse username and platform from URL
def parse_profile_url(url, platform):
    url = url.strip()
    if not url:
        return None
        
    temp_url = url
    while temp_url.endswith("/"):
        temp_url = temp_url[:-1]
        
    if "/" not in temp_url and not temp_url.lower().startswith("http"):
        username = temp_url.replace("@", "")
        username = username.split("?")[0].split("#")[0].strip()
        return username if username else None
        
    if not url.lower().startswith("http"):
        url = "https://" + url
        
    t = url.replace("http://", "").replace("https://", "")
    if t.startswith("/"):
        t = t[1:]
    parts = t.split("/")
    if len(parts) < 2:
        return None
        
    dom = parts[0].replace("www.", "").lower()
    usr = parts[1]
    
    if platform == "instagram" and dom != "instagram.com": return None
    if platform == "tiktok" and dom != "tiktok.com": return None
    if platform == "facebook" and dom != "facebook.com": return None
    if platform == "x" and dom not in ["x.com", "twitter.com"]: return None
    
    username = usr.replace("@", "")
    for char in ["?", "#", "/"]:
        username = username.split(char)[0]
    return username if username else None

# Send Main Menu Markup
def send_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 Sherlock Scan", callback_data="menu_sherlock"),
        InlineKeyboardButton("🔮 Holehe Check", callback_data="menu_holehe"),
        InlineKeyboardButton("📸 Toutatis Instagram", callback_data="menu_toutatis"),
        InlineKeyboardButton("📥 MINT Social Tool", callback_data="menu_social_sub"),
        InlineKeyboardButton("📊 Bot Status", callback_data="menu_status")
    )
    bot.send_message(
        chat_id,
        "🌿 *MINT OSINT & Media Command Center Bot* 🌿\n\n"
        "Select a tool from the interactive menu below to begin:",
        parse_mode="Markdown",
        reply_markup=markup
    )

# Send MINT Social Submenu
def send_social_submenu(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📥 Download Single URL Directly", callback_data="social_single"),
        InlineKeyboardButton("📝 Add Profile to Batch Lists", callback_data="social_add"),
        InlineKeyboardButton("🔄 Run Batch Download (Lists)", callback_data="social_batch"),
        InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="social_back")
    )
    bot.send_message(
        chat_id,
        "📥 *MINT Social Downloader Tool*\n\n"
        "Select an option to download or manage your target profiles:",
        parse_mode="Markdown",
        reply_markup=markup
    )

# Core Logic: Sherlock
def run_sherlock_logic(message, username):
    if not is_safe_username(username):
        bot.reply_to(message, "❌ *Error:* Invalid or unsafe username format.", parse_mode="Markdown")
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

# Core Logic: Download Single URL (Directly matched to E:\mint\mint.py parameters and cookies)
def run_download_logic(message, url):
    if not is_safe_url(url):
        bot.reply_to(message, "❌ *Error:* Invalid or unsafe URL format.", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, "📥 *Media Downloader:* Initializing download connection...\n_Downloading and packaging files, please wait..._", parse_mode="Markdown")
    temp_dir = tempfile.mkdtemp(prefix="mint_bot_")
    
    try:
        # Detect platform
        platform = "generic"
        if "instagram.com" in url.lower(): platform = "instagram"
        elif "tiktok.com" in url.lower(): platform = "tiktok"
        elif "facebook.com" in url.lower(): platform = "facebook"
        elif "x.com" in url.lower() or "twitter.com" in url.lower(): platform = "x"

        cookie_path = get_cookies_arg(platform)
        download_success = False
        
        # 1. Attempt Gallery-DL first if it's a social profile/post
        if platform != "generic":
            logger.info(f"Attempting download via gallery-dl for URL: {url} (Platform: {platform})")
            cmd_gdl = ["gallery-dl", "-D", temp_dir]
            
            # Pass cookies if available
            if cookie_path:
                cmd_gdl += ["--cookies", cookie_path]
            elif platform == "tiktok":
                cmd_gdl += ["--cookies-from-browser", "chrome"]
                
            # Match user-agent, sleep request, and filters from mint.py
            cmd_gdl += [
                "-o", f"user-agent={UA}",
                "--sleep-request", "5",
                url
            ]
            
            process_gdl = subprocess.run(cmd_gdl, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            if process_gdl.returncode == 0:
                download_success = True
                logger.info("gallery-dl downloaded media successfully.")
        
        # 2. Fallback or primary run with yt-dlp
        if not download_success:
            logger.info(f"Attempting download via yt-dlp for URL: {url}")
            cmd_ytd = ["yt-dlp", "-o", os.path.join(temp_dir, "%(title)s.%(ext)s"), "--no-playlist"]
            
            if cookie_path:
                cmd_ytd += ["--cookies", cookie_path]
            elif platform == "tiktok":
                cmd_ytd += ["--cookies-from-browser", "chrome"]
                
            cmd_ytd += [
                "--user-agent", UA,
                url
            ]
            
            process_ytd = subprocess.run(cmd_ytd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            if process_ytd.returncode == 0:
                download_success = True
                logger.info("yt-dlp downloaded media successfully.")

        # Gather files
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

# Core Logic: Add Profile to Batch List (reconstructs exact full URLs)
def run_add_profile_logic(message, target, platform_key, display_name, filename):
    is_url = "/" in target or "." in target or target.lower().startswith("http")
    if is_url:
        if not is_safe_url(target):
            bot.reply_to(message, "❌ *Error:* Invalid or unsafe URL format.", parse_mode="Markdown")
            return
    else:
        if not is_safe_username(target):
            bot.reply_to(message, "❌ *Error:* Invalid or unsafe username format.", parse_mode="Markdown")
            return

    social_dir = get_social_dir()
    os.makedirs(social_dir, exist_ok=True)
    profile_file = os.path.join(social_dir, filename)
    
    new_username = parse_profile_url(target, platform_key)
    if not new_username:
        if "/" in target or "." in target or target.lower().startswith("http"):
            bot.reply_to(message, f"❌ *Error:* Invalid URL for {display_name}. Make sure it matches the selected platform.", parse_mode="Markdown")
            return
        else:
            new_username = target

    # Reconstruct the full profile URL exactly like mint.py
    if platform_key == "instagram":
        profile_url = f"https://www.instagram.com/{new_username}/"
    elif platform_key == "tiktok":
        profile_url = f"https://www.tiktok.com/@{new_username}/"
    elif platform_key == "facebook":
        profile_url = f"https://www.facebook.com/{new_username}/"
    elif platform_key == "x":
        profile_url = f"https://x.com/{new_username}/"
    else:
        profile_url = target

    # Duplicate check
    file_existed = os.path.exists(profile_file)
    if file_existed:
        try:
            with open(profile_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            existing_usernames = []
            for line in lines:
                line_stripped = line.strip()
                if line_stripped and not line_stripped.startswith("#") and not line_stripped.startswith(";"):
                    usr = parse_profile_url(line_stripped, platform_key)
                    if usr:
                        existing_usernames.append(usr.lower())
            if new_username.lower() in existing_usernames:
                bot.reply_to(message, f"⚠️ *Duplicate:* `{new_username}` is already in your {display_name} list.", parse_mode="Markdown")
                return
        except:
            pass

    try:
        with open(profile_file, "a", encoding="utf-8") as f:
            if not file_existed:
                f.write(f"# MINT Social Tool - {display_name} Profiles List\n")
                f.write("# Enter profile URLs or usernames here, one per line.\n")
                f.write("# Lines starting with # or ; are ignored.\n#\n\n")
            f.write(f"{profile_url}\n")
        bot.reply_to(message, f"✅ *Success:* Added `{profile_url}` to `{filename}`.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ *Error:* Failed to write to profile list: `{str(e)}`", parse_mode="Markdown")

# Core Logic: Run Batch Downloader (Uses download-archive, uploads ONLY new media files)
def run_batch_download_logic(message):
    social_dir = get_social_dir()
    if not os.path.exists(social_dir):
        bot.reply_to(message, "❌ *Error:* MINT Social folder does not exist yet. Add a profile first to initialize it.", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, "🔄 *Batch Downloader:* Scanning lists and checking for new posts...\n_This processes all whitelisted profiles. Please wait..._", parse_mode="Markdown")
    
    # 1. Take snapshot of existing files recursively to detect additions
    before_files = set()
    for root, _, files in os.walk(social_dir):
        for file in files:
            before_files.add(os.path.join(root, file))

    platforms = ["instagram", "tiktok", "facebook", "x"]
    new_files_downloaded = []

    for platform in platforms:
        profile_file = os.path.join(social_dir, f"{platform}_profiles.txt")
        if not os.path.exists(profile_file):
            continue

        try:
            with open(profile_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except:
            continue

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue

            username = parse_profile_url(line, platform)
            if not username:
                continue

            # Run download for this profile exactly like mint.py
            dest_dir = os.path.join(social_dir, platform, username)
            os.makedirs(dest_dir, exist_ok=True)
            cookie_path = get_cookies_arg(platform)

            # Photos
            photo_dir = os.path.join(dest_dir, "Photos")
            os.makedirs(photo_dir, exist_ok=True)
            archive_path = os.path.join(photo_dir, "archive.txt")
            cmd_photos = ["gallery-dl", "-D", photo_dir, "--filter", PHOTO_FILTER]
            if cookie_path: cmd_photos += ["--cookies", cookie_path]
            cmd_photos += ["-o", f"user-agent={UA}", "--download-archive", archive_path, "--sleep-request", "5", line]
            subprocess.run(cmd_photos, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Videos
            video_dir = os.path.join(dest_dir, "Videos")
            os.makedirs(video_dir, exist_ok=True)
            archive_path = os.path.join(video_dir, "archive.txt")
            cmd_videos = ["gallery-dl", "-D", video_dir, "--filter", VIDEO_FILTER]
            if cookie_path: cmd_videos += ["--cookies", cookie_path]
            cmd_videos += ["-o", f"user-agent={UA}", "--download-archive", archive_path, "--sleep-request", "5", line]
            
            # Run gallery-dl, fallback to yt-dlp for videos if return code is non-zero
            process_videos = subprocess.run(cmd_videos, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if process_videos.returncode != 0:
                cmd_ytd = ["yt-dlp", "-o", os.path.join(video_dir, "%(title)s.%(ext)s")]
                if cookie_path: cmd_ytd += ["--cookies", cookie_path]
                cmd_ytd += ["--user-agent", UA, "--no-playlist", line]
                subprocess.run(cmd_ytd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Take snapshot after download to find new files
    after_files = set()
    for root, _, files in os.walk(social_dir):
        for file in files:
            after_files.add(os.path.join(root, file))

    added_files = after_files - before_files
    new_media_files = []
    for f_path in added_files:
        if os.path.getsize(f_path) > 0 and os.path.basename(f_path) != "archive.txt":
            new_media_files.append(f_path)

    if not new_media_files:
        bot.edit_message_text("🔄 *Batch Downloader:* Finished. No new posts found on your lists.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
        return

    bot.edit_message_text(f"📤 *Batch Downloader:* Complete. Uploading {len(new_media_files)} new files...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")
    
    # Upload new files
    for idx, file_path in enumerate(new_media_files):
        file_size = os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:
            bot.send_message(message.chat.id, f"⚠️ File `{os.path.basename(file_path)}` exceeds Telegram's 50MB limit ({file_size // (1024*1024)}MB) and cannot be sent.")
            continue
            
        ext = os.path.splitext(file_path)[1].lower()
        with open(file_path, "rb") as f:
            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                try: bot.send_photo(message.chat.id, f, caption=f"New from list: {os.path.basename(file_path)}")
                except:
                    f.seek(0)
                    bot.send_document(message.chat.id, f, caption=f"New from list: {os.path.basename(file_path)}")
            elif ext in [".mp4", ".mov", ".webm", ".m4v"]:
                try: bot.send_video(message.chat.id, f, caption=f"New from list: {os.path.basename(file_path)}")
                except:
                    f.seek(0)
                    bot.send_document(message.chat.id, f, caption=f"New from list: {os.path.basename(file_path)}")
            else:
                bot.send_document(message.chat.id, f, caption=f"New from list: {os.path.basename(file_path)}")
        time.sleep(0.5)

    bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)

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
    elif action == "menu_status":
        send_status_direct(chat_id)
        
    # MINT Social Submenu Routing
    elif action == "menu_social_sub":
        send_social_submenu(chat_id)
    elif action == "social_single":
        USER_STATES[chat_id] = "awaiting_download"
        bot.send_message(chat_id, "📥 *Downloader:* Please enter the social media post URL to download:")
    elif action == "social_add":
        # Ask user for platform first
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("Instagram", callback_data="add_plat_instagram"),
            InlineKeyboardButton("TikTok", callback_data="add_plat_tiktok"),
            InlineKeyboardButton("Facebook", callback_data="add_plat_facebook"),
            InlineKeyboardButton("X / Twitter", callback_data="add_plat_x")
        )
        bot.send_message(chat_id, "📝 *Add Profile:* Select the platform:", reply_markup=markup, parse_mode="Markdown")
    elif action == "social_batch":
        run_batch_download_logic(call.message)
    elif action == "social_back":
        send_main_menu(chat_id)
        
    # Add profile platform selection callbacks
    elif action.startswith("add_plat_"):
        platform = action.replace("add_plat_", "")
        USER_STATES[chat_id] = f"awaiting_add_{platform}"
        bot.send_message(chat_id, f"📝 *Add to {platform.capitalize()} List:* Enter target username or profile URL:")

    try:
        bot.answer_callback_query(call.id)
    except:
        pass

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
        
    # Profile List adding states
    elif state and state.startswith("awaiting_add_"):
        USER_STATES.pop(chat_id, None)
        platform = state.replace("awaiting_add_", "")
        
        platforms_meta = {
            "instagram": ("instagram", "Instagram", "instagram_profiles.txt"),
            "tiktok": ("tiktok", "TikTok", "tiktok_profiles.txt"),
            "facebook": ("facebook", "Facebook", "facebook_profiles.txt"),
            "x": ("x", "X/Twitter", "x_profiles.txt")
        }
        
        meta = platforms_meta.get(platform)
        if meta:
            platform_key, display_name, filename = meta
            run_add_profile_logic(message, message.text.strip(), platform_key, display_name, filename)
        else:
            bot.reply_to(message, "❌ *Error:* Invalid state.")
    else:
        # Standard behavior: show main menu
        send_main_menu(chat_id)

# Start long polling
if __name__ == "__main__":
    logger.info("Starting MINT Telegram Bot polling service...")
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except KeyboardInterrupt:
        logger.info("Stopping bot polling...")
        sys.exit(0)
