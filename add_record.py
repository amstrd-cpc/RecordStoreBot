# Rewritten add_record.py to use SQLite instead of Excel
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler,
    ContextTypes, filters
)
import discogs_client
from dotenv import load_dotenv
import os
from db import get_db

load_dotenv()
DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
if not DISCOGS_TOKEN:
    raise ValueError("DISCOGS_TOKEN must be set in environment variables.")

d = discogs_client.Client("RecordStoreApp/1.0", user_token=DISCOGS_TOKEN)

SEARCH_INPUT, SHOW_RESULTS, ASK_CONDITION, ASK_PRICE, ASK_QUANTITY = range(5)
CONDITION_OPTIONS = ["m", "nm", "vg+", "vg", "g+", "g", "f", "p"]


# === DB Insert ===
def save_to_inventory(row):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO inventory (artist_album, genre, style, label, format, condition, price_usd, quantity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, row)
        conn.commit()

# === Discogs Utilities ===
def fetch_price_suggestions(release_id):
    try:
        return d._get(f"https://api.discogs.com/marketplace/price_suggestions/{release_id}")
    except Exception:
        return {}

# === Telegram Flow ===
async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter album name (Artist - Title):")
    context.user_data.clear()
    return SEARCH_INPUT

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    context.user_data["query"] = query
    context.user_data["page"] = 1
    return await show_results(update, context)

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = context.user_data["page"]
    query = context.user_data["query"]
    results = list(d.search(query, type='release').page(page))
    context.user_data["results"] = results

    buttons = []
    for i, release in enumerate(results):
        try:
            format_data = release.data.get("formats", [])
            format_str = ", ".join(
                [fmt.get("name", "")] + fmt.get("descriptions", [])
                for fmt in format_data
            )
        except Exception:
            format_str = "Unknown Format"
        text = f"{release.title} [{format_str}]"
        buttons.append([InlineKeyboardButton(text=text[:60], callback_data=f"select_{i}")])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="prev"))
    if len(results) == 50:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data="next"))
    if nav_buttons:
        buttons.append(nav_buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text("Select a release:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await update.message.reply_text("Select a release:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    return SHOW_RESULTS

async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "next":
        context.user_data["page"] += 1
    elif query.data == "prev":
        context.user_data["page"] = max(1, context.user_data["page"] - 1)
    return await show_results(update, context)

async def handle_release_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idx = int(update.callback_query.data.split("_")[1])
    selected = context.user_data["results"][idx]
    context.user_data["release"] = selected
    await update.callback_query.edit_message_text(
        f"Selected: {selected.title}\n\nNow choose vinyl condition:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(c, callback_data=f"cond_{c}") for c in CONDITION_OPTIONS[i:i+4]]
            for i in range(0, len(CONDITION_OPTIONS), 4)
        ])
    )
    return ASK_CONDITION

async def handle_condition_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cond = update.callback_query.data.split("_")[1]
    context.user_data["condition"] = cond
    release = context.user_data["release"]
    suggestions = fetch_price_suggestions(release.id)
    full_condition = {
        "m": "Mint (M)", "nm": "Near Mint (NM or M-)", "vg+": "Very Good Plus (VG+)",
        "vg": "Very Good (VG)", "g+": "Good Plus (G+)", "g": "Good (G)",
        "f": "Fair (F)", "p": "Poor (P)"
    }.get(cond)
    price = suggestions.get(full_condition, {}).get("value", None)
    context.user_data["suggested_price"] = round(price, 2) if price else None
    
    if price:
        msg = f"Suggested price for {full_condition}: ${price:.2f}"
    else:
        msg = "No price suggestion found."
    
    await update.callback_query.edit_message_text(
        msg + "\n\nSend your own price or type 'ok' to accept the suggested price."
    )
    return ASK_PRICE

async def handle_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    
    if msg.lower() == "ok" and context.user_data.get("suggested_price") is not None:
        final_price = context.user_data["suggested_price"]
    else:
        try:
            final_price = float(msg)
        except ValueError:
            await update.message.reply_text("❌ Invalid price. Please enter a valid number or 'ok' to accept suggested price:")
            return ASK_PRICE
    
    context.user_data["final_price"] = round(final_price, 2)
    await update.message.reply_text("How many copies do you want to add?")
    return ASK_QUANTITY

async def handle_quantity_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text.strip())
        if qty < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Invalid quantity. Enter a whole number ≥ 1:")
        return ASK_QUANTITY

    release = context.user_data["release"]
    cond = context.user_data["condition"]
    price = context.user_data["final_price"]

    format_str = ", ".join(
        [fmt.get("name", "")] + fmt.get("descriptions", [])
        for fmt in release.data.get("formats", [])
    )

    row = [
        release.title,
        ", ".join(release.genres or []),
        ", ".join(release.styles or []),
        ", ".join([l.name for l in release.labels]) if hasattr(release, 'labels') else "N/A",
        format_str,
        cond,
        price,
        qty
    ]
    
    save_to_inventory(row)
    await update.message.reply_text(f"✅ {qty} copy(ies) of '{release.title}' added to inventory at ${price:.2f} each.")
    return ConversationHandler.END

    
# === Entry Point ===
def start_add_flow():
    return ConversationHandler(
        entry_points=[CommandHandler("add", start_add)],
        states={
            SEARCH_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search)],
            SHOW_RESULTS: [
                CallbackQueryHandler(handle_release_select, pattern=r"^select_"),
                CallbackQueryHandler(handle_pagination, pattern="^(next|prev)$")
            ],
            ASK_CONDITION: [CallbackQueryHandler(handle_condition_select, pattern=r"^cond_")],
            ASK_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price_input)],
            ASK_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity_input)],
        },
        fallbacks=[],
        name="add_record",
        persistent=False
    )