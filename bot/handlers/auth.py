from __future__ import annotations

import logging

from telegram import ReplyKeyboardRemove, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from .. import session_store, supabase_service

logger = logging.getLogger(__name__)

EMAIL, PASSWORD = range(2)


async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_id = update.effective_user.id
    locked = session_store.seconds_locked_out(telegram_id)
    if locked:
        minutes = max(1, locked // 60)
        await update.message.reply_text(
            f"Hubo demasiados intentos fallidos. Probá de nuevo en {minutes} minuto(s)."
        )
        return ConversationHandler.END

    existing = supabase_service.get_authenticated_user(telegram_id)
    if existing:
        await update.message.reply_text(
            f"Ya iniciaste sesión como {existing.email}. Usá /logout si querés cambiar de cuenta."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Vamos a vincular tu cuenta de pororo-control.\n\n"
        "Escribí tu *email* (el mismo que usás para entrar a la web):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return EMAIL


async def login_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    if "@" not in email or " " in email:
        await update.message.reply_text("Ese no parece un email válido. Probá de nuevo:")
        return EMAIL
    context.user_data["login_email"] = email
    await update.message.reply_text(
        "Ahora escribí tu *contraseña*.\n\n"
        "⚠️ Telegram guarda este mensaje en el historial del chat: te recomiendo borrarlo "
        "vos misma apenas termines. El bot va a intentar borrarlo automáticamente.",
        parse_mode="Markdown",
    )
    return PASSWORD


async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_id = update.effective_user.id
    password = update.message.text
    email = context.user_data.pop("login_email", None)

    try:
        await update.message.delete()
    except TelegramError:
        pass

    if not email:
        await update.effective_chat.send_message("Algo salió mal, empezá de nuevo con /login.")
        return ConversationHandler.END

    try:
        auth_user, access_token, refresh_token = supabase_service.sign_in(email, password)
    except supabase_service.AuthError:
        session_store.register_failed_login(telegram_id)
        remaining = session_store.seconds_locked_out(telegram_id)
        if remaining:
            await update.effective_chat.send_message(
                "Demasiados intentos fallidos. Se bloqueó el login por unos minutos por seguridad."
            )
        else:
            await update.effective_chat.send_message(
                "Email o contraseña incorrectos. Probá de nuevo con /login."
            )
        return ConversationHandler.END

    session_store.clear_failed_logins(telegram_id)
    session_store.save_session(telegram_id, auth_user.user_id, auth_user.email, access_token, refresh_token)
    await update.effective_chat.send_message(
        f"✅ Cuenta vinculada: *{auth_user.email}*.\n\nProbá /resumen o /productos para ver tus datos.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def login_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("login_email", None)
    await update.message.reply_text("Login cancelado.")
    return ConversationHandler.END


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = supabase_service.get_authenticated_user(telegram_id)
    if user:
        supabase_service.sign_out(user)
    session_store.clear_session(telegram_id)
    await update.message.reply_text("Sesión cerrada en este chat. Usá /login para volver a entrar.")
