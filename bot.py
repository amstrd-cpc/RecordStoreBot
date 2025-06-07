# bot.py
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
from reports import report_handler
from inventory import has_record

# === BOT TOKEN ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")  # Use .env or hardcode

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

# === Main App Setup ===
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Core Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(inventory_handler())          # /inventory
    app.add_handler(report_handler())             # /report
    app.add_handlers(start_add_flow())            # /add
    app.add_handlers(start_sell_flow())           # /sell

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
# This is the main entry point for the bot.