import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, current_app
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash

from ..extensions import db
from ..models import (
    User,
    Role,
    Permission,
    Settings,
    Product,
    ProductCategory,
    Order,
    Customer,
    Table,
)
from ..utils import br_now, money_to_decimal

settings_bp = Blueprint("settings", __name__)

DEFAULT_SETTINGS = {
    "company_name": "Vale Verde",
    "admin_name": "Administrador",
    "company_email": "admin@valeverde.com.br",
    "company_phone": "(45) 99999-0000",
    "company_cnpj": "",
    "company_address": "",
    "company_city_uf": "Foz do Iguaçu - PR",
    "currency": "BRL",
    "timezone": "America/Sao_Paulo",
    "service_fee_percent": "10",
    "system_theme": "dark",
    "language": "pt-BR",
    "two_factor_enabled": "0",
    "email_alerts_enabled": "1",
    "printer_kitchen_enabled": "0",
    "printer_bar_enabled": "0",
    "printer_receipt_enabled": "0",
    "printer_kitchen_name": "",
    "printer_bar_name": "",
    "printer_receipt_name": "",
    "integration_whatsapp_enabled": "0",
    "integration_ifood_enabled": "0",
    "integration_delivery_enabled": "0",
    "backup_auto_enabled": "1",
    "backup_frequency": "daily",
    "last_backup_at": "",
    "system_version": "v2.4.1",
    "environment": "Produção",
    "plan_name": "Profissional",
}

PERMISSIONS = [
    ("dashboard.view", "Visualizar dashboard"),
    ("tables.manage", "Gerenciar mesas"),
    ("pos.manage", "Usar Caixa / PDV"),
    ("kds.manage", "Gerenciar KDS"),
    ("products.manage", "Gerenciar produtos"),
    ("stock.manage", "Gerenciar estoque"),
    ("customers.manage", "Gerenciar clientes / fiado"),
    ("reports.view", "Visualizar relatórios"),
    ("settings.manage", "Gerenciar configurações"),
]


def _setting(key, default=None):
    row = Settings.query.filter_by(key=key).first()
    if row and row.value is not None:
        return row.value
    return DEFAULT_SETTINGS.get(key, default or "")


def _settings_map():
    values = dict(DEFAULT_SETTINGS)
    for item in Settings.query.all():
        values[item.key] = item.value or ""
    return values


def _set_setting(key, value):
    row = Settings.query.filter_by(key=key).first()
    if not row:
        row = Settings(key=key)
        db.session.add(row)
    row.value = "" if value is None else str(value)
    return row


def _ensure_permissions():
    created = False
    for code, desc in PERMISSIONS:
        if not Permission.query.filter_by(code=code).first():
            db.session.add(Permission(code=code, description=desc))
            created = True
    if created:
        db.session.commit()


def _bool_setting(form_key):
    return "1" if request.form.get(form_key) in ["1", "on", "true", "Sim"] else "0"


def _active_tab(default="geral"):
    return request.args.get("tab") or request.form.get("tab") or default


def _system_summary(values):
    users_active = User.query.filter_by(active=True).count()
    last_backup = values.get("last_backup_at") or "Ainda não executado"
    return {
        "plan": values.get("plan_name") or "Profissional",
        "users_active": users_active,
        "last_backup": last_backup,
        "version": values.get("system_version") or "v2.4.1",
        "environment": values.get("environment") or "Produção",
        "products": Product.query.count(),
        "customers": Customer.query.count(),
        "tables": Table.query.count(),
        "orders": Order.query.count(),
    }


@settings_bp.route("/")
@login_required
def index():
    _ensure_permissions()
    users = User.query.order_by(User.name).all()
    roles = Role.query.order_by(Role.name).all()
    permissions = Permission.query.order_by(Permission.code).all()
    values = _settings_map()
    return render_template(
        "settings/index.html",
        users=users,
        roles=roles,
        permissions=permissions,
        settings_values=values,
        summary=_system_summary(values),
        active_tab=_active_tab(),
        title="Configurações",
    )


@settings_bp.route("/general", methods=["POST"])
@login_required
def save_general():
    keys = [
        "company_name",
        "admin_name",
        "company_email",
        "company_phone",
        "company_cnpj",
        "company_address",
        "company_city_uf",
        "currency",
        "timezone",
        "system_theme",
        "language",
    ]
    for key in keys:
        _set_setting(key, request.form.get(key, DEFAULT_SETTINGS.get(key, "")))

    fee = request.form.get("service_fee_percent") or "0"
    try:
        fee_decimal = money_to_decimal(fee) if any(c in fee for c in [",", "R$", " "]) else Decimal(str(fee).replace(",", "."))
    except (InvalidOperation, ValueError):
        fee_decimal = Decimal("0")
    if fee_decimal < 0:
        fee_decimal = Decimal("0")
    _set_setting("service_fee_percent", fee_decimal.quantize(Decimal("0.01")))

    _set_setting("two_factor_enabled", _bool_setting("two_factor_enabled"))
    _set_setting("email_alerts_enabled", _bool_setting("email_alerts_enabled"))

    # Mantém o usuário logado alinhado com os dados principais da conta.
    current_user.name = request.form.get("admin_name") or current_user.name
    email = (request.form.get("company_email") or "").strip().lower()
    if email:
        existing = User.query.filter(User.email == email, User.id != current_user.id).first()
        if existing:
            flash("Configurações salvas, mas o e-mail do administrador já pertence a outro usuário.", "warning")
        else:
            current_user.email = email
    current_user.phone = request.form.get("company_phone") or current_user.phone

    db.session.commit()
    flash("Configurações gerais salvas.", "success")
    return redirect(url_for("settings.index", tab="geral"))


@settings_bp.route("/password", methods=["POST"])
@login_required
def update_password():
    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if not current_user.check_password(current_password):
        flash("Senha atual incorreta.", "danger")
        return redirect(url_for("settings.index", tab="geral"))
    if len(new_password) < 6:
        flash("A nova senha precisa ter pelo menos 6 caracteres.", "danger")
        return redirect(url_for("settings.index", tab="geral"))
    if new_password != confirm_password:
        flash("A confirmação da nova senha não confere.", "danger")
        return redirect(url_for("settings.index", tab="geral"))

    current_user.set_password(new_password)
    db.session.commit()
    flash("Senha atualizada com sucesso.", "success")
    return redirect(url_for("settings.index", tab="geral"))


@settings_bp.route("/users", methods=["POST"])
@login_required
def create_user():
    email = (request.form.get("email") or "").lower().strip()
    if not email:
        flash("Informe o e-mail do usuário.", "danger")
        return redirect(url_for("settings.index", tab="usuarios"))
    if User.query.filter_by(email=email).first():
        flash("Já existe um usuário com esse e-mail.", "danger")
        return redirect(url_for("settings.index", tab="usuarios"))

    user = User(
        name=request.form.get("name") or "Novo usuário",
        email=email,
        phone=request.form.get("phone"),
        role_id=request.form.get("role_id") or None,
        active=bool(request.form.get("active", "1")),
    )
    user.set_password(request.form.get("password") or "123456")
    db.session.add(user)
    db.session.commit()
    flash("Usuário criado.", "success")
    return redirect(url_for("settings.index", tab="usuarios"))


@settings_bp.route("/users/<int:user_id>", methods=["POST"])
@login_required
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    email = (request.form.get("email") or user.email).lower().strip()
    existing = User.query.filter(User.email == email, User.id != user.id).first()
    if existing:
        flash("Outro usuário já usa esse e-mail.", "danger")
        return redirect(url_for("settings.index", tab="usuarios"))

    user.name = request.form.get("name") or user.name
    user.email = email
    user.phone = request.form.get("phone")
    user.role_id = request.form.get("role_id") or None
    user.active = bool(request.form.get("active"))
    new_password = request.form.get("password") or ""
    if new_password.strip():
        user.set_password(new_password.strip())
    db.session.commit()
    flash("Usuário atualizado.", "success")
    return redirect(url_for("settings.index", tab="usuarios"))


@settings_bp.route("/roles/<int:role_id>/permissions", methods=["POST"])
@login_required
def update_role_permissions(role_id):
    _ensure_permissions()
    role = Role.query.get_or_404(role_id)
    selected = request.form.getlist("permissions")
    role.permissions = Permission.query.filter(Permission.code.in_(selected)).all() if selected else []
    db.session.commit()
    flash(f"Permissões de {role.name} atualizadas.", "success")
    return redirect(url_for("settings.index", tab="permissoes"))


@settings_bp.route("/printers", methods=["POST"])
@login_required
def save_printers():
    for key in ["printer_kitchen_name", "printer_bar_name", "printer_receipt_name"]:
        _set_setting(key, request.form.get(key, ""))
    for key in ["printer_kitchen_enabled", "printer_bar_enabled", "printer_receipt_enabled"]:
        _set_setting(key, _bool_setting(key))
    db.session.commit()
    flash("Configurações de impressoras salvas.", "success")
    return redirect(url_for("settings.index", tab="impressoras"))


@settings_bp.route("/integrations", methods=["POST"])
@login_required
def save_integrations():
    for key in ["integration_whatsapp_enabled", "integration_ifood_enabled", "integration_delivery_enabled"]:
        _set_setting(key, _bool_setting(key))
    for key in ["integration_whatsapp_token", "integration_ifood_token", "integration_delivery_token"]:
        _set_setting(key, request.form.get(key, ""))
    db.session.commit()
    flash("Integrações salvas.", "success")
    return redirect(url_for("settings.index", tab="integracoes"))


@settings_bp.route("/backup/settings", methods=["POST"])
@login_required
def save_backup_settings():
    _set_setting("backup_auto_enabled", _bool_setting("backup_auto_enabled"))
    _set_setting("backup_frequency", request.form.get("backup_frequency") or "daily")
    db.session.commit()
    flash("Preferências de backup salvas.", "success")
    return redirect(url_for("settings.index", tab="backup"))


@settings_bp.route("/backup/download")
@login_required
def download_backup():
    values = _settings_map()
    now = br_now()
    _set_setting("last_backup_at", now.strftime("%d/%m/%Y às %H:%M"))
    db.session.commit()

    data = {
        "generated_at": now.isoformat(),
        "settings": values,
        "roles": [
            {"id": r.id, "name": r.name, "permissions": [p.code for p in r.permissions]}
            for r in Role.query.order_by(Role.name).all()
        ],
        "users": [
            {"id": u.id, "name": u.name, "email": u.email, "phone": u.phone, "active": u.active, "role": u.role.name if u.role else None}
            for u in User.query.order_by(User.name).all()
        ],
        "counts": _system_summary(_settings_map()),
    }
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"vale-verde-backup-config-{now.strftime('%Y%m%d-%H%M')}.json"
    return Response(
        payload,
        mimetype="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
