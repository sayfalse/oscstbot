# MINT OSINT & Media Command Center — Telegram Bot

🌿 **MINT Telegram Bot** is a secure, interactive conversational wrapper around the MINT OSINT and Media Command Center, optimized for one-click containerized deployment on [Railway.com](https://railway.com/). 

It exposes the full capabilities of Sherlock, Holehe, Toutatis, and the MINT Social Downloader through an interactive, state-based Telegram chat interface.

---

## ✨ Features

*   🌿 **Interactive Inline Keyboards**: Navigate all tools through buttons and a guided state-based wizard. No manual slash command typing is required.
*   🛡️ **Access Control List (ACL)**: Secure your bot instance by whitelisting specific Telegram User IDs using the `ALLOWED_USERS` environment variable. Unauthorized users are blocked automatically.
*   🔒 **Strict Input Sanitization**: Prevents command injection attacks. All inputs (usernames, emails, and URLs) are validated against strict whitelisting regular expressions before execution.
*   📥 **MINT Social Downloader Suite**:
    *   **Direct Media Downloader**: Download photos, videos, and multi-post carousels from Instagram, TikTok, Facebook, and X/Twitter using `gallery-dl` and `yt-dlp`.
    *   **Cookie & User-Agent Integration**: Automatically loads session cookies from the `cookies/` directory and applies custom User-Agents and 5-second sleep request intervals to avoid rate limits and platform blocks.
    *   **Batch Downloader**: Add target profiles to lists, run batch downloads, and automatically receive **only newly posted media** via a directory diff-checker.
*   📄 **Smart Document Overflow**: Long scan results that exceed Telegram’s 4,000-character message limit are automatically formatted, written to a text file, and uploaded as a document.
*   📊 **Status Monitor**: Check container health, host platform, Python version, and active disk space allocation using the `/status` command or menu button.

---

## 🚀 Quick Deployment to Railway.com

This repository is pre-configured with a `Dockerfile` and automated setup scripts that provision the container and download all required OSINT tools during the image build phase.

### 1. Prerequisites
1.  **Telegram Bot Token**: Create a bot and obtain an API token from [@BotFather](https://t.me/BotFather) on Telegram.
2.  **Your Telegram User ID**: Get your numerical ID from [@userinfobot](https://t.me/userinfobot) on Telegram to secure your bot.

### 2. Deployment Steps
1.  Log in to [Railway.com](https://railway.com/).
2.  Create a **New Project** and select **Deploy from GitHub repo**.
3.  Choose the `sayfalse/oscstbot` repository.
4.  Navigate to the **Variables** tab and add the following environment variables:
    *   `TELEGRAM_BOT_TOKEN` = `[Your Telegram Bot Token]` *(Required)*
    *   `ALLOWED_USERS` = `[Your Telegram User ID]` *(Highly Recommended. Separate multiple IDs with commas, e.g., `987654321,123456789`)*
5.  Click **Deploy**. Railway will build the container, install all system packages (including Git and FFmpeg), clone the sub-tools, and launch the bot polling service.

---

## 🛠️ Local Development & Testing

If you want to run or test the bot locally on your machine:

### 1. Install System Dependencies
Ensure you have the following installed on your host system:
*   Python 3.10+
*   Git
*   FFmpeg (required by `yt-dlp` and `gallery-dl` for merging/extracting video streams)

### 2. Clone and Install
```bash
git clone https://github.com/sayfalse/oscstbot.git
cd oscstbot
pip install -r requirements.txt
```

### 3. Run Unit Tests
A comprehensive test suite is provided to verify input sanitization, ANSI stripping, and access control:
```bash
# Windows
$env:TELEGRAM_BOT_TOKEN="12345:dummy"; python -m unittest test_bot.py

# Linux/macOS
TELEGRAM_BOT_TOKEN="12345:dummy" python3 -m unittest test_bot.py
```

### 4. Run the Bot Locally
```bash
# Windows
$env:TELEGRAM_BOT_TOKEN="your_token_here"; $env:ALLOWED_USERS="your_id_here"; python bot.py

# Linux/macOS
TELEGRAM_BOT_TOKEN="your_token_here" ALLOWED_USERS="your_id_here" python3 bot.py
```

---

## 📂 Repository Structure

```
├── bot.py                  # Main Telegram Bot application script
├── Dockerfile              # Docker container configuration optimized for Railway
├── requirements.txt        # Python package dependencies
├── setup_noninteractive.py # Automates OSINT tool cloning and dependency installation
├── test_bot.py             # Unit test suite for validation and security checks
├── mint.py                 # Core MINT CLI module (preserves layout)
└── installer.py            # Core MINT Installer module (preserves layout)
```

---

## 🛡️ Security Best Practices

1.  **Enable Whitelisting**: Never run the bot publicly. Always set `ALLOWED_USERS` to prevent abuse, resource exhaustion, and unauthorized scans from your container.
2.  **Cookie Safety**: If uploading session cookies to the `mint-social/cookies/` folder to bypass Instagram/Facebook rate limits, ensure your repository is **private** so your active session tokens are not exposed to the public.
3.  **Command Execution Safety**: All CLI interactions are executed via list-based argument passing (`subprocess.run(shell=False)`) coupled with regex whitelisting, entirely mitigating shell injection risks.