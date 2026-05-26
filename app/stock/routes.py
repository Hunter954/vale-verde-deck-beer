from decimal import Decimal, InvalidOperation
from math import ceil

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_

from ..extensions import db
from ..models import Product, ProductCategory, StockMovement, Supplier
from ..utils import money_to_decimal

stock_bp = Blueprint("stock", __name__)


def decimal_value(value, default="0"):
    try:
        return Decimal(str(value if value is not None else default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def stock_status(product):
    current = decimal_value(product.stock)
    minimum = decimal_value(product.min_stock)

    if current <= 0:
        return "critical"
    if minimum <= 0:
        return "normal"
    if current <= (minimum * Decimal("0.50")):
        return "critical"
    if current <= minimum:
        return "attention"
    return "normal"


def status_label(status):
    return {
        "normal": "Normal",
        "attention": "Atenção",
        "critical": "Crítico",
    }.get(status, "Normal")


def paginate_items(items, page, per_page):
    total = len(items)
    pages = max(ceil(total / per_page), 1)
    page = min(max(page, 1), pages)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
        "prev_num": page - 1,
        "next_num": page + 1,
    }


@stock_bp.route("/")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "all").lower()
    category_id = request.args.get("category_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    if per_page not in (8, 10, 15, 20, 50):
        per_page = 10

    base_products = Product.query.all()
    total_count = len(base_products)
    attention_count = sum(1 for product in base_products if stock_status(product) == "attention")
    critical_count = sum(1 for product in base_products if stock_status(product) == "critical")

    query = Product.query.outerjoin(ProductCategory)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Product.name.ilike(like),
            Product.internal_code.ilike(like),
            Product.barcode.ilike(like),
            ProductCategory.name.ilike(like),
        ))
    if category_id:
        query = query.filter(Product.category_id == category_id)

    products = query.order_by(Product.name.asc()).all()
    if status in {"normal", "attention", "critical"}:
        products = [product for product in products if stock_status(product) == status]
    else:
        status = "all"

    for product in products:
        product.stock_ui_status = stock_status(product)
        product.stock_ui_label = status_label(product.stock_ui_status)

    pagination = paginate_items(products, page, per_page)
    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    movements = StockMovement.query.order_by(StockMovement.created_at.desc()).limit(20).all()
    suppliers = Supplier.query.order_by(Supplier.name).all()

    return render_template(
        "stock/index.html",
        products=pagination["items"],
        pagination=pagination,
        categories=categories,
        movements=movements,
        suppliers=suppliers,
        q=q,
        status=status,
        category_id=category_id,
        per_page=per_page,
        total_count=total_count,
        attention_count=attention_count,
        critical_count=critical_count,
    )


@stock_bp.route("/movement", methods=["POST"])
@login_required
def movement():
    product = Product.query.get_or_404(request.form["product_id"])
    qty = float(request.form.get("quantity") or 0)
    mtype = request.form.get("type") or "Entrada"
    if mtype in ["Saída", "Perda", "Consumo interno", "Transferência"]:
        qty = -abs(qty)
    elif mtype == "Ajuste":
        qty = qty
    else:
        qty = abs(qty)

    product.stock = (product.stock or 0) + Decimal(str(qty))
    db.session.add(StockMovement(
        product=product,
        type=mtype,
        quantity=Decimal(str(qty)),
        unit_cost=money_to_decimal(request.form.get("unit_cost")) if request.form.get("unit_cost") else (product.cost or 0),
        note=request.form.get("note"),
        user=current_user,
    ))
    db.session.commit()
    flash("Movimentação registrada.", "success")
    return redirect(url_for("stock.index"))


@stock_bp.route("/supplier", methods=["POST"])
@login_required
def supplier():
    db.session.add(Supplier(name=request.form["name"], phone=request.form.get("phone"), email=request.form.get("email")))
    db.session.commit()
    flash("Fornecedor cadastrado.", "success")
    return redirect(url_for("stock.index"))
