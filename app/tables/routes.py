from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Table, Order, Product
from ..utils import br_now, money as br_money

tables_bp = Blueprint("tables", __name__)


def _minutes_opened(dt):
    if not dt:
        return 0
    diff = br_now() - dt
    return max(0, int(diff.total_seconds() // 60))


def _opened_label(minutes):
    if minutes <= 0:
        return "aberta agora"
    if minutes < 60:
        return f"aberta há {minutes} min"
    hours = minutes // 60
    rest = minutes % 60
    if rest:
        return f"aberta há {hours}h {rest}min"
    return f"aberta há {hours}h"


def _format_money(value):
    return br_money(value)


def _table_capacity(number):
    # Capacidade visual padrão sem alterar o banco. Pode ser trocada depois por campo real.
    return 6 if number in (10, 16, 19, 20) else 4


def _reservation_text(table):
    people = _table_capacity(table.number)
    # Enquanto a reserva ainda não tem tela própria de horário, mantemos uma regra previsível por mesa.
    if table.number == 19:
        return f"{people} pessoas", "amanhã às 19:00"
    return f"{people} pessoas", "hoje às 20:00"


def _build_table_cards(tables):
    cards = []
    for table in tables:
        order = Order.query.get(table.current_order_id) if table.current_order_id else None
        if order:
            order.recalc()
            minutes = _minutes_opened(order.created_at)
            cards.append({
                "id": table.id,
                "number": table.number,
                "status": "Ocupada",
                "status_class": "ocupada",
                "main": _format_money(order.total),
                "meta": f"• {minutes//60:02d}:{minutes%60:02d}",
                "footer": _opened_label(minutes),
                "href": url_for("tables.detail", table_id=table.id),
            })
            continue

        status = (table.status or "Livre").strip()
        status_class = status.lower().replace(" ", "-")
        if status.lower() == "reservada":
            main, footer = _reservation_text(table)
            cards.append({
                "id": table.id,
                "number": table.number,
                "status": "Reservada",
                "status_class": "reservada",
                "main": main,
                "meta": "",
                "footer": footer,
                "href": url_for("tables.detail", table_id=table.id),
            })
        else:
            capacity = _table_capacity(table.number)
            main = "Disponível" if table.number % 2 else f"Capacidade {capacity}"
            cards.append({
                "id": table.id,
                "number": table.number,
                "status": "Livre",
                "status_class": "livre",
                "main": main,
                "meta": "",
                "footer": "toque para abrir",
                "href": url_for("tables.detail", table_id=table.id),
            })
    return cards


@tables_bp.route("/")
@login_required
def index():
    tables = Table.query.order_by(Table.number).all()
    cards = _build_table_cards(tables)
    return render_template("tables/index.html", tables=tables, table_cards=cards)


@tables_bp.route("/new", methods=["POST"])
@login_required
def create_table():
    last = db.session.query(db.func.max(Table.number)).scalar() or 0
    table = Table(number=last + 1, status="Livre")
    db.session.add(table)
    db.session.commit()
    flash(f"Mesa {table.number:02d} criada.", "success")
    return redirect(url_for("tables.index"))


@tables_bp.route("/<int:table_id>")
@login_required
def detail(table_id):
    table = Table.query.get_or_404(table_id)
    order = None
    if table.current_order_id:
        order = Order.query.get(table.current_order_id)
        if order:
            order.recalc()
            db.session.commit()
    products = Product.query.filter_by(active=True).order_by(Product.name).all()
    return render_template("tables/detail.html", table=table, order=order, products=products)


@tables_bp.route("/<int:table_id>/open", methods=["POST"])
@login_required
def open_table(table_id):
    table = Table.query.get_or_404(table_id)
    if table.current_order_id:
        return redirect(url_for("tables.detail", table_id=table.id))
    order = Order(type="Mesa", table=table, status="Aberta", opened_by=current_user,
                  customer_name=request.form.get("customer_name"), note=request.form.get("note"))
    db.session.add(order)
    db.session.flush()
    order.code = f"VV{order.id:06d}"
    table.status = "Ocupada"
    table.current_order_id = order.id
    db.session.commit()
    flash(f"Mesa {table.number:02d} aberta.", "success")
    return redirect(url_for("tables.detail", table_id=table.id))


@tables_bp.route("/<int:table_id>/reserve", methods=["POST"])
@login_required
def reserve(table_id):
    table = Table.query.get_or_404(table_id)
    if not table.current_order_id:
        table.status = "Reservada"
        db.session.commit()
        flash("Mesa reservada.", "info")
    return redirect(url_for("tables.index"))
