# bot.py
import logging
from telegram.ext import ApplicationBuilder, CommandHandler

from add_record import start_add_flow
from sales import start_sell_flow
from reports import report_handler
from inventory import load_inventory

from telegram import Update
from telegram.ext import ContextTypes


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎶 Welcome to Record Store Bot!\n\n"
        "Available commands:\n"
        "/inventory - View stock\n"
        "/add - Add vinyl via Discogs\n"
        "/sell - Sell vinyls to customer\n"
        "/report - Generate daily Excel report"
    )

# /inventory command
async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = load_inventory()
    if not records:
        await update.message.reply_text("📦 Inventory is empty.")
        return
    for rec in records[:20]:  # limit to 20
        msg = (
            f"🎵 {rec['Artist - Album']}\n"
            f"Format: {rec.get('Format', 'N/A')}\n"
            f"Condition: {rec['Condition']}\n"
            f"Price: ${rec['USD Price']}"
        )
        await update.message.reply_text(msg)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("inventory", inventory))
    app.add_handler(report_handler())                  # /report
    app.add_handlers(start_add_flow())                 # /add
    app.add_handlers(start_sell_flow())                # /sell

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
