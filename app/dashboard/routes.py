from datetime import datetime, timedelta
from decimal import Decimal

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from ..extensions import db
from ..models import Order, Table, Product, Payment, OrderItem
from ..utils import br_now


dashboard_bp = Blueprint("dashboard", __name__)


def _money(value):
    return float(value or 0)


def _percent_change(current, previous):
    current = float(current or 0)
    previous = float(previous or 0)
    if previous <= 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def _sum_closed_orders_between(start, end):
    return db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.status == "Fechada",
        Order.closed_at >= start,
        Order.closed_at < end,
    ).scalar() or Decimal("0")


@dashboard_bp.route("/")
@login_required
def index():
    now = br_now()
    today = now.date()
    today_start = datetime.combine(today, datetime.min.time())
    tomorrow_start = today_start + timedelta(days=1)
    yesterday_start = today_start - timedelta(days=1)

    total_today = _sum_closed_orders_between(today_start, tomorrow_start)
    total_yesterday = _sum_closed_orders_between(yesterday_start, today_start)

    orders_today = Order.query.filter(
        Order.created_at >= today_start,
        Order.created_at < tomorrow_start,
    ).count()
    orders_yesterday = Order.query.filter(
        Order.created_at >= yesterday_start,
        Order.created_at < today_start,
    ).count()

    closed_today = Order.query.filter(
        Order.status == "Fechada",
        Order.closed_at >= today_start,
        Order.closed_at < tomorrow_start,
    ).count()
    closed_yesterday = Order.query.filter(
        Order.status == "Fechada",
        Order.closed_at >= yesterday_start,
        Order.closed_at < today_start,
    ).count()

    ticket_today = (total_today / closed_today) if closed_today else Decimal("0")
    ticket_yesterday = (total_yesterday / closed_yesterday) if closed_yesterday else Decimal("0")

    customer_ids_today = db.session.query(func.count(func.distinct(Order.customer_id))).filter(
        Order.status == "Fechada",
        Order.closed_at >= today_start,
        Order.closed_at < tomorrow_start,
        Order.customer_id.isnot(None),
    ).scalar() or 0
    customers_today = int(customer_ids_today or closed_today)
    customers_yesterday = Order.query.filter(
        Order.status == "Fechada",
        Order.closed_at >= yesterday_start,
        Order.closed_at < today_start,
    ).count()

    week_labels = []
    week_values = []
    total_period = Decimal("0")
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        value = _sum_closed_orders_between(start, end)
        total_period += value
        week_labels.append(day.strftime("%d/%m"))
        week_values.append(_money(value))

    payments_today = db.session.query(
        Payment.method,
        func.coalesce(func.sum(Payment.amount), 0).label("total"),
    ).filter(
        Payment.created_at >= today_start,
        Payment.created_at < tomorrow_start,
    ).group_by(Payment.method).all()

    payment_palette = {
        "Dinheiro": "#17c964",
        "Cartão": "#339dff",
        "Pix": "#f5b82e",
        "PIX": "#f5b82e",
        "Outros": "#8b5cf6",
    }
    payment_cards = []
    paid_total = sum([row.total or Decimal("0") for row in payments_today], Decimal("0"))
    for method, amount in payments_today:
        total = amount or Decimal("0")
        payment_cards.append({
            "method": (method or "Outros").strip(),
            "total": _money(total),
            "percent": round((float(total) / float(paid_total) * 100), 1) if paid_total else 0,
            "color": payment_palette.get((method or "Outros").strip(), "#8b5cf6"),
        })

    if not payment_cards:
        payment_cards = [
            {"method": "Dinheiro", "total": 0, "percent": 0, "color": "#17c964"},
            {"method": "Cartão", "total": 0, "percent": 0, "color": "#339dff"},
            {"method": "PIX", "total": 0, "percent": 0, "color": "#f5b82e"},
            {"method": "Outros", "total": 0, "percent": 0, "color": "#8b5cf6"},
        ]

    main_payment = max(payment_cards, key=lambda item: item["total"])["method"] if payment_cards else "-"

    occupied_tables = Table.query.filter(Table.status != "Livre").count()
    total_tables = Table.query.count() or 1
    prep_items = OrderItem.query.filter(OrderItem.status.in_(["Pendente", "Em preparo"])).count()
    avg_prep = db.session.query(func.coalesce(func.avg(Product.avg_prep_minutes), 0)).join(
        OrderItem, Product.id == OrderItem.product_id
    ).filter(OrderItem.status.in_(["Pendente", "Em preparo"])).scalar() or 0
    low_stock = Product.query.filter(Product.stock <= Product.min_stock, Product.active == True).count()

    cards = {
        "total_today": _money(total_today),
        "orders_today": orders_today,
        "ticket_today": _money(ticket_today),
        "customers_today": customers_today,
        "sales_change": _percent_change(total_today, total_yesterday),
        "orders_change": _percent_change(orders_today, orders_yesterday),
        "ticket_change": _percent_change(ticket_today, ticket_yesterday),
        "customers_change": _percent_change(customers_today, customers_yesterday),
        "period_total": _money(total_period),
        "daily_avg": _money(total_period / Decimal(len(week_values) or 1)),
        "occupied_tables": occupied_tables,
        "total_tables": total_tables,
        "table_occupation_percent": round((occupied_tables / total_tables) * 100),
        "prep_items": prep_items,
        "avg_prep_minutes": round(float(avg_prep or 0)),
        "low_stock": low_stock,
        "main_payment": main_payment,
        "paid_total": _money(paid_total),
    }

    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    moment_label = f"{today.day:02d} de {meses[today.month - 1]} de {today.year}"

    return render_template(
        "dashboard/index.html",
        title="Dashboard — Vale Verde Deck Beer",
        moment_label=moment_label,
        cards=cards,
        week_labels=week_labels,
        week_values=week_values,
        payment_cards=payment_cards,
        payment_labels=[item["method"] for item in payment_cards],
        payment_values=[item["total"] for item in payment_cards],
        payment_colors=[item["color"] for item in payment_cards],
    )
