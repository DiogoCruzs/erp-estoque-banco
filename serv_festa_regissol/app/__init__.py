from flask import Flask
from config import SECRET_KEY, DATA_DIR, BACKUP_DIR
from .db import init_db

def create_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY=SECRET_KEY, DATA_DIR=DATA_DIR, BACKUP_DIR=BACKUP_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    def brl(cents):
        value = f"{float(cents or 0)/100:,.2f}"
        return "R$ " + value.replace(",", "X").replace(".", ",").replace("X", ".")
    app.jinja_env.filters["brl"] = brl
    app.jinja_env.filters["qty"] = lambda value: f"{float(value or 0):g}"
    init_db()
    from .routes import bp
    app.register_blueprint(bp)
    return app

