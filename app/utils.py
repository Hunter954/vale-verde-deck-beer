from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from zoneinfo import ZoneInfo

from flask import abort
from flask_login import current_user

BR_TZ = ZoneInfo("America/Sao_Paulo")


def br_now():
    """Data/hora atual do Brasil, sem timezone, para manter compatibilidade com colunas DateTime existentes."""
    return datetime.now(BR_TZ).replace(tzinfo=None)


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
        number = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"R$ {number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def money_to_decimal(value, default="0"):
    """
    Aceita valores em formato BR e também digitação de caixa:
    - 350   -> 3,50
    - 35000 -> 350,00
    - 3,50  -> 3,50
    - R$ 3,50 -> 3,50
    """
    if value is None:
        value = default
    raw = str(value).strip()
    if raw == "":
        raw = str(default)

    cleaned = raw.replace("R$", "").replace("r$", "").replace(" ", "").strip()
    negative = cleaned.startswith("-")
    cleaned = cleaned.lstrip("-")

    try:
        if "," in cleaned:
            normalized = cleaned.replace(".", "").replace(",", ".")
            amount = Decimal(normalized or default)
        elif "." in cleaned:
            # Valor vindo de inputs antigos type=number ou banco/template: 7.50 = 7,50.
            amount = Decimal(cleaned or default)
        else:
            digits = "".join(ch for ch in cleaned if ch.isdigit())
            if digits == "":
                amount = Decimal(default)
            else:
                amount = (Decimal(digits) / Decimal("100"))
        if negative:
            amount = -amount
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal(default).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
