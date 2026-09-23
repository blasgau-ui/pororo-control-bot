"""Punto de entrada del bot de Telegram de pororo-control.

El bot en sí funciona por long-polling (no necesita servidor propio ni puerto expuesto),
así que sirve para correrlo en una notebook, un VPS chico, o un worker de Railway. Si se
despliega en el free tier de Render (que sólo ofrece "Web Service", no worker gratis),
start_health_server_if_configured() levanta un servidor HTTP mínimo en paralelo únicamente
para que Render considere el servicio "vivo" (ver README.md, sección Render). Todas las
operaciones de datos van directo contra la misma base de Supabase que usa la web de
pororo-control, autenticadas como la cuenta de cada usuaria.
"""

from __future__ import annotations

import datetime
import logging
import warnings

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot import config
from bot.errors import on_error
from bot.handlers import auth, costs, export, income, notifications, products, start, stock, summary
from bot.health_server import start_health_server_if_configured

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Nuestras conversaciones mezclan a propósito MessageHandler y CallbackQueryHandler por
# estado (por ejemplo: elegir producto con botones y despues escribir una cantidad), que
# es exactamente el caso de uso para el que per_message=False (el default) esta pensado.
# python-telegram-bot igual avisa por las dudas; el aviso no aplica a este caso.
warnings.filterwarnings("ignore", message="If 'per_message=False'", category=Warning)


def build_application() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start.start))
    app.add_handler(CommandHandler("ayuda", start.help_command))
    app.add_handler(CommandHandler("help", start.help_command))
    app.add_handler(CommandHandler("logout", auth.logout))

    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("login", auth.login_start)],
            states={
                auth.EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth.login_email)],
                auth.PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth.login_password)],
            },
            fallbacks=[CommandHandler("cancelar", auth.login_cancel)],
            name="login",
        )
    )

    app.add_handler(CommandHandler("productos", products.list_products))
    app.add_handler(CallbackQueryHandler(products.products_page_callback, pattern=r"^prodlist:page:"))

    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("crear_producto", products.create_start)],
            states=products.create_product_conversation_states,
            fallbacks=[CommandHandler("cancelar", products.create_cancel)],
            name="crear_producto",
        )
    )
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("editar_producto", products.edit_start)],
            states=products.edit_product_conversation_states,
            fallbacks=[CommandHandler("cancelar", products.edit_cancel)],
            name="editar_producto",
        )
    )
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("stock", stock.stock_start)],
            states=stock.stock_conversation_states,
            fallbacks=[CommandHandler("cancelar", stock.stock_cancel)],
            name="stock",
        )
    )
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("ganancia", income.income_start)],
            states=income.income_conversation_states,
            fallbacks=[CommandHandler("cancelar", income.income_cancel)],
            name="ganancia",
        )
    )
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("gasto", costs.cost_start)],
            states=costs.cost_conversation_states,
            fallbacks=[CommandHandler("cancelar", costs.cost_cancel)],
            name="gasto",
        )
    )

    app.add_handler(CommandHandler("resumen", summary.summary))
    app.add_handler(CommandHandler("exportar", export.export_data))

    app.add_handler(CommandHandler("notificaciones", notifications.notifications_menu))
    app.add_handler(CallbackQueryHandler(notifications.notifications_toggle, pattern=r"^notif:"))

    app.add_error_handler(on_error)

    if app.job_queue is not None:
        app.job_queue.run_daily(
            notifications.send_daily_digests,
            time=datetime.time(hour=config.DAILY_DIGEST_HOUR),
        )

    return app


def main() -> None:
    start_health_server_if_configured()
    app = build_application()
    logging.getLogger(__name__).info("Bot de pororo-control arrancado (long polling).")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
