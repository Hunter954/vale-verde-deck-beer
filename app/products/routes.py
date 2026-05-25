from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from sqlalchemy import or_
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Product, ProductCategory, PreparationSector, StockMovement

products_bp = Blueprint("products", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def money_to_decimal(value, default="0"):
    if value is None:
        value = default
    value = str(value).strip().replace("R$", "").replace(".", "").replace(",", ".")
    if value == "":
        value = default
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def number_to_decimal(value, default="0"):
    if value is None:
        value = default
    value = str(value).strip().replace(",", ".")
    if value == "":
        value = default
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def int_value(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def clean_optional(value):
    value = (value or "").strip()
    return value or None


def upload_root():
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "products"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_image(file):
    if not file or not file.filename:
        return None

    original_name = secure_filename(file.filename)
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato de imagem inválido. Use PNG, JPG, JPEG, WEBP ou GIF.")

    file.stream.seek(0, 2)
    size = file.stream.tell()
    file.stream.seek(0)
    if size and size > MAX_IMAGE_BYTES:
        raise ValueError("Imagem muito pesada. Envie uma imagem com até 8MB.")

    filename = f"{uuid4().hex}.{ext}"
    path = upload_root() / filename
    file.save(path)
    return f"products/{filename}"


def product_image_url(product):
    if product and product.image:
        return url_for("products.uploads", filename=product.image)
    return url_for("static", filename="img/products/produto.svg")


@products_bp.app_context_processor
def inject_product_helpers():
    return {"product_image_url": product_image_url}


@products_bp.errorhandler(RequestEntityTooLarge)
def file_too_large(error):
    flash("Imagem muito pesada. Envie uma imagem com até 8MB.", "danger")
    return redirect(request.referrer or url_for("products.index"))


@products_bp.route("/")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "all").lower()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    if per_page not in (8, 10, 15, 20, 50):
        per_page = 10

    query = Product.query.outerjoin(ProductCategory)

    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Product.name.ilike(like),
            Product.internal_code.ilike(like),
            Product.barcode.ilike(like),
            ProductCategory.name.ilike(like),
        ))

    if status == "active":
        query = query.filter(Product.active.is_(True))
    elif status == "inactive":
        query = query.filter(Product.active.is_(False))
    else:
        status = "all"

    pagination = query.order_by(Product.name.asc()).paginate(page=page, per_page=per_page, error_out=False)

    total_count = Product.query.count()
    active_count = Product.query.filter(Product.active.is_(True)).count()
    inactive_count = Product.query.filter(Product.active.is_(False)).count()

    return render_template(
        "products/index.html",
        products=pagination.items,
        pagination=pagination,
        q=q,
        status=status,
        per_page=per_page,
        total_count=total_count,
        active_count=active_count,
        inactive_count=inactive_count,
    )


def apply_product_form(product):
    product.name = (request.form.get("name") or "").strip()
    product.category_id = request.form.get("category_id") or None
    product.sector_id = request.form.get("sector_id") or None
    product.price = money_to_decimal(request.form.get("price"))
    product.cost = money_to_decimal(request.form.get("cost"))
    product.stock = number_to_decimal(request.form.get("stock"))
    product.min_stock = number_to_decimal(request.form.get("min_stock"))
    product.internal_code = clean_optional(request.form.get("internal_code"))
    product.barcode = clean_optional(request.form.get("barcode"))
    product.active = bool(request.form.get("active"))
    product.controlled = bool(request.form.get("controlled"))
    product.adult_warning = bool(request.form.get("adult_warning"))
    product.prep_note = clean_optional(request.form.get("prep_note"))
    product.avg_prep_minutes = int_value(request.form.get("avg_prep_minutes"))


@products_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    categories = ProductCategory.query.order_by(ProductCategory.name).all()
    sectors = PreparationSector.query.order_by(PreparationSector.name).all()
    if request.method == "POST":
        product = Product()
        apply_product_form(product)
        if not product.name:
            flash("Informe o nome do produto.", "danger")
            return render_template("products/form.html", product=product, categories=categories, sectors=sectors)
        try:
            img = save_image(request.files.get("image"))
            if img:
                product.image = img
            db.session.add(product)
            db.session.flush()
            if product.stock and product.stock > 0:
                db.session.add(StockMovement(product=product, type="Entrada", quantity=product.stock, unit_cost=product.cost, note="Estoque inicial", user=current_user))
            db.session.commit()
            flash("Produto cadastrado com sucesso.", "success")
            return redirect(url_for("products.index"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception("Erro ao cadastrar produto")
            flash("Não foi possível salvar o produto. Confira código interno/código de barras duplicado e tente novamente.", "danger")
    return render_template("products/form.html", product=None, categories=categories, sectors=sectors)


@products_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    product = Product.query.get_or_404(id)
    categories = ProductCategory.query.order_by(ProductCategory.name).all()
    sectors = PreparationSector.query.order_by(PreparationSector.name).all()
    if request.method == "POST":
        old_stock = Decimal(product.stock or 0)
        try:
            apply_product_form(product)
            img = save_image(request.files.get("image"))
            if img:
                product.image = img
            diff = Decimal(product.stock or 0) - old_stock
            if diff:
                db.session.add(StockMovement(product=product, type="Ajuste", quantity=diff, unit_cost=product.cost, note="Ajuste manual no cadastro", user=current_user))
            db.session.commit()
            flash("Produto atualizado com sucesso.", "success")
            return redirect(url_for("products.index", q=request.args.get("q", ""), status=request.args.get("status", "all")))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao atualizar produto")
            flash("Não foi possível atualizar o produto. Confira código interno/código de barras duplicado e tente novamente.", "danger")
    return render_template("products/form.html", product=product, categories=categories, sectors=sectors)


@products_bp.route("/<int:id>/duplicate", methods=["POST"])
@login_required
def duplicate(id):
    source = Product.query.get_or_404(id)
    clone = Product(
        name=f"{source.name} cópia",
        image=source.image,
        category_id=source.category_id,
        sector_id=source.sector_id,
        price=source.price,
        cost=source.cost,
        stock=0,
        min_stock=source.min_stock,
        internal_code=None,
        barcode=None,
        active=source.active,
        controlled=source.controlled,
        adult_warning=source.adult_warning,
        prep_note=source.prep_note,
        avg_prep_minutes=source.avg_prep_minutes,
    )
    db.session.add(clone)
    db.session.commit()
    flash("Produto duplicado. Edite nome, códigos e estoque se necessário.", "success")
    return redirect(url_for("products.edit", id=clone.id))


@products_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    product = Product.query.get_or_404(id)
    try:
        db.session.delete(product)
        db.session.commit()
        flash("Produto excluído.", "success")
    except Exception:
        db.session.rollback()
        product.active = False
        db.session.commit()
        flash("Produto já possui movimentações/pedidos. Ele foi marcado como inativo para preservar o histórico.", "warning")
    return redirect(url_for("products.index"))


@products_bp.route("/<int:id>/toggle", methods=["POST"])
@login_required
def toggle(id):
    product = Product.query.get_or_404(id)
    product.active = not product.active
    db.session.commit()
    flash("Status do produto atualizado.", "success")
    return redirect(request.referrer or url_for("products.index"))


@products_bp.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
