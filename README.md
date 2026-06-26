<h1 align="center">MINT — Telegram Bot Command Center</h1>

<p align="center">
  <a href="https://railway.app/template/deploy"><img src="https://railway.app/button.svg" alt="Deploy on Railway"></a>
  <a href="https://github.com/sayfalse/oscstbot/blob/main/LICENSE"><img src="https://img.shields.io/github/license/sayfalse/oscstbot?color=7fd88f" alt="License"></a>
  <img src="https://img.shields.io/badge/platform-Docker%20%7C%20Railway%20%7C%20Linux%20%7C%20macOS%20%7C%20Windows-7fd88f" alt="Platform">
</p>

<p align="center">
  <strong>MINT Telegram Bot</strong> is a secure, interactive conversational command center that wraps industry-standard OSINT (Open Source Intelligence) engines and a social media archiver into a single, cohesive Telegram bot interface. Optimized for containerized deployment on Railway.com, it allows security researchers, analysts, and developers to trigger scans and media downloads directly from any Telegram chat using a clean, state-based inline keyboard wizard.
</p>

---

## Table of Contents
- [Key Features](#key-features)
- [Integrated Engines](#integrated-engines)
- [Railway.com Deployment](#railwaycom-deployment)
- [Interactive Inline Menu Flow](#interactive-inline-menu-flow)
- [Environment Variables](#environment-variables)
- [Local Development & Testing](#local-development--testing)
  - [Prerequisites](#prerequisites)
  - [Local Installation](#local-installation)
  - [Running Unit Tests](#running-unit-tests)
  - [Starting the Bot](#starting-the-bot)
- [Directory Layout](#directory-layout)
- [Security & Access Control](#security--access-control)

---

## Key Features

* **Interactive Inline Menu:** Navigate all OSINT scanners and media downloaders using interactive buttons and a state-based wizard, eliminating the need to type manual slash commands.
* **Access Control List (ACL):** Restrict bot execution exclusively to whitelisted Telegram User IDs. Unauthorized attempts are rejected automatically.
* **Input Sanitization:** All user inputs (usernames, emails, and URLs) are validated against strict whitelist regular expressions, blocking shell metacharacters and injection vectors.
* **MINT Social Downloader Suite:** 
  * **Direct Downloader:** Extract photos, videos, and multi-post carousels from Instagram, TikTok, Facebook, and X (Twitter) using integrated `gallery-dl` and `yt-dlp` engines.
  * **Cookie & UA Management:** Automatically loads session cookies from the `cookies/` folder and applies custom User-Agents and request sleep intervals to prevent rate limits and blocks.
  * **Batch Downloader:** Add targets to platform subscription lists, download updates using built-in archives, and automatically receive only new media via folder diff monitoring.
* **Smart Document Overflow:** Long scan results exceeding Telegram’s 4,000-character message limit are automatically written to a text file and uploaded as a document.
* **Host Status Monitor:** Check container health, host platform, Python version, and active disk space allocation directly from the chat.

---

## Integrated Engines

MINT Telegram Bot aggregates and configures the following engines inside the container:

| Engine | Purpose | Capabilities | Source |
| :--- | :--- | :--- | :--- |
| **Sherlock** | Username Intelligence | Scans 300+ social platforms simultaneously to locate accounts. | [sherlock-project/sherlock](https://github.com/sherlock-project/sherlock) |
| **Holehe** | Email Reconnaissance | Checks registration status on 120+ sites via password recovery endpoints. | [megadose/holehe](https://github.com/megadose/holehe) |
| **Toutatis** | Instagram Metadata | Extracts associated public emails, phone numbers, and profile details. | [megadose/toutatis](https://github.com/megadose/toutatis) |
| **MINT Social Tool** | Media Archiving | High-speed, interactive backup engine for Instagram, TikTok, Facebook, and X (Twitter). Powered by `gallery-dl` & `yt-dlp`. | *Built-in* |

---

## Railway.com Deployment

This repository is pre-configured with a `Dockerfile` and automated setup scripts that provision the container and download all required OSINT tools during the image build phase.

1. Create a bot and obtain an API token from [@BotFather](https://t.me/BotFather) on Telegram.
2. Obtain your numerical Telegram User ID from [@userinfobot](https://t.me/userinfobot) to secure your bot.
3. Log in to [Railway.com](https://railway.com/).
4. Click **New Project** -> **Deploy from GitHub repo**, and select your `oscstbot` repository.
5. Configure the required environment variables in the **Variables** tab (see [Environment Variables](#environment-variables)).
6. Click **Deploy**. Railway will build the container, install system packages (Git, FFmpeg), clone the sub-tools, and launch the bot polling service.

---

## Interactive Inline Menu Flow

When you send a message or run `/start`, the bot presents the main interactive menu:

```
🌿 MINT OSINT & Media Command Center Bot 🌿

Select a tool from the interactive menu below to begin:
[🔍 Sherlock Scan]     [🔮 Holehe Check]
[📸 Toutatis Instagram] [📥 MINT Social Tool]
[📊 Bot Status]
```

Clicking a button prompts the bot to ask you for the target input (username, email, or URL). Once you reply, the bot executes the corresponding command and sends the output or downloaded files directly into your chat, resetting your active state automatically.

---

## Environment Variables

Configure these variables in your deployment environment (such as the Railway dashboard or your local `.env` file):

| Variable | Required | Description | Example |
| :--- | :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | **Yes** | The API token obtained from Telegram's BotFather. | `123456:ABC-DEF1234ghIkl-zyx57...` |
| `ALLOWED_USERS` | No | Comma-separated list of Telegram User IDs allowed to use the bot. If empty, the bot is public. | `987654321,123456789` |

---

## Local Development & Testing

### Prerequisites
Ensure you have the following installed on your local host system:
* Python 3.10+
* Git
* FFmpeg (required by `yt-dlp` and `gallery-dl` for video stream extraction)

### Local Installation
```bash
git clone https://github.com/sayfalse/oscstbot.git
cd oscstbot
pip install -r requirements.txt
```

### Running Unit Tests
Execute the unit test suite to verify input sanitization, ANSI stripping, and access control:
```bash
# Windows
$env:TELEGRAM_BOT_TOKEN="12345:dummy"; python -m unittest test_bot.py

# Linux/macOS
TELEGRAM_BOT_TOKEN="12345:dummy" python3 -m unittest test_bot.py
```

### Starting the Bot
```bash
# Windows
$env:TELEGRAM_BOT_TOKEN="your_token_here"; $env:ALLOWED_USERS="your_id_here"; python bot.py

# Linux/macOS
TELEGRAM_BOT_TOKEN="your_token_here" ALLOWED_USERS="your_id_here" python3 bot.py
```

---

## Directory Layout

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

## Security & Access Control

* **Access Control Whitelisting:** Running OSINT scans and media downloads consumes significant system resources. Always configure the `ALLOWED_USERS` variable to prevent unauthorized third parties from abusing your container resources.
* **Cookie Safety:** If you place session cookies in the `mint-social/cookies/` folder to bypass Instagram/Facebook rate limits, ensure your repository is **private** to prevent exposing your active session tokens.
* **Command Execution:** All CLI interactions are executed via list-based argument passing (`subprocess.run(shell=False)`) coupled with regex whitelisting, entirely mitigating shell injection risks.