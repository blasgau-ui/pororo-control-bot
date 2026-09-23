from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Falta la variable de entorno {name}. Copiá .env.example a .env y completala.", file=sys.stderr)
        sys.exit(1)
    return value


TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = _require("SUPABASE_URL")
SUPABASE_ANON_KEY = _require("SUPABASE_ANON_KEY")
BOT_ENCRYPTION_KEY = _require("BOT_ENCRYPTION_KEY")

BOT_DB_PATH = os.getenv("BOT_DB_PATH", "bot_sessions.db")
DAILY_DIGEST_HOUR = int(os.getenv("DAILY_DIGEST_HOUR", "20"))

TABLE_NAME = "pororo_control_state"

# Intentos de login fallidos permitidos antes de bloquear temporalmente a un usuario de Telegram.
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60
