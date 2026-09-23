"""Variables de entorno dummy para que bot.config y bot.crypto_utils puedan importarse
en los tests sin necesitar un .env real ni credenciales verdaderas."""

import os

from cryptography.fernet import Fernet

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-TOKEN")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("BOT_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("BOT_DB_PATH", "test_bot_sessions.db")
