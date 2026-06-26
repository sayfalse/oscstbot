import os
import sys
import time
import subprocess
import json
import shutil
import urllib.request
import zipfile
import io

try:
    import msvcrt
    is_windows = True
except ImportError:
    is_windows = False
    import tty
    import termios

# Force UTF-8 encoding on Windows to prevent UnicodeEncodeErrors with box-drawing characters
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from colorama import init, Fore, Back, Style

# Initialize colorama
init(autoreset=True)

OPTIONS = [
    {"name": "Sherlock (Username Scanner)", "desc": "Hunts down social media accounts by username across 300+ sites"},
    {"name": "Holehe (Email Checker)", "desc": "Checks if an email address is registered on 120+ different websites"},
    {"name": "SpiderFoot (OSINT Web Server)", "desc": "Automates intelligence gathering via a local web interface"},
    {"name": "Toutatis (Instagram Extractor)", "desc": "Extracts associated emails and phone numbers from Instagram profiles"},
    {"name": "MINT Social Tool (Social Downloader)", "desc": "Downloads photos, videos, stories, and highlights from profiles"},
    {"name": "Update Tools (GitHub Pull)", "desc": "Pull the latest updates for all 4 external OSINT tools from their official repositories"},
    {"name": "Exit", "desc": "Close the MINT Command Center"}
]

# Constants and Paths for MINT Social Tool (dynamically resolved from config.json if available)
user_home = os.path.expanduser("~")
mint_home_dir = os.path.join(user_home, ".mint")
config_path = os.path.join(mint_home_dir, "config.json")

def resolve_portable_path(path):
    if not path:
        return path
    if os.path.exists(path):
        return path
    norm_path = os.path.normpath(path)
    parts = norm_path.split(os.sep)
    current_home = os.path.expanduser("~")
    if len(parts) > 2 and parts[0].upper() == "C:" and parts[1].lower() == "users":
        subpath = os.path.join(*parts[3:]) if len(parts) > 3 else ""
        new_path = os.path.join(current_home, subpath)
        if os.path.exists(new_path):
            return new_path
    elif len(parts) > 2 and parts[1].lower() in ["home", "users"]:
        subpath = os.path.join(*parts[3:]) if len(parts) > 3 else ""
        new_path = os.path.join(current_home, subpath)
        if os.path.exists(new_path):
            return new_path
    return path

# Dynamic defaults based on user's home directory (standard writeable location across Windows users)
BASE = os.path.join(user_home, "mint-social")
COOKIES_DIR = os.path.join(BASE, "cookies")

if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            if "social_dir" in config_data:
                BASE = resolve_portable_path(config_data["social_dir"])
                COOKIES_DIR = os.path.join(BASE, "cookies")
    except:
        pass

BROWSER = "chrome"
PYTHON = sys.executable
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

PHOTO_FILTER = "extension in ('jpg','jpeg','png','gif','webp','bmp','jfif','heic','avif','tiff','svg')"
VIDEO_FILTER = "extension in ('mp4','webm','mkv','mov','avi','m4v','flv','wmv','3gp','mpeg','mpg','ts','f4v','mts','m2ts')"
MEDIA_EXTS = ["jpg", "jpeg", "png", "gif", "webp", "bmp", "jfif", "heic", "avif", "tiff", "svg", "mp4", "webm", "mkv", "mov", "avi", "m4v", "flv", "wmv", "3gp", "mpeg", "mpg", "ts", "f4v", "mts", "m2ts"]

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_terminal_width():
    try:
        width = os.get_terminal_size().columns
        return width if width > 20 else 80
    except:
        return 80

def print_centered(text, visible_len, color=""):
    width = get_terminal_width()
    padding = max(0, (width - visible_len) // 2)
    print(" " * padding + color + text)

def wrap_text(text, max_len=52):
    words = text.split()
    lines = []
    current_line = []
    current_len = 0
    for word in words:
        if current_len + len(word) + len(current_line) > max_len:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_len = len(word)
        else:
            current_line.append(word)
            current_len += len(word)
    if current_line:
        lines.append(" ".join(current_line))
    return lines

def draw_header(subtitle="Select a tool to launch from the menu below:"):
    logo_lines = [
        "              ▄              ",
        "            ▄█▀█▄            ",
        "           ▄██ ██▄           ",
        "          ████ ████          ",
        "         ▄████ ████▄         ",
        "        ██████ ██████        ",
        "         ▀████ ████▀         ",
        "        ▄█████ █████▄        ",
        "         ▀████ ████▀         ",
        "           ▀██ ██▀           ",
        "             █ █             ",
        "             ▀ ▀             "
    ]
    
    current_workspace = os.getcwd()
    
    for line in logo_lines:
        print_centered(line, 26, Fore.GREEN)
        
    print()
    print_centered("M I N T   v1.0", 14, Fore.GREEN + Style.BRIGHT)
    print_centered("─" * 50, 50, Fore.LIGHTBLACK_EX)
    print_centered("The Unified OSINT & Media Command Center", 40, Fore.WHITE + Style.BRIGHT)
    print_centered(f"Workspace: {current_workspace}", len(f"Workspace: {current_workspace}"), Fore.LIGHTBLACK_EX)
    print_centered(Fore.LIGHTBLACK_EX + "GitHub: " + Fore.BLUE + "https://github.com/sayfalse", 36)
    print_centered("Environment: Windows  •  Python: 3.14", 37, Fore.LIGHTBLACK_EX)
    print()
    print_centered(subtitle, len(subtitle), Fore.WHITE)
    print()

def draw_menu(selected_index):
    clear_screen()
    draw_header()
    
    menu_width = 43
    width = get_terminal_width()
    menu_padding = max(0, (width - menu_width) // 2)
    
    for i, opt in enumerate(OPTIONS):
        if i == selected_index:
            print(" " * menu_padding + Fore.GREEN + Style.BRIGHT + "  ❯ " + Back.GREEN + Fore.BLACK + f" {opt['name'].ljust(38)} " + Style.RESET_ALL)
        else:
            print(" " * menu_padding + Fore.WHITE + f"    {opt['name']}")
    print()
    
    desc_width = 50
    desc_padding = max(0, (width - desc_width) // 2)
    
    print(" " * desc_padding + Fore.LIGHTBLACK_EX + "─" * 50)
    current_desc = OPTIONS[selected_index]['desc']
    wrapped_desc = wrap_text(current_desc, 44)
    for idx, d_line in enumerate(wrapped_desc):
        if idx == 0:
            print(" " * desc_padding + Fore.YELLOW + "Info: " + Fore.WHITE + d_line)
        else:
            print(" " * desc_padding + "      " + Fore.WHITE + d_line)
    print(" " * desc_padding + Fore.LIGHTBLACK_EX + "─" * 50)
    print()
    
    print_centered(Fore.BLACK + Back.LIGHTBLACK_EX + "  ↑/↓: Move  •  Enter: Run  •  1-7: Hotkey  •  Esc: Exit  ", 58)
    print()

def get_key():
    if is_windows:
        ch = msvcrt.getch()
        if ch in (b'\x00', b'\xe0'):
            ch = msvcrt.getch()
            if ch == b'H': return 'up'
            if ch == b'P': return 'down'
        elif ch == b'\r':
            return 'enter'
        elif ch == b'\x1b':
            return 'esc'
        else:
            try:
                return ch.decode('utf-8')
            except:
                return None
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                import select
                rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                if rlist:
                    ch2 = sys.stdin.read(1)
                    if ch2 == '[':
                        rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                        if rlist:
                            ch3 = sys.stdin.read(1)
                            if ch3 == 'A': return 'up'
                            if ch3 == 'B': return 'down'
                return 'esc'
            elif ch == '\r' or ch == '\n':
                return 'enter'
            elif ch == '\x03': # Ctrl+C
                raise KeyboardInterrupt
            else:
                return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def prompt_input(label):
    print(Fore.GREEN + f"  ❯ {label}: " + Fore.WHITE, end="")
    sys.stdout.flush()
    return input().strip()

def run_command(cmd_string):
    try:
        subprocess.run(cmd_string, shell=True)
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n  [!] Process stopped by user.")
    except Exception as e:
        print(Fore.RED + f"\n  [!] Error executing command: {e}")

import re

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

def parse_profile_url(url, platform):
    url = url.strip()
    if not url:
        return None
        
    # Check if it's a plain username (no slashes and doesn't start with http)
    temp_url = url
    while temp_url.endswith("/"):
        temp_url = temp_url[:-1]
        
    if "/" not in temp_url and not temp_url.lower().startswith("http"):
        # It's a plain username
        username = temp_url.replace("@", "")
        username = username.split("?")[0].split("#")[0].strip()
        return username if username else None
        
    # Otherwise parse as URL
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

def get_cookies_arg(platform):
    if platform == "tiktok":
        return f"--cookies-from-browser {BROWSER}"
        
    possible_dirs = [d for d in [COOKIES_DIR, BASE] if d and os.path.exists(d)]
    possible_names = [
        f"{platform}.com_cookies.txt",
        f"{platform}_cookies.txt",
        f"{platform}.com_cookies.txt"
    ]
    
    possible_paths = [os.path.join(d, name) for d in possible_dirs for name in possible_names]
    for path in possible_paths:
        if os.path.exists(path):
            return f'--cookies "{path}"'
            
    return ""

def check_archive(directory, archive_path):
    if not os.path.exists(directory):
        if os.path.exists(archive_path):
            try: os.remove(archive_path)
            except: pass
        return
    
    media_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            ext = file.split(".")[-1].lower()
            if ext in MEDIA_EXTS:
                media_count += 1
                
    archive_lines = 0
    if os.path.exists(archive_path):
        try:
            with open(archive_path, "r", encoding="utf-8", errors="ignore") as f:
                archive_lines = len(f.readlines())
        except:
            pass
            
    if media_count == 0:
        if os.path.exists(archive_path):
            try:
                os.remove(archive_path)
                print("    Empty, archive cleared.")
            except:
                pass
    elif archive_lines == 0:
        print(f"    {media_count} files, rebuilding...")
    else:
        print(f"    {media_count} files, archive ok.")

def run_gallery_dl(gdir, gfil, gck, gurl):
    os.makedirs(gdir, exist_ok=True)
    archive_path = os.path.join(gdir, "archive.txt")
    cmd = f'"{PYTHON}" -m gallery_dl -D "{gdir}" --filter "{gfil}" {gck} -o "user-agent={UA}" --download-archive "{archive_path}" --sleep-request 5 "{gurl}"'
    return subprocess.run(cmd, shell=True).returncode

def run_yt_dlp(ydir, yck, yurl):
    os.makedirs(ydir, exist_ok=True)
    cmd = f'"{PYTHON}" -m yt_dlp -o "{ydir}\\%(title)s.%(ext)s" {yck} --no-playlist --user-agent "{UA}" "{yurl}"'
    return subprocess.run(cmd, shell=True).returncode

def download_photos(dest_dir, cookies_arg, url):
    check_archive(os.path.join(dest_dir, "Photos"), os.path.join(dest_dir, "Photos", "archive.txt"))
    print("    [Photos]")
    ret = run_gallery_dl(os.path.join(dest_dir, "Photos"), PHOTO_FILTER, cookies_arg, url)
    if ret != 0:
        print("    [ERROR]")

def download_videos(dest_dir, cookies_arg, url):
    check_archive(os.path.join(dest_dir, "Videos"), os.path.join(dest_dir, "Videos", "archive.txt"))
    print("    [Videos]")
    ret = run_gallery_dl(os.path.join(dest_dir, "Videos"), VIDEO_FILTER, cookies_arg, url)
    if ret != 0:
        print("    Trying yt-dlp...")
        ret_yt = run_yt_dlp(os.path.join(dest_dir, "Videos"), cookies_arg, url)
        if ret_yt != 0:
            print("    [ERROR]")

def download_stories(dest_dir, cookies_arg, platform, username):
    if platform != "instagram":
        return
    check_archive(os.path.join(dest_dir, "Stories"), os.path.join(dest_dir, "Stories", "archive.txt"))
    print("    [Stories]")
    url = f"https://www.instagram.com/stories/{username}/"
    ret = run_gallery_dl(os.path.join(dest_dir, "Stories"), "true", cookies_arg, url)
    if ret != 0:
        print("    [ERROR]")

def download_highlights(dest_dir, cookies_arg, platform, username):
    if platform != "instagram":
        return
    check_archive(os.path.join(dest_dir, "Highlights"), os.path.join(dest_dir, "Highlights", "archive.txt"))
    print("    [Highlights]")
    url = f"https://www.instagram.com/{username}/highlights/"
    ret = run_gallery_dl(os.path.join(dest_dir, "Highlights"), "true", cookies_arg, url)
    if ret != 0:
        print("    [ERROR]")

def download_profile(username, dest_dir, platform, original_url, media_choice):
    cookies_arg = get_cookies_arg(platform)
    url = original_url.strip()
    
    # Reconstruct URL if it's a plain username
    if "/" not in url and not url.lower().startswith("http"):
        if platform == "instagram":
            url = f"https://www.instagram.com/{username}/"
        elif platform == "tiktok":
            url = f"https://www.tiktok.com/@{username}/"
        elif platform == "facebook":
            url = f"https://www.facebook.com/{username}/"
        elif platform == "x":
            url = f"https://x.com/{username}/"
            
    while url.endswith("/"):
        url = url[:-1]
        
    if media_choice in ["1", "5", "7"]:
        download_photos(dest_dir, cookies_arg, url)
    if media_choice in ["2", "5", "7"]:
        download_videos(dest_dir, cookies_arg, url)
    if media_choice in ["3", "6", "7"]:
        download_stories(dest_dir, cookies_arg, platform, username)
    if media_choice in ["4", "6", "7"]:
        download_highlights(dest_dir, cookies_arg, platform, username)

def run_social_tool_downloads(media_choice):
    os.makedirs(BASE, exist_ok=True)
    os.makedirs(COOKIES_DIR, exist_ok=True)
    
    platforms = ["instagram", "tiktok", "facebook", "x"]
    for platform in platforms:
        profile_file = os.path.join(BASE, f"{platform}_profiles.txt")
        if os.path.exists(profile_file):
            if platform == "x":
                print(Fore.CYAN + "\n  [X/TWITTER]")
            else:
                print(Fore.CYAN + f"\n  [{platform.upper()}]")
                
            try:
                with open(profile_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception as e:
                print(Fore.RED + f"  [!] Error reading profiles: {e}")
                continue
                
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#") or line.startswith(";"):
                    continue
                    
                username = parse_profile_url(line, platform)
                if username and username != "INVALID_URL":
                    print(Fore.WHITE + f"  --- {username}")
                    dest_dir = os.path.join(BASE, platform, username)
                    download_profile(username, dest_dir, platform, line, media_choice)

def draw_social_main_menu(selected_index):
    clear_screen()
    draw_header("Running: MINT Social Tool (Social Downloader)")
    
    print_centered("=== MINT Social Tool ===", 24, Fore.GREEN + Style.BRIGHT)
    print()
    print_centered("What do you want to do?", 23, Fore.WHITE + Style.BRIGHT)
    print()
    
    menu_options = [
        "Add a profile to your lists",
        "Download from a single profile directly",
        "Run batch downloads from your lists",
        "Back to Main Menu"
    ]
    
    menu_width = 45
    width = get_terminal_width()
    menu_padding = max(0, (width - menu_width) // 2)
    
    for i, opt in enumerate(menu_options):
        if i == selected_index:
            print(" " * menu_padding + Fore.GREEN + Style.BRIGHT + f"  ❯ " + Back.GREEN + Fore.BLACK + f" [{i+1}] {opt.ljust(40)} " + Style.RESET_ALL)
        else:
            print(" " * menu_padding + Fore.WHITE + f"    [{i+1}] {opt}")
            
    print()
    print_centered("  ↑/↓: Move  •  Enter: Select  •  1-4: Hotkey  ", 48, Fore.BLACK + Back.LIGHTBLACK_EX)
    print()

def add_social_profile_interactive():
    clear_screen()
    draw_header("MINT Social Tool - Add Target Profile")
    print(Fore.GREEN + Style.BRIGHT + "  === Add Target Profile ===")
    print()
    print(Fore.WHITE + "  Select the social media platform:")
    print(Fore.WHITE + "    [1] Instagram")
    print(Fore.WHITE + "    [2] TikTok")
    print(Fore.WHITE + "    [3] Facebook")
    print(Fore.WHITE + "    [4] X / Twitter")
    print()
    
    platform_choice = prompt_input("Select option (1-4) or press Enter to cancel")
    if not platform_choice:
        return
        
    platforms = {
        "1": ("instagram", "instagram_profiles.txt", "Instagram"),
        "2": ("tiktok", "tiktok_profiles.txt", "TikTok"),
        "3": ("facebook", "facebook_profiles.txt", "Facebook"),
        "4": ("x", "x_profiles.txt", "X/Twitter")
    }
    
    if platform_choice not in platforms:
        print(Fore.RED + "\n  [!] Invalid option.")
        time.sleep(1.5)
        return
        
    platform_key, filename, display_name = platforms[platform_choice]
    print(Fore.WHITE + f"\n  Adding profile for {Fore.GREEN}{display_name}{Fore.WHITE}:")
    target = prompt_input("Enter the username or profile URL to add")
    if not target:
        return
        
    # Input validation to prevent shell injection
    is_url = "/" in target or "." in target or target.lower().startswith("http")
    if is_url:
        if not is_safe_url(target):
            print(Fore.RED + f"\n  [!] Invalid or unsafe URL format.")
            time.sleep(2.5)
            return
    else:
        if not is_safe_username(target):
            print(Fore.RED + f"\n  [!] Invalid or unsafe username format.")
            time.sleep(2.5)
            return
            
    # Automatically make sure directory exists
    os.makedirs(BASE, exist_ok=True)
    profile_file = os.path.join(BASE, filename)
    
    # Check if file exists
    file_existed = os.path.exists(profile_file)
    
    # Parse username from target
    new_username = parse_profile_url(target, platform_key)
    if not new_username:
        # Mismatched or invalid URL validation
        if "/" in target or "." in target or target.lower().startswith("http"):
            print(Fore.RED + f"\n  [!] Invalid URL for {display_name}.")
            print(Fore.YELLOW + "  [+] Please make sure the URL matches the selected platform.")
            time.sleep(2.5)
            return
        else:
            new_username = target
            
    # Reconstruct the full profile URL
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
        
    # Duplicate checking
    if file_existed:
        try:
            with open(profile_file, "r", encoding="utf-8", errors="ignore") as f:
                existing_lines = f.readlines()
            
            existing_usernames = []
            for line in existing_lines:
                line_stripped = line.strip()
                if line_stripped and not line_stripped.startswith("#") and not line_stripped.startswith(";"):
                    usr = parse_profile_url(line_stripped, platform_key)
                    if usr:
                        existing_usernames.append(usr.lower())
            
            if new_username.lower() in existing_usernames:
                print(Fore.YELLOW + f"\n  [!] The profile '{target}' (resolved as '{new_username}') is already in your {display_name} list.")
                print()
                input("  Press Enter to return to menu...")
                return
        except Exception as e:
            pass
            
    try:
        with open(profile_file, "a", encoding="utf-8") as f:
            if not file_existed:
                f.write(f"# MINT Social Tool - {display_name} Profiles List\n")
                f.write("# Enter profile URLs or usernames here, one per line.\n")
                f.write("# Lines starting with # or ; are ignored.\n#\n\n")
            f.write(f"{profile_url}\n")
        print(Fore.GREEN + Style.BRIGHT + f"\n  [+] Successfully added '{profile_url}' to {filename}.")
    except Exception as e:
        print(Fore.RED + f"\n  [!] Error writing to file: {e}")
        
    print()
    input("  Press Enter to return to menu...")

def run_direct_profile_download():
    clear_screen()
    draw_header("MINT Social Tool - Quick Download")
    print(Fore.GREEN + Style.BRIGHT + "  === Quick Download (Single Profile) ===")
    print()
    print(Fore.WHITE + "  Select the platform:")
    print(Fore.WHITE + "    [1] Instagram")
    print(Fore.WHITE + "    [2] TikTok")
    print(Fore.WHITE + "    [3] Facebook")
    print(Fore.WHITE + "    [4] X / Twitter")
    print()
    
    platform_choice = prompt_input("Select option (1-4) or press Enter to cancel")
    if not platform_choice:
        return
        
    platforms = {
        "1": ("instagram", "Instagram"),
        "2": ("tiktok", "TikTok"),
        "3": ("facebook", "Facebook"),
        "4": ("x", "X/Twitter")
    }
    
    if platform_choice not in platforms:
        print(Fore.RED + "\n  [!] Invalid option.")
        time.sleep(1.5)
        return
        
    platform_key, display_name = platforms[platform_choice]
    print(Fore.WHITE + f"\n  Downloading from {Fore.GREEN}{display_name}{Fore.WHITE}:")
    target = prompt_input("Enter target username or profile URL")
    if not target:
        return
        
    # Input validation to prevent shell injection
    is_url = "/" in target or "." in target or target.lower().startswith("http")
    if is_url:
        if not is_safe_url(target):
            print(Fore.RED + f"\n  [!] Invalid or unsafe URL format.")
            time.sleep(2.5)
            return
    else:
        if not is_safe_username(target):
            print(Fore.RED + f"\n  [!] Invalid or unsafe username format.")
            time.sleep(2.5)
            return
        
    username = parse_profile_url(target, platform_key)
    if not username:
        # Mismatched or invalid URL validation
        if "/" in target or "." in target or target.lower().startswith("http"):
            print(Fore.RED + f"\n  [!] Invalid URL for {display_name}.")
            print(Fore.YELLOW + "  [+] Please make sure the URL matches the selected platform.")
            time.sleep(2.5)
            return
        else:
            username = target
            
    # Now show the media choice menu!
    selected_media_index = 0
    while True:
        draw_social_menu(selected_media_index)
        key = get_key()
        
        if key == 'up':
            selected_media_index = (selected_media_index - 1) % 8
        elif key == 'down':
            selected_media_index = (selected_media_index + 1) % 8
        elif key == 'esc':
            return
        elif key in ['1', '2', '3', '4', '5', '6', '7', '8']:
            selected_media_index = int(key) - 1
            key = 'enter'
            
        if key == 'enter':
            if selected_media_index == 7: # Back
                return
                
            clear_screen()
            media_choice = str(selected_media_index + 1)
            draw_header(f"Running: Quick Download - Mode [{media_choice}]")
            
            print(Fore.GREEN + Style.BRIGHT + f"  === Quick Download: {username} ({display_name}) ===")
            print(Fore.YELLOW + f"  [+] Downloading mode [{media_choice}]...")
            print(Fore.LIGHTBLACK_EX + "  " + "─" * 50)
            
            try:
                dest_dir = os.path.join(BASE, platform_key, username)
                os.makedirs(dest_dir, exist_ok=True)
                download_profile(username, dest_dir, platform_key, target, media_choice)
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\n  [!] Download stopped by user.")
            except Exception as e:
                print(Fore.RED + f"\n  [!] Error: {e}")
                
            print(Fore.LIGHTBLACK_EX + "\n  " + "─" * 50)
            print(Fore.GREEN + "  [+] Done.")
            print()
            input("  Press Enter to return to MINT Social Tool menu...")
            break

def draw_social_menu(selected_index):
    clear_screen()
    draw_header("Running: MINT Social Tool (Social Downloader)")
    
    print_centered("=== MINT Social Tool ===", 24, Fore.GREEN + Style.BRIGHT)
    print()
    print_centered("What do you want to download?", 29, Fore.WHITE + Style.BRIGHT)
    print()
    
    menu_options = [
        "Photos only",
        "Videos only",
        "Stories only",
        "Highlights only",
        "Photos + Videos",
        "Stories + Highlights",
        "All",
        "Back to Menu"
    ]
    
    menu_width = 30
    width = get_terminal_width()
    menu_padding = max(0, (width - menu_width) // 2)
    
    for i, opt in enumerate(menu_options):
        if i == selected_index:
            print(" " * menu_padding + Fore.GREEN + Style.BRIGHT + f"  ❯ " + Back.GREEN + Fore.BLACK + f" [{i+1}] {opt.ljust(20)} " + Style.RESET_ALL)
        else:
            print(" " * menu_padding + Fore.WHITE + f"    [{i+1}] {opt}")
            
    print()
    print_centered("  ↑/↓: Move  •  Enter: Select  •  1-8: Hotkey  ", 48, Fore.BLACK + Back.LIGHTBLACK_EX)
    print()

def run_social_tool_tui():
    selected_index = 0
    while True:
        draw_social_main_menu(selected_index)
        key = get_key()
        
        if key == 'up':
            selected_index = (selected_index - 1) % 4
        elif key == 'down':
            selected_index = (selected_index + 1) % 4
        elif key == 'esc':
            break
        elif key in ['1', '2', '3', '4']:
            selected_index = int(key) - 1
            key = 'enter'
            
        if key == 'enter':
            if selected_index == 3:  # Back to Main Menu
                break
            elif selected_index == 0:  # Add a profile to lists
                add_social_profile_interactive()
            elif selected_index == 1:  # Download from a single profile directly
                run_direct_profile_download()
            elif selected_index == 2:  # Run batch downloads from lists
                # Show the media type menu
                selected_media_index = 0
                while True:
                    draw_social_menu(selected_media_index)
                    key2 = get_key()
                    
                    if key2 == 'up':
                        selected_media_index = (selected_media_index - 1) % 8
                    elif key2 == 'down':
                        selected_media_index = (selected_media_index + 1) % 8
                    elif key2 == 'esc':
                        break
                    elif key2 in ['1', '2', '3', '4', '5', '6', '7', '8']:
                        selected_media_index = int(key2) - 1
                        key2 = 'enter'
                        
                    if key2 == 'enter':
                        if selected_media_index == 7:  # Back
                            break
                            
                        clear_screen()
                        media_choice = str(selected_media_index + 1)
                        draw_header(f"Running: MINT Social Tool - Mode [{media_choice}]")
                        
                        print(Fore.GREEN + Style.BRIGHT + f"  === MINT Social Tool - Mode [{media_choice}] ===")
                        print()
                        print(Fore.YELLOW + f"  [+] Starting downloads in mode [{media_choice}]...")
                        print(Fore.LIGHTBLACK_EX + "  " + "─" * 50)
                        
                        try:
                            run_social_tool_downloads(media_choice)
                        except KeyboardInterrupt:
                            print(Fore.YELLOW + "\n  [!] Downloads interrupted by user.")
                        except Exception as e:
                            print(Fore.RED + f"\n  [!] Error running downloads: {e}")
                            
                        print(Fore.LIGHTBLACK_EX + "\n  " + "─" * 50)
                        print(Fore.GREEN + "  [+] Done.")
                        print()
                        input("  Press Enter to return to MINT Social Tool menu...")
                        break

def update_single_tool(key, name, path):
    if os.path.exists(os.path.join(path, ".git")):
        try:
            print(Fore.LIGHTBLACK_EX + "    Running git pull...")
            subprocess.run(["git", "-C", path, "pull"], check=True)
            
            req_file = os.path.join(path, "requirements.txt")
            if os.path.exists(req_file):
                if key == "spiderfoot":
                    try:
                        with open(req_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        new_content = re.sub(r'lxml\s*>=\s*4\.9\.2\s*,\s*<\s*5', 'lxml>=4.9.2', content)
                        if new_content != content:
                            with open(req_file, "w", encoding="utf-8") as f:
                                f.write(new_content)
                    except Exception as e:
                        print(Fore.RED + f"    [!] Warning: Failed to patch SpiderFoot requirements: {e}")

                print(Fore.LIGHTBLACK_EX + "    Upgrading dependencies...")
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file], check=True)
                
            print(Fore.GREEN + f"    [+] {name} updated successfully.")
        except Exception as e:
            print(Fore.RED + f"    [!] Error updating {name}: {e}")
        return

    print(Fore.LIGHTBLACK_EX + "    Not a git repo. Attempting re-download from GitHub...")
    try:
        repos = {
            "sherlock": "sherlock-project/sherlock",
            "holehe": "megadose/holehe",
            "spiderfoot": "smicallef/spiderfoot",
            "toutatis": "leogout/toutatis"
        }
        
        repo = repos.get(key)
        if not repo:
            return
            
        zip_url = f"https://github.com/{repo}/archive/refs/heads/master.zip"
        import ssl
        context = ssl.create_default_context()
        try:
            req = urllib.request.Request(zip_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15, context=context) as response:
                zip_data = response.read()
        except:
            zip_url = f"https://github.com/{repo}/archive/refs/heads/main.zip"
            req = urllib.request.Request(zip_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15, context=context) as response:
                zip_data = response.read()
                
        temp_dir = os.path.join(os.path.dirname(path), f"{key}_temp_update")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)
        
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
            zip_ref.extractall(temp_dir)
            
        extracted_folder = None
        for folder in os.listdir(temp_dir):
            if folder.startswith(key) or folder.startswith(name.lower()):
                extracted_folder = os.path.join(temp_dir, folder)
                break
                
        if extracted_folder:
            for item in os.listdir(extracted_folder):
                s = os.path.join(extracted_folder, item)
                d = os.path.join(path, item)
                if os.path.isdir(s):
                    if os.path.exists(d):
                        shutil.rmtree(d)
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
                    
            req_file = os.path.join(path, "requirements.txt")
            if os.path.exists(req_file):
                if key == "spiderfoot":
                    try:
                        with open(req_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        new_content = re.sub(r'lxml\s*>=\s*4\.9\.2\s*,\s*<\s*5', 'lxml>=4.9.2', content)
                        if new_content != content:
                            with open(req_file, "w", encoding="utf-8") as f:
                                f.write(new_content)
                    except Exception as e:
                        print(Fore.RED + f"    [!] Warning: Failed to patch SpiderFoot requirements: {e}")
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file], check=True)
                
            print(Fore.GREEN + f"    [+] {name} re-downloaded and updated successfully.")
        else:
            print(Fore.RED + f"    [!] Could not locate extracted files in zip.")
            
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    except Exception as e:
        print(Fore.RED + f"    [!] Error downloading update: {e}")

def run_tools_update():
    clear_screen()
    draw_header("Updating OSINT Tools from GitHub")
    
    print(Fore.GREEN + Style.BRIGHT + "  === Update OSINT Tools ===")
    print()
    
    user_home = os.path.expanduser("~")
    mint_home_dir = os.path.join(user_home, ".mint")
    config_path = os.path.join(mint_home_dir, "config.json")
    if not os.path.exists(config_path):
        print(Fore.RED + "  [!] Configuration file (config.json) not found.")
        print(Fore.YELLOW + "  [+] Please run the setup installer first to configure and install the tools.")
        print()
        input("  Press Enter to return to menu...")
        return
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(Fore.RED + f"  [!] Error reading config.json: {e}")
        print()
        input("  Press Enter to return to menu...")
        return
        
    tools = {
        "sherlock": ("Sherlock", resolve_portable_path(config.get("sherlock_path"))),
        "holehe": ("Holehe", resolve_portable_path(config.get("holehe_path"))),
        "spiderfoot": ("SpiderFoot", resolve_portable_path(config.get("spiderfoot_path"))),
        "toutatis": ("Toutatis", resolve_portable_path(config.get("toutatis_path")))
    }
    
    print(Fore.YELLOW + "  [+] Checking for updates from official GitHub repositories...\n")
    
    for key, (name, path) in tools.items():
        if not path or not os.path.exists(path):
            print(Fore.RED + f"  [!] {name} path not configured or directory does not exist.")
            continue
            
        print(Fore.WHITE + f"  ❯ Updating {name} at {path}...")
        update_single_tool(key, name, path)
        print()
        
    print(Fore.GREEN + Style.BRIGHT + "  [+] Update process finished.")
    print()
    input("  Press Enter to return to menu...")

def main():
    # Check if MINT is configured. If not, automatically launch the interactive setup installer.
    user_home = os.path.expanduser("~")
    mint_home_dir = os.path.join(user_home, ".mint")
    config_path = os.path.join(mint_home_dir, "config.json")
    
    if not os.path.exists(config_path):
        clear_screen()
        logo_lines = [
            "              ▄              ",
            "            ▄█▀█▄            ",
            "           ▄██ ██▄           ",
            "          ████ ████          ",
            "         ▄████ ████▄         ",
            "        ██████ ██████        ",
            "         ▀████ ████▀         ",
            "        ▄█████ █████▄        ",
            "         ▀████ ████▀         ",
            "           ▀██ ██▀           ",
            "             █ █             ",
            "             ▀ ▀             "
        ]
        for line in logo_lines:
            print_centered(line, 26, Fore.GREEN)
        print()
        print_centered("M I N T   S E T U P", 19, Fore.GREEN + Style.BRIGHT)
        print_centered("─" * 50, 50, Fore.LIGHTBLACK_EX)
        print()
        print(Fore.YELLOW + "  [!] MINT has not been configured yet, and the sub-tools are missing.")
        print(Fore.WHITE + "  [+] The setup installer will download Sherlock, Holehe, Toutatis,")
        print(Fore.WHITE + "      and SpiderFoot, and configure your directories automatically.")
        print()
        
        try:
            choice = input(Fore.GREEN + "  ❯ Would you like to run the interactive installer now? (y/n): " + Fore.WHITE).strip().lower()
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\n\n  [!] Setup cancelled by user.")
            sys.exit(0)
            
        if choice in ('y', 'yes'):
            try:
                import installer
                installer.main()
                if os.path.exists(config_path):
                    # Successfully configured! Restart this script to boot directly into the main menu
                    os.execv(sys.executable, [sys.executable] + sys.argv)
            except ImportError:
                print(Fore.RED + "\n  [!] Error: The installer module (installer.py) was not found in your path.")
                print(Fore.YELLOW + "  [+] Please run setup.bat or setup.sh manually to configure MINT.")
                print()
                input("  Press Enter to exit...")
                sys.exit(1)
            except Exception as e:
                print(Fore.RED + f"\n  [!] Error running installer: {e}")
                print()
                input("  Press Enter to exit...")
                sys.exit(1)
        else:
            print(Fore.YELLOW + "\n  [!] Setup skipped. MINT cannot run without configuration.")
            sys.exit(0)

    if len(sys.argv) > 1:
        if sys.argv[1] == "--social":
            run_social_tool_tui()
            sys.exit(0)
        elif sys.argv[1] == "--update":
            run_tools_update()
            sys.exit(0)

    selected_index = 0
    
    while True:
        draw_menu(selected_index)
        key = get_key()
        
        if key == 'up':
            selected_index = (selected_index - 1) % len(OPTIONS)
        elif key == 'down':
            selected_index = (selected_index + 1) % len(OPTIONS)
        elif key == 'esc':
            break
        elif key in ['1', '2', '3', '4', '5', '6', '7']:
            idx = int(key) - 1
            selected_index = idx
            key = 'enter'
            
        if key == 'enter':
            clear_screen()
            
            if selected_index == 0:  # Sherlock
                draw_header("Running: Sherlock (Username Scanner)")
                print(Fore.GREEN + Style.BRIGHT + "  === Sherlock (Username Scanner) ===")
                print()
                username = prompt_input("Enter target username")
                if not username:
                    continue
                if username.lower() == "/update":
                    run_tools_update()
                    continue
                
                if not is_safe_username(username):
                    print(Fore.RED + "\n  [!] Invalid or unsafe username format.")
                    print(Fore.YELLOW + "  [+] Usernames must contain only letters, numbers, periods, underscores, hyphens, and @.")
                    time.sleep(3)
                    continue
                
                print(Fore.YELLOW + f"\n  [+] Querying 300+ platforms for '{username}'...\n")
                run_command(f"sherlock {username}")
                print()
                input("  Press Enter to return to menu...")
                
            elif selected_index == 1:  # Holehe
                draw_header("Running: Holehe (Email Checker)")
                print(Fore.GREEN + Style.BRIGHT + "  === Holehe (Email Checker) ===")
                print()
                email = prompt_input("Enter target email address")
                if not email:
                    continue
                if email.lower() == "/update":
                    run_tools_update()
                    continue
                
                if not is_safe_email(email):
                    print(Fore.RED + "\n  [!] Invalid or unsafe email format.")
                    print(Fore.YELLOW + "  [+] Emails must contain only letters, numbers, periods, underscores, hyphens, +, and @.")
                    time.sleep(3)
                    continue
                
                print(Fore.YELLOW + f"\n  [+] Querying registration endpoints for '{email}'...\n")
                run_command(f"holehe {email}")
                print()
                input("  Press Enter to return to menu...")
                
            elif selected_index == 2:  # SpiderFoot
                draw_header("Running: SpiderFoot (OSINT Web Server)")
                print(Fore.GREEN + Style.BRIGHT + "  === SpiderFoot (OSINT Web Server) ===")
                print()
                print(Fore.GREEN + "  [+] Starting SpiderFoot local web server...")
                print(Fore.YELLOW + "  [+] Dashboard URL: http://127.0.0.1:5001")
                print(Fore.RED + "  [+] Press Ctrl+C inside this window to stop the server.")
                print()
                run_command("spiderfoot")
                print()
                input("  Press Enter to return to menu...")
                
            elif selected_index == 3:  # Toutatis
                draw_header("Running: Toutatis (Instagram Extractor)")
                print(Fore.GREEN + Style.BRIGHT + "  === Toutatis (Instagram Extractor) ===")
                print()
                username = prompt_input("Enter target Instagram username")
                if not username:
                    continue
                if username.lower() == "/update":
                    run_tools_update()
                    continue
                
                if not is_safe_username(username):
                    print(Fore.RED + "\n  [!] Invalid or unsafe username format.")
                    print(Fore.YELLOW + "  [+] Usernames must contain only letters, numbers, periods, underscores, hyphens, and @.")
                    time.sleep(3)
                    continue
                
                sessionid = prompt_input("Enter Instagram Session ID (optional - press Enter to skip)")
                if sessionid and not re.match(r'^[a-zA-Z0-9:_]+$', sessionid):
                    print(Fore.RED + "\n  [!] Invalid or unsafe Session ID format.")
                    time.sleep(3)
                    continue
                    
                if sessionid:
                    cmd = f"toutatis -u {username} -s {sessionid}"
                else:
                    cmd = f"toutatis -u {username}"
                print(Fore.YELLOW + f"\n  [+] Querying Instagram API for '{username}'...\n")
                run_command(cmd)
                print()
                input("  Press Enter to return to menu...")
                
            elif selected_index == 4:  # MINT Social Tool (Social Downloader)
                run_social_tool_tui()
                
            elif selected_index == 5:  # Update Tools
                run_tools_update()
                
            elif selected_index == 6:  # Exit
                break

    clear_screen()
    print(Fore.GREEN + Style.BRIGHT + "========================================")
    print(Fore.GREEN + Style.BRIGHT + "   Thank you for using MINT. Goodbye!   ")
    print(Fore.GREEN + Style.BRIGHT + "========================================")
    time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        clear_screen()
        print(Fore.GREEN + "\nGoodbye!")
        sys.exit(0)
