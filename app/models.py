from datetime import date
from decimal import Decimal
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db
from .utils import br_now

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("role.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permission.id"), primary_key=True),
)

class TimestampMixin:
    created_at = db.Column(db.DateTime, default=br_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=br_now, onupdate=br_now, nullable=False)

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    permissions = db.relationship("Permission", secondary=role_permissions, backref="roles")

class Permission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.String(255))

class User(UserMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(40))
    active = db.Column(db.Boolean, default=True)
    commission_percent = db.Column(db.Numeric(6, 2), default=0)
    role_id = db.Column(db.Integer, db.ForeignKey("role.id"))
    role = db.relationship("Role")

    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_role(self, *names):
        return self.role and self.role.name in names

    def can(self, code):
        if self.has_role("Admin"):
            return True
        return bool(self.role and any(p.code == code for p in self.role.permissions))

class PreparationSector(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)

class ProductCategory(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True)

class Product(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    image = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey("product_category.id"))
    category = db.relationship("ProductCategory", backref="products")
    price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    stock = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    min_stock = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    internal_code = db.Column(db.String(80), unique=True)
    barcode = db.Column(db.String(120), index=True)
    active = db.Column(db.Boolean, default=True)
    controlled = db.Column(db.Boolean, default=False)
    adult_warning = db.Column(db.Boolean, default=False)
    prep_note = db.Column(db.Text)
    avg_prep_minutes = db.Column(db.Integer, default=0)
    sector_id = db.Column(db.Integer, db.ForeignKey("preparation_sector.id"))
    sector = db.relationship("PreparationSector")

    @property
    def margin(self):
        return (self.price or 0) - (self.cost or 0)

class ProductVariation(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    product = db.relationship("Product", backref="variations")
    name = db.Column(db.String(120), nullable=False)
    required = db.Column(db.Boolean, default=False)

class ProductVariationOption(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    variation_id = db.Column(db.Integer, db.ForeignKey("product_variation.id"))
    variation = db.relationship("ProductVariation", backref="options")
    name = db.Column(db.String(120), nullable=False)
    price_delta = db.Column(db.Numeric(12, 2), default=0)

class Table(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False)
    status = db.Column(db.String(40), default="Livre")
    current_order_id = db.Column(db.Integer, db.ForeignKey("order.id"))

class Customer(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40))
    cpf = db.Column(db.String(20))
    birthdate = db.Column(db.Date)
    notes = db.Column(db.Text)
    blocked = db.Column(db.Boolean, default=False)
    credit_limit = db.Column(db.Numeric(12, 2), default=0)

class CustomerDebt(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))
    customer = db.relationship("Customer", backref="debts")
    description = db.Column(db.String(255))
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    paid_amount = db.Column(db.Numeric(12, 2), default=0)
    due_date = db.Column(db.Date)
    status = db.Column(db.String(40), default="Aberto")

class Order(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, index=True)
    type = db.Column(db.String(30), default="Mesa")  # Mesa, Balcão, Retirada, Delivery
    status = db.Column(db.String(40), default="Aberta")
    table_id = db.Column(db.Integer, db.ForeignKey("table.id"))
    table = db.relationship("Table", foreign_keys=[table_id], backref="orders")
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))
    customer = db.relationship("Customer")
    customer_name = db.Column(db.String(160))
    customer_phone = db.Column(db.String(40))
    delivery_address = db.Column(db.String(255))
    delivery_fee = db.Column(db.Numeric(12, 2), default=0)
    note = db.Column(db.Text)
    opened_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    opened_by = db.relationship("User", foreign_keys=[opened_by_id])
    closed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    closed_by = db.relationship("User", foreign_keys=[closed_by_id])
    subtotal = db.Column(db.Numeric(12, 2), default=0)
    discount = db.Column(db.Numeric(12, 2), default=0)
    service_fee = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), default=0)
    closed_at = db.Column(db.DateTime)

    def recalc(self):
        subtotal = sum([(item.total or Decimal("0")) for item in self.items if item.status != "Cancelado"], Decimal("0"))
        self.subtotal = subtotal
        self.total = subtotal + (self.delivery_fee or 0) + (self.service_fee or 0) - (self.discount or 0)

class OrderItem(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"))
    order = db.relationship("Order", backref="items")
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    product = db.relationship("Product")
    sector_id = db.Column(db.Integer, db.ForeignKey("preparation_sector.id"))
    sector = db.relationship("PreparationSector")
    quantity = db.Column(db.Numeric(12, 3), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    note = db.Column(db.Text)
    person_name = db.Column(db.String(120))
    status = db.Column(db.String(40), default="Pendente")
    cancelled_reason = db.Column(db.String(255))

class Payment(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"))
    order = db.relationship("Order", backref="payments")
    method = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    operator_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    operator = db.relationship("User")
    note = db.Column(db.String(255))

class CashRegister(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    opened_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    opened_by = db.relationship("User", foreign_keys=[opened_by_id])
    closed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    closed_by = db.relationship("User", foreign_keys=[closed_by_id])
    opening_amount = db.Column(db.Numeric(12, 2), default=0)
    closing_amount = db.Column(db.Numeric(12, 2))
    status = db.Column(db.String(40), default="Aberto")
    opened_at = db.Column(db.DateTime, default=br_now)
    closed_at = db.Column(db.DateTime)

class CashMovement(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cash_register_id = db.Column(db.Integer, db.ForeignKey("cash_register.id"))
    cash_register = db.relationship("CashRegister", backref="movements")
    type = db.Column(db.String(40), nullable=False)  # Sangria, Suprimento, Venda
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    note = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User")

class Supplier(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40))
    email = db.Column(db.String(160))
    notes = db.Column(db.Text)

class StockMovement(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    product = db.relationship("Product", backref="stock_movements")
    type = db.Column(db.String(40), nullable=False)  # Entrada, Venda, Ajuste, Perda, Consumo, Transferência
    quantity = db.Column(db.Numeric(12, 3), nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), default=0)
    note = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User")
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"))
    supplier = db.relationship("Supplier")

class Recipe(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), unique=True)
    product = db.relationship("Product", backref="recipe")

class RecipeItem(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id"))
    recipe = db.relationship("Recipe", backref="items")
    ingredient_product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    ingredient = db.relationship("Product")
    quantity = db.Column(db.Numeric(12, 3), nullable=False)

class CancellationLog(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_item.id"))
    order_item = db.relationship("OrderItem")
    reason = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User")

class DiscountLog(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"))
    order = db.relationship("Order")
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    reason = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User")

class Settings(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False)
    value = db.Column(db.Text)
