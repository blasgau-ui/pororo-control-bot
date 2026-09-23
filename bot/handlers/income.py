from __future__ import annotations

import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from .. import supabase_service
from ..auth_helpers import require_login
from ..domain import income_key
from ..formatting import money
from ..keyboards import carts_keyboard, confirm_keyboard

PICK_CART, PICK_DATE, AMOUNT, CONFIRM = range(4)


async def income_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_login(update, context)
    if not user:
        return ConversationHandler.END
    data = supabase_service.load_app_data(user)
    carts = data.get("carts", [])
    if not carts:
        await update.message.reply_text("Todavía no tenés puestos cargados (se cargan desde la web).")
        return ConversationHandler.END
    context.user_data["income_carts_cache"] = {c["id"]: c for c in carts}
    await update.message.reply_text("¿De qué puesto es la venta?", reply_markup=carts_keyboard(carts, "incart"))
    return PICK_CART


async def pick_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cart_id = query.data.split(":", 1)[1]
    cart = context.user_data["income_carts_cache"].get(cart_id)
    context.user_data["income_entry"] = {"cartId": cart_id}
    today = datetime.date.today()
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"📅 Hoy ({today.strftime('%d/%m')})", callback_data="income_date:today")]]
    )
    await query.edit_message_text(
        f"Puesto: *{cart['name'] if cart else cart_id}*\n\n"
        "¿Qué día fue la venta? Tocá *Hoy* o escribí la fecha como dd/mm (o dd/mm/aaaa):",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return PICK_DATE


async def pick_date_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    today = datetime.date.today()
    context.user_data["income_entry"].update(year=today.year, month=today.month, day=today.day)
    await query.edit_message_text(f"Día: {today.strftime('%d/%m/%Y')}\n\n¿Cuánto se vendió ese día en total?")
    return AMOUNT


async def pick_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    today = datetime.date.today()
    parts = raw.split("/")
    try:
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2]) if len(parts) > 2 else today.year
        date = datetime.date(year, month, day)
    except (ValueError, IndexError):
        await update.message.reply_text("No entendí la fecha. Usá el formato dd/mm o dd/mm/aaaa:")
        return PICK_DATE
    context.user_data["income_entry"].update(year=date.year, month=date.month, day=date.day)
    await update.message.reply_text(f"Día: {date.strftime('%d/%m/%Y')}\n\n¿Cuánto se vendió ese día en total?")
    return AMOUNT


async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.strip().replace(",", "."))
        if amount < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Tiene que ser un número igual o mayor a 0. Probá de nuevo:")
        return AMOUNT
    context.user_data["income_entry"]["amount"] = amount
    e = context.user_data["income_entry"]
    await update.message.reply_text(
        f"Confirmás cargar {money(amount)} vendidos el {e['day']:02d}/{e['month']:02d}/{e['year']}?\n\n"
        "⚠️ Esto reemplaza lo que hubiera cargado ese día para ese puesto (no lo suma).",
        reply_markup=confirm_keyboard("incomeconfirm"),
    )
    return CONFIRM


async def confirm_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    answer = query.data.split(":")[1]
    e = context.user_data.pop("income_entry", None)
    context.user_data.pop("income_carts_cache", None)
    if answer != "yes" or not e:
        await query.edit_message_text("Cancelado, no se cargó nada.")
        return ConversationHandler.END

    user = await require_login(update, context)
    if not user:
        return ConversationHandler.END
    data = supabase_service.load_app_data(user)
    key = income_key(e["cartId"], e["year"], e["month"], e["day"])
    if e["amount"] == 0:
        data.get("dailyIncome", {}).pop(key, None)
    else:
        data.setdefault("dailyIncome", {})[key] = e["amount"]
    supabase_service.save_app_data(user, data)
    await query.edit_message_text(f"✅ Venta cargada: {money(e['amount'])} el {e['day']:02d}/{e['month']:02d}/{e['year']}.")
    return ConversationHandler.END


async def income_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("income_entry", None)
    context.user_data.pop("income_carts_cache", None)
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


income_conversation_states = {
    PICK_CART: [CallbackQueryHandler(pick_cart, pattern=r"^incart:")],
    PICK_DATE: [
        CallbackQueryHandler(pick_date_today, pattern=r"^income_date:today"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, pick_date_text),
    ],
    AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount)],
    CONFIRM: [CallbackQueryHandler(confirm_income, pattern=r"^incomeconfirm:")],
}
