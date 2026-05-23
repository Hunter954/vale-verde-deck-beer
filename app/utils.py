from functools import wraps
from flask import abort
from flask_login import current_user

def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.has_role("Admin") or current_user.has_role(*roles):
                return fn(*args, **kwargs)
            abort(403)
        return wrapper
    return deco

def money(value):
    try:
        return f"R$ {float(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"
