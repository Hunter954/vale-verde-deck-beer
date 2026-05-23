from datetime import datetime, timedelta
from sqlalchemy import func
from flask import Blueprint, render_template
from flask_login import login_required
from ..extensions import db
from ..models import Order, Table, Product, Payment, OrderItem, CashMovement, DiscountLog, CancellationLog

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@login_required
def index():
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    def sales_since(d):
        return db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(Order.status=="Fechada", Order.closed_at >= datetime.combine(d, datetime.min.time())).scalar()

    cards = {
        "day": sales_since(today),
        "week": sales_since(week_start),
        "month": sales_since(month_start),
        "open_tables": Table.query.filter(Table.status!="Livre").count(),
        "open_orders": Order.query.filter(Order.status!="Fechada").count(),
        "low_stock": Product.query.filter(Product.stock <= Product.min_stock, Product.active==True).count(),
        "discounts": db.session.query(func.coalesce(func.sum(DiscountLog.amount), 0)).scalar(),
        "cancellations": CancellationLog.query.count(),
    }

    top_products = (
        db.session.query(Product.name, func.sum(OrderItem.quantity).label("qty"))
        .join(OrderItem, Product.id == OrderItem.product_id)
        .filter(OrderItem.status != "Cancelado")
        .group_by(Product.name).order_by(func.sum(OrderItem.quantity).desc()).limit(8).all()
    )
    payment_methods = (
        db.session.query(Payment.method, func.coalesce(func.sum(Payment.amount), 0))
        .group_by(Payment.method).all()
    )
    employee_sales = (
        db.session.query(Order.opened_by_id, func.coalesce(func.sum(Order.total), 0), func.count(Order.id))
        .filter(Order.status=="Fechada").group_by(Order.opened_by_id).limit(10).all()
    )
    movements = CashMovement.query.order_by(CashMovement.created_at.desc()).limit(8).all()
    return render_template("dashboard/index.html", cards=cards, top_products=top_products,
                           payment_methods=payment_methods, employee_sales=employee_sales, movements=movements)
