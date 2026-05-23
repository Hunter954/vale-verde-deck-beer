from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..extensions import db
from ..models import User, Role, Settings

settings_bp = Blueprint("settings", __name__)

@settings_bp.route("/")
@login_required
def index():
    users = User.query.order_by(User.name).all()
    roles = Role.query.order_by(Role.name).all()
    settings = Settings.query.order_by(Settings.key).all()
    return render_template("settings/index.html", users=users, roles=roles, settings=settings)

@settings_bp.route("/users", methods=["POST"])
@login_required
def create_user():
    u = User(name=request.form["name"], email=request.form["email"].lower().strip(),
             phone=request.form.get("phone"), role_id=request.form.get("role_id"), active=True)
    u.set_password(request.form.get("password") or "123456")
    db.session.add(u); db.session.commit()
    flash("Funcionário criado.", "success")
    return redirect(url_for("settings.index"))
