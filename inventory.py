# Rewritten inventory.py to use SQLite with full quantity support
from db import get_db


def has_record(query: str) -> bool:
    """
    Checks if a given artist/album name exists in the inventory with available quantity.
    Match is case-insensitive and substring-based.
    Only returns True if quantity > 0.
    """
    query = query.strip().lower()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM inventory
            WHERE LOWER(artist_album) LIKE ? AND quantity > 0
            LIMIT 1
        """, (f"%{query}%",))
        return cursor.fetchone() is not None


def search_inventory(query: str) -> list:
    """
    Returns a list of matching inventory items for the given query.
    Only returns items with quantity > 0.
    Includes all relevant fields including quantity.
    """
    query = query.strip().lower()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, artist_album, genre, style, label, format, condition, price_usd, quantity
            FROM inventory
            WHERE LOWER(artist_album) LIKE ? AND quantity > 0
            ORDER BY artist_album, condition
        """, (f"%{query}%",))

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
                "price_usd": row[7],
                "quantity": row[8]
            } for row in rows
        ]


def get_inventory_by_id(inventory_id: int) -> dict:
    """
    Get a specific inventory item by its ID.
    Returns None if not found or quantity is 0.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, artist_album, genre, style, label, format, condition, price_usd, quantity
            FROM inventory
            WHERE id = ? AND quantity > 0
        """, (inventory_id,))
        
        row = cursor.fetchone()
        if row is None:
            return None
        
        return {
            "id": row[0],
            "artist_album": row[1],
            "genre": row[2],
            "style": row[3],
            "label": row[4],
            "format": row[5],
            "condition": row[6],
            "price_usd": row[7],
            "quantity": row[8]
        }


def get_all_inventory() -> list:
    """
    Returns all inventory items with quantity > 0.
    Useful for generating full inventory reports.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, artist_album, genre, style, label, format, condition, price_usd, quantity
            FROM inventory
            WHERE quantity > 0
            ORDER BY artist_album, condition
        """)
        
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
                "price_usd": row[7],
                "quantity": row[8]
            } for row in rows
        ]


def update_inventory_quantity(inventory_id: int, new_quantity: int) -> bool:
    """
    Update the quantity of a specific inventory item.
    Returns True if successful, False if item not found.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE inventory 
            SET quantity = ? 
            WHERE id = ?
        """, (new_quantity, inventory_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        
        # Clean up if quantity is now 0 or less
        if new_quantity <= 0:
            cursor.execute("DELETE FROM inventory WHERE id = ? AND quantity <= 0", (inventory_id,))
            conn.commit()
        
        return success


def reduce_inventory_quantity(inventory_id: int, reduce_by: int = 1) -> bool:
    """
    Reduce the quantity of a specific inventory item.
    Returns True if successful, False if not enough quantity or item not found.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check current quantity
        cursor.execute("SELECT quantity FROM inventory WHERE id = ?", (inventory_id,))
        result = cursor.fetchone()
        
        if result is None or result[0] < reduce_by:
            return False
        
        new_quantity = result[0] - reduce_by
        cursor.execute("""
            UPDATE inventory 
            SET quantity = ? 
            WHERE id = ?
        """, (new_quantity, inventory_id))
        
        conn.commit()
        
        # Clean up if quantity is now 0
        if new_quantity <= 0:
            cursor.execute("DELETE FROM inventory WHERE id = ? AND quantity <= 0", (inventory_id,))
            conn.commit()
        
        return True


def find_exact_match(artist_album: str, condition: str) -> dict:
    """
    Find an exact match for artist/album and condition.
    Useful for sales processing when you need to find the specific item to sell.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, artist_album, genre, style, label, format, condition, price_usd, quantity
            FROM inventory
            WHERE LOWER(artist_album) = LOWER(?) AND LOWER(condition) = LOWER(?) AND quantity > 0
            LIMIT 1
        """, (artist_album.strip(), condition.strip()))
        
        row = cursor.fetchone()
        if row is None:
            return None
        
        return {
            "id": row[0],
            "artist_album": row[1],
            "genre": row[2],
            "style": row[3],
            "label": row[4],
            "format": row[5],
            "condition": row[6],
            "price_usd": row[7],
            "quantity": row[8]
        }


def get_low_stock_items(threshold: int = 1) -> list:
    """
    Returns items with quantity <= threshold.
    Useful for inventory management alerts.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, artist_album, genre, style, label, format, condition, price_usd, quantity
            FROM inventory
            WHERE quantity <= ? AND quantity > 0
            ORDER BY quantity ASC, artist_album
        """, (threshold,))
        
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
                "price_usd": row[7],
                "quantity": row[8]
            } for row in rows
        ]