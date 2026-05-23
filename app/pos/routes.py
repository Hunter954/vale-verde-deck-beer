from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Order, Product, Payment, Table, CashRegister, CashMovement, CustomerDebt

pos_bp = Blueprint("pos", __name__)

@pos_bp.route("/")
@login_required
def index():
    open_orders = Order.query.filter(Order.status!="Fechada").order_by(Order.created_at.desc()).all()
    products = Product.query.filter_by(active=True).order_by(Product.name).limit(80).all()
    return render_template("pos/index.html", open_orders=open_orders, products=products)

@pos_bp.route("/quick", methods=["POST"])
@login_required
def quick_sale():
    order = Order(type="Balcão", status="Aberta", opened_by=current_user)
    db.session.add(order); db.session.flush()
    order.code = f"VV{order.id:06d}"
    db.session.commit()
    return redirect(url_for("pos.order", order_id=order.id))

@pos_bp.route("/order/<int:order_id>", methods=["GET", "POST"])
@login_required
def order(order_id):
    order = Order.query.get_or_404(order_id)
    order.recalc()
    db.session.commit()
    return render_template("pos/order.html", order=order)

@pos_bp.route("/order/<int:order_id>/discount", methods=["POST"])
@login_required
def discount(order_id):
    order = Order.query.get_or_404(order_id)
    order.discount = Decimal(request.form.get("discount") or 0)
    order.service_fee = Decimal(request.form.get("service_fee") or 0)
    order.recalc()
    db.session.commit()
    flash("Totais atualizados.", "success")
    return redirect(url_for("pos.order", order_id=order.id))

@pos_bp.route("/order/<int:order_id>/pay", methods=["POST"])
@login_required
def pay(order_id):
    order = Order.query.get_or_404(order_id)
    amount = Decimal(request.form.get("amount") or 0)
    method = request.form.get("method")
    if amount <= 0:
        flash("Informe um valor válido.", "danger")
        return redirect(url_for("pos.order", order_id=order.id))
    db.session.add(Payment(order=order, amount=amount, method=method, operator=current_user, note=request.form.get("note")))
    if method == "Fiado":
        db.session.add(CustomerDebt(customer=order.customer, description=f"Fiado pedido {order.code}", amount=amount, status="Aberto"))
    db.session.commit()
    paid = sum([p.amount for p in order.payments])
    order.recalc()
    if paid >= order.total:
        order.status = "Fechada"
        order.closed_at = datetime.utcnow()
        order.closed_by = current_user
        if order.table:
            order.table.status = "Livre"
            order.table.current_order_id = None
        db.session.add(CashMovement(type="Venda", amount=order.total, note=f"Pedido {order.code}", user=current_user))
        flash("Conta fechada com sucesso.", "success")
    else:
        flash("Pagamento parcial registrado.", "info")
    db.session.commit()
    return redirect(url_for("pos.order", order_id=order.id))
