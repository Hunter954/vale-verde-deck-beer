from pathlib import Path
from uuid import uuid4
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from ..extensions import db
from ..models import Product, ProductCategory, PreparationSector, StockMovement

products_bp = Blueprint("products", __name__)

ALLOWED = {"png", "jpg", "jpeg", "webp", "gif"}

def save_image(file):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return None
    filename = f"{uuid4().hex}.{ext}"
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "products"
    folder.mkdir(parents=True, exist_ok=True)
    file.save(folder / filename)
    return f"products/{filename}"

@products_bp.route("/")
@login_required
def index():
    q = request.args.get("q", "")
    query = Product.query
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    products = query.order_by(Product.name).all()
    return render_template("products/index.html", products=products, q=q)

@products_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    categories = ProductCategory.query.order_by(ProductCategory.name).all()
    sectors = PreparationSector.query.order_by(PreparationSector.name).all()
    if request.method == "POST":
        p = Product(
            name=request.form["name"],
            category_id=request.form.get("category_id") or None,
            sector_id=request.form.get("sector_id") or None,
            price=request.form.get("price") or 0,
            cost=request.form.get("cost") or 0,
            stock=request.form.get("stock") or 0,
            min_stock=request.form.get("min_stock") or 0,
            internal_code=request.form.get("internal_code") or None,
            barcode=request.form.get("barcode") or None,
            active=bool(request.form.get("active")),
            controlled=bool(request.form.get("controlled")),
            adult_warning=bool(request.form.get("adult_warning")),
            prep_note=request.form.get("prep_note"),
            avg_prep_minutes=request.form.get("avg_prep_minutes") or 0,
        )
        p.image = save_image(request.files.get("image"))
        db.session.add(p)
        db.session.flush()
        if float(p.stock or 0) > 0:
            db.session.add(StockMovement(product=p, type="Entrada", quantity=p.stock, unit_cost=p.cost, note="Estoque inicial", user=current_user))
        db.session.commit()
        flash("Produto cadastrado.", "success")
        return redirect(url_for("products.index"))
    return render_template("products/form.html", product=None, categories=categories, sectors=sectors)

@products_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    product = Product.query.get_or_404(id)
    categories = ProductCategory.query.order_by(ProductCategory.name).all()
    sectors = PreparationSector.query.order_by(PreparationSector.name).all()
    if request.method == "POST":
        old_stock = product.stock
        for field in ["name", "internal_code", "barcode", "prep_note"]:
            setattr(product, field, request.form.get(field))
        product.category_id = request.form.get("category_id") or None
        product.sector_id = request.form.get("sector_id") or None
        product.price = request.form.get("price") or 0
        product.cost = request.form.get("cost") or 0
        product.stock = request.form.get("stock") or 0
        product.min_stock = request.form.get("min_stock") or 0
        product.avg_prep_minutes = request.form.get("avg_prep_minutes") or 0
        product.active = bool(request.form.get("active"))
        product.controlled = bool(request.form.get("controlled"))
        product.adult_warning = bool(request.form.get("adult_warning"))
        img = save_image(request.files.get("image"))
        if img:
            product.image = img
        diff = product.stock - old_stock
        if diff:
            db.session.add(StockMovement(product=product, type="Ajuste", quantity=diff, unit_cost=product.cost, note="Ajuste manual no cadastro", user=current_user))
        db.session.commit()
        flash("Produto atualizado.", "success")
        return redirect(url_for("products.index"))
    return render_template("products/form.html", product=product, categories=categories, sectors=sectors)

@products_bp.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
