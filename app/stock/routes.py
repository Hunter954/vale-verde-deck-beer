from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Product, StockMovement, Supplier

stock_bp = Blueprint("stock", __name__)

@stock_bp.route("/")
@login_required
def index():
    products = Product.query.order_by(Product.name).all()
    movements = StockMovement.query.order_by(StockMovement.created_at.desc()).limit(80).all()
    suppliers = Supplier.query.order_by(Supplier.name).all()
    return render_template("stock/index.html", products=products, movements=movements, suppliers=suppliers)

@stock_bp.route("/movement", methods=["POST"])
@login_required
def movement():
    product = Product.query.get_or_404(request.form["product_id"])
    qty = float(request.form.get("quantity") or 0)
    mtype = request.form.get("type")
    if mtype in ["Saída", "Perda", "Consumo interno", "Transferência"]:
        qty = -abs(qty)
    product.stock = (product.stock or 0) + qty
    db.session.add(StockMovement(product=product, type=mtype, quantity=qty,
                                 unit_cost=request.form.get("unit_cost") or product.cost or 0,
                                 note=request.form.get("note"), user=current_user))
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
