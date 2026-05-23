from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..extensions import db
from ..models import Customer, CustomerDebt

customers_bp = Blueprint("customers", __name__)

@customers_bp.route("/")
@login_required
def index():
    customers = Customer.query.order_by(Customer.name).all()
    debts = CustomerDebt.query.filter_by(status="Aberto").order_by(CustomerDebt.created_at.desc()).all()
    return render_template("customers/index.html", customers=customers, debts=debts)

@customers_bp.route("/new", methods=["POST"])
@login_required
def create():
    c = Customer(name=request.form["name"], phone=request.form.get("phone"), cpf=request.form.get("cpf"),
                 notes=request.form.get("notes"), credit_limit=request.form.get("credit_limit") or 0,
                 blocked=bool(request.form.get("blocked")))
    db.session.add(c)
    db.session.commit()
    flash("Cliente cadastrado.", "success")
    return redirect(url_for("customers.index"))

@customers_bp.route("/debt", methods=["POST"])
@login_required
def debt():
    d = CustomerDebt(customer_id=request.form["customer_id"], description=request.form.get("description"),
                     amount=request.form.get("amount") or 0, status="Aberto")
    db.session.add(d); db.session.commit()
    flash("Débito lançado.", "warning")
    return redirect(url_for("customers.index"))

@customers_bp.route("/debt/<int:id>/pay", methods=["POST"])
@login_required
def pay_debt(id):
    d = CustomerDebt.query.get_or_404(id)
    d.paid_amount = (d.paid_amount or 0) + float(request.form.get("amount") or 0)
    if d.paid_amount >= d.amount:
        d.status = "Pago"
    db.session.commit()
    flash("Pagamento de fiado registrado.", "success")
    return redirect(url_for("customers.index"))
