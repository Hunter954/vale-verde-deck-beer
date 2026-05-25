from flask import Flask
from config import Config
from .extensions import db, migrate, login_manager
from .models import User
from .utils import money, br_now

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.template_filter("money")
    def money_filter(value):
        return money(value)

    @app.context_processor
    def inject_global_helpers():
        return {"money": money, "br_now": br_now}

    from .auth.routes import auth_bp
    from .dashboard.routes import dashboard_bp
    from .tables.routes import tables_bp
    from .orders.routes import orders_bp
    from .products.routes import products_bp
    from .stock.routes import stock_bp
    from .pos.routes import pos_bp
    from .kitchen.routes import kitchen_bp
    from .customers.routes import customers_bp
    from .reports.routes import reports_bp
    from .settings.routes import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tables_bp, url_prefix="/tables")
    app.register_blueprint(orders_bp, url_prefix="/orders")
    app.register_blueprint(products_bp, url_prefix="/products")
    app.register_blueprint(stock_bp, url_prefix="/stock")
    app.register_blueprint(pos_bp, url_prefix="/pos")
    app.register_blueprint(kitchen_bp, url_prefix="/kds")
    app.register_blueprint(customers_bp, url_prefix="/customers")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(settings_bp, url_prefix="/settings")

    return app
