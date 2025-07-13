# inventory_conversation.py - Conversation handler for inventory search
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, ConversationHandler, filters
from auth import require_auth
from db import get_db
import inventory as inventory_utils
import re

# Conversation states
WAITING_FOR_QUERY = 0

def escape_markdown(text: str) -> str:
    """
    Escape Telegram MarkdownV2 special characters in user-provided text.
    """
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r"_*[]()~`>#+-=|{}.!\\"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def safe_field(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    return escape_markdown(text.strip().replace("\n", " "))


@require_auth
async def start_inventory_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the inventory search conversation"""
    await update.message.reply_text(
        "🔍 Inventory Search\n\n"
        "Please enter your search query:\n"
        "• Artist name (e.g., 'Beatles')\n"
        "• Album name (e.g., 'Abbey Road')\n"
        "• Partial match (e.g., 'Dark Side')\n"
        "• Or type 'all' to see everything\n\n"
        "Type /cancel to cancel this operation."
    )
    return WAITING_FOR_QUERY

async def handle_inventory_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the inventory search query"""
    query = update.message.text.strip()

    if not query:
        await update.message.reply_text(
            "❌ Please enter a valid search query or type /cancel to cancel."
        )
        return WAITING_FOR_QUERY

    searching_message = await update.message.reply_text("🔍 Searching inventory...")

    try:
        if query.lower() == "all":
            results = inventory_utils.get_all_inventory()
            title = "📦 All Inventory"
        else:
            results = inventory_utils.search_inventory(query)
            title = f"🔍 Search Results for: {query}"

        await searching_message.delete()

        if not results:
            await update.message.reply_text(
                f"❌ No records found\n\n"
                f"Search query: {query}\n\n"
                "Try a different search term or use /inventory to search again."
            )
            return ConversationHandler.END

        await send_inventory_results(update, results, title, query)

    except Exception as e:
        try:
            await searching_message.delete()
        except:
            pass

        await update.message.reply_text(
            f"❌ Error searching inventory\n\n"
            f"An error occurred: {str(e)}\n\n"
            "Please try again with /inventory"
        )

    return ConversationHandler.END


@require_auth
async def send_inventory_results(update: Update, results: list, title: str, query: str):
    """Send formatted inventory results, handling long messages"""
    total_results = len(results)
    results_per_message = 8

    # Remove MarkdownV2 for now - use plain text
    title_clean = title.replace("*", "").replace("\\", "")
    message = f"{title_clean}\n"
    message += f"Found {total_results} record(s)\n\n"

    for i, item in enumerate(results[:results_per_message]):
        message += format_inventory_item(item, i + 1)

    if total_results > results_per_message:
        showing_end = min(results_per_message, total_results)
        message += f"\n📄 Showing 1-{showing_end} of {total_results} results"

    await update.message.reply_text(message)

    for batch_start in range(results_per_message, total_results, results_per_message):
        batch_end = min(batch_start + results_per_message, total_results)
        batch_message = f"📄 Continued results ({batch_start + 1}-{batch_end} of {total_results})\n\n"

        for i, item in enumerate(results[batch_start:batch_end]):
            batch_message += format_inventory_item(item, batch_start + i + 1)

        await update.message.reply_text(batch_message)

def format_inventory_item(item: dict, index: int) -> str:
    # Use plain text formatting - no markdown at all
    price = item.get('price_gel', 0)
    quantity = item.get('quantity', 0)
    
    # Clean up any potential problematic characters in text fields
    def clean_field(value):
        if not isinstance(value, str):
            value = str(value)
        return value.strip().replace("\n", " ")
    
    return (
        f"{index}. {clean_field(item.get('artist_album', 'Unknown'))}\n"
        f"📀 Format: {clean_field(item.get('format', 'N/A'))}\n"
        f"🏷️ Condition: {clean_field(item.get('condition', 'N/A'))}\n"
        f"💰 Price: ₾{price:.2f}\n"
        f"📦 Quantity: {quantity}\n"
        f"🏢 Label: {clean_field(item.get('label', 'N/A'))}\n"
        f"🎵 Genre: {clean_field(item.get('genre', 'N/A'))}\n\n"
    )


@require_auth
async def cancel_inventory_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel inventory search"""
    await update.message.reply_text(
        "✅ Inventory search cancelled\n\n"
        "Use /inventory to start a new search."
    )
    return ConversationHandler.END

def create_inventory_conversation():
    """Create the inventory search conversation handler"""
    return ConversationHandler(
        entry_points=[CommandHandler("inventory", start_inventory_search)],
        states={
            WAITING_FOR_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inventory_query)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_inventory_search)],
        name="inventory_search",
        persistent=False
    )

# === Inventory Utility Functions ===

def search_inventory(query: str) -> list:
    """Search inventory records matching the query string."""
    like = f"%{query.lower()}%"
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, artist_album, genre, style, label, format,
                   condition, price_gel, quantity
            FROM inventory
            WHERE lower(artist_album) LIKE ?
               OR lower(genre) LIKE ?
               OR lower(style) LIKE ?
               OR lower(label) LIKE ?
            ORDER BY artist_album
            """,
            (like, like, like, like),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "artist_album": row[1],
                "genre": row[2],
                "style": row[3],
                "label": row[4],
                "format": row[5],
                "condition": row[6],
                "price_gel": row[7],
                "quantity": row[8],
            }
            for row in rows
        ]


def get_all_inventory() -> list:
    """Return all inventory records."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, artist_album, genre, style, label, format,
                   condition, price_gel, quantity
            FROM inventory
            ORDER BY artist_album
            """
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "artist_album": row[1],
                "genre": row[2],
                "style": row[3],
                "label": row[4],
                "format": row[5],
                "condition": row[6],
                "price_gel": row[7],
                "quantity": row[8],
            }
            for row in rows
        ]


def reduce_inventory_quantity(item_id: int, amount: int) -> bool:
    """Decrease quantity for an item. Returns True if successful."""
    if amount <= 0:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT quantity FROM inventory WHERE id = ?",
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            return False
        new_qty = row[0] - amount
        if new_qty < 0:
            return False
        cursor.execute(
            "UPDATE inventory SET quantity = ? WHERE id = ?",
            (new_qty, item_id),
        )
        conn.commit()
        return True


def get_inventory_by_id(item_id: int):
    """Fetch a single inventory record by id."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, artist_album, genre, style, label, format,
                   condition, price_gel, quantity
            FROM inventory
            WHERE id = ?
            """,
            (item_id,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "artist_album": row[1],
                "genre": row[2],
                "style": row[3],
                "label": row[4],
                "format": row[5],
                "condition": row[6],
                "price_gel": row[7],
                "quantity": row[8],
            }
        return None

