from __future__ import annotations

import datetime

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from .. import supabase_service
from ..auth_helpers import require_login
from ..domain import generate_id, get_location_balance
from ..formatting import money
from ..keyboards import carts_keyboard, confirm_keyboard, movement_type_keyboard, products_keyboard

PICK_PRODUCT, PICK_LOCATION, PICK_TYPE, QUANTITY, UNIT_COST, NOTE, CONFIRM = range(7)

TYPE_LABELS = {"entrada": "📥 Entrada", "salida": "📤 Salida", "ajuste": "🛠️ Ajuste"}


async def stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_login(update, context)
    if not user:
        return ConversationHandler.END
    data = supabase_service.load_app_data(user)
    products = data.get("products", [])
    if not products:
        await update.message.reply_text("No hay productos cargados. Usá /crear_producto primero.")
        return ConversationHandler.END
    context.user_data["stock_products_cache"] = {p["id"]: p for p in products}
    context.user_data["stock_carts_cache"] = data.get("carts", [])
    await update.message.reply_text("¿De qué producto es el movimiento?", reply_markup=products_keyboard(products, "stockprod", 0))
    return PICK_PRODUCT


async def pick_product_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[2])
    products = list(context.user_data.get("stock_products_cache", {}).values())
    await query.edit_message_reply_markup(products_keyboard(products, "stockprod", page))
    return PICK_PRODUCT


async def pick_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    product_id = query.data.split(":")[2]
    product = context.user_data["stock_products_cache"].get(product_id)
    if not product:
        await query.edit_message_text("Ese producto ya no existe.")
        return ConversationHandler.END
    context.user_data["stock_movement"] = {"productId": product_id}
    carts = context.user_data.get("stock_carts_cache", [])
    await query.edit_message_text(
        f"Producto: *{product['name']}*\n¿En qué ubicación?", parse_mode="Markdown",
        reply_markup=carts_keyboard(carts, "stockloc", include_deposit=True),
    )
    return PICK_LOCATION


async def pick_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    location_id = query.data.split(":", 1)[1]
    context.user_data["stock_movement"]["locationId"] = location_id
    await query.edit_message_text("¿Qué tipo de movimiento?", reply_markup=movement_type_keyboard("stocktype"))
    return PICK_TYPE


async def pick_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    movement_type = query.data.split(":")[1]
    context.user_data["stock_movement"]["type"] = movement_type
    label = TYPE_LABELS[movement_type]
    await query.edit_message_text(f"Tipo: {label}\n\n¿Qué cantidad?")
    return QUANTITY


async def enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        quantity = float(update.message.text.strip().replace(",", "."))
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Tiene que ser un número mayor a 0. Probá de nuevo:")
        return QUANTITY
    context.user_data["stock_movement"]["quantity"] = quantity
    if context.user_data["stock_movement"]["type"] == "entrada":
        await update.message.reply_text("Costo unitario pagado (0 si no lo sabés/no aplica):")
        return UNIT_COST
    await update.message.reply_text("Nota opcional (o escribí \"-\" para dejarlo en blanco):")
    return NOTE


async def enter_unit_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        unit_cost = float(update.message.text.strip().replace(",", "."))
        if unit_cost < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Tiene que ser un número igual o mayor a 0. Probá de nuevo:")
        return UNIT_COST
    context.user_data["stock_movement"]["unitCost"] = unit_cost
    await update.message.reply_text("Nota opcional (o escribí \"-\" para dejarlo en blanco):")
    return NOTE


async def enter_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    note = update.message.text.strip()
    context.user_data["stock_movement"]["note"] = "" if note == "-" else note[:200]
    m = context.user_data["stock_movement"]
    summary = (
        f"Confirmás este movimiento:\n\n"
        f"Tipo: {TYPE_LABELS[m['type']]}\n"
        f"Cantidad: {m['quantity']:g}\n"
    )
    if "unitCost" in m:
        summary += f"Costo unitario: {money(m['unitCost'])}\n"
    if m.get("note"):
        summary += f"Nota: {m['note']}\n"
    await update.message.reply_text(summary, reply_markup=confirm_keyboard("stockconfirm"))
    return CONFIRM


async def confirm_movement(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    answer = query.data.split(":")[1]
    if answer != "yes":
        _clear_stock_state(context)
        await query.edit_message_text("Cancelado, no se registró el movimiento.")
        return ConversationHandler.END

    user = await require_login(update, context)
    if not user:
        return ConversationHandler.END
    m = context.user_data["stock_movement"]
    product = context.user_data["stock_products_cache"].get(m["productId"])
    _clear_stock_state(context)

    data = supabase_service.load_app_data(user)
    movement = {
        "id": generate_id("mov"),
        "productId": m["productId"],
        "locationId": m["locationId"],
        "date": datetime.date.today().isoformat(),
        "type": m["type"],
        "quantity": m["quantity"],
        "note": m.get("note", ""),
        "createdAt": int(datetime.datetime.now().timestamp() * 1000),
    }
    if "unitCost" in m:
        movement["unitCost"] = m["unitCost"]
    data.setdefault("stockMovements", []).append(movement)
    supabase_service.save_app_data(user, data)

    new_balance = get_location_balance(data["stockMovements"], m["productId"], m["locationId"])
    name = product["name"] if product else m["productId"]
    await query.edit_message_text(
        f"✅ Movimiento guardado. Nuevo stock de *{name}* en esa ubicación: {new_balance:g}",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


def _clear_stock_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in ("stock_movement", "stock_products_cache", "stock_carts_cache"):
        context.user_data.pop(key, None)


async def stock_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _clear_stock_state(context)
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


stock_conversation_states = {
    PICK_PRODUCT: [
        CallbackQueryHandler(pick_product_page, pattern=r"^stockprod:page:"),
        CallbackQueryHandler(pick_product, pattern=r"^stockprod:pick:"),
    ],
    PICK_LOCATION: [CallbackQueryHandler(pick_location, pattern=r"^stockloc:")],
    PICK_TYPE: [CallbackQueryHandler(pick_type, pattern=r"^stocktype:")],
    QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_quantity)],
    UNIT_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_unit_cost)],
    NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_note)],
    CONFIRM: [CallbackQueryHandler(confirm_movement, pattern=r"^stockconfirm:")],
}
