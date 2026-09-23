from __future__ import annotations

import sys

from cryptography.fernet import Fernet, InvalidToken

from . import config

try:
    _fernet = Fernet(config.BOT_ENCRYPTION_KEY.encode())
except Exception as exc:  # clave con formato invalido
    print(
        "BOT_ENCRYPTION_KEY invalida. Generá una nueva con:\n"
        '  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"\n'
        f"Detalle: {exc}",
        file=sys.stderr,
    )
    sys.exit(1)


def encrypt(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        return None
