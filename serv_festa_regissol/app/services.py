import shutil
from datetime import datetime, timedelta
from flask import current_app
from config import DB_PATH
from .db import now_iso

PRODUCT_NAMES = ["Espeto de Carne","Espeto de Coração","Espeto de Costela","Espeto de Frango","Medalhão de Frango","Kafta","Kafta com Queijo","Cudiguim","Cudiguim Apimentado","Queijo Coalho","Linguiça Mista","Linguiça com Pimenta"]

def seed_products(db):
    if db.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]: return
    stamp = now_iso()
    for name in PRODUCT_NAMES: db.execute("INSERT INTO products(name,category,sale_price_cents,created_at,updated_at) VALUES (?,?,?,?,?)", (name,"Espetos",800,stamp,stamp))

def audit(db, user_id, action, entity_type, entity_id=None, details=""):
    db.execute("INSERT INTO audit_logs(created_at,user_id,action,entity_type,entity_id,details) VALUES (?,?,?,?,?,?)", (now_iso(),user_id,action,entity_type,entity_id,details[:1000]))

def change_stock(db, product_id, delta, user_id, movement_type, reason="", notes="", reference_type=None, reference_id=None):
    product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product: raise ValueError("Produto não encontrado.")
    before = product["stock_qty"]; after = before + delta
    if after < 0: raise ValueError(f"Estoque insuficiente para {product['name']}.")
    db.execute("UPDATE products SET stock_qty=?, updated_at=? WHERE id=?", (after,now_iso(),product_id))
    db.execute("INSERT INTO stock_movements(created_at,product_id,movement_type,qty_delta,qty_before,qty_after,user_id,reason,notes,reference_type,reference_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (now_iso(),product_id,movement_type,delta,before,after,user_id,reason,notes,reference_type,reference_id))
    return product, before, after

def parse_money(value):
    text=str(value or "").strip().replace("R$","").replace(".","").replace(",",".")
    if not text: return 0
    amount=round(float(text),2)
    if amount<0: raise ValueError("Valor não pode ser negativo.")
    return int(round(amount*100))

def parse_qty(value):
    qty=int(str(value or "0"))
    if qty<=0: raise ValueError("Quantidade deve ser maior que zero.")
    return qty

def make_backup():
    backup_dir=current_app.config["BACKUP_DIR"]; backup_dir.mkdir(parents=True,exist_ok=True)
    filename=backup_dir/f"backup_{datetime.now():%Y-%m-%d_%H%M%S}.db"; shutil.copy2(DB_PATH,filename)
    files=sorted(backup_dir.glob("backup_*.db"),key=lambda p:p.stat().st_mtime,reverse=True)
    for old in files[30:]: old.unlink(missing_ok=True)
    return filename

def period_bounds(period):
    today=datetime.now().date()
    if period=="yesterday": start=end=today-timedelta(days=1)
    elif period=="7d": start,end=today-timedelta(days=6),today
    elif period=="month": start,end=today.replace(day=1),today
    elif period=="prev_month":
        first=today.replace(day=1); end=first-timedelta(days=1); start=end.replace(day=1)
    elif period=="year": start,end=today.replace(month=1,day=1),today
    else: start=end=today
    return f"{start} 00:00:00",f"{end} 23:59:59"

def metrics(db,start,end):
    sales=db.execute("SELECT COALESCE(SUM(total_qty),0) qty,COALESCE(SUM(revenue_cents),0) revenue,COALESCE(SUM(cogs_cents),0) cogs,COALESCE(SUM(gross_profit_cents),0) profit FROM sales WHERE status='completed' AND sold_at BETWEEN ? AND ?",(start,end)).fetchone()
    purchases=db.execute("SELECT COALESCE(SUM(total_cents),0) total FROM purchases WHERE purchased_at BETWEEN ? AND ?",(start,end)).fetchone()["total"]
    losses=db.execute("SELECT COALESCE(SUM(ABS(qty_delta)),0) qty FROM stock_movements WHERE movement_type IN ('Perda','Perda/Quebra') AND created_at BETWEEN ? AND ?",(start,end)).fetchone()["qty"]
    return {"qty":sales["qty"],"revenue":sales["revenue"],"cogs":sales["cogs"],"profit":sales["profit"],"purchases":purchases,"losses":losses,"margin":sales["profit"]/sales["revenue"]*100 if sales["revenue"] else 0}

