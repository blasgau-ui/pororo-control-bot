from __future__ import annotations

from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .domain import PRODUCT_CATEGORIES


def category_keyboard(prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(cat, callback_data=f"{prefix}:{i}")] for i, cat in enumerate(PRODUCT_CATEGORIES)]
    return InlineKeyboardMarkup(rows)


def confirm_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Confirmar", callback_data=f"{prefix}:yes"),
          InlineKeyboardButton("❌ Cancelar", callback_data=f"{prefix}:no")]]
    )


def products_keyboard(products: list[dict[str, Any]], prefix: str, page: int, page_size: int = 8) -> InlineKeyboardMarkup:
    start = page * page_size
    page_items = products[start:start + page_size]
    rows = [[InlineKeyboardButton(p["name"], callback_data=f"{prefix}:pick:{p['id']}")] for p in page_items]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{prefix}:page:{page - 1}"))
    if start + page_size < len(products):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{prefix}:page:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(rows)


def carts_keyboard(carts: list[dict[str, Any]], prefix: str, include_deposit: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(c["name"], callback_data=f"{prefix}:{c['id']}")] for c in carts]
    if include_deposit:
        rows.append([InlineKeyboardButton("🏬 Depósito central", callback_data=f"{prefix}:deposito-central")])
    return InlineKeyboardMarkup(rows)


def movement_type_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📥 Entrada (compra)", callback_data=f"{prefix}:entrada")],
            [InlineKeyboardButton("📤 Salida (venta/uso)", callback_data=f"{prefix}:salida")],
            [InlineKeyboardButton("🛠️ Ajuste", callback_data=f"{prefix}:ajuste")],
        ]
    )
