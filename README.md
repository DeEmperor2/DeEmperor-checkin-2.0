# Telegram Productivity Bot

A Python Telegram bot that uses scheduled reminders, check-ins, quotes, and PostgreSQL-backed storage.

## Features

- Telegram command handling with `python-telegram-bot`
- Scheduled jobs with APScheduler
- PostgreSQL database support with `psycopg2`
- Environment-based configuration for secrets
- Africa/Lagos timezone scheduling

## Requirements

- Python 3.10+
- Telegram bot token from BotFather
- PostgreSQL database URL

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file locally:

```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=your_postgres_database_url
```

3. Run the bot:

```bash
python bot.py
```

## Deployment

The project includes a `Procfile` for worker-based deployment:

```Procfile
worker: python bot.py
```

Set `BOT_TOKEN` and `DATABASE_URL` as environment variables in the deployment platform. Do not commit `.env` files or real secrets.

## Security Note

This repository intentionally excludes `.env` from version control. Keep bot tokens, database credentials, and other secrets private.
