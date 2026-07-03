"""
SQLite-at-rest encryption support for DocTel.

When ``settings.security.encrypt_sqlite`` is ``True`` the application
decrypts the database file on startup and re-encrypts it on graceful
shutdown using Fernet (symmetric AES-128-CBC with HMAC-SHA256 via the
``cryptography`` library).

The encryption key is derived with PBKDF2-HMAC-SHA256 from:
  1. The ``DOCINTEL_ENCRYPTION_KEY`` environment variable (preferred), OR
     the machine's ``COMPUTERNAME`` + ``USERNAME`` as a fallback.
  2. A random 16-byte salt persisted to ``{base_dir}/.db_salt``.

On the very first run the database is stored unencrypted and is encrypted
only when the application shuts down.  On subsequent starts the encrypted
file is transparently decrypted before SQLAlchemy opens it.
"""

import os
import hashlib
import base64
import logging
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_SALT_FILENAME = ".db_salt"
_FERNET_PREFIX = b"gAAAAA"  # all Fernet tokens start with this base64 prefix


# ── Key derivation ────────────────────────────────────────────────────────────


def _get_machine_secret() -> str:
    """Return a stable, machine-scoped secret for key derivation."""
    env_key = os.getenv("DOCINTEL_ENCRYPTION_KEY", "").strip()
    if env_key:
        return env_key
    comp = os.getenv("COMPUTERNAME", "UNKNOWN")
    user = os.getenv("USERNAME", "UNKNOWN")
    return f"{comp}:{user}"


def _get_salt_path(base_dir: str) -> Path:
    return Path(base_dir) / _SALT_FILENAME


def _ensure_salt(base_dir: str) -> bytes:
    """Load an existing salt file or create a new one."""
    salt_path = _get_salt_path(base_dir)
    if salt_path.exists():
        return salt_path.read_bytes()
    salt = os.urandom(16)
    salt_path.parent.mkdir(parents=True, exist_ok=True)
    salt_path.write_bytes(salt)
    logger.info("Created new encryption salt at %s", salt_path)
    return salt


def _derive_key(secret: str, salt: bytes) -> bytes:
    """Derive a 32-byte url-safe-base64 Fernet key via PBKDF2."""
    raw = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, 100_000, dklen=32)
    return base64.urlsafe_b64encode(raw)


def _get_fernet(base_dir: str) -> Fernet:
    """Build a Fernet instance from the derived key."""
    secret = _get_machine_secret()
    salt = _ensure_salt(base_dir)
    key = _derive_key(secret, salt)
    return Fernet(key)


# ── Public API ────────────────────────────────────────────────────────────────


def is_encrypted(db_path: str) -> bool:
    """Check whether the database file looks like a Fernet-encrypted blob."""
    db_file = Path(db_path)
    if not db_file.exists():
        return False
    try:
        head = db_file.open("rb").read(len(_FERNET_PREFIX))
        return head.startswith(_FERNET_PREFIX)
    except OSError:
        return False


def decrypt_database(db_path: str, base_dir: str) -> bool:
    """Decrypt the SQLite database file **in-place**.

    If the file is not encrypted or does not exist this is a no-op.
    Returns ``True`` on success (or when no decryption was needed).
    """
    db_file = Path(db_path)
    if not db_file.exists():
        return True
    if not is_encrypted(db_path):
        return True  # already plaintext

    try:
        fernet = _get_fernet(base_dir)
        ciphertext = db_file.read_bytes()
        plaintext = fernet.decrypt(ciphertext)
        db_file.write_bytes(plaintext)
        logger.info("Decrypted database at %s", db_path)
        return True
    except InvalidToken:
        logger.error("Encryption key mismatch – cannot decrypt database %s", db_path)
        return False
    except Exception as exc:
        logger.error("Failed to decrypt database %s: %s", db_path, exc)
        return False


def encrypt_database(db_path: str, base_dir: str) -> bool:
    """Encrypt the SQLite database file **in-place**.

    If the file is already encrypted or does not exist this is a no-op.
    Returns ``True`` on success.
    """
    db_file = Path(db_path)
    if not db_file.exists():
        return True
    if is_encrypted(db_path):
        return True  # already encrypted

    try:
        fernet = _get_fernet(base_dir)
        plaintext = db_file.read_bytes()
        ciphertext = fernet.encrypt(plaintext)
        db_file.write_bytes(ciphertext)
        logger.info("Encrypted database at %s", db_path)
        return True
    except Exception as exc:
        logger.error("Failed to encrypt database %s: %s", db_path, exc)
        return False
