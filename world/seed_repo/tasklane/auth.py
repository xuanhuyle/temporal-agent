"""Password hashing, registration, login and sessions.

Passwords are hashed with PBKDF2-HMAC-SHA256. The iteration count is a
setting (``pbkdf2_iterations``, see ADR-0002) and is embedded in every stored
hash, so verification always uses the cost the hash was created with. When the
configured cost differs from a user's stored hash, :func:`authenticate`
re-hashes the password on the next successful login.

Session tokens are random and returned to the client exactly once; the
database stores only their SHA-256 digest.
"""

import base64
import binascii
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta

from tasklane.config import Settings
from tasklane.db import format_timestamp, parse_timestamp

ALGORITHM = "pbkdf2_sha256"
MIN_PASSWORD_LENGTH = 8
SALT_BYTES = 16
SESSION_TOKEN_BYTES = 32

# Salt for the throwaway hash computed when a login names an unknown email.
_UNKNOWN_USER_SALT = bytes(SALT_BYTES)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    padded = text + "=" * (-len(text) % 4)
    return base64.b64decode(padded, altchars=b"-_", validate=True)


def _derive(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def _parse(encoded: str) -> tuple[int, bytes, bytes] | None:
    """Split an encoded hash into (iterations, salt, digest), or None if malformed."""
    if not isinstance(encoded, str):
        return None
    parts = encoded.split("$")
    if len(parts) != 4 or parts[0] != ALGORITHM:
        return None
    iterations_text, salt_text, digest_text = parts[1:]
    if not (iterations_text.isascii() and iterations_text.isdigit()):
        return None
    iterations = int(iterations_text)
    if iterations <= 0:
        return None
    try:
        salt = _b64decode(salt_text)
        digest = _b64decode(digest_text)
    except (binascii.Error, ValueError):
        return None
    if not salt or not digest:
        return None
    return iterations, salt, digest


def hash_password(password: str, iterations: int, salt: bytes | None = None) -> str:
    """Hash ``password`` as ``pbkdf2_sha256$<iterations>$<salt>$<digest>``.

    Salt and digest are URL-safe base64 without padding. A random 16-byte salt
    is generated when ``salt`` is not given.
    """
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations <= 0:
        raise ValueError(f"iterations must be a positive integer, got {iterations!r}")
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTES)
    digest = _derive(password, salt, iterations)
    return f"{ALGORITHM}${iterations}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    """Check ``password`` against a stored hash; malformed hashes never match."""
    parsed = _parse(encoded)
    if parsed is None:
        return False
    iterations, salt, expected = parsed
    return hmac.compare_digest(_derive(password, salt, iterations), expected)


def needs_rehash(encoded: str, iterations: int) -> bool:
    """True if the stored hash was not produced with the configured cost."""
    parsed = _parse(encoded)
    return parsed is None or parsed[0] != iterations


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_email(email: str) -> None:
    local, sep, domain = email.partition("@")
    if not sep or not local or not domain or "@" in domain or any(c.isspace() for c in email):
        raise ValueError(f"invalid email address: {email!r}")


def register_user(
    conn: sqlite3.Connection,
    email: str,
    password: str,
    settings: Settings,
    now: datetime,
) -> int:
    """Create a user and return its id.

    Raises:
        ValueError: invalid email, password shorter than
            :data:`MIN_PASSWORD_LENGTH`, or email already registered.
    """
    email = normalize_email(email)
    _validate_email(email)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")

    password_hash = hash_password(password, settings.pbkdf2_iterations)
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, password_hash, format_timestamp(now)),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"email already registered: {email}") from exc
    return int(cursor.lastrowid)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate(
    conn: sqlite3.Connection,
    email: str,
    password: str,
    settings: Settings,
    now: datetime,
) -> str | None:
    """Log a user in and return a new session token, or None on bad credentials.

    If the stored hash uses a different iteration count than
    ``settings.pbkdf2_iterations``, it is replaced with a fresh hash at the
    configured cost (no data migration is needed to change the cost).
    An unknown email costs the same hashing work as a wrong password, so
    response times do not reveal which emails are registered.
    """
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE email = ?",
        (normalize_email(email),),
    ).fetchone()
    if row is None:
        hash_password(password, settings.pbkdf2_iterations, _UNKNOWN_USER_SALT)
        return None
    if not verify_password(password, row["password_hash"]):
        return None

    user_id = int(row["id"])
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    expires_at = now + timedelta(hours=settings.session_ttl_hours)
    with conn:
        if needs_rehash(row["password_hash"], settings.pbkdf2_iterations):
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(password, settings.pbkdf2_iterations), user_id),
            )
        conn.execute(
            "INSERT INTO sessions (token_sha256, user_id, created_at, expires_at)"
            " VALUES (?, ?, ?, ?)",
            (_token_digest(token), user_id, format_timestamp(now), format_timestamp(expires_at)),
        )
    return token


def get_user_id_for_session(conn: sqlite3.Connection, token: str, now: datetime) -> int | None:
    """Return the user id for a live session token, or None if unknown or expired."""
    row = conn.execute(
        "SELECT user_id, expires_at FROM sessions WHERE token_sha256 = ?",
        (_token_digest(token),),
    ).fetchone()
    if row is None or parse_timestamp(row["expires_at"]) <= now:
        return None
    return int(row["user_id"])


def revoke_session(conn: sqlite3.Connection, token: str) -> None:
    """Delete a session (logout). Unknown tokens are ignored."""
    with conn:
        conn.execute("DELETE FROM sessions WHERE token_sha256 = ?", (_token_digest(token),))
