from decimal import Decimal
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Order, OrderItem, Product, StockMovement, CancellationLog, Table

orders_bp = Blueprint("orders", __name__)

def decrease_stock(product, qty, order_item=None):
    product.stock = (product.stock or 0) - qty
    db.session.add(StockMovement(product=product, type="Venda", quantity=-qty, unit_cost=product.cost,
                                 note=f"Baixa venda item #{order_item.id if order_item else ''}", user=current_user))

@orders_bp.route("/<int:order_id>/add-item", methods=["POST"])
@login_required
def add_item(order_id):
    order = Order.query.get_or_404(order_id)
    product = Product.query.get_or_404(request.form["product_id"])
    qty = Decimal(request.form.get("quantity") or "1")
    unit = product.price or Decimal("0")
    item = OrderItem(order=order, product=product, sector=product.sector, quantity=qty,
                     unit_price=unit, total=unit * qty, note=request.form.get("note"),
                     person_name=request.form.get("person_name"), status="Pendente")
    db.session.add(item)
    db.session.flush()
    decrease_stock(product, qty, item)
    order.recalc()
    if order.table:
        order.table.status = "Pedido em preparo"
    db.session.commit()
    flash("Item enviado para o setor correto.", "success")
    if order.table:
        return redirect(url_for("tables.detail", table_id=order.table.id))
    return redirect(url_for("pos.order", order_id=order.id))

@orders_bp.route("/item/<int:item_id>/status", methods=["POST"])
@login_required
def item_status(item_id):
    item = OrderItem.query.get_or_404(item_id)
    status = request.form.get("status") or (request.json or {}).get("status")
    if status not in ["Pendente", "Em preparo", "Pronto", "Entregue", "Cancelado"]:
        return jsonify({"ok": False, "error": "Status inválido"}), 400
    item.status = status
    db.session.commit()
    return jsonify({"ok": True, "status": item.status})

@orders_bp.route("/item/<int:item_id>/cancel", methods=["POST"])
@login_required
def cancel_item(item_id):
    item = OrderItem.query.get_or_404(item_id)
    reason = request.form.get("reason", "Cancelamento sem motivo informado")
    if item.status != "Cancelado":
        item.status = "Cancelado"
        item.cancelled_reason = reason
        item.product.stock = (item.product.stock or 0) + item.quantity
        db.session.add(StockMovement(product=item.product, type="Ajuste", quantity=item.quantity,
                                     unit_cost=item.product.cost, note=f"Estorno cancelamento item #{item.id}", user=current_user))
        db.session.add(CancellationLog(order_item=item, reason=reason, user=current_user))
        item.order.recalc()
        db.session.commit()
        flash("Item cancelado e estoque estornado.", "warning")
    return redirect(request.referrer or url_for("dashboard.index"))
