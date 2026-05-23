from datetime import datetime, timedelta
from sqlalchemy import func
from flask import Blueprint, render_template, request
from flask_login import login_required
from ..extensions import db
from ..models import Order, OrderItem, Product, Payment, StockMovement, CustomerDebt, CancellationLog, DiscountLog

reports_bp = Blueprint("reports", __name__)

@reports_bp.route("/")
@login_required
def index():
    start = request.args.get("start")
    end = request.args.get("end")
    q = Order.query.filter(Order.status=="Fechada")
    if start:
        q = q.filter(Order.closed_at >= datetime.fromisoformat(start))
    if end:
        q = q.filter(Order.closed_at <= datetime.fromisoformat(end) + timedelta(days=1))
    orders = q.order_by(Order.closed_at.desc()).all()
    total = sum([o.total or 0 for o in orders])

    by_payment = db.session.query(Payment.method, func.sum(Payment.amount)).group_by(Payment.method).all()
    by_category = db.session.query(Product.name, func.sum(OrderItem.quantity), func.sum(OrderItem.total)).join(OrderItem).group_by(Product.name).order_by(func.sum(OrderItem.total).desc()).limit(20).all()
    debts = CustomerDebt.query.filter_by(status="Aberto").all()
    return render_template("reports/index.html", orders=orders, total=total, by_payment=by_payment, by_category=by_category, debts=debts)
