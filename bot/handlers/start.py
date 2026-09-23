from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from .. import supabase_service

WELCOME = (
    "🍿 *Pororo Control Bot*\n\n"
    "Manejá productos, stock, ventas y gastos de tu negocio sin abrir la web. "
    "Todo lo que cargues acá se guarda en la misma cuenta de pororo-control, "
    "así que aparece al instante en la página.\n\n"
    "Para empezar: /login\n"
    "Para ver todos los comandos: /ayuda"
)

HELP = (
    "*Comandos disponibles*\n\n"
    "🔐 *Cuenta*\n"
    "/login — Iniciar sesión\n"
    "/logout — Cerrar sesión en este chat\n\n"
    "📦 *Productos y stock*\n"
    "/productos — Ver productos y stock actual\n"
    "/crear\\_producto — Cargar un producto nuevo\n"
    "/editar\\_producto — Modificar un producto existente\n"
    "/stock — Registrar entrada, salida o ajuste de stock\n\n"
    "💰 *Ventas y gastos*\n"
    "/ganancia — Cargar lo vendido de un día en un puesto\n"
    "/gasto — Registrar un gasto del mes\n"
    "/resumen — Resumen financiero y de stock del mes\n\n"
    "🔔 *Otros*\n"
    "/exportar — Recibir un backup en JSON de todos tus datos\n"
    "/notificaciones — Activar o desactivar el resumen diario\n"
    "/cancelar — Cancelar la operación en curso\n"
    "/ayuda — Este mensaje"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = supabase_service.get_authenticated_user(update.effective_user.id)
    suffix = f"\n\n✅ Ya iniciaste sesión como *{user.email}*." if user else ""
    await update.message.reply_markdown(WELCOME + suffix)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_markdown(HELP)
