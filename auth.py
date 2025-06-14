# auth.py - Authentication system for the bot
import hashlib
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, ConversationHandler, filters
from db import get_db
from dotenv import load_dotenv

load_dotenv()

# Get password from environment variable
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "your_default_password_here")
SESSION_TIMEOUT_HOURS = int(os.getenv("SESSION_TIMEOUT_HOURS", "24"))  # Default 24 hours

# Conversation state
WAITING_FOR_PASSWORD = 0

class AuthManager:
    def __init__(self):
        self.authenticated_users = {}  # user_id: expiry_time
        self.setup_auth_db()
    
    def setup_auth_db(self):
        """Create authentication tracking table"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    authenticated_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    last_activity TIMESTAMP
                )
            """)
            conn.commit()
    
    def hash_password(self, password):
        """Hash password with salt"""
        salt = "your_unique_salt_here_change_this"
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def verify_password(self, input_password):
        """Verify if the input password is correct"""
        return self.hash_password(input_password) == self.hash_password(BOT_PASSWORD)
    
    def authenticate_user(self, user_id, username=None, first_name=None):
        """Authenticate a user and create session"""
        expiry_time = datetime.now() + timedelta(hours=SESSION_TIMEOUT_HOURS)
        self.authenticated_users[user_id] = expiry_time
        
        # Store in database
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_sessions 
                (user_id, username, first_name, authenticated_at, expires_at, last_activity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id, username, first_name,
                datetime.now(), expiry_time, datetime.now()
            ))
            conn.commit()
        
        return True
    
    def is_authenticated(self, user_id):
        """Check if user is authenticated and session is valid"""
        # Check memory first
        if user_id in self.authenticated_users:
            if datetime.now() < self.authenticated_users[user_id]:
                self.update_last_activity(user_id)
                return True
            else:
                # Session expired, remove from memory
                del self.authenticated_users[user_id]
        
        # Check database
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT expires_at FROM user_sessions 
                WHERE user_id = ? AND expires_at > ?
            """, (user_id, datetime.now()))
            
            result = cursor.fetchone()
            if result:
                # Update memory cache
                expiry_time = datetime.fromisoformat(result[0])
                self.authenticated_users[user_id] = expiry_time
                self.update_last_activity(user_id)
                return True
        
        return False
    
    def update_last_activity(self, user_id):
        """Update user's last activity timestamp"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_sessions 
                SET last_activity = ? 
                WHERE user_id = ?
            """, (datetime.now(), user_id))
            conn.commit()
    
    def logout_user(self, user_id):
        """Logout a user (remove authentication)"""
        if user_id in self.authenticated_users:
            del self.authenticated_users[user_id]
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
            conn.commit()
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions from database"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_sessions WHERE expires_at < ?", (datetime.now(),))
            conn.commit()
    
    def get_active_users(self):
        """Get list of currently authenticated users"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, first_name, authenticated_at, last_activity 
                FROM user_sessions 
                WHERE expires_at > ?
                ORDER BY last_activity DESC
            """, (datetime.now(),))
            return cursor.fetchall()

# Global auth manager instance
auth_manager = AuthManager()

def require_auth(func):
    """Decorator to require authentication for bot commands"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if not auth_manager.is_authenticated(user_id):
            await update.message.reply_text(
                "🔒 Access Denied!\n\n"
                "You need to authenticate first.\n"
                "Use /login to enter the password."
            )
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper

# Authentication handlers
async def start_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the login process"""
    user_id = update.effective_user.id
    
    # Check if already authenticated
    if auth_manager.is_authenticated(user_id):
        await update.message.reply_text(
            "✅ You are already authenticated!\n"
            f"Session expires in: {auth_manager.authenticated_users[user_id] - datetime.now()}\n\n"
            "Use /logout to sign out or /help to see available commands."
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🔐 **Authentication Required**\n\n"
        "Please enter the bot password:",
        parse_mode="Markdown"
    )
    return WAITING_FOR_PASSWORD

async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle password input"""
    password = update.message.text.strip()
    user = update.effective_user
    
    # Delete the message containing the password for security
    try:
        await update.message.delete()
    except:
        pass
    
    if auth_manager.verify_password(password):
        # Authenticate user
        auth_manager.authenticate_user(user.id, user.username, user.first_name)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ **Authentication Successful!**\n\n"
                 f"Welcome, {user.first_name}!\n"
                 f"Session expires in {SESSION_TIMEOUT_HOURS} hours.\n\n"
                 f"You can now use all bot commands.\n"
                 f"Type /help to see available commands.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ **Incorrect Password!**\n\n"
                 "Access denied. Please try again with /login",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

async def logout_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logout the current user"""
    user_id = update.effective_user.id
    
    if auth_manager.is_authenticated(user_id):
        auth_manager.logout_user(user_id)
        await update.message.reply_text(
            "✅ **Logged Out Successfully**\n\n"
            "You have been signed out of the bot.\n"
            "Use /login to authenticate again."
        )
    else:
        await update.message.reply_text(
            "ℹ️ You are not currently logged in.\n"
            "Use /login to authenticate."
        )

async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show authentication status"""
    user_id = update.effective_user.id
    
    if auth_manager.is_authenticated(user_id):
        expiry = auth_manager.authenticated_users[user_id]
        time_left = expiry - datetime.now()
        
        await update.message.reply_text(
            f"✅ **Authentication Status: ACTIVE**\n\n"
            f"Session expires in: {time_left}\n"
            f"Use /logout to sign out."
        )
    else:
        await update.message.reply_text(
            "❌ **Authentication Status: NOT AUTHENTICATED**\n\n"
            "Use /login to enter the password."
        )

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active users (admin command)"""
    user_id = update.effective_user.id
    
    if not auth_manager.is_authenticated(user_id):
        await update.message.reply_text("🔒 Authentication required!")
        return
    
    active_users = auth_manager.get_active_users()
    
    if not active_users:
        await update.message.reply_text("No active users.")
        return
    
    message = "👥 **Active Users:**\n\n"
    for user_data in active_users:
        user_id, username, first_name, auth_time, last_activity = user_data
        username_str = f"@{username}" if username else "No username"
        message += f"• {first_name} ({username_str})\n"
        message += f"  ID: {user_id}\n"
        message += f"  Last active: {last_activity}\n\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def cancel_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel login process"""
    await update.message.reply_text("🚫 Login cancelled.")
    return ConversationHandler.END

# Authentication conversation handler
def create_auth_handlers():
    """Create authentication-related handlers"""
    login_handler = ConversationHandler(
        entry_points=[CommandHandler("login", start_login)],
        states={
            WAITING_FOR_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password)]
        },
        fallbacks=[CommandHandler("cancel", cancel_login)],
        name="login",
        persistent=False
    )
    
    return [
        login_handler,
        CommandHandler("logout", logout_user),
        CommandHandler("status", show_status),
        CommandHandler("users", admin_users),
    ]

# Utility function to check auth before any command
async def check_auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Middleware to check authentication for all commands"""
    user_id = update.effective_user.id
    
    # Skip auth check for auth-related commands
    if update.message and update.message.text:
        command = update.message.text.split()[0].lower()
        if command in ['/login', '/start', '/help']:
            return True
    
    if not auth_manager.is_authenticated(user_id):
        await update.message.reply_text(
            "🔒 **Access Denied!**\n\n"
            "You must authenticate first.\n"
            "Use /login to enter the password.",
            parse_mode="Markdown"
        )
        return False
    
    return True