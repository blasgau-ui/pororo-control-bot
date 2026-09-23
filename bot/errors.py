from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Excepción no manejada procesando un update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Uy, algo falló de este lado. Probá de nuevo en un momento; si sigue "
                "pasando, avisale a quien mantiene el bot."
            )
        except Exception:
            logger.exception("No se pudo avisar del error al usuario")
