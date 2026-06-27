import os
import sys
import subprocess
import json
import shutil
import ssl
import urllib.request
import zipfile
import io

GIT_REPOS = {
    "sherlock": {
        "name": "Sherlock (Username Scanner)",
        "repo": "https://github.com/sherlock-project/sherlock.git",
        "folder": "sherlock",
        "zip_url": "https://github.com/sherlock-project/sherlock/archive/refs/heads/master.zip"
    },
    "holehe": {
        "name": "Holehe (Email Checker)",
        "repo": "https://github.com/megadose/holehe.git",
        "folder": "holehe",
        "zip_url": "https://github.com/megadose/holehe/archive/refs/heads/master.zip"
    },
    "toutatis": {
        "name": "Toutatis (Instagram Extractor)",
        "repo": "https://github.com/megadose/toutatis.git",
        "folder": "toutatis",
        "zip_url": "https://github.com/megadose/toutatis/archive/refs/heads/master.zip"
    }
}

def main():
    print("=== MINT Non-Interactive Setup (Docker Build) ===")
    
    # 1. Determine paths
    user_home = os.path.expanduser("~")
    mint_home_dir = os.path.join(user_home, ".mint")
    os.makedirs(mint_home_dir, exist_ok=True)
    
    # In container, we place MINT folders under /app/mint
    parent_dir = "/app/mint"
    tools_dir = os.path.join(parent_dir, "MINT_Tools")
    social_dir = os.path.join(parent_dir, "mint-social")
    cookie_dir = os.path.join(social_dir, "cookies")
    
    os.makedirs(tools_dir, exist_ok=True)
    os.makedirs(social_dir, exist_ok=True)
    os.makedirs(cookie_dir, exist_ok=True)
    
    # Secure permissions
    try:
        os.chmod(cookie_dir, 0o700)
    except Exception as e:
        print(f"Warning: Could not set permissions on cookie directory: {e}")
        
    # Create platforms directories
    platforms = ["Facebook", "Instagram", "TikTok", "X", "Telegram"]
    for p in platforms:
        os.makedirs(os.path.join(social_dir, p), exist_ok=True)
        
    # Create profile files
    profile_files = ["facebook_profiles.txt", "instagram_profiles.txt", "tiktok_profiles.txt", "x_profiles.txt"]
    for pf in profile_files:
        pf_path = os.path.join(social_dir, pf)
        if not os.path.exists(pf_path):
            with open(pf_path, "w", encoding="utf-8") as f:
                p_name = pf.split("_")[0].capitalize()
                f.write(f"# MINT Social Tool - {p_name} Profiles List\n")
                f.write("# Enter profile URLs or usernames here, one per line.\n")
                f.write("# Lines starting with # or ; are ignored.\n#\n\n")
                
    # Create cookie files
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
                os.chmod(cf_path, 0o600)
            except Exception as e:
                print(f"Warning: Could not set permissions on cookie file: {e}")
                
    # 2. Clone repositories and install requirements
    mint_dir = "/app"
    mint_py_path = os.path.join(mint_dir, "mint.py")
    
    config_data = {
        "tools_dir": tools_dir,
        "social_dir": social_dir,
        "mint_dir": mint_dir,
        "mint_py_path": mint_py_path
    }
    
    for key, info in GIT_REPOS.items():
        tool_path = os.path.join(tools_dir, info["folder"])
        print(f"  ❯ Installing {info['name']}...")
        
        # Clone using git if available
        cloned = False
        try:
            subprocess.run(
                ["git", "clone", info["repo"], tool_path],
                check=True
            )
            cloned = True
            print(f"    [+] Cloned successfully.")
        except Exception as e:
            print(f"    [-] Git clone failed: {e}. Falling back to ZIP download...")
            
        if not cloned:
            try:
                import ssl
                context = ssl.create_default_context()
                req = urllib.request.Request(info["zip_url"], headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15, context=context) as response:
                    zip_data = response.read()
                    
                temp_extract_dir = os.path.join(tools_dir, f"{key}_temp_setup")
                if os.path.exists(temp_extract_dir):
                    shutil.rmtree(temp_extract_dir)
                os.makedirs(temp_extract_dir, exist_ok=True)
                
                with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
                    zip_ref.extractall(temp_extract_dir)
                    
                extracted_folder = None
                for item in os.listdir(temp_extract_dir):
                    item_path = os.path.join(temp_extract_dir, item)
                    if os.path.isdir(item_path):
                        extracted_folder = item_path
                        break
                        
                if extracted_folder:
                    os.rename(extracted_folder, tool_path)
                    print(f"    [+] Downloaded and extracted ZIP successfully.")
                else:
                    print(f"    [!] Error: Could not locate folder in ZIP.")
                    
                if os.path.exists(temp_extract_dir):
                    shutil.rmtree(temp_extract_dir)
            except Exception as ex:
                print(f"    [!] Critical failure downloading ZIP for {key}: {ex}")
                sys.exit(1)
                
        # Install requirements
        req_file = os.path.join(tool_path, "requirements.txt")
        setup_py = os.path.join(tool_path, "setup.py")
        pyproject = os.path.join(tool_path, "pyproject.toml")
        
        if os.path.exists(req_file):
            print(f"    ❯ Installing requirements for {key}...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", req_file],
                    check=True
                )
                print(f"    [+] Requirements installed successfully.")
            except Exception as e:
                print(f"    [!] Error installing requirements: {e}")
        elif os.path.exists(setup_py) or os.path.exists(pyproject):
            print(f"    ❯ Installing {key} package and dependencies...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "."],
                    cwd=tool_path,
                    check=True
                )
                print(f"    [+] Package installed successfully.")
            except Exception as e:
                print(f"    [!] Error installing package: {e}")
                
        config_data[f"{key}_path"] = tool_path

    # Save configuration file
    config_file_path = os.path.join(mint_home_dir, "config.json")
    try:
        with open(config_file_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        print(f"[+] Path configuration saved to {config_file_path}")
    except Exception as e:
        print(f"[!] Error saving configuration: {e}")
        sys.exit(1)
        
    print("=== Setup Completed Successfully ===")

if __name__ == "__main__":
    main()
