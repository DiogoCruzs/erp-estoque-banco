import sqlite3
from contextlib import contextmanager
from config import DB_PATH, DATA_DIR

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','operator')), active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, category TEXT NOT NULL DEFAULT 'Espetos', sale_price_cents INTEGER NOT NULL DEFAULT 0, avg_cost_cents INTEGER NOT NULL DEFAULT 0, last_cost_cents INTEGER NOT NULL DEFAULT 0, stock_qty INTEGER NOT NULL DEFAULT 0, min_stock INTEGER NOT NULL DEFAULT 0, ideal_stock INTEGER NOT NULL DEFAULT 0, unit TEXT NOT NULL DEFAULT 'unidade', active INTEGER NOT NULL DEFAULT 1, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY, sold_at TEXT NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id), status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('completed','cancelled')), total_qty INTEGER NOT NULL, revenue_cents INTEGER NOT NULL, cogs_cents INTEGER NOT NULL, gross_profit_cents INTEGER NOT NULL, cancel_reason TEXT, cancelled_at TEXT, cancelled_by INTEGER REFERENCES users(id));
CREATE TABLE IF NOT EXISTS sale_items (id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id), product_id INTEGER NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL CHECK(quantity > 0), sale_price_cents INTEGER NOT NULL, unit_cost_cents INTEGER NOT NULL, revenue_cents INTEGER NOT NULL, cogs_cents INTEGER NOT NULL, gross_profit_cents INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY, purchased_at TEXT NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id), supplier TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', total_cents INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS purchase_items (id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES purchases(id), product_id INTEGER NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL CHECK(quantity > 0), unit_cost_cents INTEGER NOT NULL, total_cents INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS stock_movements (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, product_id INTEGER NOT NULL REFERENCES products(id), movement_type TEXT NOT NULL, qty_delta INTEGER NOT NULL, qty_before INTEGER NOT NULL, qty_after INTEGER NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id), reason TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', reference_type TEXT, reference_id INTEGER);
CREATE TABLE IF NOT EXISTS product_cost_history (id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), changed_at TEXT NOT NULL, unit_cost_cents INTEGER NOT NULL, source TEXT NOT NULL, reference_id INTEGER, user_id INTEGER NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS product_price_history (id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), changed_at TEXT NOT NULL, sale_price_cents INTEGER NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, user_id INTEGER REFERENCES users(id), action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id INTEGER, details TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS inventory_counts (id INTEGER PRIMARY KEY, counted_at TEXT NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id), notes TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS inventory_count_items (id INTEGER PRIMARY KEY, count_id INTEGER NOT NULL REFERENCES inventory_counts(id), product_id INTEGER NOT NULL REFERENCES products(id), system_qty INTEGER NOT NULL, physical_qty INTEGER NOT NULL, difference INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sales_sold_at ON sales(sold_at);
CREATE INDEX IF NOT EXISTS idx_movements_product_date ON stock_movements(product_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_date ON audit_logs(created_at);
"""

@contextmanager
def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.executescript(SCHEMA)
        defaults = {"establishment_name":"SERV FESTA REGISSOL","daily_goal":"100","moving_average_days":"7","yellow_alert_percent":"30","backup_frequency":"daily"}
        for key, value in defaults.items(): db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)", (key, value))

def now_iso():
    from datetime import datetime
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")

def get_settings(db):
    return {row["key"]: row["value"] for row in db.execute("SELECT key,value FROM settings")}

