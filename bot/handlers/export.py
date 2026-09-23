from __future__ import annotations

import datetime
import io
import json

from telegram import InputFile, Update
from telegram.ext import ContextTypes

from .. import supabase_service
from ..auth_helpers import require_login


async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await require_login(update, context)
    if not user:
        return
    data = supabase_service.load_app_data(user)
    buffer = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    stamp = datetime.date.today().isoformat()
    buffer.name = f"pororo-control-backup-{stamp}.json"
    await update.effective_message.reply_document(
        document=InputFile(buffer, filename=buffer.name),
        caption="📄 Backup de tus datos. Se puede volver a importar desde la web (Configuración → Importar).",
    )
