#!/usr/bin/env python3
"""
Protected Record Store Telegram Bot
All functions require authentication with password
"""

import logging
import os
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Import your existing modules
from auth import auth_manager, require_auth, create_auth_handlers, check_auth_middleware
from add_record import start_add_flow
from sales import start_sell_flow
from inventory import create_inventory_conversation
from db import init_db
import inventory as inventory_utils
import reports

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in environment variables")

def escape_markdown_v2(text: str) -> str:
    """
    Escape MarkdownV2 special characters
    """
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r"_*[]()~`>#+-=|{}.!\\"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

# === Protected Command Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - always accessible"""
    user = update.effective_user
    welcome_message = (
        f"🎵 *Welcome to the Record Store Bot\\!* 🎵\n\n"
        f"Hello {escape_markdown_v2(user.first_name)}\\!\n\n"
        f"🔒 *This bot is password protected\\.*\n"
        f"You must authenticate before using any commands\\.\n\n"
        f"*Commands:*\n"
        f"• /login \\- Enter password to authenticate\n"
        f"• /help \\- Show this help message\n\n"
        f"After authentication, you'll have access to:\n"
        f"• /add \\- Add new records to inventory\n"
        f"• /sell \\- Process record sales\n"
        f"• /inventory \\- Search and view inventory\n"
        f"• /reports \\- Generate sales reports\n"
        f"• /status \\- Check authentication status\n"
        f"• /logout \\- Sign out\n\n"
        f"🔐 *Use /login to get started\\!*"
    )
    
    await update.message.reply_text(welcome_message, parse_mode="MarkdownV2")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command - always accessible"""
    user_id = update.effective_user.id
    
    if auth_manager.is_authenticated(user_id):
        help_text = (
            "🎵 *Record Store Bot \\- Commands* 🎵\n\n"
            "*Inventory Management:*\n"
            "• /add \\- Add new records from Discogs\n"
            "• /inventory \\- Interactive inventory search\n"
            "• /stock \\- View low stock items\n\n"
            "*Sales:*\n"
            "• /sell \\- Process a sale\n"
            "• /sales \\- View recent sales\n\n"
            "*Reports:*\n"
            "• /reports \\- Generate sales reports\n"
            "• /daily \\- Today's sales summary\n"
            "• /weekly \\- Weekly sales report\n"
            "• /monthly \\- Monthly sales report\n\n"
            "*Account:*\n"
            "• /status \\- Check authentication status\n"
            "• /logout \\- Sign out\n"
            "• /users \\- View active users \\(admin\\)\n\n"
            "*General:*\n"
            "• /help \\- Show this help\n"
            "• /cancel \\- Cancel current operation"
        )
    else:
        help_text = (
            "🔒 *Authentication Required* 🔒\n\n"
            "*Available Commands:*\n"
            "• /login \\- Enter password to authenticate\n"
            "• /help \\- Show this help\n"
            "• /start \\- Welcome message\n\n"
            "*After authentication, you'll have access to:*\n"
            "• Inventory management\n"
            "• Sales processing\n"
            "• Report generation\n"
            "• And much more\\!\n\n"
            "🔐 *Use /login to get started\\!*"
        )
    
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")

@require_auth
async def recent_sales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent sales - requires authentication"""
    sales = reports.get_recent_sales(limit=10)
    
    if not sales:
        await update.message.reply_text("📊 No recent sales found\\.", parse_mode="MarkdownV2")
        return
    
    message = "💰 *Recent Sales*\n\n"
    for sale in sales:
        # Escape the artist_album field for MarkdownV2
        safe_artist_album = escape_markdown_v2(str(sale['artist_album']))
        safe_payment_method = escape_markdown_v2(str(sale['payment_method']))
        safe_date = escape_markdown_v2(str(sale['date']))
        price = sale['price_usd']
        
        message += (
            f"🎵 {safe_artist_album}\n"
            f"💰 ${price:.2f} \\({safe_payment_method}\\)\n"
            f"📅 {safe_date}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode="MarkdownV2")

@require_auth
async def daily_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate daily sales report - requires authentication"""
    try:
        report = reports.generate_daily_report()
        # Convert the report to MarkdownV2 if it's in Markdown v1
        # For now, let's use plain text to avoid parsing issues
        await update.message.reply_text(report)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating daily report: {escape_markdown_v2(str(e))}", parse_mode="MarkdownV2")

@require_auth
async def weekly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate weekly sales report - requires authentication"""
    try:
        report = reports.generate_weekly_report()
        # Convert the report to MarkdownV2 if it's in Markdown v1
        # For now, let's use plain text to avoid parsing issues
        await update.message.reply_text(report)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating weekly report: {escape_markdown_v2(str(e))}", parse_mode="MarkdownV2")

@require_auth
async def monthly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate monthly sales report - requires authentication"""
    try:
        report = reports.generate_monthly_report()
        # Convert the report to MarkdownV2 if it's in Markdown v1
        # For now, let's use plain text to avoid parsing issues
        await update.message.reply_text(report)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating monthly report: {escape_markdown_v2(str(e))}", parse_mode="MarkdownV2")

async def unauthorized_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages from unauthorized users"""
    if not await check_auth_middleware(update, context):
        return  # Auth check already sent the denial message

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Exception while handling an update: {context.error}")

def main():
    """Main function to run the bot"""
    # Ensure required tables exist
    init_db()
    reports.init_report_db()
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add authentication handlers (these don't require auth)
    auth_handlers = create_auth_handlers()
    for handler in auth_handlers:
        application.add_handler(handler)
    
    # Add always-accessible commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Add protected command handlers
    application.add_handler(CommandHandler("sales", recent_sales))
    application.add_handler(CommandHandler("daily", daily_report))
    application.add_handler(CommandHandler("weekly", weekly_report))
    application.add_handler(CommandHandler("monthly", monthly_report))
    
    # Add conversation handlers (these have their own auth checks)
    application.add_handler(start_add_flow())
    application.add_handler(start_sell_flow())
    application.add_handler(create_inventory_conversation())
    
    # Add fallback handler for unauthorized access
    application.add_handler(MessageHandler(filters.ALL, unauthorized_handler))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Cleanup expired sessions on startup
    auth_manager.cleanup_expired_sessions()
    
    # Start the bot
    logger.info("🤖 Starting protected record store bot...")
    logger.info(f"🔒 Session timeout: {os.getenv('SESSION_TIMEOUT_HOURS', '24')} hours")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()