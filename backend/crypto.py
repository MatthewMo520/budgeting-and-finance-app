"""Transparent at-rest encryption for sensitive columns (Plaid access tokens).

Set PLAID_TOKEN_ENC_KEY to a Fernet key to enable encryption:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

If the key is unset (e.g. local dev), values are stored as plaintext so the app
still runs. Reads transparently handle both encrypted and legacy-plaintext rows,
so turning encryption on does not require a data migration.
"""
import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator

_key = os.getenv("PLAID_TOKEN_ENC_KEY")
_fernet = Fernet(_key.encode()) if _key else None

if _fernet is None:
    print("WARNING: PLAID_TOKEN_ENC_KEY not set — Plaid access tokens stored in plaintext.")


class EncryptedString(TypeDecorator):
    """A String column that is encrypted at rest when a key is configured."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or _fernet is None:
            return value
        return _fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None or _fernet is None:
            return value
        try:
            return _fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            # Legacy plaintext row written before encryption was enabled.
            return value
