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
# Temporary storage for transfer modes (chat_id -> dict)
USER_PARAMS = {}

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
            bot.reply_to(message, "<b>Access Denied.</b>\nYou are not authorized to use this MINT Bot instance.", parse_mode="HTML")
            logger.warning(f"Unauthorized access attempt by User ID: {message.from_user.id} ({message.from_user.username})")
            return
        return func(message, *args, **kwargs)
    return wrapper

# Utility: Strip ANSI escape sequences (color codes) from output
def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# Helper to escape HTML special characters
def escape_html(text):
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

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

# Detect if a URL is a profile instead of a single post
def is_profile_url(url):
    url_lower = url.lower()
    if "instagram.com" in url_lower:
        if not any(x in url_lower for x in ["/p/", "/reel/", "/tv/", "/stories/"]):
            return True
    if "tiktok.com" in url_lower:
        if "@" in url_lower and "/video/" not in url_lower:
            return True
    if "x.com" in url_lower or "twitter.com" in url_lower:
        if "/status/" not in url_lower:
            return True
    return False

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
        InlineKeyboardButton("Sherlock Scan", callback_data="menu_sherlock"),
        InlineKeyboardButton("Holehe Check", callback_data="menu_holehe"),
        InlineKeyboardButton("Toutatis Instagram", callback_data="menu_toutatis"),
        InlineKeyboardButton("MINT Social Tool", callback_data="menu_social_sub"),
        InlineKeyboardButton("Bot Status", callback_data="menu_status")
    )
    bot.send_message(
        chat_id,
        "<b>MINT OSINT & Media Command Center Bot</b>\n\n"
        "Select a tool from the menu below to begin:",
        parse_mode="HTML",
        reply_markup=markup
    )

# Send MINT Social Submenu
def send_social_submenu(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("Download Single URL", callback_data="social_single"),
        InlineKeyboardButton("Add Profile to Batch Lists", callback_data="social_add"),
        InlineKeyboardButton("Run Batch Download", callback_data="social_batch"),
        InlineKeyboardButton("Back to Main Menu", callback_data="social_back")
    )
    bot.send_message(
        chat_id,
        "<b>MINT Social Downloader Tool</b>\n\n"
        "Select an option to download or manage your target profiles:",
        parse_mode="HTML",
        reply_markup=markup
    )

# Helper: Upload Single File
def upload_single_file(chat_id, file_path, reply_to_id, caption=""):
    file_size = os.path.getsize(file_path)
    if file_size > 50 * 1024 * 1024:
        bot.send_message(chat_id, f"File <code>{escape_html(os.path.basename(file_path))}</code> exceeds Telegram's 50MB limit ({file_size // (1024*1024)}MB) and cannot be sent.", reply_to_message_id=reply_to_id, parse_mode="HTML")
        return False
        
    ext = os.path.splitext(file_path)[1].lower()
    logger.info(f"Real-time upload: {file_path} ({file_size} bytes)")
    
    with open(file_path, "rb") as f:
        try:
            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                bot.send_photo(chat_id, f, reply_to_message_id=reply_to_id, caption=caption)
            elif ext in [".mp4", ".mov", ".webm", ".m4v"]:
                bot.send_video(chat_id, f, reply_to_message_id=reply_to_id, caption=caption)
            else:
                bot.send_document(chat_id, f, reply_to_message_id=reply_to_id, caption=caption)
            return True
        except Exception as e:
            logger.error(f"Failed uploading {file_path} as media: {e}. Trying document fallback...")
            f.seek(0)
            try:
                bot.send_document(chat_id, f, reply_to_message_id=reply_to_id, caption=caption)
                return True
            except Exception as ex:
                logger.error(f"Fallback upload failed: {ex}")
                return False

# Helper: Watch directory in real-time and upload newly completed files
def monitor_and_upload_realtime(temp_dir, process, chat_id, reply_to_id, silent=False):
    uploaded = set()
    
    while process.poll() is None:
        if not silent:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file_path in uploaded or file == "archive.txt":
                        continue
                    
                    try:
                        size_before = os.path.getsize(file_path)
                        if size_before == 0:
                            continue
                        time.sleep(0.8)
                        size_after = os.path.getsize(file_path)
                        if size_before == size_after:
                            upload_single_file(chat_id, file_path, reply_to_id)
                            uploaded.add(file_path)
                    except Exception as e:
                        logger.error(f"Error checking file for real-time upload: {e}")
        time.sleep(0.5)
        
    if not silent:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if file_path in uploaded or file == "archive.txt":
                    continue
                try:
                    if os.path.getsize(file_path) > 0:
                        upload_single_file(chat_id, file_path, reply_to_id)
                        uploaded.add(file_path)
                except Exception as e:
                    logger.error(f"Error in final upload sweep: {e}")
                    
    return len(uploaded)

# Core Logic: Sherlock
def run_sherlock_logic(message, username):
    if not is_safe_username(username):
        bot.reply_to(message, "Error: Invalid or unsafe username format.", parse_mode="HTML")
        return

    sherlock_dir = get_tool_path("sherlock")
    if not sherlock_dir:
        bot.reply_to(message, "Error: Sherlock path is not configured on this host/container.", parse_mode="HTML")
        return

    sherlock_py = os.path.join(sherlock_dir, "sherlock", "sherlock.py")
    if not os.path.exists(sherlock_py):
        sherlock_py = os.path.join(sherlock_dir, "sherlock.py")

    status_msg = bot.reply_to(message, f"Sherlock: Querying 300+ platforms for <code>{escape_html(username)}</code>...\n<i>This may take up to a minute.</i>", parse_mode="HTML")

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
            bot.edit_message_text("Error: No output received from Sherlock.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
        elif len(output) > 4000:
            bot.edit_message_text("Scan complete. Result exceeds message limit, sending as file...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write(output)
                temp_name = f.name
            with open(temp_name, "rb") as report:
                bot.send_document(message.chat.id, report, visible_file_name=f"sherlock_{username}.txt", reply_to_message_id=message.message_id)
            os.remove(temp_name)
        else:
            formatted_output = f"Sherlock Results for {escape_html(username)}:\n\n<pre>{escape_html(output)}</pre>"
            bot.edit_message_text(formatted_output, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
            
        if os.path.exists(local_report):
            try: os.remove(local_report)
            except: pass
                
    except subprocess.TimeoutExpired:
        bot.edit_message_text("Error: Sherlock process timed out (exceeded 120s).", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(f"Error executing Sherlock: <code>{escape_html(str(e))}</code>", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")

# Core Logic: Holehe
def run_holehe_logic(message, email):
    if not is_safe_email(email):
        bot.reply_to(message, "Error: Invalid or unsafe email address format.", parse_mode="HTML")
        return

    holehe_dir = get_tool_path("holehe")
    if not holehe_dir:
        bot.reply_to(message, "Error: Holehe path is not configured on this host/container.", parse_mode="HTML")
        return

    status_msg = bot.reply_to(message, f"Holehe: Querying registration endpoints for <code>{escape_html(email)}</code>...\n<i>This may take up to a minute.</i>", parse_mode="HTML")

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
            bot.edit_message_text("Error: No output received from Holehe.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
        elif len(clean_output) > 4000:
            bot.edit_message_text("Scan complete. Result exceeds message limit, sending as file...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write(output)
                temp_name = f.name
            with open(temp_name, "rb") as report:
                bot.send_document(message.chat.id, report, visible_file_name=f"holehe_{email}.txt", reply_to_message_id=message.message_id)
            os.remove(temp_name)
        else:
            formatted_output = f"Holehe Results for {escape_html(email)}:\n\n<pre>{escape_html(clean_output)}</pre>"
            bot.edit_message_text(formatted_output, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
            
    except subprocess.TimeoutExpired:
        bot.edit_message_text("Error: Holehe process timed out (exceeded 120s).", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(f"Error executing Holehe: <code>{escape_html(str(e))}</code>", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")

# Core Logic: Toutatis
def run_toutatis_logic(message, username):
    if not is_safe_username(username):
        bot.reply_to(message, "Error: Invalid or unsafe username format.", parse_mode="HTML")
        return

    toutatis_dir = get_tool_path("toutatis")
    if not toutatis_dir:
        bot.reply_to(message, "Error: Toutatis path is not configured on this host/container.", parse_mode="HTML")
        return

    status_msg = bot.reply_to(message, f"Toutatis: Extracting Instagram profile metadata for <code>{escape_html(username)}</code>...", parse_mode="HTML")

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
            bot.edit_message_text("Error: No output received from Toutatis.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
        elif len(output) > 4000:
            bot.edit_message_text("Scan complete. Result exceeds message limit, sending as file...", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write(output)
                temp_name = f.name
            with open(temp_name, "rb") as report:
                bot.send_document(message.chat.id, report, visible_file_name=f"toutatis_{username}.txt", reply_to_message_id=message.message_id)
            os.remove(temp_name)
        else:
            formatted_output = f"Toutatis Instagram Metadata for {escape_html(username)}:\n\n<pre>{escape_html(output)}</pre>"
            bot.edit_message_text(formatted_output, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
            
    except subprocess.TimeoutExpired:
        bot.edit_message_text("Error: Toutatis process timed out (exceeded 90s).", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(f"Error executing Toutatis: <code>{escape_html(str(e))}</code>", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")

# Core Logic: Download Single URL
def run_download_logic(message, url, silent=False):
    if not is_safe_url(url):
        bot.reply_to(message, "Error: Invalid or unsafe URL format.", parse_mode="HTML")
        return

    if is_profile_url(url):
        bot.reply_to(
            message,
            "💡 <b>Tip:</b> This is a profile URL, not a single post URL.\n\n"
            "• To download an entire profile recursively, please use <b>Add Profile to Batch Lists</b> and then run a batch download.\n"
            "• For direct downloader, please provide a link to a specific post (e.g., <code>https://www.instagram.com/p/...</code>).",
            parse_mode="HTML"
        )
        return

    status_msg = bot.reply_to(message, "Media Downloader: Starting download connection...\n<i>Media transfer will occur in real time.</i>", parse_mode="HTML")
    
    social_dir = get_social_dir()
    if silent:
        dest_dir = os.path.join(social_dir, "downloads")
        os.makedirs(dest_dir, exist_ok=True)
    else:
        dest_dir = tempfile.mkdtemp(prefix="mint_bot_")
    
    try:
        platform = "generic"
        if "instagram.com" in url.lower(): platform = "instagram"
        elif "tiktok.com" in url.lower(): platform = "tiktok"
        elif "facebook.com" in url.lower(): platform = "facebook"
        elif "x.com" in url.lower() or "twitter.com" in url.lower(): platform = "x"

        cookie_path = get_cookies_arg(platform)
        download_success = False
        
        if platform != "generic":
            cmd_gdl = ["gallery-dl", "-D", dest_dir]
            if cookie_path: cmd_gdl += ["--cookies", cookie_path]
            elif platform == "tiktok": cmd_gdl += ["--cookies-from-browser", "chrome"]
            cmd_gdl += ["-o", f"user-agent={UA}", "--sleep-request", "5", url]
            
            process = subprocess.Popen(cmd_gdl, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            uploaded_count = monitor_and_upload_realtime(dest_dir, process, message.chat.id, message.message_id, silent)
            if process.poll() == 0 or uploaded_count > 0:
                download_success = True

        if not download_success:
            cmd_ytd = ["yt-dlp", "-o", os.path.join(dest_dir, "%(title)s.%(ext)s"), "--no-playlist"]
            if cookie_path: cmd_ytd += ["--cookies", cookie_path]
            elif platform == "tiktok": cmd_ytd += ["--cookies-from-browser", "chrome"]
            cmd_ytd += ["--user-agent", UA, url]
            
            process = subprocess.Popen(cmd_ytd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            uploaded_count = monitor_and_upload_realtime(dest_dir, process, message.chat.id, message.message_id, silent)
            if process.poll() == 0 or uploaded_count > 0:
                download_success = True

        if not download_success:
            bot.edit_message_text("Error: Failed to download media. The link may be private, expired, or unsupported. Make sure your session cookies are configured.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
            return

        if silent:
            bot.edit_message_text(f"Success: Media downloaded and saved silently to server archive: <code>{escape_html(dest_dir)}</code>.", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
        else:
            bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)

    except Exception as e:
        logger.error(f"Error during media download: {e}")
        bot.edit_message_text(f"Error executing download: <code>{escape_html(str(e))}</code>", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")
    finally:
        if not silent and os.path.exists(dest_dir) and "mint_bot_" in dest_dir:
            try:
                shutil.rmtree(dest_dir)
                logger.info("Cleaned up temporary download directory.")
            except Exception as e:
                logger.error(f"Failed to delete temp dir: {e}")

# Core Logic: Add Profile to Batch List
def run_add_profile_logic(message, target, platform_key, display_name, filename):
    is_url = "/" in target or "." in target or target.lower().startswith("http")
    if is_url:
        if not is_safe_url(target):
            bot.reply_to(message, "Error: Invalid or unsafe URL format.", parse_mode="HTML")
            return
    else:
        if not is_safe_username(target):
            bot.reply_to(message, "Error: Invalid or unsafe username format.", parse_mode="HTML")
            return

    social_dir = get_social_dir()
    os.makedirs(social_dir, exist_ok=True)
    profile_file = os.path.join(social_dir, filename)
    
    new_username = parse_profile_url(target, platform_key)
    if not new_username:
        if "/" in target or "." in target or target.lower().startswith("http"):
            bot.reply_to(message, f"Error: Invalid URL for {display_name}. Make sure it matches the selected platform.", parse_mode="HTML")
            return
        else:
            new_username = target

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
                bot.reply_to(message, f"Duplicate: <code>{escape_html(new_username)}</code> is already in your {display_name} list.", parse_mode="HTML")
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
        bot.reply_to(message, f"Success: Added <code>{escape_html(profile_url)}</code> to <code>{escape_html(filename)}</code>.", parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"Error: Failed to write to profile list: <code>{escape_html(str(e))}</code>", parse_mode="HTML")

# Core Logic: Run Batch Downloader (Uses HTML parser)
def run_batch_download_logic(message, silent=False):
    social_dir = get_social_dir()
    if not os.path.exists(social_dir):
        bot.reply_to(message, "Error: MINT Social folder does not exist yet. Add a profile first to initialize it.", parse_mode="HTML")
        return

    status_msg = bot.reply_to(message, "Batch Downloader: Scanning lists and checking for new posts...\n<i>Media transfer will occur in real time.</i>", parse_mode="HTML")
    
    # 1. Take snapshot of existing files
    before_files = set()
    for root, _, files in os.walk(social_dir):
        for file in files:
            before_files.add(os.path.join(root, file))

    platforms = ["instagram", "tiktok", "facebook", "x"]
    new_files_count = 0
    failed_profiles = []

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

            dest_dir = os.path.join(social_dir, platform, username)
            os.makedirs(dest_dir, exist_ok=True)
            cookie_path = get_cookies_arg(platform)

            # Check if cookies are missing
            if platform in ["instagram", "facebook"] and not cookie_path:
                failed_profiles.append(f"{platform}/{username} (No session cookies configured)")
                continue

            profile_success = False

            # Photos
            photo_dir = os.path.join(dest_dir, "Photos")
            os.makedirs(photo_dir, exist_ok=True)
            archive_path = os.path.join(photo_dir, "archive.txt")
            cmd_photos = ["gallery-dl", "-D", photo_dir, "--filter", PHOTO_FILTER]
            if cookie_path: cmd_photos += ["--cookies", cookie_path]
            cmd_photos += ["-o", f"user-agent={UA}", "--download-archive", archive_path, "--sleep-request", "5", line]
            
            process_p = subprocess.Popen(cmd_photos, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            new_photos = monitor_and_upload_realtime(photo_dir, process_p, message.chat.id, message.message_id, silent)
            new_files_count += new_photos
            if process_p.poll() == 0:
                profile_success = True

            # Videos
            video_dir = os.path.join(dest_dir, "Videos")
            os.makedirs(video_dir, exist_ok=True)
            archive_path = os.path.join(video_dir, "archive.txt")
            cmd_videos = ["gallery-dl", "-D", video_dir, "--filter", VIDEO_FILTER]
            if cookie_path: cmd_videos += ["--cookies", cookie_path]
            cmd_videos += ["-o", f"user-agent={UA}", "--download-archive", archive_path, "--sleep-request", "5", line]
            
            process_v = subprocess.Popen(cmd_videos, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            new_vids = monitor_and_upload_realtime(video_dir, process_v, message.chat.id, message.message_id, silent)
            new_files_count += new_vids
            if process_v.poll() == 0:
                profile_success = True
            
            # Fallback to yt-dlp
            if process_v.poll() != 0:
                cmd_ytd = ["yt-dlp", "-o", os.path.join(video_dir, "%(title)s.%(ext)s")]
                if cookie_path: cmd_ytd += ["--cookies", cookie_path]
                cmd_ytd += ["--user-agent", UA, "--no-playlist", line]
                
                process_y = subprocess.Popen(cmd_ytd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                new_ytd = monitor_and_upload_realtime(video_dir, process_y, message.chat.id, message.message_id, silent)
                new_files_count += new_ytd
                if process_y.poll() == 0:
                    profile_success = True

            if not profile_success and new_photos == 0 and new_vids == 0:
                failed_profiles.append(f"{platform}/{username} (Engine error / rate limit / check connection)")

    # Format status text as HTML
    status_parts = []
    if silent:
        status_parts.append(f"Success: Batch download finished. Saved to server archive: <code>{escape_html(social_dir)}</code>.")
    else:
        if new_files_count == 0:
            status_parts.append("Batch Downloader: Finished. No new posts found on your lists.")
        else:
            status_parts.append(f"Batch Downloader: Completed. Uploaded {new_files_count} new files.")

    if failed_profiles:
        status_parts.append("\n<b>Warnings / Failures:</b>")
        for fp in failed_profiles:
            status_parts.append(f"• <code>{escape_html(fp)}</code>")
        status_parts.append("\n<i>Note: Social networks like Instagram require cookies to scan profiles. Drag and drop your <code>instagram.com_cookies.txt</code> file into this chat to securely configure cookies.</i>")

    final_text = "\n".join(status_parts)
    bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="HTML")

# Document Handler: Securely upload cookie files directly through chat
@bot.message_handler(content_types=['document'])
@check_auth
def handle_document_upload(message):
    try:
        file_name = message.document.file_name
        # Validate filename matches expected cookie format
        if not file_name.endswith("_cookies.txt"):
            bot.reply_to(
                message,
                "Document received but ignored.\n\n"
                "• To configure session cookies, please upload a Netscape cookie file named exactly like:\n"
                "  <code>instagram.com_cookies.txt</code> or <code>facebook.com_cookies.txt</code>\n"
                "  Drag and drop the file directly into this chat.",
                parse_mode="HTML"
            )
            return
            
        social_dir = get_social_dir()
        cookies_dir = os.path.join(social_dir, "cookies")
        os.makedirs(cookies_dir, exist_ok=True)
        
        clean_name = os.path.basename(file_name)
        dest_path = os.path.join(cookies_dir, clean_name)
        
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open(dest_path, "wb") as new_file:
            new_file.write(downloaded_file)
            
        try:
            os.chmod(dest_path, 0o600)
        except:
            pass
            
        bot.reply_to(
            message,
            f"Success: Saved session cookies file <code>{escape_html(clean_name)}</code> securely to server storage.\n"
            f"You can now run downloads for this platform.",
            parse_mode="HTML"
        )
        logger.info(f"User uploaded cookies file: {clean_name}")
        
    except Exception as e:
        logger.error(f"Error handling document upload: {e}")
        bot.reply_to(message, f"Error saving file: <code>{escape_html(str(e))}</code>", parse_mode="HTML")

# Helper: Show Status Directly
def send_status_direct(chat_id):
    total, used, free = shutil.disk_usage("/")
    status_text = (
        "<b>MINT Bot Status</b>\n\n"
        f"• Platform: <code>{sys.platform.upper()}</code>\n"
        f"• Python Version: <code>{sys.version.split()[0]}</code>\n"
        f"• Disk Usage: <code>{used // (2**30)}GB</code> / <code>{total // (2**30)}GB</code> used ({free // (2**30)}GB free)\n"
        f"• Access Control: <code>{'ENABLED' if ALLOWED_USERS else 'DISABLED (PUBLIC)'}</code>\n"
        f"• Sherlock Path: <code>{get_tool_path('sherlock') is not None}</code>\n"
        f"• Holehe Path: <code>{get_tool_path('holehe') is not None}</code>\n"
        f"• Toutatis Path: <code>{get_tool_path('toutatis') is not None}</code>\n"
    )
    bot.send_message(chat_id, status_text, parse_mode="HTML")

# Callback Query Handler for Inline Keyboard Buttons
@bot.callback_query_handler(func=lambda call: True)
def handle_menu_click(call):
    if not is_authorized(call.from_user.id):
        bot.answer_callback_query(call.id, "Access Denied", show_alert=True)
        return
        
    chat_id = call.message.chat.id
    action = call.data
    
    if action == "menu_sherlock":
        USER_STATES[chat_id] = "awaiting_sherlock"
        bot.send_message(chat_id, "Sherlock: Please enter the target username to scan:")
    elif action == "menu_holehe":
        USER_STATES[chat_id] = "awaiting_holehe"
        bot.send_message(chat_id, "Holehe: Please enter the target email address to check:")
    elif action == "menu_toutatis":
        USER_STATES[chat_id] = "awaiting_toutatis"
        bot.send_message(chat_id, "Toutatis: Please enter the target Instagram username to extract:")
    elif action == "menu_status":
        send_status_direct(chat_id)
        
    # MINT Social Submenu Routing
    elif action == "menu_social_sub":
        send_social_submenu(chat_id)
        
    # Single Downloader Options
    elif action == "social_single":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("Download & Send to Chat", callback_data="dl_mode_send"),
            InlineKeyboardButton("Archive on Server Only (Silent)", callback_data="dl_mode_silent")
        )
        bot.send_message(chat_id, "Downloader: Select transfer mode:", reply_markup=markup, parse_mode="HTML")
    elif action == "dl_mode_send":
        USER_STATES[chat_id] = "awaiting_download"
        USER_PARAMS[chat_id] = {"silent": False}
        bot.send_message(chat_id, "Downloader: Please enter the social media post URL to download and send:")
    elif action == "dl_mode_silent":
        USER_STATES[chat_id] = "awaiting_download"
        USER_PARAMS[chat_id] = {"silent": True}
        bot.send_message(chat_id, "Downloader: Please enter the social media post URL to archive silently on the server:")
        
    # Add Profile to Batch List
    elif action == "social_add":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("Instagram", callback_data="add_plat_instagram"),
            InlineKeyboardButton("TikTok", callback_data="add_plat_tiktok"),
            InlineKeyboardButton("Facebook", callback_data="add_plat_facebook"),
            InlineKeyboardButton("X / Twitter", callback_data="add_plat_x")
        )
        bot.send_message(chat_id, "Add Profile: Select the platform:", reply_markup=markup, parse_mode="HTML")
        
    # Batch Downloader Options
    elif action == "social_batch":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("Run & Send Updates to Chat", callback_data="batch_mode_send"),
            InlineKeyboardButton("Silent Archive Only", callback_data="batch_mode_silent")
        )
        bot.send_message(chat_id, "Batch Downloader: Select transfer mode:", reply_markup=markup, parse_mode="HTML")
    elif action == "batch_mode_send":
        run_batch_download_logic(call.message, silent=False)
    elif action == "batch_mode_silent":
        run_batch_download_logic(call.message, silent=True)
        
    elif action == "social_back":
        send_main_menu(chat_id)
        
    elif action.startswith("add_plat_"):
        platform = action.replace("add_plat_", "")
        USER_STATES[chat_id] = f"awaiting_add_{platform}"
        bot.send_message(chat_id, f"Add to {platform.capitalize()} List: Enter target username or profile URL:")

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
        bot.reply_to(message, "Usage: <code>/sherlock &lt;username&gt;</code>", parse_mode="HTML")
        return
    run_sherlock_logic(message, args[1].strip())

@bot.message_handler(commands=['holehe'])
@check_auth
def run_holehe_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: <code>/holehe &lt;email&gt;</code>", parse_mode="HTML")
        return
    run_holehe_logic(message, args[1].strip())

@bot.message_handler(commands=['toutatis'])
@check_auth
def run_toutatis_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: <code>/toutatis &lt;username&gt;</code>", parse_mode="HTML")
        return
    run_toutatis_logic(message, args[1].strip())

@bot.message_handler(commands=['download'])
@check_auth
def run_download_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: <code>/download &lt;url&gt;</code>", parse_mode="HTML")
        return
    run_download_logic(message, args[1].strip(), silent=False)

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
        params = USER_PARAMS.pop(chat_id, {"silent": False})
        run_download_logic(message, message.text.strip(), silent=params.get("silent", False))
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
            bot.reply_to(message, "Error: Invalid state.")
    else:
        send_main_menu(chat_id)

# Start long polling
if __name__ == "__main__":
    logger.info("Starting MINT Telegram Bot polling service...")
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except KeyboardInterrupt:
        logger.info("Stopping bot polling...")
        sys.exit(0)
