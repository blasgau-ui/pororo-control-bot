"""Guarda, por usuario de Telegram, la sesion de Supabase (access/refresh token) que le
permite operar sobre su propia cuenta de pororo-control sin volver a pedir la contraseña
en cada mensaje. Nunca se guarda la contraseña, solo los tokens de sesion, y cifrados en
disco con Fernet (bot.crypto_utils) para que tener el archivo bot_sessions.db no alcance
para usar las cuentas si alguien lo copia.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass

from . import config
from .crypto_utils import decrypt, encrypt

_SCHEMA = """
create table if not exists sessions (
    telegram_id integer primary key,
    user_id text not null,
    email text not null,
    access_token text not null,
    refresh_token text not null,
    updated_at integer not null
);

create table if not exists login_attempts (
    telegram_id integer primary key,
    failed_count integer not null default 0,
    locked_until integer not null default 0
);

create table if not exists notification_prefs (
    telegram_id integer primary key,
    daily_digest integer not null default 0
);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(config.BOT_DB_PATH)
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


@dataclass
class StoredSession:
    telegram_id: int
    user_id: str
    email: str
    access_token: str
    refresh_token: str


def save_session(telegram_id: int, user_id: str, email: str, access_token: str, refresh_token: str) -> None:
    with _connect() as conn:
        conn.execute(
            """
            insert into sessions (telegram_id, user_id, email, access_token, refresh_token, updated_at)
            values (?, ?, ?, ?, ?, ?)
            on conflict(telegram_id) do update set
                user_id=excluded.user_id,
                email=excluded.email,
                access_token=excluded.access_token,
                refresh_token=excluded.refresh_token,
                updated_at=excluded.updated_at
            """,
            (telegram_id, user_id, email, encrypt(access_token), encrypt(refresh_token), int(time.time())),
        )


def load_session(telegram_id: int) -> StoredSession | None:
    with _connect() as conn:
        row = conn.execute(
            "select user_id, email, access_token, refresh_token from sessions where telegram_id = ?",
            (telegram_id,),
        ).fetchone()
    if not row:
        return None
    user_id, email, enc_access, enc_refresh = row
    access = decrypt(enc_access)
    refresh = decrypt(enc_refresh)
    if access is None or refresh is None:
        # Tokens ilegibles (por ejemplo, cambió BOT_ENCRYPTION_KEY): forzar re-login.
        clear_session(telegram_id)
        return None
    return StoredSession(telegram_id=telegram_id, user_id=user_id, email=email, access_token=access, refresh_token=refresh)


def clear_session(telegram_id: int) -> None:
    with _connect() as conn:
        conn.execute("delete from sessions where telegram_id = ?", (telegram_id,))


# --- rate limiting de intentos de login -----------------------------------------------


def register_failed_login(telegram_id: int) -> None:
    with _connect() as conn:
        row = conn.execute(
            "select failed_count from login_attempts where telegram_id = ?", (telegram_id,)
        ).fetchone()
        failed = (row[0] if row else 0) + 1
        locked_until = 0
        if failed >= config.MAX_LOGIN_ATTEMPTS:
            locked_until = int(time.time()) + config.LOGIN_LOCKOUT_SECONDS
            failed = 0
        conn.execute(
            """
            insert into login_attempts (telegram_id, failed_count, locked_until) values (?, ?, ?)
            on conflict(telegram_id) do update set failed_count=excluded.failed_count, locked_until=excluded.locked_until
            """,
            (telegram_id, failed, locked_until),
        )


def clear_failed_logins(telegram_id: int) -> None:
    with _connect() as conn:
        conn.execute("delete from login_attempts where telegram_id = ?", (telegram_id,))


def seconds_locked_out(telegram_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "select locked_until from login_attempts where telegram_id = ?", (telegram_id,)
        ).fetchone()
    if not row or not row[0]:
        return 0
    remaining = row[0] - int(time.time())
    return max(0, remaining)


# --- preferencias de notificaciones ----------------------------------------------------


def set_daily_digest(telegram_id: int, enabled: bool) -> None:
    with _connect() as conn:
        conn.execute(
            """
            insert into notification_prefs (telegram_id, daily_digest) values (?, ?)
            on conflict(telegram_id) do update set daily_digest=excluded.daily_digest
            """,
            (telegram_id, int(enabled)),
        )


def list_daily_digest_subscribers() -> list[int]:
    with _connect() as conn:
        rows = conn.execute(
            "select telegram_id from notification_prefs where daily_digest = 1"
        ).fetchall()
    return [r[0] for r in rows]
