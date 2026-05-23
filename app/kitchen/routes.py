from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from ..models import OrderItem, PreparationSector
from ..extensions import db

kitchen_bp = Blueprint("kitchen", __name__)

@kitchen_bp.route("/")
@login_required
def index():
    sector_slug = request.args.get("sector", "cozinha")
    sector = PreparationSector.query.filter_by(slug=sector_slug).first()
    sectors = PreparationSector.query.order_by(PreparationSector.name).all()
    items = []
    if sector:
        items = OrderItem.query.filter(OrderItem.sector_id==sector.id, OrderItem.status.in_(["Pendente", "Em preparo", "Pronto"])).order_by(OrderItem.created_at).all()
    return render_template("kitchen/index.html", items=items, sectors=sectors, active_sector=sector)

@kitchen_bp.route("/api/items")
@login_required
def api_items():
    sector_slug = request.args.get("sector", "cozinha")
    sector = PreparationSector.query.filter_by(slug=sector_slug).first_or_404()
    items = OrderItem.query.filter(OrderItem.sector_id==sector.id, OrderItem.status.in_(["Pendente", "Em preparo", "Pronto"])).order_by(OrderItem.created_at).all()
    return jsonify([{
        "id": i.id,
        "table": f"Mesa {i.order.table.number:02d}" if i.order.table else i.order.type,
        "product": i.product.name,
        "quantity": float(i.quantity),
        "note": i.note or "",
        "status": i.status,
        "created_at": i.created_at.strftime("%H:%M")
    } for i in items])

@kitchen_bp.route("/api/items/<int:item_id>/status", methods=["POST"])
@login_required
def api_item_status(item_id):
    item = OrderItem.query.get_or_404(item_id)
    status = (request.json or {}).get("status")
    if status not in ["Pendente", "Em preparo", "Pronto", "Entregue"]:
        return jsonify({"ok": False}), 400
    item.status = status
    db.session.commit()
    return jsonify({"ok": True})
