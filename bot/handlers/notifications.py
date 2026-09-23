from __future__ import annotations

import datetime
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from .. import session_store, supabase_service
from ..domain import get_low_stock_products, income_key
from ..formatting import money

logger = logging.getLogger(__name__)


async def notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔔 Activar resumen diario", callback_data="notif:on")],
            [InlineKeyboardButton("🔕 Desactivar", callback_data="notif:off")],
        ]
    )
    await update.message.reply_text(
        "El resumen diario te manda, una vez por día, lo vendido en el día y si hay "
        "productos por debajo del stock mínimo. ¿Qué querés hacer?",
        reply_markup=keyboard,
    )


async def notifications_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    enabled = query.data.split(":")[1] == "on"
    session_store.set_daily_digest(update.effective_user.id, enabled)
    if enabled:
        user = supabase_service.get_authenticated_user(update.effective_user.id)
        if not user:
            await query.edit_message_text(
                "Activado, pero primero necesitás /login para que el resumen tenga datos que mandar."
            )
            return
        await query.edit_message_text("🔔 Resumen diario activado.")
    else:
        await query.edit_message_text("🔕 Resumen diario desactivado.")


async def send_daily_digests(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job periodico (registrado en main.py) que manda el resumen del dia a quienes lo
    activaron con /notificaciones. Si a alguien se le vencio la sesion, se lo salta en
    silencio (ya se le avisa la proxima vez que use el bot y el /login falle)."""
    today = datetime.date.today()
    for telegram_id in session_store.list_daily_digest_subscribers():
        user = supabase_service.get_authenticated_user(telegram_id)
        if not user:
            continue
        try:
            data = supabase_service.load_app_data(user)
            total_today = sum(
                data.get("dailyIncome", {}).get(income_key(cart["id"], today.year, today.month, today.day), 0)
                for cart in data.get("carts", [])
            )
            low_stock = get_low_stock_products(data)
            lines = [f"🌙 *Resumen del {today.strftime('%d/%m')}*", f"Vendido hoy: {money(total_today)}"]
            if low_stock:
                lines.append(f"⚠️ {len(low_stock)} producto(s) por debajo del stock mínimo. Mirá /resumen para el detalle.")
            await context.bot.send_message(telegram_id, "\n".join(lines), parse_mode="Markdown")
        except TelegramError:
            logger.info("No se pudo mandar el resumen diario a telegram_id=%s", telegram_id, exc_info=True)
        except Exception:
            logger.exception("Error armando el resumen diario para telegram_id=%s", telegram_id)
