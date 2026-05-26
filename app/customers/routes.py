from datetime import datetime, date, timedelta
from decimal import Decimal
from math import ceil

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import or_

from ..extensions import db
from ..models import Customer, CustomerDebt, Order
from ..utils import money_to_decimal, br_now

customers_bp = Blueprint("customers", __name__)


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def debt_balance(debt):
    return Decimal(str(debt.amount or 0)) - Decimal(str(debt.paid_amount or 0))


def customer_open_debts(customer):
    return [d for d in customer.debts if (d.status or "Aberto") == "Aberto" and debt_balance(d) > 0]


def customer_balance(customer):
    return sum((debt_balance(d) for d in customer_open_debts(customer)), Decimal("0"))


def customer_last_purchase(customer):
    order = (
        Order.query.filter(Order.customer_id == customer.id)
        .order_by(Order.created_at.desc())
        .first()
    )
    if order:
        return order.created_at.date()
    debts = sorted(customer.debts, key=lambda d: d.created_at or br_now(), reverse=True)
    return debts[0].created_at.date() if debts else None


def customer_status(customer, today=None):
    today = today or date.today()
    balance = customer_balance(customer)
    debts = customer_open_debts(customer)
    overdue = any(d.due_date and d.due_date < today for d in debts)

    if balance <= 0:
        return "sem_fiado", "Sem fiado"
    if overdue or customer.blocked:
        return "vencido", "Vencido"

    limit = Decimal(str(customer.credit_limit or 0))
    if limit > 0 and balance >= (limit * Decimal("0.50")):
        return "attention", "Atenção"
    return "em_dia", "Em dia"


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


@customers_bp.route("/")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    status_filter = (request.args.get("status") or "all").lower()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    if per_page not in (6, 10, 15, 20, 50):
        per_page = 10

    query = Customer.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Customer.name.ilike(like), Customer.phone.ilike(like), Customer.cpf.ilike(like)))

    all_customers = Customer.query.order_by(Customer.name.asc()).all()
    today = br_now().date()
    for customer in all_customers:
        customer.fiado_balance = customer_balance(customer)
        customer.fiado_status, customer.fiado_label = customer_status(customer, today)
        customer.last_purchase_date = customer_last_purchase(customer)
        customer.initials = "".join([part[:1] for part in customer.name.split()[:2]]).upper() or "CL"
        customer.open_debts = customer_open_debts(customer)

    customers = query.order_by(Customer.name.asc()).all()
    for customer in customers:
        customer.fiado_balance = customer_balance(customer)
        customer.fiado_status, customer.fiado_label = customer_status(customer, today)
        customer.last_purchase_date = customer_last_purchase(customer)
        customer.initials = "".join([part[:1] for part in customer.name.split()[:2]]).upper() or "CL"
        customer.open_debts = customer_open_debts(customer)

    if status_filter == "with_debt":
        customers = [c for c in customers if c.fiado_balance > 0]
    elif status_filter == "current":
        customers = [c for c in customers if c.fiado_status == "em_dia"]
    elif status_filter == "overdue":
        customers = [c for c in customers if c.fiado_status == "vencido"]
    else:
        status_filter = "all"

    total_balance = sum((c.fiado_balance for c in all_customers), Decimal("0"))
    with_debt_count = sum(1 for c in all_customers if c.fiado_balance > 0)
    overdue_count = sum(1 for c in all_customers if c.fiado_status == "vencido")

    pagination = paginate_items(customers, page, per_page)

    return render_template(
        "customers/index.html",
        customers=pagination["items"],
        all_customers=all_customers,
        pagination=pagination,
        q=q,
        status=status_filter,
        per_page=per_page,
        total_count=len(all_customers),
        with_debt_count=with_debt_count,
        total_balance=total_balance,
        overdue_count=overdue_count,
    )


@customers_bp.route("/new", methods=["POST"])
@login_required
def create():
    customer = Customer(
        name=request.form["name"].strip(),
        phone=request.form.get("phone"),
        cpf=request.form.get("cpf"),
        birthdate=parse_date(request.form.get("birthdate")),
        notes=request.form.get("notes"),
        credit_limit=money_to_decimal(request.form.get("credit_limit")),
        blocked=bool(request.form.get("blocked")),
    )
    db.session.add(customer)
    db.session.commit()
    flash("Cliente cadastrado.", "success")
    return redirect(url_for("customers.index"))


@customers_bp.route("/<int:id>/update", methods=["POST"])
@login_required
def update(id):
    customer = Customer.query.get_or_404(id)
    customer.name = request.form["name"].strip()
    customer.phone = request.form.get("phone")
    customer.cpf = request.form.get("cpf")
    customer.birthdate = parse_date(request.form.get("birthdate"))
    customer.notes = request.form.get("notes")
    customer.credit_limit = money_to_decimal(request.form.get("credit_limit"))
    customer.blocked = bool(request.form.get("blocked"))
    db.session.commit()
    flash("Cliente atualizado.", "success")
    return redirect(url_for("customers.index"))


@customers_bp.route("/debt", methods=["POST"])
@login_required
def debt():
    customer_id = request.form.get("customer_id")
    if not customer_id:
        flash("Selecione um cliente para lançar o fiado.", "warning")
        return redirect(url_for("customers.index"))
    amount = money_to_decimal(request.form.get("amount"))
    if amount <= 0:
        flash("Informe um valor maior que zero.", "warning")
        return redirect(url_for("customers.index"))

    debt = CustomerDebt(
        customer_id=customer_id,
        description=request.form.get("description") or "Compra fiado",
        amount=amount,
        paid_amount=Decimal("0"),
        due_date=parse_date(request.form.get("due_date")),
        status="Aberto",
    )
    db.session.add(debt)
    db.session.commit()
    flash("Débito lançado no fiado.", "warning")
    return redirect(url_for("customers.index"))


@customers_bp.route("/<int:id>/debt", methods=["POST"])
@login_required
def customer_debt(id):
    # rota de conveniência para os botões da tabela
    amount = money_to_decimal(request.form.get("amount"))
    if amount <= 0:
        flash("Informe um valor maior que zero.", "warning")
        return redirect(url_for("customers.index"))
    db.session.add(CustomerDebt(
        customer_id=id,
        description=request.form.get("description") or "Compra fiado",
        amount=amount,
        paid_amount=Decimal("0"),
        due_date=parse_date(request.form.get("due_date")),
        status="Aberto",
    ))
    db.session.commit()
    flash("Débito lançado no fiado.", "warning")
    return redirect(url_for("customers.index"))


@customers_bp.route("/debt/<int:id>/pay", methods=["POST"])
@login_required
def pay_debt(id):
    debt = CustomerDebt.query.get_or_404(id)
    amount = money_to_decimal(request.form.get("amount"))
    if amount <= 0:
        flash("Informe um valor maior que zero.", "warning")
        return redirect(url_for("customers.index"))

    debt.paid_amount = Decimal(str(debt.paid_amount or 0)) + amount
    if debt.paid_amount >= debt.amount:
        debt.paid_amount = debt.amount
        debt.status = "Pago"
    db.session.commit()
    flash("Pagamento de fiado registrado.", "success")
    return redirect(url_for("customers.index"))


@customers_bp.route("/<int:id>/pay", methods=["POST"])
@login_required
def pay_customer(id):
    amount = money_to_decimal(request.form.get("amount"))
    if amount <= 0:
        flash("Informe um valor maior que zero.", "warning")
        return redirect(url_for("customers.index"))

    debts = CustomerDebt.query.filter_by(customer_id=id, status="Aberto").all()
    debts = sorted(debts, key=lambda d: (d.due_date or date.max, d.created_at or br_now()))
    remaining = amount
    for debt in debts:
        if remaining <= 0:
            break
        balance = debt_balance(debt)
        applied = min(balance, remaining)
        debt.paid_amount = Decimal(str(debt.paid_amount or 0)) + applied
        remaining -= applied
        if debt.paid_amount >= debt.amount:
            debt.paid_amount = debt.amount
            debt.status = "Pago"
    db.session.commit()
    flash("Pagamento abatido do fiado.", "success")
    return redirect(url_for("customers.index"))
