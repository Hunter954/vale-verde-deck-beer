from decimal import Decimal, ROUND_HALF_UP
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Order, OrderItem, Product, ProductCategory, Payment, Table, CashRegister, CashMovement, CustomerDebt, StockMovement, Settings
from ..utils import br_now, money as br_money, money_to_decimal
from ..maintenance import normalize_legacy_product_prices_once

pos_bp = Blueprint("pos", __name__)


def _money(value):
    return br_money(value)


def _service_fee_percent():
    row = Settings.query.filter_by(key="service_fee_percent").first()
    try:
        value = Decimal(str(row.value if row and row.value is not None else "10").replace(",", "."))
    except Exception:
        value = Decimal("10")
    if value < 0:
        value = Decimal("0")
    return value


def _thumb_for_product(product):
    """Retorna imagem real do produto quando existir ou um SVG local por tipo."""
    img = (product.image or "").strip().replace("\\", "/")
    if img:
        if img.startswith(("http://", "https://")):
            return img
        if "/products/uploads/" in img:
            return img
        if img.startswith("/app/uploads/"):
            img = img.split("/app/uploads/", 1)[1]
        elif "/uploads/" in img:
            img = img.split("/uploads/", 1)[1]
        img = img.lstrip("/")
        if not img.startswith("products/") and "." in img:
            img = f"products/{img}"
        return url_for("products.uploads", filename=img)

    name = (product.name or "").lower()
    category = ((product.category.name if product.category else "") or "").lower()
    key = "produto"
    if any(t in name for t in ["coca", "refrigerante", "guaran", "sprite", "fanta"]):
        key = "coca"
    elif any(t in name for t in ["água", "agua", "mineral"]):
        key = "agua"
    elif any(t in name for t in ["cerveja", "long", "beer", "heineken", "amstel", "brahma", "skol"]):
        key = "cerveja"
    elif any(t in name for t in ["batata", "frita"]):
        key = "batata"
    elif any(t in name for t in ["anel", "cebola"]):
        key = "aneis"
    elif any(t in name for t in ["frango", "passarinho"]):
        key = "frango"
    elif any(t in name for t in ["picanha", "carne", "bife"]):
        key = "picanha"
    elif "por" in category:
        key = "porcao"
    elif "bebida" in category:
        key = "bebida"
    elif any(t in category for t in ["prato", "lanche", "combo"]):
        key = "prato"
    elif any(t in category for t in ["narg", "ess", "carv"]):
        key = "narguile"
    return url_for("static", filename=f"img/products/{key}.svg")


def _active_order():
    order_id = request.args.get("order_id", type=int)
    if order_id:
        return Order.query.filter(Order.id == order_id, ~Order.status.in_(["Fechada", "Cancelada"])).first()
    table_id = request.args.get("table_id", type=int)
    if table_id:
        return Order.query.filter(Order.table_id == table_id, ~Order.status.in_(["Fechada", "Cancelada"])).order_by(Order.created_at.desc()).first()
    return Order.query.filter(~Order.status.in_(["Fechada", "Cancelada"])).order_by(Order.created_at.desc()).first()


def _refresh_order(order):
    if not order:
        return None
    order.recalc()
    db.session.commit()
    return order


@pos_bp.route("/")
@login_required
def index():
    normalize_legacy_product_prices_once(db, Product, current_app)
    q = (request.args.get("q") or "").strip()
    selected_category = request.args.get("category", "todos")
    open_orders = Order.query.filter(~Order.status.in_(["Fechada", "Cancelada"])).order_by(Order.created_at.desc()).all()
    order = _refresh_order(_active_order())

    categories = ProductCategory.query.filter_by(active=True).order_by(ProductCategory.name).all()
    product_query = Product.query.filter_by(active=True)
    if selected_category not in ("", "todos"):
        try:
            product_query = product_query.filter(Product.category_id == int(selected_category))
        except ValueError:
            selected_category = "todos"
    if q:
        like = f"%{q}%"
        product_query = product_query.filter(db.or_(Product.name.ilike(like), Product.barcode.ilike(like), Product.internal_code.ilike(like)))
    products = product_query.order_by(Product.name).limit(120).all()

    product_cards = [{"product": p, "thumb": _thumb_for_product(p)} for p in products]
    service_preview = Decimal("0.00")
    preview_total = Decimal("0.00")
    active_items = []
    active_item_cards = []
    if order:
        active_items = [i for i in order.items if i.status != "Cancelado"]
        active_item_cards = [{"item": i, "thumb": _thumb_for_product(i.product)} for i in active_items]
        service_percent = _service_fee_percent()
        service_preview = (Decimal(order.subtotal or 0) * service_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        preview_total = Decimal(order.subtotal or 0) + service_preview

    return render_template(
        "pos/index.html",
        open_orders=open_orders,
        order=order,
        products=products,
        product_cards=product_cards,
        categories=categories,
        selected_category=str(selected_category),
        q=q,
        active_items=active_items,
        active_item_cards=active_item_cards,
        service_preview=service_preview,
        preview_total=preview_total,
        service_fee_percent=_service_fee_percent(),
        money=_money,
    )


@pos_bp.route("/quick", methods=["POST"])
@login_required
def quick_sale():
    order = Order(type="Balcão", status="Aberta", opened_by=current_user)
    db.session.add(order); db.session.flush()
    order.code = f"VV{order.id:06d}"
    db.session.commit()
    return redirect(url_for("pos.index", order_id=order.id))


@pos_bp.route("/order/<int:order_id>", methods=["GET", "POST"])
@login_required
def order(order_id):
    order = Order.query.get_or_404(order_id)
    order.recalc()
    db.session.commit()
    return render_template("pos/order.html", order=order)


@pos_bp.route("/order/<int:order_id>/add-product", methods=["POST"])
@login_required
def add_product(order_id):
    order = Order.query.get_or_404(order_id)
    product = Product.query.get_or_404(request.form["product_id"])
    qty = Decimal(request.form.get("quantity") or "1")
    if qty <= 0:
        flash("Quantidade inválida.", "danger")
        return redirect(url_for("pos.index", order_id=order.id))

    item = OrderItem.query.filter_by(order_id=order.id, product_id=product.id, status="Pendente").first()
    if item and not (request.form.get("note") or "").strip():
        item.quantity = Decimal(item.quantity or 0) + qty
        item.total = Decimal(item.quantity or 0) * Decimal(item.unit_price or 0)
    else:
        unit = Decimal(product.price or 0)
        item = OrderItem(order=order, product=product, sector=product.sector, quantity=qty,
                         unit_price=unit, total=unit * qty, note=request.form.get("note"),
                         person_name=request.form.get("person_name"), status="Pendente")
        db.session.add(item)
        db.session.flush()

    product.stock = Decimal(product.stock or 0) - qty
    db.session.add(StockMovement(product=product, type="Venda", quantity=-qty, unit_cost=product.cost,
                                 note=f"Baixa venda pelo PDV pedido {order.code}", user=current_user))
    order.recalc()
    if order.table:
        order.table.status = "Ocupada"
    db.session.commit()
    return redirect(url_for("pos.index", order_id=order.id, category=request.form.get("category") or "todos", q=request.form.get("q") or ""))


@pos_bp.route("/item/<int:item_id>/quantity", methods=["POST"])
@login_required
def update_quantity(item_id):
    item = OrderItem.query.get_or_404(item_id)
    action = request.form.get("action")
    current_qty = Decimal(item.quantity or 0)
    new_qty = current_qty
    if action == "minus":
        new_qty = current_qty - Decimal("1")
    elif action == "plus":
        new_qty = current_qty + Decimal("1")
    else:
        new_qty = Decimal(request.form.get("quantity") or current_qty)

    if new_qty <= 0:
        item.status = "Cancelado"
        item.cancelled_reason = "Removido pelo PDV"
        item.product.stock = Decimal(item.product.stock or 0) + current_qty
        db.session.add(StockMovement(product=item.product, type="Ajuste", quantity=current_qty,
                                     unit_cost=item.product.cost, note=f"Estorno remoção PDV item #{item.id}", user=current_user))
    else:
        diff = new_qty - current_qty
        item.quantity = new_qty
        item.total = Decimal(item.unit_price or 0) * new_qty
        if diff:
            item.product.stock = Decimal(item.product.stock or 0) - diff
            db.session.add(StockMovement(product=item.product, type="Venda" if diff > 0 else "Ajuste", quantity=-diff,
                                         unit_cost=item.product.cost, note=f"Ajuste quantidade PDV item #{item.id}", user=current_user))
    item.order.recalc()
    db.session.commit()
    return redirect(url_for("pos.index", order_id=item.order.id))


@pos_bp.route("/order/<int:order_id>/send-kitchen", methods=["POST"])
@login_required
def send_kitchen(order_id):
    order = Order.query.get_or_404(order_id)
    for item in order.items:
        if item.status not in ["Cancelado", "Pronto", "Entregue"]:
            item.status = "Pendente"
    if order.table:
        order.table.status = "Ocupada"
    db.session.commit()
    flash("Pedido enviado para a cozinha/KDS.", "success")
    return redirect(url_for("pos.index", order_id=order.id))


@pos_bp.route("/order/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    for item in order.items:
        if item.status != "Cancelado":
            item.status = "Cancelado"
            item.cancelled_reason = "Pedido cancelado pelo PDV"
            item.product.stock = Decimal(item.product.stock or 0) + Decimal(item.quantity or 0)
    order.status = "Cancelada"
    order.closed_at = br_now()
    order.closed_by = current_user
    if order.table:
        order.table.status = "Livre"
        order.table.current_order_id = None
    db.session.commit()
    flash("Pedido cancelado.", "warning")
    return redirect(url_for("pos.index"))


@pos_bp.route("/order/<int:order_id>/discount", methods=["POST"])
@login_required
def discount(order_id):
    order = Order.query.get_or_404(order_id)
    order.discount = money_to_decimal(request.form.get("discount"))
    order.service_fee = money_to_decimal(request.form.get("service_fee"))
    order.recalc()
    db.session.commit()
    flash("Totais atualizados.", "success")
    return redirect(url_for("pos.order", order_id=order.id))


@pos_bp.route("/order/<int:order_id>/pay", methods=["POST"])
@login_required
def pay(order_id):
    order = Order.query.get_or_404(order_id)
    amount = money_to_decimal(request.form.get("amount"))
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
        order.closed_at = br_now()
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
