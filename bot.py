from dotenv import load_dotenv
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, 
    MessageHandler, filters
)
import datetime
import os
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN:
    raise ValueError("BOT_TOKEN not found!")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found!")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize scheduler
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Africa/Lagos'))
telegram_app = None

# Database connection
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# Initialize database
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        created_at TIMESTAMP
    )''')
    
    # Check-ins table
    c.execute('''CREATE TABLE IF NOT EXISTS checkins (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        task TEXT,
        timestamp TEXT,
        date TEXT,
        photo_path TEXT
    )''')
    
    # Schedules table
    c.execute('''CREATE TABLE IF NOT EXISTS schedules (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        date TEXT,
        time TEXT,
        task TEXT,
        emoji TEXT
    )''')
    
    # Quotes table
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (
        id SERIAL PRIMARY KEY,
        quote TEXT,
        active INTEGER DEFAULT 1
    )''')
    
    # Streaks table
    c.execute('''CREATE TABLE IF NOT EXISTS streaks (
        user_id BIGINT PRIMARY KEY,
        current_streak INTEGER DEFAULT 0,
        longest_streak INTEGER DEFAULT 0,
        last_checkin_date TEXT
    )''')
    
    # Goals table
    c.execute('''CREATE TABLE IF NOT EXISTS goals (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        goal TEXT,
        target_date TEXT,
        completed INTEGER DEFAULT 0,
        created_at TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# Initialize quotes
def init_quotes():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM quotes")
    count = c.fetchone()['count']
    
    if count == 0:
        quotes = [
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Success is not final, failure is not fatal: it is the courage to continue that counts. - Winston Churchill",
            "Believe you can and you're halfway there. - Theodore Roosevelt",
            "Don't watch the clock; do what it does. Keep going. - Sam Levenson",
            "The future belongs to those who believe in the beauty of their dreams. - Eleanor Roosevelt",
            "Push yourself, because no one else is going to do it for you.",
            "Great things never come from comfort zones.",
            "Dream it. Wish it. Do it.",
            "Wake up with determination. Go to bed with satisfaction.",
            "Do something today that your future self will thank you for."
        ]
        
        for quote in quotes:
            c.execute("INSERT INTO quotes (quote, active) VALUES (%s, 1)", (quote,))
        
        conn.commit()
        logger.info("Initialized 10 starter quotes")
    
    conn.close()

# Get random quote
def get_random_quote():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT quote FROM quotes WHERE active = 1")
    quotes = c.fetchall()
    conn.close()
    
    if quotes:
        return random.choice(quotes)['quote']
    return "You've got this! 💪"

# Update streak
def update_streak(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    
    c.execute("SELECT current_streak, longest_streak, last_checkin_date FROM streaks WHERE user_id = %s", (user_id,))
    result = c.fetchone()
    
    if result:
        current = result['current_streak']
        longest = result['longest_streak']
        last_date = result['last_checkin_date']
        
        if last_date == today:
            conn.close()
            return current, longest
        
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        
        if last_date == yesterday:
            current += 1
        else:
            current = 1
        
        longest = max(current, longest)
        c.execute("UPDATE streaks SET current_streak = %s, longest_streak = %s, last_checkin_date = %s WHERE user_id = %s",
                  (current, longest, today, user_id))
    else:
        current, longest = 1, 1
        c.execute("INSERT INTO streaks (user_id, current_streak, longest_streak, last_checkin_date) VALUES (%s, %s, %s, %s)",
                  (user_id, current, longest, today))
    
    conn.commit()
    conn.close()
    return current, longest

# Register user
def register_user(user_id, username):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO users (user_id, username, created_at) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING",
              (user_id, username, datetime.datetime.now()))
    conn.commit()
    conn.close()

# COMMAND HANDLERS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "User"
    register_user(user_id, username)
    
    await update.message.reply_text(
        f"👑 Welcome to DeEmperor Checkin, {username}!\n\n"
        "🔥 I'll help you dominate your day with:\n"
        "• Automated reminders (5 mins before tasks)\n"
        "• Motivational quotes\n"
        "• Streak tracking\n"
        "• Goal management\n"
        "• Progress reports\n\n"
        "📋 Commands:\n"
        "/schedule - View today's schedule\n"
        "/editschedule - Edit tomorrow's schedule\n"
        "/checkin - Mark task complete\n"
        "/progress - View your progress\n"
        "/streak - Check your streak 🔥\n"
        "/goals - Manage your goals\n"
        "/quotes - Manage motivational quotes\n"
        "/weeklyreport - Get weekly summary\n"
        "/help - Show all commands"
    )

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.date.today().isoformat()
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT time, task, emoji FROM schedules WHERE user_id = %s AND date = %s ORDER BY time",
              (user_id, today))
    schedule_items = c.fetchall()
    conn.close()
    
    if not schedule_items:
        await update.message.reply_text(
            "📅 No schedule set for today!\n\n"
            "Use /editschedule to create tomorrow's schedule."
        )
        return
    
    now = datetime.datetime.now()
    current_time = now.strftime("%I:%M %p")
    
    message = f"📅 Today's Schedule ({current_time})\n\n"
    for item in schedule_items:
        message += f"{item['time']}: {item['emoji']} {item['task']}\n"
    
    message += "\n💡 Tip: Use /checkin <task> to mark complete!"
    await update.message.reply_text(message)

async def editschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 Edit Tomorrow's Schedule\n\n"
        "Send your schedule in this format:\n"
        "```\n"
        "6:30 AM | 🏋️ | Workout\n"
        "7:00 AM | 🗣️ | Duolingo\n"
        "9:00 AM | 💼 | Work\n"
        "```\n\n"
        "Each line: TIME | EMOJI | TASK\n"
        "Send /done when finished.",
        parse_mode='Markdown'
    )
    context.user_data['editing_schedule'] = True

async def done_editing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('editing_schedule'):
        context.user_data['editing_schedule'] = False
        await update.message.reply_text("✅ Schedule editing complete! Tomorrow's schedule is set.")

async def handle_schedule_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('editing_schedule'):
        return
    
    user_id = update.effective_user.id
    text = update.message.text
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    
    try:
        parts = text.split('|')
        if len(parts) != 3:
            await update.message.reply_text("❌ Format: TIME | EMOJI | TASK")
            return
        
        time_str = parts[0].strip()
        emoji = parts[1].strip()
        task = parts[2].strip()
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO schedules (user_id, date, time, task, emoji) VALUES (%s, %s, %s, %s, %s)",
                  (user_id, tomorrow, time_str, task, emoji))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Added: {time_str} {emoji} {task}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "Please specify what you completed!\n"
            "Example: /checkin workout\n\n"
            "Or send a photo with caption: /checkin workout"
        )
        return
    
    task = " ".join(context.args).lower()
    today = datetime.date.today().isoformat()
    timestamp = datetime.datetime.now().strftime("%I:%M %p")
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO checkins (user_id, task, timestamp, date, photo_path) VALUES (%s, %s, %s, %s, %s)",
              (user_id, task, timestamp, today, None))
    conn.commit()
    conn.close()
    
    current, longest = update_streak(user_id)
    quote = get_random_quote()
    
    await update.message.reply_text(
        f"✅ Great job! Marked '{task}' as complete at {timestamp}\n\n"
        f"🔥 Current Streak: {current} days\n"
        f"🏆 Longest Streak: {longest} days\n\n"
        f"💭 {quote}"
    )

async def handle_photo_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.caption or not update.message.caption.startswith('/checkin'):
        return
    
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    
    photo_path = f"photos/{user_id}_{datetime.datetime.now().timestamp()}.jpg"
    os.makedirs("photos", exist_ok=True)
    await file.download_to_drive(photo_path)
    
    caption_parts = update.message.caption.split(maxsplit=1)
    task = caption_parts[1] if len(caption_parts) > 1 else "task"
    
    today = datetime.date.today().isoformat()
    timestamp = datetime.datetime.now().strftime("%I:%M %p")
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO checkins (user_id, task, timestamp, date, photo_path) VALUES (%s, %s, %s, %s, %s)",
              (user_id, task, timestamp, today, photo_path))
    conn.commit()
    conn.close()
    
    current, longest = update_streak(user_id)
    quote = get_random_quote()
    
    await update.message.reply_text(
        f"📸 Photo check-in complete for '{task}'!\n\n"
        f"🔥 Streak: {current} days | 🏆 Best: {longest} days\n\n"
        f"💭 {quote}"
    )

async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.date.today().isoformat()
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT task, timestamp FROM checkins WHERE user_id = %s AND date = %s ORDER BY timestamp",
              (user_id, today))
    checkins = c.fetchall()
    conn.close()
    
    if not checkins:
        await update.message.reply_text(
            "📊 No check-ins yet today!\n\n"
            "Use /checkin <task> to log completed tasks."
        )
        return
    
    message = f"📊 Today's Progress ({len(checkins)} tasks)\n\n"
    for i, item in enumerate(checkins, 1):
        message += f"{i}. ✅ {item['task']} at {item['timestamp']}\n"
    
    message += "\n🔥 Keep crushing it!"
    await update.message.reply_text(message)

async def streak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT current_streak, longest_streak FROM streaks WHERE user_id = %s", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        current = result['current_streak']
        longest = result['longest_streak']
        message = (
            f"🔥 Your Streak Stats:\n\n"
            f"Current Streak: {current} days\n"
            f"Longest Streak: {longest} days\n\n"
        )
        
        if current >= 30:
            message += "👑 LEGENDARY! 30-day streak!"
        elif current >= 7:
            message += "🏆 You're on fire! Week streak!"
        else:
            message += "💪 Keep going!"
    else:
        message = "Start your streak with /checkin!"
    
    await update.message.reply_text(message)

async def goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, goal, target_date, completed FROM goals WHERE user_id = %s ORDER BY target_date",
                  (user_id,))
        goals_list = c.fetchall()
        conn.close()
        
        if not goals_list:
            await update.message.reply_text(
                "🎯 No goals set yet!\n\n"
                "Add a goal:\n"
                "/goals add <goal> | <target_date>\n\n"
                "Example:\n"
                "/goals add Learn Python | 2024-12-31"
            )
            return
        
        message = "🎯 Your Goals:\n\n"
        for item in goals_list:
            status = "✅" if item['completed'] else "⏳"
            message += f"{status} {item['goal']} (by {item['target_date']})\n"
        
        message += "\n💡 Commands:\n"
        message += "/goals add <goal> | <date>\n"
        message += "/goals complete <id>\n"
        message += "/goals delete <id>"
        
        await update.message.reply_text(message)
        return
    
    action = context.args[0].lower()
    
    if action == "add":
        text = " ".join(context.args[1:])
        if '|' not in text:
            await update.message.reply_text("Format: /goals add <goal> | <YYYY-MM-DD>")
            return
        
        goal_text, target_date = text.split('|', 1)
        goal_text = goal_text.strip()
        target_date = target_date.strip()
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO goals (user_id, goal, target_date, completed, created_at) VALUES (%s, %s, %s, 0, %s)",
                  (user_id, goal_text, target_date, datetime.datetime.now()))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"🎯 Goal added: {goal_text}\nTarget: {target_date}")
    
    elif action == "complete" and len(context.args) > 1:
        goal_id = context.args[1]
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE goals SET completed = 1 WHERE id = %s AND user_id = %s", (goal_id, user_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"🎉 Goal #{goal_id} marked complete!")
    
    elif action == "delete" and len(context.args) > 1:
        goal_id = context.args[1]
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM goals WHERE id = %s AND user_id = %s", (goal_id, user_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"🗑️ Goal #{goal_id} deleted")

async def quotes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, quote, active FROM quotes ORDER BY id")
        quotes_list = c.fetchall()
        conn.close()
        
        message = "💭 Motivational Quotes:\n\n"
        for item in quotes_list:
            status = "✅" if item['active'] else "❌"
            message += f"{item['id']}. {status} {item['quote']}\n\n"
        
        message += "Commands:\n"
        message += "/quotes add <your quote>\n"
        message += "/quotes remove <id>\n"
        message += "/quotes activate <id>\n"
        message += "/quotes random"
        
        await update.message.reply_text(message)
        return
    
    action = context.args[0].lower()
    
    if action == "add":
        quote_text = " ".join(context.args[1:])
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO quotes (quote, active) VALUES (%s, 1)", (quote_text,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Quote added: {quote_text}")
    
    elif action == "remove" and len(context.args) > 1:
        quote_id = context.args[1]
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE quotes SET active = 0 WHERE id = %s", (quote_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"❌ Quote #{quote_id} deactivated")
    
    elif action == "activate" and len(context.args) > 1:
        quote_id = context.args[1]
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE quotes SET active = 1 WHERE id = %s", (quote_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Quote #{quote_id} activated")
    
    elif action == "random":
        quote = get_random_quote()
        await update.message.reply_text(f"💭 {quote}")

async def weeklyreport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    today = datetime.date.today().isoformat()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) as count FROM checkins WHERE user_id = %s AND date >= %s AND date <= %s",
              (user_id, week_ago, today))
    total_checkins = c.fetchone()['count']
    
    c.execute("SELECT COUNT(DISTINCT date) as count FROM checkins WHERE user_id = %s AND date >= %s AND date <= %s",
              (user_id, week_ago, today))
    active_days = c.fetchone()['count']
    
    c.execute("SELECT current_streak, longest_streak FROM streaks WHERE user_id = %s", (user_id,))
    streak_result = c.fetchone()
    
    conn.close()
    
    current_streak = streak_result['current_streak'] if streak_result else 0
    longest_streak = streak_result['longest_streak'] if streak_result else 0
    
    message = (
        f"📊 Weekly Report (Last 7 Days)\n\n"
        f"✅ Total Check-ins: {total_checkins}\n"
        f"📅 Active Days: {active_days}/7\n"
        f"🔥 Current Streak: {current_streak} days\n"
        f"🏆 Longest Streak: {longest_streak} days\n\n"
        f"Keep pushing forward! 💪"
    )
    
    await update.message.reply_text(message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# SCHEDULED REMINDERS

async def send_reminder(user_id, task, emoji):
    try:
        quote = get_random_quote()
        message = (
            f"⏰ Reminder: {emoji} {task} starts in 5 minutes!\n\n"
            f"💭 {quote}"
        )
        await telegram_app.bot.send_message(chat_id=user_id, text=message)
    except Exception as e:
        logger.error(f"Error sending reminder: {e}")

async def send_night_reminder():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT user_id FROM users")
    users = c.fetchall()
    conn.close()
    
    quote = get_random_quote()
    message = (
        f"🌙 Good evening!\n\n"
        f"Time to plan tomorrow's schedule.\n"
        f"Use /editschedule to set it up.\n\n"
        f"💭 {quote}"
    )
    
    for item in users:
        try:
            await telegram_app.bot.send_message(chat_id=item['user_id'], text=message)
        except Exception as e:
            logger.error(f"Error sending night reminder to {item['user_id']}: {e}")

def schedule_user_reminders():
    conn = get_db_connection()
    c = conn.cursor()
    
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    c.execute("SELECT user_id, time, task, emoji FROM schedules WHERE date = %s", (tomorrow,))
    schedules = c.fetchall()
    conn.close()
    
    for item in schedules:
        try:
            time_obj = datetime.datetime.strptime(item['time'], "%I:%M %p").time()
            reminder_time = (datetime.datetime.combine(datetime.date.today(), time_obj) - 
                           datetime.timedelta(minutes=5)).time()
            
            scheduler.add_job(
                send_reminder,
                CronTrigger(hour=reminder_time.hour, minute=reminder_time.minute),
                args=[item['user_id'], item['task'], item['emoji']],
                id=f"reminder_{item['user_id']}_{item['task']}_{tomorrow}",
                replace_existing=True
            )
            logger.info(f"Scheduled reminder for {item['user_id']}: {item['task']} at {reminder_time}")
            
        except Exception as e:
            logger.error(f"Error scheduling reminder: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

def main():
    global telegram_app
    
    init_db()
    init_quotes()
    
    telegram_app = ApplicationBuilder().token(TOKEN).build()
    
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("schedule", schedule))
    telegram_app.add_handler(CommandHandler("editschedule", editschedule))
    telegram_app.add_handler(CommandHandler("done", done_editing))
    telegram_app.add_handler(CommandHandler("checkin", checkin))
    telegram_app.add_handler(CommandHandler("progress", progress))
    telegram_app.add_handler(CommandHandler("streak", streak_command))
    telegram_app.add_handler(CommandHandler("goals", goals))
    telegram_app.add_handler(CommandHandler("quotes", quotes_command))
    telegram_app.add_handler(CommandHandler("weeklyreport", weeklyreport))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo_checkin))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_schedule_input))
    telegram_app.add_error_handler(error_handler)
    
    scheduler.add_job(send_night_reminder, CronTrigger(hour=21, minute=0), id="night_reminder")
    scheduler.add_job(schedule_user_reminders, CronTrigger(hour=0, minute=1), id="refresh_reminders")
    scheduler.start()
    
    logger.info("Bot started successfully with PostgreSQL!")
    telegram_app.run_polling()

if __name__ == "__main__":
    main()