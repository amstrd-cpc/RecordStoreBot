# sales.py — Fully updated with quantity tracking and dual DB logging
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler,
    ContextTypes, filters
)
from db import get_db
from reports import log_sale_to_report_db
import inventory as inventory_utils

SELL_QUERY, SELL_SELECT, SELL_PAYMENT, SELL_PRICE = range(4)

# === Start Sell Flow ===
async def sell_flow_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 Welcome to the Sell Vinyls flow!\n"
                                    "Please enter the artist or album name you want to sell:")
    context.user_data.clear()
    return SELL_QUERY

async def sell_flow_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    context.user_data["query"] = query
    found_items = inventory_utils.search_inventory(query)

    if not found_items:
        await update.message.reply_text(f"❌ No matching records found for: *{query}*", parse_mode="Markdown")
        return ConversationHandler.END

    context.user_data["found_items"] = found_items
    
    # Create buttons with proper item information including quantity
    buttons = []
    for i, item in enumerate(found_items):
        button_text = f"{item['artist_album']} - {item['condition']} (Qty: {item['quantity']}) - ${item['price_usd']:.2f}"
        # Truncate if too long for button
        if len(button_text) > 60:
            button_text = button_text[:57] + "..."
        buttons.append([InlineKeyboardButton(button_text, callback_data=f"select_{i}")])

    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Please select the record you want to sell:", reply_markup=reply_markup)
    return SELL_SELECT

async def sell_flow_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected_index = int(query.data.split("_")[1])
    selected_item = context.user_data["found_items"][selected_index]
    context.user_data["selected_item"] = selected_item

    # Create payment method buttons
    payment_buttons = [
        [InlineKeyboardButton("💵 Cash", callback_data="payment_cash")],
        [InlineKeyboardButton("💳 POS/Card", callback_data="payment_pos")]
    ]
    
    await query.edit_message_text(
        f"Selected: *{selected_item['artist_album']}*\n"
        f"Condition: {selected_item['condition']}\n"
        f"Available: {selected_item['quantity']} copies\n"
        f"Listed price: ${selected_item['price_usd']:.2f}\n\n"
        f"Choose payment method:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(payment_buttons)
    )
    return SELL_PAYMENT

async def sell_flow_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    payment_method = query.data.split("_")[1]  # 'cash' or 'pos'
    context.user_data["payment_method"] = payment_method
    
    selected_item = context.user_data["selected_item"]
    
    await query.edit_message_text(
        f"Payment method: *{payment_method.upper()}*\n\n"
        f"Listed price: ${selected_item['price_usd']:.2f}\n\n"
        f"Enter the selling price or type 'ok' to use the listed price:",
        parse_mode="Markdown"
    )
    return SELL_PRICE

async def sell_flow_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    selected_item = context.user_data["selected_item"]
    payment_method = context.user_data["payment_method"]

    # Handle price input
    if msg.lower() == "ok":
        final_price = selected_item['price_usd']
    else:
        try:
            final_price = float(msg)
            if final_price < 0:
                await update.message.reply_text("❌ Price cannot be negative. Please enter a valid price or 'ok':")
                return SELL_PRICE
        except ValueError:
            await update.message.reply_text("❌ Invalid price format. Please enter a valid number or 'ok':")
            return SELL_PRICE

    # Process the sale
    today = datetime.date.today().isoformat()
    
    try:
        # Reduce inventory quantity using the inventory utility
        success = inventory_utils.reduce_inventory_quantity(selected_item['id'], 1)
        
        if not success:
            await update.message.reply_text("❌ Unable to complete sale - item may be out of stock.")
            return ConversationHandler.END

        # Save to main database sales table
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sales (
                    date, artist_album, genre, style, label, format,
                    condition, price_usd, payment_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                today,
                selected_item['artist_album'],
                selected_item['genre'],
                selected_item['style'],
                selected_item['label'],
                selected_item['format'],
                selected_item['condition'],
                final_price,
                payment_method
            ))
            conn.commit()

        # Log to sales report database
        log_sale_to_report_db({
            'date': today,
            'artist_album': selected_item['artist_album'],
            'genre': selected_item['genre'],
            'style': selected_item['style'],
            'label': selected_item['label'],
            'format': selected_item['format'],
            'condition': selected_item['condition'],
            'price_usd': final_price,
            'payment_method': payment_method
        })

        # Get updated quantity for confirmation
        updated_item = inventory_utils.get_inventory_by_id(selected_item['id'])
        remaining_qty = updated_item['quantity'] if updated_item else 0
        
        confirmation_msg = (
            f"✅ Sale recorded successfully!\n\n"
            f"📀 Album: {selected_item['artist_album']}\n"
            f"💿 Condition: {selected_item['condition']}\n"
            f"💰 Price: ${final_price:.2f}\n"
            f"💳 Payment: {payment_method.upper()}\n"
            f"📦 Remaining quantity: {remaining_qty}"
        )
        
        if remaining_qty == 0:
            confirmation_msg += "\n\n⚠️ This item is now out of stock."
        elif remaining_qty <= 2:
            confirmation_msg += f"\n\n⚠️ Low stock warning: Only {remaining_qty} left!"

        await update.message.reply_text(confirmation_msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Error processing sale: {str(e)}")
        return ConversationHandler.END

    return ConversationHandler.END

async def cancel_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cancellation of sale process"""
    await update.message.reply_text("❌ Sale cancelled.")
    return ConversationHandler.END

# === Entry Point ===
def start_sell_flow():
    return ConversationHandler(
        entry_points=[CommandHandler("sell", sell_flow_start)],
        states={
            SELL_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_flow_query)],
            SELL_SELECT: [CallbackQueryHandler(sell_flow_select, pattern=r"^select_\d+$")],
            SELL_PAYMENT: [CallbackQueryHandler(sell_flow_payment, pattern=r"^payment_(cash|pos)$")],
            SELL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_flow_price)]
        },
        fallbacks=[CommandHandler("cancel", cancel_sale)],
        name="sell_vinyls",
        persistent=False
    )