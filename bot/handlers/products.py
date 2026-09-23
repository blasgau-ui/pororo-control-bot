from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from .. import supabase_service
from ..auth_helpers import require_login
from ..domain import PRODUCT_CATEGORIES, generate_id, get_total_balance
from ..formatting import money, product_line
from ..keyboards import category_keyboard, confirm_keyboard, products_keyboard

PAGE_SIZE = 8

# --- /productos (solo lectura, paginado) ------------------------------------------------


async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_login(update, context)
    if not user:
        return
    data = supabase_service.load_app_data(user)
    await _send_products_page(update.message.reply_text, data, page=0)


async def _send_products_page(send, data, page: int) -> None:
    products = data.get("products", [])
    if not products:
        await send("Todavía no cargaste productos. Usá /crear_producto para el primero.")
        return
    movements = data.get("stockMovements", [])
    lines = [
        product_line(p, get_total_balance(movements, p["id"]))
        for p in products[page * PAGE_SIZE : page * PAGE_SIZE + PAGE_SIZE]
    ]
    text = f"📦 *Productos* ({len(products)} en total)\n\n" + "\n".join(lines)
    await send(text, parse_mode="Markdown", reply_markup=products_keyboard(products, "prodlist", page))


async def products_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = await require_login(update, context)
    if not user:
        return
    data = supabase_service.load_app_data(user)
    _, _, page_str = query.data.split(":")
    products = data.get("products", [])
    movements = data.get("stockMovements", [])
    page = int(page_str)
    lines = [
        product_line(p, get_total_balance(movements, p["id"]))
        for p in products[page * PAGE_SIZE : page * PAGE_SIZE + PAGE_SIZE]
    ]
    text = f"📦 *Productos* ({len(products)} en total)\n\n" + "\n".join(lines)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=products_keyboard(products, "prodlist", page))


# --- /crear_producto ---------------------------------------------------------------------

NAME, CATEGORY, UNIT, MIN_STOCK, SALE_PRICE, CONFIRM = range(6)


async def create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_login(update, context)
    if not user:
        return ConversationHandler.END
    context.user_data["new_product"] = {}
    await update.message.reply_text("Nombre del producto nuevo:")
    return NAME


async def create_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("El nombre no puede estar vacío. Probá de nuevo:")
        return NAME
    context.user_data["new_product"]["name"] = name[:120]
    await update.message.reply_text("Elegí la categoría:", reply_markup=category_keyboard("newprod_cat"))
    return CATEGORY


async def create_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":")[1])
    context.user_data["new_product"]["category"] = PRODUCT_CATEGORIES[idx]
    await query.edit_message_text(f"Categoría: {PRODUCT_CATEGORIES[idx]}")
    await query.message.reply_text("Unidad (ej: unid, kg, litro, paquete):")
    return UNIT


async def create_unit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_product"]["unit"] = update.message.text.strip()[:30] or "unid"
    await update.message.reply_text("Stock mínimo antes de avisar que hay que reponer (número, ej: 10):")
    return MIN_STOCK


async def create_min_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        min_stock = float(update.message.text.strip().replace(",", "."))
        if min_stock < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Tiene que ser un número igual o mayor a 0. Probá de nuevo:")
        return MIN_STOCK
    context.user_data["new_product"]["minStock"] = min_stock
    await update.message.reply_text(
        "Precio de venta habitual (0 si es un insumo que no se vende suelto):"
    )
    return SALE_PRICE


async def create_sale_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        price = float(update.message.text.strip().replace(",", "."))
        if price < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Tiene que ser un número igual o mayor a 0. Probá de nuevo:")
        return SALE_PRICE
    p = context.user_data["new_product"]
    p["salePrice"] = price
    summary = (
        f"Confirmá el producto nuevo:\n\n"
        f"*{p['name']}*\n"
        f"Categoría: {p['category']}\n"
        f"Unidad: {p['unit']}\n"
        f"Stock mínimo: {p['minStock']:g}\n"
        f"Precio de venta: {money(price)}"
    )
    await update.message.reply_markdown(summary, reply_markup=confirm_keyboard("newprod_confirm"))
    return CONFIRM


async def create_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    answer = query.data.split(":")[1]
    if answer != "yes":
        context.user_data.pop("new_product", None)
        await query.edit_message_text("Cancelado, no se creó el producto.")
        return ConversationHandler.END

    user = await require_login(update, context)
    if not user:
        return ConversationHandler.END
    data = supabase_service.load_app_data(user)
    p = context.user_data.pop("new_product")
    p["id"] = generate_id("prod")
    data["products"].append(p)
    supabase_service.save_app_data(user, data)
    await query.edit_message_text(f"✅ Producto *{p['name']}* creado.", parse_mode="Markdown")
    return ConversationHandler.END


async def create_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("new_product", None)
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


create_product_conversation_states = {
    NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_name)],
    CATEGORY: [CallbackQueryHandler(create_category, pattern=r"^newprod_cat:")],
    UNIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_unit)],
    MIN_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_min_stock)],
    SALE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_sale_price)],
    CONFIRM: [CallbackQueryHandler(create_confirm, pattern=r"^newprod_confirm:")],
}


# --- /editar_producto ---------------------------------------------------------------------

EDIT_PICK, EDIT_FIELD, EDIT_VALUE, EDIT_CATEGORY, EDIT_CONFIRM = range(6, 11)

EDITABLE_FIELDS = {
    "name": "Nombre",
    "category": "Categoría",
    "unit": "Unidad",
    "minStock": "Stock mínimo",
    "salePrice": "Precio de venta",
}


async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await require_login(update, context)
    if not user:
        return ConversationHandler.END
    data = supabase_service.load_app_data(user)
    products = data.get("products", [])
    if not products:
        await update.message.reply_text("No hay productos cargados todavía.")
        return ConversationHandler.END
    context.user_data["edit_products_cache"] = {p["id"]: p for p in products}
    await update.message.reply_text(
        "¿Qué producto querés editar?", reply_markup=products_keyboard(products, "editprod", 0)
    )
    return EDIT_PICK


async def edit_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[2])
    products = list(context.user_data.get("edit_products_cache", {}).values())
    await query.edit_message_reply_markup(products_keyboard(products, "editprod", page))
    return EDIT_PICK


async def edit_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    product_id = query.data.split(":")[2]
    product = context.user_data["edit_products_cache"].get(product_id)
    if not product:
        await query.edit_message_text("Ese producto ya no existe.")
        return ConversationHandler.END
    context.user_data["editing_product_id"] = product_id
    rows = [[InlineKeyboardButton(label, callback_data=f"editfield:{key}")] for key, label in EDITABLE_FIELDS.items()]
    await query.edit_message_text(
        f"Editando *{product['name']}*. ¿Qué campo?", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return EDIT_FIELD


async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    field_key = query.data.split(":")[1]
    context.user_data["editing_field"] = field_key
    if field_key == "category":
        await query.edit_message_text("Elegí la nueva categoría:", reply_markup=category_keyboard("editcat"))
        return EDIT_CATEGORY
    label = EDITABLE_FIELDS[field_key]
    await query.edit_message_text(f"Escribí el nuevo valor para *{label}*:", parse_mode="Markdown")
    return EDIT_VALUE


async def edit_category_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":")[1])
    context.user_data["editing_value"] = PRODUCT_CATEGORIES[idx]
    return await _edit_show_confirm(query.edit_message_text, context)


async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field_key = context.user_data["editing_field"]
    raw = update.message.text.strip()
    if field_key in ("minStock", "salePrice"):
        try:
            value: object = float(raw.replace(",", "."))
            if value < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Tiene que ser un número igual o mayor a 0. Probá de nuevo:")
            return EDIT_VALUE
    else:
        if not raw:
            await update.message.reply_text("No puede estar vacío. Probá de nuevo:")
            return EDIT_VALUE
        value = raw[:120]
    context.user_data["editing_value"] = value
    return await _edit_show_confirm(update.message.reply_text, context)


async def _edit_show_confirm(send, context: ContextTypes.DEFAULT_TYPE) -> int:
    field_key = context.user_data["editing_field"]
    label = EDITABLE_FIELDS[field_key]
    value = context.user_data["editing_value"]
    await send(f"Confirmás cambiar *{label}* a: {value}", parse_mode="Markdown", reply_markup=confirm_keyboard("editconfirm"))
    return EDIT_CONFIRM


async def edit_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    answer = query.data.split(":")[1]
    if answer != "yes":
        await query.edit_message_text("Cancelado, no se modificó nada.")
        return ConversationHandler.END

    user = await require_login(update, context)
    if not user:
        return ConversationHandler.END
    product_id = context.user_data.pop("editing_product_id")
    field_key = context.user_data.pop("editing_field")
    value = context.user_data.pop("editing_value")
    context.user_data.pop("edit_products_cache", None)

    data = supabase_service.load_app_data(user)
    for p in data.get("products", []):
        if p["id"] == product_id:
            p[field_key] = value
            break
    else:
        await query.edit_message_text("Ese producto ya no existe (quizás lo borraron desde la web).")
        return ConversationHandler.END
    supabase_service.save_app_data(user, data)
    await query.edit_message_text("✅ Producto actualizado.")
    return ConversationHandler.END


async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    for key in ("editing_product_id", "editing_field", "editing_value", "edit_products_cache"):
        context.user_data.pop(key, None)
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


edit_product_conversation_states = {
    EDIT_PICK: [
        CallbackQueryHandler(edit_page, pattern=r"^editprod:page:"),
        CallbackQueryHandler(edit_pick, pattern=r"^editprod:pick:"),
    ],
    EDIT_FIELD: [CallbackQueryHandler(edit_field, pattern=r"^editfield:")],
    EDIT_CATEGORY: [CallbackQueryHandler(edit_category_value, pattern=r"^editcat:")],
    EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)],
    EDIT_CONFIRM: [CallbackQueryHandler(edit_confirm, pattern=r"^editconfirm:")],
}
