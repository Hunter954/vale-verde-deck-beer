from datetime import datetime, timedelta
from decimal import Decimal
import calendar
import csv
import io

from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from sqlalchemy import func

from ..extensions import db
from ..models import (
    Order,
    OrderItem,
    Product,
    ProductCategory,
    Payment,
    Table,
)
from ..utils import br_now, money

reports_bp = Blueprint("reports", __name__)


BR_MONTHS = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}



def _to_decimal(value):
    return Decimal(str(value or 0))


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def _period_defaults():
    today = br_now().date()
    first = today.replace(day=1)
    last = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return first, last


def _previous_period(start_date, end_date):
    days = (end_date - start_date).days
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days)
    return prev_start, prev_end


def _pct_change(current, previous):
    current = _to_decimal(current)
    previous = _to_decimal(previous)
    if previous == 0:
        if current == 0:
            return Decimal("0")
        return Decimal("100")
    return ((current - previous) / previous * Decimal("100")).quantize(Decimal("0.1"))


def _safe_pct(part, total):
    part = _to_decimal(part)
    total = _to_decimal(total)
    if total == 0:
        return Decimal("0")
    return (part / total * Decimal("100")).quantize(Decimal("0.1"))


def _closed_orders_query(start_date, end_date):
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    return Order.query.filter(
        Order.status == "Fechada",
        Order.closed_at.isnot(None),
        Order.closed_at >= start_dt,
        Order.closed_at < end_dt,
    )


def _period_metrics(start_date, end_date):
    orders = _closed_orders_query(start_date, end_date).all()
    total = sum((_to_decimal(o.total) for o in orders), Decimal("0"))
    count = len(orders)
    ticket = total / count if count else Decimal("0")

    customer_keys = set()
    for order in orders:
        if order.customer_id:
            customer_keys.add(f"id:{order.customer_id}")
        elif order.customer_name:
            customer_keys.add(f"name:{order.customer_name.strip().lower()}")
        elif order.customer_phone:
            customer_keys.add(f"phone:{order.customer_phone.strip()}")
    clients = len(customer_keys)

    return {
        "orders": orders,
        "total": total,
        "count": count,
        "ticket": ticket,
        "clients": clients,
    }


def _payment_rows(start_date, end_date, total):
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    rows = (
        db.session.query(Payment.method, func.coalesce(func.sum(Payment.amount), 0))
        .join(Order, Payment.order_id == Order.id)
        .filter(
            Order.status == "Fechada",
            Order.closed_at.isnot(None),
            Order.closed_at >= start_dt,
            Order.closed_at < end_dt,
        )
        .group_by(Payment.method)
        .order_by(func.sum(Payment.amount).desc())
        .all()
    )

    clean = []
    for method, amount in rows:
        amount = _to_decimal(amount)
        clean.append(
            {
                "method": method or "Não informado",
                "amount": amount,
                "percent": _safe_pct(amount, total),
            }
        )

    if not clean and total:
        clean = [{"method": "Não informado", "amount": total, "percent": Decimal("100")}]

    return clean


def _top_products(start_date, end_date, limit=5):
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    rows = (
        db.session.query(
            Product.name,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("qty"),
            func.coalesce(func.sum(OrderItem.total), 0).label("revenue"),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.status == "Fechada",
            Order.closed_at.isnot(None),
            Order.closed_at >= start_dt,
            Order.closed_at < end_dt,
            OrderItem.status != "Cancelado",
        )
        .group_by(Product.id, Product.name)
        .order_by(func.sum(OrderItem.total).desc())
        .limit(limit)
        .all()
    )

    total_revenue = sum((_to_decimal(r.revenue) for r in rows), Decimal("0"))
    return [
        {
            "rank": idx,
            "name": name,
            "qty": _to_decimal(qty),
            "revenue": _to_decimal(revenue),
            "percent": _safe_pct(revenue, total_revenue),
        }
        for idx, (name, qty, revenue) in enumerate(rows, 1)
    ]


def _category_rows(start_date, end_date, period_total):
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    rows = (
        db.session.query(
            func.coalesce(ProductCategory.name, "Sem categoria").label("category"),
            func.coalesce(func.sum(OrderItem.total), 0).label("revenue"),
            func.count(func.distinct(Order.id)).label("orders_count"),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
        .filter(
            Order.status == "Fechada",
            Order.closed_at.isnot(None),
            Order.closed_at >= start_dt,
            Order.closed_at < end_dt,
            OrderItem.status != "Cancelado",
        )
        .group_by(ProductCategory.name)
        .order_by(func.sum(OrderItem.total).desc())
        .all()
    )

    clean = []
    for category, revenue, orders_count in rows:
        revenue = _to_decimal(revenue)
        orders_count = int(orders_count or 0)
        clean.append(
            {
                "category": category or "Sem categoria",
                "revenue": revenue,
                "percent": _safe_pct(revenue, period_total),
                "orders": orders_count,
                "ticket": revenue / orders_count if orders_count else Decimal("0"),
            }
        )
    return clean


def _daily_rows(start_date, end_date, orders):
    totals = {}
    current = start_date
    while current <= end_date:
        totals[current] = Decimal("0")
        current += timedelta(days=1)

    for order in orders:
        if order.closed_at:
            key = order.closed_at.date()
            if key in totals:
                totals[key] += _to_decimal(order.total)

    max_total = max(totals.values() or [Decimal("0")])
    rows = []
    for day, total in totals.items():
        rows.append(
            {
                "label": day.strftime("%d"),
                "date": day.strftime("%d/%m/%Y"),
                "amount": total,
                "height": int((_safe_pct(total, max_total) if max_total else Decimal("0"))),
            }
        )
    return rows


def _summary(start_date, end_date, orders):
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    cost_rows = (
        db.session.query(
            func.coalesce(func.sum(Product.cost * OrderItem.quantity), 0),
            func.coalesce(func.sum(OrderItem.total), 0),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.status == "Fechada",
            Order.closed_at.isnot(None),
            Order.closed_at >= start_dt,
            Order.closed_at < end_dt,
            OrderItem.status != "Cancelado",
        )
        .first()
    )

    product_cost = _to_decimal(cost_rows[0] if cost_rows else 0)
    items_revenue = _to_decimal(cost_rows[1] if cost_rows else 0)
    discounts = sum((_to_decimal(o.discount) for o in orders), Decimal("0"))
    service_fee = sum((_to_decimal(o.service_fee) for o in orders), Decimal("0"))
    cancelled_total = (
        db.session.query(func.coalesce(func.sum(OrderItem.total), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.closed_at.isnot(None),
            Order.closed_at >= start_dt,
            Order.closed_at < end_dt,
            OrderItem.status == "Cancelado",
        )
        .scalar()
    )
    cancelled_total = _to_decimal(cancelled_total)

    tables_total = Table.query.count()
    tables_busy = Table.query.filter(Table.status.in_(["Ocupada", "Reservada"])).count()
    table_rate = _safe_pct(tables_busy, tables_total)

    estimated_profit = items_revenue - product_cost - discounts + service_fee

    return {
        "profit": estimated_profit,
        "product_cost": product_cost,
        "service_fee": service_fee,
        "discounts": discounts,
        "cancellations": cancelled_total,
        "table_rate": table_rate,
    }


@reports_bp.route("/")
@login_required
def index():
    default_start, default_end = _period_defaults()
    start_date = _parse_date(request.args.get("start")) or default_start
    end_date = _parse_date(request.args.get("end")) or default_end
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    period = _period_metrics(start_date, end_date)
    prev_start, prev_end = _previous_period(start_date, end_date)
    previous = _period_metrics(prev_start, prev_end)

    payment_rows = _payment_rows(start_date, end_date, period["total"])
    top_products = _top_products(start_date, end_date)
    categories = _category_rows(start_date, end_date, period["total"])
    daily_rows = _daily_rows(start_date, end_date, period["orders"])
    summary = _summary(start_date, end_date, period["orders"])

    if request.args.get("export") == "csv":
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["Relatório Vale Verde"])
        writer.writerow(["Período", start_date.strftime("%d/%m/%Y"), end_date.strftime("%d/%m/%Y")])
        writer.writerow([])
        writer.writerow(["Indicador", "Valor"])
        writer.writerow(["Faturamento", money(period["total"])])
        writer.writerow(["Pedidos", period["count"]])
        writer.writerow(["Ticket médio", money(period["ticket"])])
        writer.writerow(["Clientes", period["clients"]])
        writer.writerow([])
        writer.writerow(["Top produtos", "Qtd.", "Faturamento"])
        for row in top_products:
            writer.writerow([row["name"], str(row["qty"]).replace(".", ","), money(row["revenue"])])
        data = output.getvalue().encode("utf-8-sig")
        filename = f"relatorio-vale-verde-{start_date:%Y%m%d}-{end_date:%Y%m%d}.csv"
        return Response(
            data,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    period_label = f"{start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')}"
    if start_date.day == 1 and end_date.day == calendar.monthrange(end_date.year, end_date.month)[1] and start_date.month == end_date.month:
        period_label = f"{BR_MONTHS[start_date.month]}/{start_date.year}"

    kpis = {
        "revenue_pct": _pct_change(period["total"], previous["total"]),
        "orders_pct": _pct_change(period["count"], previous["count"]),
        "ticket_pct": _pct_change(period["ticket"], previous["ticket"]),
        "clients_pct": _pct_change(period["clients"], previous["clients"]),
    }

    return render_template(
        "reports/index.html",
        start_date=start_date,
        end_date=end_date,
        period_label=period_label,
        period=period,
        previous=previous,
        kpis=kpis,
        payment_rows=payment_rows,
        top_products=top_products,
        categories=categories,
        daily_rows=daily_rows,
        summary=summary,
    )
