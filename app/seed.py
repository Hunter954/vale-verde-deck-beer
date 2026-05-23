from app import create_app
from app.extensions import db
from app.models import Role, Permission, User, Table, ProductCategory, PreparationSector, Product, Supplier

ROLES = ["Admin", "Gerente", "Atendente", "Caixa", "Cozinha", "Bar", "Narguilé"]
PERMISSIONS = [
    ("cancel_item", "Cancelar item"), ("discount", "Aplicar desconto"), ("reopen_table", "Reabrir mesa"),
    ("close_cash", "Fechar caixa"), ("adjust_stock", "Ajustar estoque"), ("pos", "Operar caixa"),
    ("kds", "Operar painel de preparo"), ("reports", "Visualizar relatórios")
]
CATEGORIES = ["Narguilé","Essências","Carvão","Bebidas","Porções","Lanches","Combos","Acessórios","Cigarros / Tabacaria","Promoções","Taxas / adicionais"]
SECTORS = [("Cozinha","cozinha"),("Bar","bar"),("Narguilé","narguile"),("Caixa","caixa"),("Estoque","estoque")]

def run():
    app = create_app()
    with app.app_context():
        db.create_all()

        perms = {}
        for code, desc in PERMISSIONS:
            p = Permission.query.filter_by(code=code).first() or Permission(code=code, description=desc)
            db.session.add(p); perms[code]=p

        for name in ROLES:
            role = Role.query.filter_by(name=name).first() or Role(name=name)
            if name == "Gerente":
                role.permissions = [perms[c] for c in ["cancel_item","discount","reopen_table","close_cash","adjust_stock","reports"]]
            elif name == "Atendente":
                role.permissions = []
            elif name == "Caixa":
                role.permissions = [perms["pos"]]
            elif name in ["Cozinha","Bar","Narguilé"]:
                role.permissions = [perms["kds"]]
            db.session.add(role)

        db.session.flush()
        admin_role = Role.query.filter_by(name="Admin").first()
        admin = User.query.filter_by(email="admin@valeverde.com").first()
        if not admin:
            admin = User(name="Administrador", email="admin@valeverde.com", role=admin_role, active=True)
            admin.set_password("admin123")
            db.session.add(admin)

        for n in range(1, 21):
            if not Table.query.filter_by(number=n).first():
                db.session.add(Table(number=n, status="Livre"))

        for name in CATEGORIES:
            if not ProductCategory.query.filter_by(name=name).first():
                db.session.add(ProductCategory(name=name))

        for name, slug in SECTORS:
            if not PreparationSector.query.filter_by(slug=slug).first():
                db.session.add(PreparationSector(name=name, slug=slug))

        db.session.commit()

        # Produtos exemplo úteis para testar fluxo completo
        bar = PreparationSector.query.filter_by(slug="bar").first()
        cozinha = PreparationSector.query.filter_by(slug="cozinha").first()
        narg = PreparationSector.query.filter_by(slug="narguile").first()
        cat_bebidas = ProductCategory.query.filter_by(name="Bebidas").first()
        cat_porcoes = ProductCategory.query.filter_by(name="Porções").first()
        cat_narg = ProductCategory.query.filter_by(name="Narguilé").first()
        samples = [
            ("Coca-Cola lata", cat_bebidas, bar, 7.00, 3.50, 48, 10),
            ("Porção de batata", cat_porcoes, cozinha, 38.00, 15.00, 20, 5),
            ("Narguilé Love 66", cat_narg, narg, 45.00, 18.00, 15, 3),
        ]
        for name, cat, sector, price, cost, stock, min_stock in samples:
            if not Product.query.filter_by(name=name).first():
                db.session.add(Product(name=name, category=cat, sector=sector, price=price, cost=cost, stock=stock, min_stock=min_stock, active=True))
        if not Supplier.query.filter_by(name="Fornecedor padrão").first():
            db.session.add(Supplier(name="Fornecedor padrão", phone=""))
        db.session.commit()
        print("Seed concluído.")
        print("Admin: admin@valeverde.com / admin123")

if __name__ == "__main__":
    run()
