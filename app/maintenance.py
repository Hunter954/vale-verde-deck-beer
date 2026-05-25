from decimal import Decimal
from pathlib import Path


def normalize_legacy_product_prices_once(db, Product, current_app):
    """
    Corrige uma vez produtos que foram salvos antes da máscara monetária.
    Ex.: 70000 aparecia como R$ 70.000,00; vira R$ 700,00.
    Em operação de bar/restaurante, valores acima de R$ 1.000,00 em cardápio quase sempre são erro de centavos.
    """
    try:
        upload_folder = Path(current_app.config.get("UPLOAD_FOLDER") or "uploads")
        upload_folder.mkdir(parents=True, exist_ok=True)
        marker = upload_folder / ".price_cents_fix_done"
        if marker.exists():
            return

        changed = 0
        for product in Product.query.all():
            price = Decimal(product.price or 0)
            cost = Decimal(product.cost or 0)
            if price >= Decimal("1000"):
                product.price = (price / Decimal("100")).quantize(Decimal("0.01"))
                changed += 1
            if cost >= Decimal("1000"):
                product.cost = (cost / Decimal("100")).quantize(Decimal("0.01"))
                changed += 1
        if changed:
            db.session.commit()
        marker.write_text("done", encoding="utf-8")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao normalizar preços legados")
