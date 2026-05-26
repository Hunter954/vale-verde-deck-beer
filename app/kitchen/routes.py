from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

from ..models import OrderItem, PreparationSector
from ..extensions import db
from ..utils import br_now, money as br_money

kitchen_bp = Blueprint("kitchen", __name__)

KDS_STATUSES = ["Pendente", "Em preparo", "Pronto"]
STATUS_META = {
    "Pendente": {"key": "new", "title": "Novos Pedidos", "icon": "bi-clipboard2-check", "next": "Em preparo"},
    "Em preparo": {"key": "prep", "title": "Em Preparo", "icon": "bi-egg-fried", "next": "Pronto"},
    "Pronto": {"key": "ready", "title": "Prontos", "icon": "bi-check-circle", "next": "Entregue"},
}


def _money(value):
    return br_money(value)


def _fmt_qty(value):
    value = Decimal(value or 0)
    if value == value.to_integral():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".").replace(".", ",")


def _elapsed_parts(dt):
    if not dt:
        return 0, "00:00"
    total = max(0, int((br_now() - dt).total_seconds()))
    minutes = total // 60
    seconds = total % 60
    return minutes, f"{minutes:02d}:{seconds:02d}"


def _base_items_query(sector_slug):
    query = OrderItem.query.filter(OrderItem.status.in_(KDS_STATUSES))
    if sector_slug and sector_slug != "todos":
        sector = PreparationSector.query.filter_by(slug=sector_slug).first()
        if not sector:
            return query.filter(OrderItem.id == 0), None
        query = query.filter(OrderItem.sector_id == sector.id)
        return query, sector
    return query, None


def _build_board(sector_slug="cozinha"):
    query, active_sector = _base_items_query(sector_slug)
    items = query.order_by(OrderItem.created_at.asc()).all()

    grouped = {status: [] for status in KDS_STATUSES}
    buckets = defaultdict(list)
    for item in items:
        buckets[(item.status, item.order_id)].append(item)

    for status in KDS_STATUSES:
        status_groups = [(order_id, group) for (st, order_id), group in buckets.items() if st == status]
        status_groups.sort(key=lambda pair: min((i.created_at for i in pair[1] if i.created_at), default=br_now()))
        for order_id, group_items in status_groups:
            order = group_items[0].order
            table_title = f"Mesa {order.table.number:02d}" if order and order.table else (order.type if order else "Pedido")
            oldest = min((i.created_at for i in group_items if i.created_at), default=br_now())
            minutes, timer = _elapsed_parts(oldest)
            total = sum((Decimal(i.total or 0) for i in group_items), Decimal("0"))
            grouped[status].append({
                "order_id": order_id,
                "order_code": (order.code if order and order.code else f"#{order_id}"),
                "table": table_title,
                "kds_items": group_items,
                "total": total,
                "total_money": _money(total),
                "minutes": minutes,
                "timer": timer,
                "status": status,
                "next_status": STATUS_META[status]["next"],
            })

    summary = {
        "queue": len(grouped["Pendente"]),
        "prep": len(grouped["Em preparo"]),
        "ready": len(grouped["Pronto"]),
        "avg": 0,
    }
    active_minutes = [card["minutes"] for status in KDS_STATUSES for card in grouped[status]]
    if active_minutes:
        summary["avg"] = int(round(sum(active_minutes) / len(active_minutes)))

    return grouped, active_sector, summary


@kitchen_bp.route("/")
@login_required
def index():
    sector_slug = request.args.get("sector", "cozinha")
    sectors = PreparationSector.query.order_by(PreparationSector.name).all()
    grouped, active_sector, summary = _build_board(sector_slug)
    return render_template(
        "kitchen/index.html",
        grouped=grouped,
        status_meta=STATUS_META,
        statuses=KDS_STATUSES,
        sectors=sectors,
        active_sector=active_sector,
        active_sector_slug=sector_slug,
        summary=summary,
        money=_money,
        fmt_qty=_fmt_qty,
    )


@kitchen_bp.route("/api/items")
@login_required
def api_items():
    """Compatibilidade com a versão antiga do JS."""
    sector_slug = request.args.get("sector", "cozinha")
    query, _ = _base_items_query(sector_slug)
    items = query.order_by(OrderItem.created_at).all()
    return jsonify([{
        "id": i.id,
        "table": f"Mesa {i.order.table.number:02d}" if i.order and i.order.table else (i.order.type if i.order else "Pedido"),
        "product": i.product.name if i.product else "Produto",
        "quantity": float(i.quantity or 0),
        "note": i.note or "",
        "status": i.status,
        "created_at": i.created_at.strftime("%H:%M") if i.created_at else "--:--"
    } for i in items])


@kitchen_bp.route("/api/items/<int:item_id>/status", methods=["POST"])
@login_required
def api_item_status(item_id):
    item = OrderItem.query.get_or_404(item_id)
    status = (request.json or {}).get("status")
    if status not in ["Pendente", "Em preparo", "Pronto", "Entregue"]:
        return jsonify({"ok": False, "error": "Status inválido"}), 400
    item.status = status
    db.session.commit()
    return jsonify({"ok": True})


@kitchen_bp.route("/api/order-status", methods=["POST"])
@login_required
def api_order_status():
    data = request.json or {}
    order_id = data.get("order_id")
    current_status = data.get("current_status")
    next_status = data.get("status")
    sector_slug = data.get("sector", "cozinha")

    if next_status not in ["Pendente", "Em preparo", "Pronto", "Entregue"]:
        return jsonify({"ok": False, "error": "Status inválido"}), 400

    query = OrderItem.query.filter(OrderItem.order_id == order_id)
    if current_status in KDS_STATUSES:
        query = query.filter(OrderItem.status == current_status)
    if sector_slug and sector_slug != "todos":
        sector = PreparationSector.query.filter_by(slug=sector_slug).first()
        if sector:
            query = query.filter(OrderItem.sector_id == sector.id)

    changed = 0
    for item in query.all():
        if item.status != "Cancelado":
            item.status = next_status
            changed += 1
    db.session.commit()
    return jsonify({"ok": True, "changed": changed})


@kitchen_bp.route("/api/mark-ready-delivered", methods=["POST"])
@login_required
def api_mark_ready_delivered():
    data = request.json or {}
    sector_slug = data.get("sector", "cozinha")
    query = OrderItem.query.filter(OrderItem.status == "Pronto")
    if sector_slug and sector_slug != "todos":
        sector = PreparationSector.query.filter_by(slug=sector_slug).first()
        if sector:
            query = query.filter(OrderItem.sector_id == sector.id)
    count = 0
    for item in query.all():
        item.status = "Entregue"
        count += 1
    db.session.commit()
    return jsonify({"ok": True, "changed": count})
