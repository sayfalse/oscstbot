# Use official Python 3.10 slim image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    gcc \
    g++ \
    libffi-dev \
    make \
    curl \
    libxml2-dev \
    libxslt1-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . /app/

# Run the non-interactive setup script to download OSINT tools (Sherlock, Holehe, Toutatis)
# and install their individual dependencies during the container build process
RUN python setup_noninteractive.py

# Expose no ports since the Telegram bot runs in long-polling mode (outgoing connections only)
# This keeps the container highly secure and free of open-port vulnerabilities

# Set the entrypoint command to run the Telegram bot
CMD ["python", "bot.py"]
