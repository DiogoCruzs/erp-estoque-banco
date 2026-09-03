from functools import wraps
from secrets import token_urlsafe
from flask import session, redirect, url_for, request, abort
from .db import get_db

def current_user():
    user_id = session.get("user_id")
    if not user_id: return None
    with get_db() as db: return db.execute("SELECT * FROM users WHERE id=? AND active=1", (user_id,)).fetchone()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user(): return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user: return redirect(url_for("main.login"))
        if user["role"] != "admin": abort(403)
        return view(*args, **kwargs)
    return wrapped

def csrf_token():
    if "csrf_token" not in session: session["csrf_token"] = token_urlsafe(32)
    return session["csrf_token"]

def validate_csrf():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not supplied or supplied != session.get("csrf_token"): abort(400, "Token de segurança inválido.")

