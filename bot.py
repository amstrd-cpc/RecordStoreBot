# bot.py — Fixed version with proper handler setup and SQLite integration
import os
import logging
from telegram import Update
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from add_record import start_add_flow
from sales import start_sell_flow
from reports import report_handler, init_report_db
from inventory import has_record
from db import init_db

# === Load environment and bot token ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in .env or environment variables.")

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === /start Command ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎶 Welcome to Record Store Bot!\n\n"
        "Available commands:\n"
        "/inventory - Check if a record is in stock\n"
        "/add - Add vinyl via Discogs\n"
        "/sell - Sell vinyls to customer\n"
        "/report - Generate daily Excel report"
    )

# === /inventory Command ===
INVENTORY_QUERY = range(1)

async def inventory_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Enter the artist or album name to check:")
    return INVENTORY_QUERY

async def handle_inventory_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    found = has_record(name)
    if found:
        await update.message.reply_text(f"✅ Yes, we have something matching: *{name}*", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ No match found for: *{name}*", parse_mode="Markdown")
    return ConversationHandler.END

def inventory_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("inventory", inventory_start)],
        states={
            INVENTORY_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inventory_query)]
        },
        fallbacks=[],
        name="inventory_check",
        persistent=False
    )

# === Fallback handlers ===
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Unknown command. Use /start to see available commands.")

async def handle_text_without_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please use a command. Type /start to see available commands.")

async def handle_other_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I can only process text commands. Use /start to see available commands.")

# === Error handler ===
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# === Main Bot App ===
def main():
    # Initialize databases
    print("🔧 Initializing databases...")
    init_db()
    init_report_db()
    print("✅ Databases initialized")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register conversation handlers first (they have priority)
    app.add_handler(inventory_handler())
    app.add_handler(start_add_flow())
    app.add_handler(start_sell_flow())
    
    # Register simple command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(report_handler())
    
    # Register fallback handlers (these should be last)
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_without_command))
    app.add_handler(MessageHandler(filters.ALL, handle_other_content))
    
    # Add error handler
    app.add_error_handler(error_handler)

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()