"""Capa de acceso a datos. Toda la integracion con pororo-control pasa por acá: si algún
día pororo-control expone una API propia en lugar de usar Supabase directamente, sólo
hay que reescribir este archivo (load_app_data / save_app_data / sign_in / restore_client)
y el resto del bot (handlers, domain.py) no se entera del cambio.

pororo-control es una SPA sin backend propio: la web lee y escribe directamente en
Supabase, en la tabla pororo_control_state (una fila por cuenta, protegida con Row Level
Security para que cada usuaria solo pueda ver/escribir la suya). El bot hace lo mismo,
autenticado como la misma cuenta, para que los cambios se vean al instante en la web.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from supabase import Client, create_client

from . import config, session_store
from .domain import normalize_app_data

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Credenciales invalidas o sesion vencida/irrecuperable."""


@dataclass
class AuthenticatedUser:
    client: Client
    user_id: str
    email: str


def _new_client() -> Client:
    return create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)


def sign_in(email: str, password: str) -> tuple[AuthenticatedUser, str, str]:
    """Inicia sesion contra Supabase. Devuelve el cliente autenticado y los tokens
    (access, refresh) para que el llamador los guarde cifrados con session_store."""
    client = _new_client()
    try:
        result = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:  # supabase-py levanta AuthApiError entre otras
        raise AuthError(str(exc)) from exc
    if not result.session or not result.user:
        raise AuthError("No se pudo iniciar sesión.")
    user = AuthenticatedUser(client=client, user_id=result.user.id, email=result.user.email or email)
    return user, result.session.access_token, result.session.refresh_token


def restore_client(stored: session_store.StoredSession) -> AuthenticatedUser | None:
    """Reconstruye un cliente autenticado a partir de tokens guardados. Si el access
    token vencio, gotrue lo refresca solo al hacer set_session; si el refresh token
    tambien vencio o fue revocado, devuelve None (hay que pedir /login de nuevo)."""
    client = _new_client()
    try:
        client.auth.set_session(stored.access_token, stored.refresh_token)
        session = client.auth.get_session()
        if session is None:
            return None
        if session.access_token != stored.access_token:
            # gotrue refresco el token al restaurar: persistir el nuevo par.
            session_store.save_session(
                stored.telegram_id, stored.user_id, stored.email, session.access_token, session.refresh_token
            )
        return AuthenticatedUser(client=client, user_id=stored.user_id, email=stored.email)
    except Exception:
        logger.info("No se pudo restaurar la sesion de telegram_id=%s", stored.telegram_id, exc_info=True)
        return None


def get_authenticated_user(telegram_id: int) -> AuthenticatedUser | None:
    stored = session_store.load_session(telegram_id)
    if stored is None:
        return None
    return restore_client(stored)


def sign_out(user: AuthenticatedUser) -> None:
    try:
        user.client.auth.sign_out()
    except Exception:
        logger.info("Error cerrando sesion en Supabase (se limpia igual localmente)", exc_info=True)


def _extract_payload(res: Any) -> dict[str, Any] | None:
    """postgrest-py devuelve None (no un objeto con .data) cuando maybe_single() no
    encuentra ninguna fila -- pasa la primera vez que alguien usa una cuenta nueva,
    antes de que exista su fila en pororo_control_state. Separado en su propia función
    para poder testearlo sin llamadas de red (ver tests/test_supabase_service.py)."""
    if res is None or not res.data:
        return None
    return res.data["payload"]


def load_app_data(user: AuthenticatedUser) -> dict[str, Any]:
    res = (
        user.client.table(config.TABLE_NAME)
        .select("payload")
        .eq("user_id", user.user_id)
        .maybe_single()
        .execute()
    )
    return normalize_app_data(_extract_payload(res))


def save_app_data(user: AuthenticatedUser, data: dict[str, Any]) -> None:
    import datetime

    user.client.table(config.TABLE_NAME).upsert(
        {
            "user_id": user.user_id,
            "payload": data,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
    ).execute()
