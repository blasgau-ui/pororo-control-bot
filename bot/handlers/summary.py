from __future__ import annotations

import datetime

from telegram import Update
from telegram.ext import ContextTypes

from .. import supabase_service
from ..auth_helpers import require_login
from ..domain import get_low_stock_products, get_monthly_profit_summary
from ..formatting import money, month_name


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_login(update, context)
    if not user:
        return
    data = supabase_service.load_app_data(user)
    today = datetime.date.today()
    report = get_monthly_profit_summary(data, today.year, today.month)

    lines = [f"📊 *Resumen de {month_name(today.month)} {today.year}*\n"]
    if not report.carts:
        lines.append("Todavía no hay puestos cargados.")
    for c in report.carts:
        lines.append(f"• {c.cart_name}: vendido {money(c.gross)}, sueldos {money(c.employees_total)} → {money(c.net_after_employees)}")

    lines.append("")
    lines.append(f"💵 Total vendido: {money(report.total_gross)}")
    lines.append(f"👷 Total sueldos: {money(report.total_employees)}")
    lines.append(f"🧾 Gastos (mercadería + otros): {money(report.total_expenses)}")
    lines.append(f"📈 *Ganancia neta estimada: {money(report.net_profit)}*")

    low_stock = get_low_stock_products(data)
    if low_stock:
        lines.append("\n⚠️ *Stock bajo:*")
        for item in low_stock[:10]:
            lines.append(
                f"• {item.product['name']}: {item.total_stock:g} {item.product.get('unit', '')} "
                f"(mínimo {item.product.get('minStock', 0):g})"
            )
        if len(low_stock) > 10:
            lines.append(f"…y {len(low_stock) - 10} producto(s) más bajo el mínimo.")

    await update.effective_message.reply_markdown("\n".join(lines))
