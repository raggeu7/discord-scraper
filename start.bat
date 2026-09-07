@echo off
setlocal
title Discord Scraper Bot

if "%DISCORD_TOKEN%"=="" (
  echo ERROR: Set DISCORD_TOKEN before starting the bot.
  echo Example: set DISCORD_TOKEN=your_bot_token
  pause
  exit /b 1
)

python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py
pause