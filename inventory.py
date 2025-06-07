# inventory.py
import os
from openpyxl import load_workbook

INVENTORY_FILE = "clime_db.xlsx"

def load_inventory():
    """Load inventory from Excel into a list of dictionaries."""
    if not os.path.exists(INVENTORY_FILE):
        raise FileNotFoundError(f"{INVENTORY_FILE} not found.")
    
    wb = load_workbook(INVENTORY_FILE)
    ws = wb.active

    headers = [cell.value for cell in ws[1]]
    inventory = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        record = dict(zip(headers, row))
        inventory.append(record)

    return inventory
