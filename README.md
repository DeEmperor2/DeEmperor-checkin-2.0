# DeEmperor Checkin 2.0

A Python Telegram productivity bot for schedules, reminders, check-ins, streaks, goals, quotes, and weekly progress reports.

## Deployment Notes

Set these environment variables in Railway or your deployment platform:

```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=your_postgres_database_url
```

The project uses `requirements.txt` for Python dependencies and `Procfile` for the worker start command:

```Procfile
worker: python bot.py
```

Do not commit `.env` or real secrets.
