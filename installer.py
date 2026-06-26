import os
import sys
import subprocess
import sysconfig
import json
import re

# Force UTF-8 encoding on Windows to prevent UnicodeEncodeErrors with box-drawing characters
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 1. Auto-install colorama if not present
try:
    from colorama import init, Fore, Back, Style
except ImportError:
    print("Installing setup prerequisites (colorama)...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "colorama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        from colorama import init, Fore, Back, Style
    except Exception as e:
        print(f"Error installing colorama: {e}")
        sys.exit(1)

# Initialize colorama
init(autoreset=True)

# Define official GitHub repositories for the 4 external tools
GIT_REPOS = {
    "sherlock": {
        "name": "Sherlock (Username Scanner)",
        "repo": "https://github.com/sherlock-project/sherlock.git",
        "folder": "sherlock",
        "launcher": "sherlock",
        "zip_url": "https://github.com/sherlock-project/sherlock/archive/refs/heads/master.zip"
    },
    "holehe": {
        "name": "Holehe (Email Checker)",
        "repo": "https://github.com/megadose/holehe.git",
        "folder": "holehe",
        "launcher": "holehe",
        "zip_url": "https://github.com/megadose/holehe/archive/refs/heads/master.zip"
    },
    "spiderfoot": {
        "name": "SpiderFoot (OSINT Web Server)",
        "repo": "https://github.com/smicallef/spiderfoot.git",
        "folder": "spiderfoot",
        "launcher": "spiderfoot",
        "zip_url": "https://github.com/smicallef/spiderfoot/archive/refs/heads/master.zip"
    },
    "toutatis": {
        "name": "Toutatis (Instagram Extractor)",
        "repo": "https://github.com/megadose/toutatis.git",
        "folder": "toutatis",
        "launcher": "toutatis",
        "zip_url": "https://github.com/megadose/toutatis/archive/refs/heads/master.zip"
    }
}

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

def draw_setup_header(subtitle="System Setup and Tool Installer"):
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
    print_centered("The Unified OSINT & Media Command Center Installer", 50, Fore.WHITE + Style.BRIGHT)
    print_centered(f"System: {sys.platform.capitalize()}  •  Python: {sys.version.split()[0]}", 35, Fore.LIGHTBLACK_EX)
    print_centered("─" * 50, 50, Fore.LIGHTBLACK_EX)
    print()
    if subtitle:
        print_centered(subtitle, len(subtitle), Fore.YELLOW)
        print()

def check_command_exists(cmd):
    try:
        subprocess.run([cmd, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def check_git_exists():
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def install_engine_package(pkg_name):
    print(Fore.WHITE + f"  ❯ Installing {pkg_name} via pip...".ljust(55), end="", flush=True)
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "--upgrade", pkg_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            print(Fore.GREEN + Style.BRIGHT + "[ SUCCESS ]")
            return True
        else:
            print(Fore.RED + Style.BRIGHT + "[ FAILED  ]")
            return False
    except Exception as e:
        print(Fore.RED + Style.BRIGHT + "[ FAILED  ]")
        return False

def install_tool_from_github(key, info, target_dir, has_git):
    display_name = info["name"]
    repo_url = info["repo"]
    folder_name = info["folder"]
    zip_url = info["zip_url"]
    
    tool_path = os.path.join(target_dir, folder_name)
    print(Fore.WHITE + f"  ❯ Setting up {display_name}...".ljust(55), end="", flush=True)
    
    try:
        # 1. Clone or Download
        if not os.path.exists(tool_path):
            cloned = False
            if has_git:
                try:
                    subprocess.run(
                        ["git", "clone", repo_url, tool_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )
                    cloned = True
                except:
                    pass
            
            if not cloned:
                # Fallback: Download ZIP and extract
                import urllib.request
                import zipfile
                import io
                import shutil
                
                import ssl
                req = urllib.request.Request(zip_url, headers={'User-Agent': 'Mozilla/5.0'})
                context = ssl.create_default_context()
                with urllib.request.urlopen(req, timeout=15, context=context) as response:
                    zip_data = response.read()
                
                with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
                    temp_extract_dir = os.path.join(target_dir, f"{key}_temp_setup")
                    if os.path.exists(temp_extract_dir):
                        shutil.rmtree(temp_extract_dir)
                    os.makedirs(temp_extract_dir, exist_ok=True)
                    
                    zip_ref.extractall(temp_extract_dir)
                    
                    extracted_folder = None
                    for item in os.listdir(temp_extract_dir):
                        item_path = os.path.join(temp_extract_dir, item)
                        if os.path.isdir(item_path):
                            extracted_folder = item_path
                            break
                    
                    if extracted_folder:
                        os.rename(extracted_folder, tool_path)
                    
                    if os.path.exists(temp_extract_dir):
                        shutil.rmtree(temp_extract_dir)
                        
        # 2. Install requirements
        req_file = os.path.join(tool_path, "requirements.txt")
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
                    print(f"    [!] Warning: Failed to patch SpiderFoot requirements: {e}")

            process = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "-r", req_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            process.communicate()
            
        print(Fore.GREEN + Style.BRIGHT + "[ SUCCESS ]")
        return True, tool_path
    except Exception as e:
        print(Fore.RED + Style.BRIGHT + "[ FAILED  ]")
        print(Fore.RED + f"    Exception: {e}")
        return False, None

def write_launchers(config_data):
    print(Fore.WHITE + "  ❯ Creating global command launchers...".ljust(55), end="", flush=True)
    try:
        scripts_dir = sysconfig.get_path('scripts')
        if not scripts_dir or not os.path.exists(scripts_dir):
            if sys.platform.startswith('win'):
                scripts_dir = os.path.join(sys.exec_prefix, "Scripts")
            else:
                scripts_dir = os.path.join(sys.exec_prefix, "bin")
                
        os.makedirs(scripts_dir, exist_ok=True)
        
        # Sherlock Launcher
        sherlock_py = os.path.join(config_data["sherlock_path"], "sherlock", "sherlock.py")
        if not os.path.exists(sherlock_py):
            sherlock_py = os.path.join(config_data["sherlock_path"], "sherlock.py")
            
        if sys.platform.startswith('win'):
            # Sherlock
            with open(os.path.join(scripts_dir, "sherlock.bat"), "w", encoding="utf-8") as f:
                f.write(f'@echo off\n"{sys.executable}" "{sherlock_py}" %*\n')
            # Holehe
            with open(os.path.join(scripts_dir, "holehe.bat"), "w", encoding="utf-8") as f:
                f.write(f'@echo off\npushd "{config_data["holehe_path"]}"\n"{sys.executable}" -m holehe.cli %*\npopd\n')
            # SpiderFoot
            sf_py = os.path.join(config_data["spiderfoot_path"], "sf.py")
            with open(os.path.join(scripts_dir, "spiderfoot.bat"), "w", encoding="utf-8") as f:
                f.write(f'@echo off\npushd "{config_data["spiderfoot_path"]}"\nif "%~1"=="" (\n    "{sys.executable}" "{sf_py}" -l 127.0.0.1:5001\n) else (\n    "{sys.executable}" "{sf_py}" %*\n)\npopd\n')
            # Toutatis
            with open(os.path.join(scripts_dir, "toutatis.bat"), "w", encoding="utf-8") as f:
                f.write(f'@echo off\npushd "{config_data["toutatis_path"]}"\n"{sys.executable}" -m toutatis %*\npopd\n')
        else:
            # Unix launchers
            # Sherlock
            sh_sherlock = os.path.join(scripts_dir, "sherlock")
            with open(sh_sherlock, "w", encoding="utf-8") as f:
                f.write(f'#!/bin/sh\nexec "{sys.executable}" "{sherlock_py}" "$@"\n')
            os.chmod(sh_sherlock, 0o755)
            
            # Holehe
            sh_holehe = os.path.join(scripts_dir, "holehe")
            with open(sh_holehe, "w", encoding="utf-8") as f:
                f.write(f'#!/bin/sh\ncd "{config_data["holehe_path"]}"\nexec "{sys.executable}" -m holehe.cli "$@"\n')
            os.chmod(sh_holehe, 0o755)
            
            # SpiderFoot
            sh_sf = os.path.join(scripts_dir, "spiderfoot")
            sf_py = os.path.join(config_data["spiderfoot_path"], "sf.py")
            with open(sh_sf, "w", encoding="utf-8") as f:
                f.write(f'#!/bin/sh\ncd "{config_data["spiderfoot_path"]}"\nif [ $# -eq 0 ]; then\n    exec "{sys.executable}" "{sf_py}" -l 127.0.0.1:5001\nelse\n    exec "{sys.executable}" "{sf_py}" "$@"\nfi\n')
            os.chmod(sh_sf, 0o755)
            
            # Toutatis
            sh_toutatis = os.path.join(scripts_dir, "toutatis")
            with open(sh_toutatis, "w", encoding="utf-8") as f:
                f.write(f'#!/bin/sh\ncd "{config_data["toutatis_path"]}"\nexec "{sys.executable}" -m toutatis "$@"\n')
            os.chmod(sh_toutatis, 0o755)
            
        print(Fore.GREEN + Style.BRIGHT + "[ SUCCESS ]")
        return True
    except Exception as e:
        print(Fore.RED + Style.BRIGHT + "[ FAILED  ]")
        print(Fore.RED + f"    Exception: {e}")
        return False

def main():
    clear_screen()
    draw_setup_header("Required Tool Pre-Check & Environment Validation")
    
    print(Fore.GREEN + Style.BRIGHT + "  === Step 1: Pre-checking System Dependencies ===")
    print()
    
    # Check Python
    print(Fore.WHITE + "   • Python Interpreter: ".ljust(35) + Fore.GREEN + Style.BRIGHT + "[ OK ] " + Fore.WHITE + sys.executable)
    
    # Check Git
    has_git = check_git_exists()
    if has_git:
        print(Fore.WHITE + "   • Git Command-Line: ".ljust(35) + Fore.GREEN + Style.BRIGHT + "[ OK ] " + Fore.WHITE + "Git is installed and available")
    else:
        print(Fore.WHITE + "   • Git Command-Line: ".ljust(35) + Fore.YELLOW + Style.BRIGHT + "[ WARNING ] " + Fore.WHITE + "Git not found (will fallback to ZIP downloads)")
        
    # Check gallery-dl
    has_gdl = check_command_exists("gallery-dl")
    if has_gdl:
        print(Fore.WHITE + "   • Gallery-DL Engine: ".ljust(35) + Fore.GREEN + Style.BRIGHT + "[ OK ] " + Fore.WHITE + "Installed globally")
    else:
        print(Fore.WHITE + "   • Gallery-DL Engine: ".ljust(35) + Fore.RED + Style.BRIGHT + "[ MISSING ] " + Fore.WHITE + "Will be installed via pip")
        
    # Check yt-dlp
    has_ytd = check_command_exists("yt-dlp")
    if has_ytd:
        print(Fore.WHITE + "   • YT-DLP Downloader: ".ljust(35) + Fore.GREEN + Style.BRIGHT + "[ OK ] " + Fore.WHITE + "Installed globally")
    else:
        print(Fore.WHITE + "   • YT-DLP Downloader: ".ljust(35) + Fore.RED + Style.BRIGHT + "[ MISSING ] " + Fore.WHITE + "Will be installed via pip")
        
    print()
    print(Fore.LIGHTBLACK_EX + "  " + "─" * 50)
    print()
    
    # Step 2: Prompt for Custom Installation Locations
    print(Fore.GREEN + Style.BRIGHT + "  === Step 2: Configure Custom Paths & Drives ===")
    print()
    
    user_home = os.path.expanduser("~")
    default_parent_dir = os.path.join(user_home, "mint")
    
    # Prompt for MINT Parent Directory
    print(Fore.GREEN + f"  ❯ MINT Parent Folder [Default: {default_parent_dir}]: " + Fore.WHITE, end="")
    sys.stdout.flush()
    try:
        user_input = input().strip()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n\n  [!] Setup cancelled by user.")
        return
    if user_input:
        parent_dir = os.path.abspath(user_input)
        # Automatically append 'mint' if the path does not already end with it to keep it organized
        if not parent_dir.lower().endswith("mint") and not parent_dir.lower().endswith("mint\\"):
            parent_dir = os.path.join(parent_dir, "mint")
    else:
        parent_dir = os.path.abspath(default_parent_dir)
        
    tools_dir = os.path.join(parent_dir, "MINT_Tools")
    social_dir = os.path.join(parent_dir, "mint-social")
    
    print()
    print(Fore.YELLOW + "  [+] Selected Locations:")
    print(Fore.LIGHTBLACK_EX + f"   • MINT Parent Folder: {Fore.WHITE}{parent_dir}")
    print(Fore.LIGHTBLACK_EX + f"   • OSINT Tools Folder: {Fore.WHITE}{tools_dir}")
    print(Fore.LIGHTBLACK_EX + f"   • Unified MINT Social: {Fore.WHITE}{social_dir}")
    print()
    
    print(Fore.GREEN + "  ❯ Press Enter to start downloading, setup and directory creation...", end="")
    try:
        input()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n\n  [!] Setup cancelled by user.")
        return
        
    clear_screen()
    draw_setup_header("Setting up MINT Environment...")
    
    # Create Directories
    print(Fore.WHITE + "  ❯ Creating MINT Social folders...".ljust(55), end="", flush=True)
    try:
        os.makedirs(social_dir, exist_ok=True)
        cookie_dir = os.path.join(social_dir, "cookies")
        os.makedirs(cookie_dir, exist_ok=True)
        try:
            os.chmod(cookie_dir, 0o700) # Secure directory permissions (owner only)
        except:
            pass
        os.makedirs(tools_dir, exist_ok=True)
        
        # Create platforms subdirectories
        platforms = ["Facebook", "Instagram", "TikTok", "X", "Telegram"]
        for p in platforms:
            os.makedirs(os.path.join(social_dir, p), exist_ok=True)
            
        # Create empty profile files with helpful comment headers
        profile_files = ["facebook_profiles.txt", "instagram_profiles.txt", "tiktok_profiles.txt", "x_profiles.txt"]
        for pf in profile_files:
            pf_path = os.path.join(social_dir, pf)
            if not os.path.exists(pf_path):
                with open(pf_path, "w", encoding="utf-8") as f:
                    p_name = pf.split("_")[0].capitalize()
                    f.write(f"# MINT Social Tool - {p_name} Profiles List\n")
                    f.write("# Enter profile URLs or usernames here, one per line.\n")
                    f.write("# Lines starting with # or ; are ignored.\n")
                    f.write("#\n")
                    f.write(f"# Example: https://www.{pf.split('_')[0]}.com/target_username\n\n")
                    
        # Create empty cookie files with helpful comments
        cookie_files = ["facebook.com_cookies.txt", "instagram.com_cookies.txt", "tiktok.com_cookies.txt", "x.com_cookies.txt"]
        for cf in cookie_files:
            cf_path = os.path.join(cookie_dir, cf)
            if not os.path.exists(cf_path):
                with open(cf_path, "w", encoding="utf-8") as f:
                    c_name = cf.split(".")[0].capitalize()
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write(f"# MINT Social Tool - {c_name} Cookies File\n")
                    f.write("# Paste your exported cookies for this platform here in Netscape format.\n\n")
                try:
                    os.chmod(cf_path, 0o600) # Secure file permissions (owner only)
                except:
                    pass
                    
        print(Fore.GREEN + Style.BRIGHT + "[ SUCCESS ]")
    except Exception as e:
        print(Fore.RED + Style.BRIGHT + "[ FAILED  ]")
        print(Fore.RED + f"    Exception: {e}")
        return
        
    # Install missing engines
    if not has_gdl:
        install_engine_package("gallery-dl")
    if not has_ytd:
        install_engine_package("yt-dlp")
        
    print()
    print(Fore.GREEN + Style.BRIGHT + "  === Downloading OSINT Tools from GitHub ===")
    print()
    
    mint_dir = os.path.dirname(os.path.abspath(__file__))
    mint_py_path = os.path.join(mint_dir, "mint.py")
    config_data = {
        "tools_dir": tools_dir,
        "social_dir": social_dir,
        "mint_dir": mint_dir,
        "mint_py_path": mint_py_path
    }
    
    success_count = 0
    total_tools = len(GIT_REPOS)
    
    # Clone/Download tools
    for key, info in GIT_REPOS.items():
        success, path = install_tool_from_github(key, info, tools_dir, has_git)
        if success:
            success_count += 1
            config_data[f"{key}_path"] = path
            
    print()
    print(Fore.LIGHTBLACK_EX + "  " + "─" * 50)
    print()
    
    # Create launchers
    launchers_success = False
    if success_count > 0:
        launchers_success = write_launchers(config_data)
        
    # Save configuration file
    config_saved = False
    if launchers_success:
        print(Fore.WHITE + "  ❯ Save path configuration...".ljust(55), end="", flush=True)
        try:
            user_home = os.path.expanduser("~")
            mint_home_dir = os.path.join(user_home, ".mint")
            os.makedirs(mint_home_dir, exist_ok=True)
            config_file_path = os.path.join(mint_home_dir, "config.json")
            with open(config_file_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
            print(Fore.GREEN + Style.BRIGHT + "[ SUCCESS ]")
            config_saved = True
        except Exception as e:
            print(Fore.RED + Style.BRIGHT + "[ FAILED  ]")
            print(Fore.RED + f"    Exception: {e}")
            
    # Register global command wrapper
    print(Fore.WHITE + "  ❯ Registering global 'mint' command...".ljust(55), end="", flush=True)
    try:
        scripts_dir = sysconfig.get_path('scripts')
        if not scripts_dir or not os.path.exists(scripts_dir):
            if sys.platform.startswith('win'):
                scripts_dir = os.path.join(sys.exec_prefix, "Scripts")
            else:
                scripts_dir = os.path.join(sys.exec_prefix, "bin")
        
        mint_dir = os.path.dirname(os.path.abspath(__file__))
        mint_py_path = os.path.join(mint_dir, "mint.py")
        
        if sys.platform.startswith('win'):
            bat_path = os.path.join(scripts_dir, "mint.bat")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(f'@echo off\n"{sys.executable}" "{mint_py_path}" %*\n')
        else:
            sh_path = os.path.join(scripts_dir, "mint")
            with open(sh_path, "w", encoding="utf-8") as f:
                f.write(f'#!/bin/sh\nexec "{sys.executable}" "{mint_py_path}" "$@"\n')
            os.chmod(sh_path, 0o755)
            
        print(Fore.GREEN + Style.BRIGHT + "[ SUCCESS ]")
        cmd_registered = True
    except:
        print(Fore.RED + Style.BRIGHT + "[ FAILED  ]")
        cmd_registered = False
        
    print()
    print(Fore.LIGHTBLACK_EX + "  " + "─" * 50)
    print()
    
    clear_screen()
    draw_setup_header("Installation Complete!")
    
    if success_count == total_tools and config_saved and cmd_registered:
        print_centered("=== ALL COMPONENTS SET UP AND CONFIGURED SUCCESSFULLY ===", 56, Fore.GREEN + Style.BRIGHT)
        print()
        print(Fore.WHITE + "  MINT Command Center has successfully configured your environment!")
        print()
        print(Fore.YELLOW + "  Installed Tools (from Official GitHub sources):")
        for key, info in GIT_REPOS.items():
            print(Fore.WHITE + f"   • {info['name']} ❯ {config_data[f'{key}_path']}")
        print()
        print(Fore.YELLOW + "  Unified MINT Social Folder:")
        print(Fore.WHITE + f"   • Target Directory: {social_dir}")
        print(Fore.WHITE + f"   • Cookies Directory:  {os.path.join(social_dir, 'cookies')}")
        print()
        print(Fore.YELLOW + "  How to run:")
        print(Fore.WHITE + "   • Open a NEW terminal window.")
        print(Fore.WHITE + f"   • Type {Fore.GREEN}mint{Fore.WHITE} and press Enter to launch the command center.")
        print()
    else:
        print_centered("=== SETUP COMPLETED WITH SOME WARNINGS ===", 41, Fore.YELLOW + Style.BRIGHT)
        print()
        print(Fore.WHITE + f"  Set up {success_count}/{total_tools} tools from GitHub.")
        print(Fore.WHITE + "  Please run setup again or check log output for troubleshooting.")
        print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n\n  [!] Setup interrupted by user.")
        sys.exit(1)
