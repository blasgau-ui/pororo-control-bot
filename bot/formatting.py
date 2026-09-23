from __future__ import annotations

from typing import Any


def money(amount: float) -> str:
    """Formato $ argentino simplificado: separador de miles con punto, sin decimales
    si son enteros (igual look que src/lib/format.ts)."""
    rounded = round(amount)
    text = f"{abs(rounded):,}".replace(",", ".")
    sign = "-" if rounded < 0 else ""
    return f"{sign}${text}"


def product_line(product: dict[str, Any], stock: float) -> str:
    low = " ⚠️" if stock < product.get("minStock", 0) else ""
    price = f" · {money(product['salePrice'])}" if product.get("salePrice") else ""
    return f"• *{product['name']}* ({product.get('category', '—')}) — {stock:g} {product.get('unit', '')}{low}{price}"


def month_name(month: int) -> str:
    names = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    return names[month - 1]
