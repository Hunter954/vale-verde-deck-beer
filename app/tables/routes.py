from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Table, Order, Product

tables_bp = Blueprint("tables", __name__)

@tables_bp.route("/")
@login_required
def index():
    tables = Table.query.order_by(Table.number).all()
    return render_template("tables/index.html", tables=tables)

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
