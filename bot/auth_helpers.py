from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from . import supabase_service


async def require_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> supabase_service.AuthenticatedUser | None:
    """Uso al principio de cualquier handler que necesite leer/escribir datos: si no hay
    sesion valida, avisa y corta el flujo devolviendo None."""
    telegram_id = update.effective_user.id
    user = supabase_service.get_authenticated_user(telegram_id)
    if user is None:
        await update.effective_message.reply_text(
            "Primero tenés que iniciar sesión con /login (con el mismo email y contraseña "
            "que usás en la web de pororo-control)."
        )
        return None
    return user
