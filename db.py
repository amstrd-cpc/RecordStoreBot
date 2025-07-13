import sqlite3
import os

# Use absolute path to ensure the same database file is used
# regardless of the current working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "clime_db.db")

def get_db():
    return sqlite3.connect(DB_FILE)

def init_db():
    """Initialize the main database with proper schema"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Check existing tables for potential migration from the old Sheet table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}
        migrate_from_sheet = "Sheet" in existing_tables and "inventory" not in existing_tables
        
        # Create inventory table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_album TEXT NOT NULL,
            genre TEXT,
            style TEXT,
            label TEXT,
            format TEXT,
            condition TEXT,
            price_gel REAL,
            quantity INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create sales table (for main database sales tracking)
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
            price_gel REAL,
            payment_method TEXT DEFAULT 'cash',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create indexes for better performance
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_inventory_artist_album 
        ON inventory(artist_album)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_inventory_condition 
        ON inventory(condition)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sales_date
        ON sales(date)
        """)

        if migrate_from_sheet:
            # Migrate existing data from the old Sheet table into the new inventory table
            cursor.execute(
                """
                INSERT INTO inventory (artist_album, genre, style, label, format, condition, price_gel, quantity)
                SELECT "Artist_-_Album", Genre, Style, Label, '' as format, Condition, gel_Price, 1
                FROM Sheet
                """
            )
            cursor.execute("DROP TABLE Sheet")
            print("🔄 Migrated data from Sheet table to inventory")

        conn.commit()
        print("✅ Main database initialized successfully")

def backup_db():
    """Create a backup of the database"""
    if os.path.exists(DB_FILE):
        backup_file = f"{DB_FILE}.backup"
        try:
            import shutil
            shutil.copy2(DB_FILE, backup_file)
            print(f"✅ Database backed up to {backup_file}")
        except Exception as e:
            print(f"❌ Backup failed: {e}")

def get_db_stats():
    """Get basic statistics about the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get inventory count
        cursor.execute("SELECT COUNT(*) FROM inventory")
        inventory_count = cursor.fetchone()[0]
        
        # Get total quantity in inventory
        cursor.execute("SELECT SUM(quantity) FROM inventory")
        total_quantity = cursor.fetchone()[0] or 0
        
        # Get sales count
        cursor.execute("SELECT COUNT(*) FROM sales")
        sales_count = cursor.fetchone()[0]
        
        return {
            'inventory_records': inventory_count,
            'total_quantity': total_quantity,
            'sales_records': sales_count
        }

def cleanup_sold_out_items():
    """Remove items from inventory where quantity is 0 or less"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM inventory WHERE quantity <= 0")
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count