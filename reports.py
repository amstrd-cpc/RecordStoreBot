# reports.py — Fixed version with proper database integration and initialization
import os
import sqlite3
import datetime
from openpyxl import Workbook
from telegram.ext import CommandHandler, ContextTypes
from telegram import Update

REPORT_DB_FILE = "sales_log.db"
EXCEL_REPORT_FOLDER = "sales_reports"

# Create reports folder if it doesn't exist
if not os.path.exists(EXCEL_REPORT_FOLDER):
    os.makedirs(EXCEL_REPORT_FOLDER)

def get_report_db():
    """Get connection to the sales report database"""
    return sqlite3.connect(REPORT_DB_FILE)

def init_report_db():
    """Initialize the sales report database with proper schema"""
    with get_report_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                artist_album TEXT,
                genre TEXT,
                style TEXT,
                label TEXT,
                format TEXT,
                condition TEXT,
                price_usd REAL,
                payment_method TEXT DEFAULT 'cash',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for better performance on date queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sales_date 
            ON sales(date)
        """)
        
        conn.commit()
        print("✅ Sales report database initialized successfully")

def log_sale_to_report_db(sale_data: dict):
    """Log a sale to the report database for Excel generation"""
    with get_report_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sales (
                date, artist_album, genre, style, label, format,
                condition, price_usd, payment_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sale_data['date'],
            sale_data['artist_album'],
            sale_data['genre'],
            sale_data['style'],
            sale_data['label'],
            sale_data['format'],
            sale_data['condition'],
            sale_data['price_usd'],
            sale_data['payment_method']
        ))
        conn.commit()

def generate_excel_report_for_today():
    """Generate Excel report for today's sales"""
    today = datetime.date.today().isoformat()
    file_path = os.path.join(EXCEL_REPORT_FOLDER, f"sales_report_{today}.xlsx")

    with get_report_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT artist_album, genre, style, label, format, condition,
                   price_usd, payment_method, created_at
            FROM sales 
            WHERE date = ?
            ORDER BY created_at
        """, (today,))

        rows = cursor.fetchall()

        if not rows:
            raise FileNotFoundError("No sales recorded for today yet.")

        # Create Excel workbook
        wb = Workbook()
        ws = wb.active
        ws.title = f"Sales {today}"
        
        # Add headers
        headers = ["Artist/Album", "Genre", "Style", "Label", "Format",
                  "Condition", "USD Price", "Payment Method", "Time"]
        ws.append(headers)
        
        # Initialize totals
        total_cash = 0.0
        total_pos = 0.0
        total_items = 0

        # Add data rows
        for row in rows:
            ws.append(row)
            total_items += 1
            
            # Calculate totals by payment method
            payment = row[7].lower() if row[7] else 'cash'
            try:
                amount = float(row[6]) if row[6] else 0.0
            except (ValueError, TypeError):
                amount = 0.0
                
            if payment == "cash":
                total_cash += amount
            elif payment == "pos":
                total_pos += amount

        # Add summary rows
        ws.append([])  # Empty row
        ws.append(["DAILY SUMMARY"])
        ws.append(["Total Items Sold:", total_items])
        ws.append(["Cash Sales:", f"${total_cash:.2f}"])
        ws.append(["POS Sales:", f"${total_pos:.2f}"])
        ws.append(["Total Revenue:", f"${total_cash + total_pos:.2f}"])

        # Save workbook
        wb.save(file_path)

    # Create summary text
    summary = (
        f"📅 *Sales Report for {today}*\n\n"
        f"📦 Items sold: {total_items}\n"
        f"💵 Cash: ${total_cash:.2f}\n"
        f"💳 POS: ${total_pos:.2f}\n"
        f"💰 Total Revenue: ${total_cash + total_pos:.2f}\n\n"
        f"📄 Excel report generated: `{os.path.basename(file_path)}`"
    )

    return file_path, summary

async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /report command - generate and send daily sales report"""
    try:
        file_path, summary = generate_excel_report_for_today()
        
        # Send summary first
        await update.message.reply_text(summary, parse_mode="Markdown")
        
        # Send Excel file
        with open(file_path, "rb") as file:
            await update.message.reply_document(
                document=file,
                filename=os.path.basename(file_path),
                caption="📊 Daily Sales Report"
            )
            
    except FileNotFoundError:
        await update.message.reply_text(
            "📭 No sales recorded for today yet.\n"
            "Start selling some records to generate a report! 🎵"
        )
    except Exception as e:
        error_msg = f"❌ Error generating report: {str(e)}"
        await update.message.reply_text(error_msg)
        print(f"Report generation error: {e}")

def report_handler():
    """Return the report command handler"""
    return CommandHandler("report", send_report)


def get_recent_sales(limit: int = 10):
    """Return the most recent sales from the report database."""
    with get_report_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT artist_album, price_usd, payment_method, date
            FROM sales
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()

    return [
        {
            "artist_album": row[0],
            "price_usd": row[1],
            "payment_method": row[2],
            "date": row[3],
        }
        for row in rows
    ]


def _generate_summary(start_date: datetime.date, end_date: datetime.date) -> str:
    """Helper to generate a textual sales summary for a date range."""
    with get_report_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT price_usd, payment_method
            FROM sales
            WHERE date BETWEEN ? AND ?
            """,
            (start_date.isoformat(), end_date.isoformat()),
        )
        rows = cursor.fetchall()

    if not rows:
        return "No sales recorded for this period."

    total_cash = sum(row[0] for row in rows if (row[1] or "cash").lower() == "cash")
    total_pos = sum(row[0] for row in rows if (row[1] or "cash").lower() == "pos")
    total_items = len(rows)

    return (
        f"Items sold: {total_items}\n"
        f"Cash: ${total_cash:.2f}\n"
        f"POS: ${total_pos:.2f}\n"
        f"Total Revenue: ${total_cash + total_pos:.2f}"
    )


def generate_daily_report() -> str:
    today = datetime.date.today()
    summary = _generate_summary(today, today)
    return f"📅 Daily Report for {today}\n\n" + summary


def generate_weekly_report() -> str:
    end = datetime.date.today()
    start = end - datetime.timedelta(days=6)
    summary = _generate_summary(start, end)
    return f"📅 Weekly Report ({start} to {end})\n\n" + summary


def generate_monthly_report() -> str:
    end = datetime.date.today()
    start = end - datetime.timedelta(days=29)
    summary = _generate_summary(start, end)
    return f"📅 Monthly Report ({start} to {end})\n\n" + summary

def get_sales_stats(days: int = 7):
    """Get sales statistics for the last N days (for future use)"""
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days-1)
    
    with get_report_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, COUNT(*) as items_sold, SUM(price_usd) as total_revenue
            FROM sales 
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date DESC
        """, (start_date.isoformat(), end_date.isoformat()))
        
        return cursor.fetchall()

def cleanup_old_reports(days_to_keep: int = 30):
    """Clean up old report files (for maintenance)"""
    if not os.path.exists(EXCEL_REPORT_FOLDER):
        return
        
    cutoff_date = datetime.date.today() - datetime.timedelta(days=days_to_keep)
    
    for filename in os.listdir(EXCEL_REPORT_FOLDER):
        if filename.startswith("sales_report_") and filename.endswith(".xlsx"):
            try:
                # Extract date from filename
                date_str = filename.replace("sales_report_", "").replace(".xlsx", "")
                file_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                
                if file_date < cutoff_date:
                    file_path = os.path.join(EXCEL_REPORT_FOLDER, filename)
                    os.remove(file_path)
                    print(f"Cleaned up old report: {filename}")
            except (ValueError, OSError) as e:
                print(f"Error cleaning up {filename}: {e}")
                continue