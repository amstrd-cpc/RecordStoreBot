# reports.py
import os
import datetime
from openpyxl import load_workbook
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

SALES_FOLDER = "sales"

def generate_daily_report():
    today = datetime.date.today().isoformat()
    file_path = os.path.join(SALES_FOLDER, f"{today}.xlsx")

    if not os.path.exists(file_path):
        raise FileNotFoundError("No sales for today yet.")

    wb = load_workbook(file_path)
    ws = wb.active

    total_cash = 0.0
    total_pos = 0.0
    headers = [cell.value for cell in ws[1]]
    pay_idx = headers.index("Payment Method")
    price_idx = headers.index("USD Price")

    for row in ws.iter_rows(min_row=2, values_only=True):
        payment = row[pay_idx]
        try:
            amount = float(row[price_idx])
        except:
            continue
        if payment.lower() == "cash":
            total_cash += amount
        elif payment.lower() == "pos":
            total_pos += amount

    summary = (
        f"📅 *Sales Report for {today}*\n"
        f"💵 Cash: ${total_cash:.2f}\n"
        f"💳 POS: ${total_pos:.2f}\n"
        f"📦 Total: ${total_cash + total_pos:.2f}"
    )

    return file_path, summary

# === Telegram command handler ===
async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        file_path, summary = generate_daily_report()
        await update.message.reply_text(summary, parse_mode="Markdown")
        await update.message.reply_document(open(file_path, "rb"))
    except FileNotFoundError:
        await update.message.reply_text("📭 No sales yet today.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

def report_handler():
    return CommandHandler("report", send_report)
