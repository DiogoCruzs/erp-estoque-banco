import csv, io, sqlite3
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from .db import get_db, get_settings, now_iso
from .auth import current_user, login_required, admin_required, csrf_token, validate_csrf
from .services import seed_products, audit, change_stock, parse_money, parse_qty, make_backup, period_bounds, metrics

bp = Blueprint("main", __name__)

@bp.before_app_request
def security_and_setup():
    validate_csrf()
    if request.endpoint and request.endpoint not in {"main.setup", "main.login", "static"}:
        with get_db() as db: configured=db.execute("SELECT 1 FROM users LIMIT 1").fetchone()
        if not configured: return redirect(url_for("main.setup"))

@bp.app_context_processor
def inject():
    user=current_user(); notifications=[]
    if user:
        with get_db() as db:
            settings=get_settings(db); percent=float(settings.get("yellow_alert_percent","30") or 30)
            products=db.execute("SELECT id,name,stock_qty,min_stock,ideal_stock FROM products WHERE active=1 AND stock_qty <= min_stock + CASE WHEN min_stock > 0 THEN MAX(1, CAST(min_stock * ? / 100 AS INTEGER)) ELSE 0 END ORDER BY stock_qty ASC,name",(percent,)).fetchall()
            for product in products:
                notifications.append({"name":product["name"],"stock":product["stock_qty"],"minimum":product["min_stock"],"level":"danger" if product["stock_qty"]<=product["min_stock"] else "warning"})
    return {"current_user":user,"csrf_token":csrf_token(),"stock_notifications":notifications}

@bp.route("/setup", methods=["GET","POST"])
def setup():
    with get_db() as db:
        if db.execute("SELECT 1 FROM users LIMIT 1").fetchone(): return redirect(url_for("main.login"))
        if request.method=="POST":
            name=request.form.get("name","").strip(); username=request.form.get("username","").strip(); password=request.form.get("password","")
            if len(name)<2 or len(username)<3 or len(password)<10: flash("Informe nome, usuário e uma senha com pelo menos 10 caracteres.","error")
            else:
                db.execute("INSERT INTO users(name,username,password_hash,role,created_at) VALUES (?,?,?,?,?)",(name,username,generate_password_hash(password),"admin",now_iso())); seed_products(db); flash("Administrador criado. Faça login para começar.","success"); return redirect(url_for("main.login"))
    return render_template("setup.html")

@bp.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        with get_db() as db: user=db.execute("SELECT * FROM users WHERE username=? AND active=1",(request.form.get("username","").strip(),)).fetchone()
        if user and check_password_hash(user["password_hash"],request.form.get("password","")):
            session.clear(); session["user_id"]=user["id"]; session["csrf_token"]=csrf_token(); return redirect(request.args.get("next") or url_for("main.dashboard"))
        flash("Usuário ou senha inválidos.","error")
    return render_template("login.html")

@bp.post("/logout")
def logout(): session.clear(); return redirect(url_for("main.login"))

def load_products(db): return db.execute("SELECT * FROM products WHERE active=1 ORDER BY name").fetchall()

@bp.route("/")
@login_required
def dashboard():
    period=request.args.get("period","today"); start,end=period_bounds(period)
    from pathlib import Path
    backup_dir=current_app.config["BACKUP_DIR"]
    today_stamp=datetime.now().strftime("%Y-%m-%d")
    if not any(today_stamp in path.name for path in backup_dir.glob("backup_*.db")):
        make_backup()
    with get_db() as db:
        settings=get_settings(db); data=metrics(db,start,end); products=load_products(db); low=[p for p in products if p["stock_qty"]<=p["min_stock"]]; stock_value=sum(p["stock_qty"]*p["avg_cost_cents"] for p in products)
        ranking=db.execute("SELECT p.name,SUM(si.quantity) qty FROM sale_items si JOIN sales s ON s.id=si.sale_id JOIN products p ON p.id=si.product_id WHERE s.status='completed' AND s.sold_at BETWEEN ? AND ? GROUP BY p.id ORDER BY qty DESC LIMIT 5",(start,end)).fetchall(); champion=ranking[0]["name"] if ranking else "Dados insuficientes"
        recent=db.execute("SELECT sm.*,p.name,u.name user_name FROM stock_movements sm JOIN products p ON p.id=sm.product_id JOIN users u ON u.id=sm.user_id ORDER BY sm.id DESC LIMIT 8").fetchall()
    return render_template("dashboard.html",data=data,products=products,low=low,stock_value=stock_value,ranking=ranking,champion=champion,recent=recent,period=period,settings=settings)

@bp.route("/sale")
@login_required
def sale():
    with get_db() as db: products=load_products(db)
    return render_template("sale.html",products=products)

@bp.post("/api/sales")
@login_required
def create_sale():
    user=current_user(); payload=request.get_json(silent=True) or {}; items=payload.get("items",[])
    if not items: return jsonify(error="Carrinho vazio."),400
    try:
        with get_db() as db:
            total_qty=revenue=cogs=0; prepared=[]
            for item in items:
                product=db.execute("SELECT * FROM products WHERE id=? AND active=1",(int(item["product_id"]),)).fetchone(); qty=parse_qty(item["quantity"])
                if not product: raise ValueError("Produto inválido.")
                if product["stock_qty"]<qty: raise ValueError(f"Estoque insuficiente para {product['name']}.")
                rev=product["sale_price_cents"]*qty; cost=product["avg_cost_cents"]*qty; prepared.append((product,qty,rev,cost)); total_qty+=qty; revenue+=rev; cogs+=cost
            profit=revenue-cogs; cur=db.execute("INSERT INTO sales(sold_at,user_id,total_qty,revenue_cents,cogs_cents,gross_profit_cents) VALUES (?,?,?,?,?,?)",(now_iso(),user["id"],total_qty,revenue,cogs,profit)); sale_id=cur.lastrowid
            for product,qty,rev,cost in prepared:
                db.execute("INSERT INTO sale_items(sale_id,product_id,quantity,sale_price_cents,unit_cost_cents,revenue_cents,cogs_cents,gross_profit_cents) VALUES (?,?,?,?,?,?,?,?)",(sale_id,product["id"],qty,product["sale_price_cents"],product["avg_cost_cents"],rev,cost,rev-cost)); change_stock(db,product["id"],-qty,user["id"],"Venda",reference_type="sale",reference_id=sale_id)
            audit(db,user["id"],"Venda registrada","sale",sale_id,f"{total_qty} unidades")
        return jsonify(ok=True,sale_id=sale_id)
    except (ValueError,KeyError,sqlite3.Error) as exc: return jsonify(error=str(exc)),400

@bp.route("/sales")
@login_required
def sales_history():
    with get_db() as db: sales=db.execute("SELECT s.*,u.name user_name FROM sales s JOIN users u ON u.id=s.user_id ORDER BY s.id DESC LIMIT 100").fetchall()
    return render_template("sales.html",sales=sales)

@bp.post("/sales/<int:sale_id>/cancel")
@admin_required
def cancel_sale(sale_id):
    reason=request.form.get("reason","").strip(); user=current_user()
    if len(reason)<3: flash("Informe o motivo do cancelamento.","error"); return redirect(url_for("main.sales_history"))
    try:
        with get_db() as db:
            sale_row=db.execute("SELECT * FROM sales WHERE id=?",(sale_id,)).fetchone()
            if not sale_row or sale_row["status"]!="completed": raise ValueError("Venda já cancelada ou inexistente.")
            for item in db.execute("SELECT * FROM sale_items WHERE sale_id=?",(sale_id,)).fetchall(): change_stock(db,item["product_id"],item["quantity"],user["id"],"Cancelamento",reason=reason,reference_type="sale",reference_id=sale_id)
            db.execute("UPDATE sales SET status='cancelled',cancel_reason=?,cancelled_at=?,cancelled_by=? WHERE id=?",(reason,now_iso(),user["id"],sale_id)); audit(db,user["id"],"Venda cancelada","sale",sale_id,reason)
        flash("Venda cancelada e estoque devolvido.","success")
    except ValueError as exc: flash(str(exc),"error")
    return redirect(url_for("main.sales_history"))

@bp.route("/purchases", methods=["GET","POST"])
@login_required
def purchases():
    user=current_user()
    if request.method=="POST":
        try:
            entries=[]; total=0
            with get_db() as db:
                for pid,qty_raw,cost_raw in zip(request.form.getlist("product_id"),request.form.getlist("quantity"),request.form.getlist("unit_cost")):
                    if not qty_raw: continue
                    qty=parse_qty(qty_raw); cost=parse_money(cost_raw); product=db.execute("SELECT * FROM products WHERE id=?",(int(pid),)).fetchone()
                    if not product: raise ValueError("Produto inválido.")
                    entries.append((product,qty,cost)); total+=qty*cost
                if not entries: raise ValueError("Adicione ao menos um produto.")
                cur=db.execute("INSERT INTO purchases(purchased_at,user_id,supplier,notes,total_cents) VALUES (?,?,?,?,?)",(now_iso(),user["id"],request.form.get("supplier","").strip(),request.form.get("notes","").strip(),total)); purchase_id=cur.lastrowid
                for product,qty,cost in entries:
                    db.execute("INSERT INTO purchase_items(purchase_id,product_id,quantity,unit_cost_cents,total_cents) VALUES (?,?,?,?,?)",(purchase_id,product["id"],qty,cost,qty*cost)); old_qty=product["stock_qty"]; old_avg=product["avg_cost_cents"]; new_avg=((old_qty*old_avg)+(qty*cost))//(old_qty+qty) if old_qty+qty else cost; db.execute("UPDATE products SET avg_cost_cents=?,last_cost_cents=?,updated_at=? WHERE id=?",(new_avg,cost,now_iso(),product["id"])); db.execute("INSERT INTO product_cost_history(product_id,changed_at,unit_cost_cents,source,reference_id,user_id) VALUES (?,?,?,?,?,?)",(product["id"],now_iso(),cost,"Compra",purchase_id,user["id"])); change_stock(db,product["id"],qty,user["id"],"Entrada",notes=request.form.get("notes","").strip(),reference_type="purchase",reference_id=purchase_id)
                audit(db,user["id"],"Compra registrada","purchase",purchase_id)
            flash("Compra registrada, estoque e custo médio atualizados.","success"); return redirect(url_for("main.purchases"))
        except (ValueError,sqlite3.Error) as exc: flash(str(exc),"error")
    with get_db() as db: products=load_products(db); history=db.execute("SELECT p.*,u.name user_name FROM purchases p JOIN users u ON u.id=p.user_id ORDER BY id DESC LIMIT 50").fetchall()
    return render_template("purchases.html",products=products,history=history)

@bp.route("/stock", methods=["GET","POST"])
@login_required
def stock():
    user=current_user()
    if request.method=="POST":
        try:
            with get_db() as db:
                product_id=int(request.form["product_id"]); qty=parse_qty(request.form["quantity"]); reason=request.form.get("reason","Ajuste"); delta=qty if request.form.get("direction")=="in" else -qty; change_stock(db,product_id,delta,user["id"],reason,notes=request.form.get("notes","").strip()); audit(db,user["id"],"Ajuste manual","stock",product_id,reason)
            flash("Ajuste registrado no histórico.","success")
        except (ValueError,sqlite3.Error) as exc: flash(str(exc),"error")
        return redirect(url_for("main.stock"))
    with get_db() as db: products=load_products(db); movements=db.execute("SELECT sm.*,p.name,u.name user_name FROM stock_movements sm JOIN products p ON p.id=sm.product_id JOIN users u ON u.id=sm.user_id ORDER BY sm.id DESC LIMIT 100").fetchall()
    return render_template("stock.html",products=products,movements=movements)

@bp.route("/inventory", methods=["GET","POST"])
@admin_required
def inventory():
    user=current_user()
    with get_db() as db:
        products=load_products(db)
        if request.method=="POST":
            rows=[]
            for product in products:
                physical=int(request.form.get(f"physical_{product['id']}",product["stock_qty"])); rows.append((product,physical,physical-product["stock_qty"]))
            cur=db.execute("INSERT INTO inventory_counts(counted_at,user_id,notes) VALUES (?,?,?)",(now_iso(),user["id"],request.form.get("notes","").strip())); count_id=cur.lastrowid
            for product,physical,diff in rows:
                db.execute("INSERT INTO inventory_count_items(count_id,product_id,system_qty,physical_qty,difference) VALUES (?,?,?,?,?)",(count_id,product["id"],product["stock_qty"],physical,diff));
                if diff: change_stock(db,product["id"],diff,user["id"],"Inventário",reason="Ajuste de inventário",reference_type="inventory",reference_id=count_id)
            audit(db,user["id"],"Inventário realizado","inventory",count_id); flash("Inventário aplicado e divergências registradas.","success"); return redirect(url_for("main.inventory"))
    return render_template("inventory.html",products=products)

@bp.route("/products", methods=["GET","POST"])
@admin_required
def products():
    user=current_user()
    if request.method=="POST":
        try:
            with get_db() as db:
                pid=request.form.get("id"); name=request.form.get("name","").strip(); price=parse_money(request.form.get("sale_price")); min_stock=int(request.form.get("min_stock",0)); ideal=int(request.form.get("ideal_stock",0))
                if not name or min_stock<0 or ideal<0: raise ValueError("Preencha os dados do produto corretamente.")
                if pid:
                    old=db.execute("SELECT * FROM products WHERE id=?",(int(pid),)).fetchone(); db.execute("UPDATE products SET name=?,category=?,sale_price_cents=?,min_stock=?,ideal_stock=?,notes=?,updated_at=? WHERE id=?",(name,request.form.get("category","Espetos"),price,min_stock,ideal,request.form.get("notes","").strip(),now_iso(),int(pid)))
                    if old["sale_price_cents"]!=price: db.execute("INSERT INTO product_price_history(product_id,changed_at,sale_price_cents,user_id) VALUES (?,?,?,?)",(int(pid),now_iso(),price,user["id"]))
                    audit(db,user["id"],"Produto editado","product",int(pid),name)
                else:
                    cur=db.execute("INSERT INTO products(name,category,sale_price_cents,min_stock,ideal_stock,notes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",(name,request.form.get("category","Espetos"),price,min_stock,ideal,request.form.get("notes","").strip(),now_iso(),now_iso())); audit(db,user["id"],"Produto criado","product",cur.lastrowid,name)
            flash("Produto salvo.","success")
        except (ValueError,sqlite3.IntegrityError): flash("Não foi possível salvar: nome duplicado ou dados inválidos.","error")
        return redirect(url_for("main.products"))
    with get_db() as db: rows=load_products(db)
    return render_template("products.html",products=rows)

@bp.post("/prices")
@admin_required
def prices():
    user=current_user()
    try:
        with get_db() as db:
            for pid,price_raw,min_raw,ideal_raw in zip(request.form.getlist("product_id"),request.form.getlist("sale_price"),request.form.getlist("min_stock"),request.form.getlist("ideal_stock")):
                product=db.execute("SELECT sale_price_cents FROM products WHERE id=?",(int(pid),)).fetchone(); price=parse_money(price_raw); minimum=int(min_raw or 0); ideal=int(ideal_raw or 0)
                if minimum<0 or ideal<0: raise ValueError("Estoque mínimo e ideal não podem ser negativos.")
                db.execute("UPDATE products SET min_stock=?,ideal_stock=?,updated_at=? WHERE id=?",(minimum,ideal,now_iso(),int(pid)))
                if product and product["sale_price_cents"]!=price: db.execute("UPDATE products SET sale_price_cents=?,updated_at=? WHERE id=?",(price,now_iso(),int(pid))); db.execute("INSERT INTO product_price_history(product_id,changed_at,sale_price_cents,user_id) VALUES (?,?,?,?)",(int(pid),now_iso(),price,user["id"]))
            audit(db,user["id"],"Preços atualizados em massa","product")
        flash("Preços atualizados.","success")
    except ValueError as exc: flash(str(exc),"error")
    return redirect(url_for("main.products"))

@bp.route("/reports")
@login_required
def reports():
    period=request.args.get("period","month"); start,end=period_bounds(period)
    with get_db() as db:
        data=metrics(db,start,end); rows=db.execute("SELECT p.name,COALESCE(SUM(CASE WHEN s.status='completed' THEN si.quantity ELSE 0 END),0) qty,COALESCE(SUM(CASE WHEN s.status='completed' THEN si.revenue_cents ELSE 0 END),0) revenue,COALESCE(SUM(CASE WHEN s.status='completed' THEN si.cogs_cents ELSE 0 END),0) cogs,COALESCE(SUM(CASE WHEN s.status='completed' THEN si.gross_profit_cents ELSE 0 END),0) profit FROM products p LEFT JOIN sale_items si ON si.product_id=p.id LEFT JOIN sales s ON s.id=si.sale_id AND s.sold_at BETWEEN ? AND ? WHERE p.active=1 GROUP BY p.id ORDER BY qty DESC",(start,end)).fetchall()
    return render_template("reports.html",data=data,rows=rows,period=period,start=start[:10],end=end[:10])

@bp.route("/close/daily")
@login_required
def daily_close(): start,end=period_bounds("today"); return close_view("Fechamento do Dia",start,end)

@bp.route("/close/monthly")
@login_required
def monthly_close(): start,end=period_bounds("month"); return close_view("Fechamento Mensal",start,end)

def close_view(title,start,end):
    with get_db() as db:
        data=metrics(db,start,end); products=load_products(db); value=sum(p["stock_qty"]*p["avg_cost_cents"] for p in products); rows=db.execute("SELECT p.name,SUM(si.quantity) qty,SUM(si.revenue_cents) revenue,SUM(si.cogs_cents) cogs,SUM(si.gross_profit_cents) profit FROM sale_items si JOIN sales s ON s.id=si.sale_id JOIN products p ON p.id=si.product_id WHERE s.status='completed' AND s.sold_at BETWEEN ? AND ? GROUP BY p.id ORDER BY qty DESC",(start,end)).fetchall()
    return render_template("close.html",title=title,data=data,value=value,rows=rows,start=start[:10])

@bp.route("/need-to-buy")
@login_required
def need_to_buy():
    with get_db() as db:
        products=load_products(db); days=int(get_settings(db).get("moving_average_days",7)); start=(datetime.now()-timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"); result=[]
        for p in products:
            sold=db.execute("SELECT COALESCE(SUM(si.quantity),0) qty FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE si.product_id=? AND s.status='completed' AND s.sold_at>=?",(p["id"],start)).fetchone()["qty"]; avg=sold/days; suggestion=max(0,p["ideal_stock"]-p["stock_qty"]); result.append({"p":p,"sold":sold,"avg":avg,"suggestion":suggestion,"days":(p["stock_qty"]/avg if avg else None)})
    return render_template("need_to_buy.html",rows=result,days=days)

@bp.route("/audit")
@admin_required
def audit_page():
    with get_db() as db: logs=db.execute("SELECT a.*,u.name user_name FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 200").fetchall()
    return render_template("audit.html",logs=logs)

@bp.route("/users", methods=["GET","POST"])
@admin_required
def users():
    user=current_user()
    if request.method=="POST":
        name=request.form.get("name","").strip(); username=request.form.get("username","").strip(); password=request.form.get("password",""); role=request.form.get("role","operator")
        if len(name)<2 or len(username)<3 or len(password)<10 or role not in {"admin","operator"}: flash("Preencha nome, usuário, senha (mínimo 10 caracteres) e perfil.","error")
        else:
            try:
                with get_db() as db:
                    cur=db.execute("INSERT INTO users(name,username,password_hash,role,created_at) VALUES (?,?,?,?,?)",(name,username,generate_password_hash(password),role,now_iso())); audit(db,user["id"],"Usuário criado","user",cur.lastrowid,role)
                flash("Usuário criado.","success")
            except sqlite3.IntegrityError: flash("Esse usuário já existe.","error")
        return redirect(url_for("main.users"))
    with get_db() as db: rows=db.execute("SELECT id,name,username,role,active,created_at FROM users ORDER BY name").fetchall()
    return render_template("users.html",users=rows)

@bp.post("/users/<int:user_id>/toggle")
@admin_required
def toggle_user(user_id):
    user=current_user()
    if user_id==user["id"]: flash("Você não pode desativar o próprio usuário.","error")
    else:
        with get_db() as db:
            row=db.execute("SELECT active FROM users WHERE id=?",(user_id,)).fetchone()
            if row: db.execute("UPDATE users SET active=? WHERE id=?",(0 if row["active"] else 1,user_id)); audit(db,user["id"],"Status de usuário alterado","user",user_id)
        flash("Status do usuário atualizado.","success")
    return redirect(url_for("main.users"))

@bp.route("/settings", methods=["GET","POST"])
@admin_required
def settings():
    user=current_user()
    with get_db() as db:
        if request.method=="POST":
            for key in ["establishment_name","daily_goal","moving_average_days","yellow_alert_percent","backup_frequency"]: db.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,request.form.get(key,"")))
            audit(db,user["id"],"Configurações alteradas","settings"); flash("Configurações salvas.","success"); return redirect(url_for("main.settings"))
        values=get_settings(db)
    return render_template("settings.html",settings=values)

@bp.post("/backup")
@admin_required
def backup():
    path=make_backup(); flash(f"Backup criado: {path.name}","success"); return redirect(request.referrer or url_for("main.settings"))

@bp.post("/restore")
@admin_required
def restore():
    user=current_user(); uploaded=request.files.get("backup_file")
    if not uploaded or not uploaded.filename.lower().endswith(".db"): flash("Selecione um arquivo SQLite .db.","error"); return redirect(url_for("main.settings"))
    import sqlite3 as sqlite
    target=current_app.config["DATA_DIR"] / "restore-upload.db"
    try:
        uploaded.save(target); check=sqlite.connect(target); tables={r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}; check.close()
        required={"users","products","sales","sale_items","stock_movements"}
        if not required.issubset(tables): raise ValueError("Arquivo não parece ser um banco do SERV FESTA REGISSOL.")
        make_backup(); from config import DB_PATH; target.replace(DB_PATH)
        with get_db() as db: audit(db,user["id"],"Backup restaurado","database",details=uploaded.filename)
        flash("Backup restaurado. Recarregue a página.","success")
    except (OSError,sqlite.Error,ValueError) as exc: flash(f"Restauração não realizada: {exc}","error")
    finally: target.unlink(missing_ok=True)
    return redirect(url_for("main.settings"))

@bp.get("/export.csv")
@login_required
def export_csv():
    start,end=period_bounds(request.args.get("period","month")); out=io.StringIO(); writer=csv.writer(out); writer.writerow(["Produto","Unidades","Faturamento","Custo dos vendidos","Lucro bruto estimado"])
    with get_db() as db: rows=db.execute("SELECT p.name,COALESCE(SUM(CASE WHEN s.status='completed' THEN si.quantity ELSE 0 END),0),COALESCE(SUM(CASE WHEN s.status='completed' THEN si.revenue_cents ELSE 0 END),0),COALESCE(SUM(CASE WHEN s.status='completed' THEN si.cogs_cents ELSE 0 END),0),COALESCE(SUM(CASE WHEN s.status='completed' THEN si.gross_profit_cents ELSE 0 END),0) FROM products p LEFT JOIN sale_items si ON si.product_id=p.id LEFT JOIN sales s ON s.id=si.sale_id AND s.sold_at BETWEEN ? AND ? GROUP BY p.id ORDER BY p.name",(start,end)).fetchall()
    for row in rows: writer.writerow([row[0],row[1],f"{row[2]/100:.2f}",f"{row[3]/100:.2f}",f"{row[4]/100:.2f}"])
    return send_file(io.BytesIO(out.getvalue().encode("utf-8-sig")),as_attachment=True,download_name=f"relatorio_{start[:10]}_{end[:10]}.csv",mimetype="text/csv")

