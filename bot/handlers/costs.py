from __future__ import annotations

import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from .. import supabase_service
from ..auth_helpers import require_login
from ..domain import generate_id
from ..formatting import money
from ..keyboards import confirm_keyboard

PICK_DESCRIPTION, CUSTOM_DESCRIPTION, AMOUNT, CONFIRM = range(4)


async def cost_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_login(update, context)
    if not user:
        return ConversationHandler.END
    data = supabase_service.load_app_data(user)
    templates = data.get("costTemplates", [])
    rows = [[InlineKeyboardButton(t, callback_data=f"costtpl:{i}")] for i, t in enumerate(templates)]
    rows.append([InlineKeyboardButton("✏️ Otro (escribir descripción)", callback_data="costtpl:custom")])
    context.user_data["cost_templates_cache"] = templates
    await update.message.reply_text(
        "¿Qué gasto querés cargar este mes?", reply_markup=InlineKeyboardMarkup(rows)
    )
    return PICK_DESCRIPTION


async def pick_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":")[1]
    if choice == "custom":
        await query.edit_message_text("Escribí la descripción del gasto:")
        return CUSTOM_DESCRIPTION
    templates = context.user_data.get("cost_templates_cache", [])
    description = templates[int(choice)]
    context.user_data["cost_entry"] = {"description": description}
    await query.edit_message_text(f"Gasto: *{description}*\n\n¿Por cuánto?", parse_mode="Markdown")
    return AMOUNT


async def custom_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    description = update.message.text.strip()
    if not description:
        await update.message.reply_text("No puede estar vacío. Probá de nuevo:")
        return CUSTOM_DESCRIPTION
    context.user_data["cost_entry"] = {"description": description[:120]}
    await update.message.reply_text("¿Por cuánto?")
    return AMOUNT


async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Tiene que ser un número mayor a 0. Probá de nuevo:")
        return AMOUNT
    context.user_data["cost_entry"]["amount"] = amount
    e = context.user_data["cost_entry"]
    today = datetime.date.today()
    await update.message.reply_text(
        f"Confirmás cargar *{e['description']}*: {money(amount)} en {today.strftime('%m/%Y')}?",
        parse_mode="Markdown",
        reply_markup=confirm_keyboard("costconfirm"),
    )
    return CONFIRM


async def confirm_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    answer = query.data.split(":")[1]
    e = context.user_data.pop("cost_entry", None)
    context.user_data.pop("cost_templates_cache", None)
    if answer != "yes" or not e:
        await query.edit_message_text("Cancelado, no se cargó nada.")
        return ConversationHandler.END

    user = await require_login(update, context)
    if not user:
        return ConversationHandler.END
    data = supabase_service.load_app_data(user)
    today = datetime.date.today()
    cost = {
        "id": generate_id("cost"),
        "year": today.year,
        "month": today.month,
        "description": e["description"],
        "amount": e["amount"],
    }
    data.setdefault("otherCosts", []).append(cost)
    supabase_service.save_app_data(user, data)
    await query.edit_message_text(f"✅ Gasto cargado: {e['description']} — {money(e['amount'])}")
    return ConversationHandler.END


async def cost_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("cost_entry", None)
    context.user_data.pop("cost_templates_cache", None)
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


cost_conversation_states = {
    PICK_DESCRIPTION: [CallbackQueryHandler(pick_description, pattern=r"^costtpl:")],
    CUSTOM_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_description)],
    AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount)],
    CONFIRM: [CallbackQueryHandler(confirm_cost, pattern=r"^costconfirm:")],
}
