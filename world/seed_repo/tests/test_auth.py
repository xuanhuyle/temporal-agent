import hashlib
from datetime import timedelta

import pytest

from tasklane import auth
from tasklane.auth import (
    ALGORITHM,
    MIN_PASSWORD_LENGTH,
    authenticate,
    get_user_id_for_session,
    hash_password,
    needs_rehash,
    register_user,
    revoke_session,
    verify_password,
)
from tasklane.config import load_settings

PASSWORD = "correct horse battery"


def stored_hash(conn, user_id):
    return conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()[0]


# -- hashing ---------------------------------------------------------------


def test_hash_format():
    encoded = hash_password(PASSWORD, 1_000)
    algorithm, iterations, salt, digest = encoded.split("$")
    assert algorithm == ALGORITHM == "pbkdf2_sha256"
    assert iterations == "1000"
    assert salt and digest
    assert "=" not in salt + digest


def test_hash_verify_roundtrip():
    encoded = hash_password(PASSWORD, 1_500)
    assert verify_password(PASSWORD, encoded)  # cost is read from the encoded hash
    assert not verify_password("wrong password", encoded)


def test_explicit_salt_is_deterministic_and_random_salt_is_not():
    salt = bytes(range(16))
    assert hash_password(PASSWORD, 1_000, salt) == hash_password(PASSWORD, 1_000, salt)
    assert hash_password(PASSWORD, 1_000) != hash_password(PASSWORD, 1_000)


@pytest.mark.parametrize(
    "encoded",
    [
        "",
        "not-a-hash",
        "md5$1000$c2FsdA$ZGlnZXN0",
        "pbkdf2_sha256$abc$c2FsdA$ZGlnZXN0",
        "pbkdf2_sha256$0$c2FsdA$ZGlnZXN0",
        "pbkdf2_sha256$-5$c2FsdA$ZGlnZXN0",
        "pbkdf2_sha256$\u00b2$c2FsdA$ZGlnZXN0",
        "pbkdf2_sha256$1000$c2FsdA",
        "pbkdf2_sha256$1000$$ZGlnZXN0",
        "pbkdf2_sha256$1000$c2F*sdA$ZGlnZXN0",
        "pbkdf2_sha256$1000$c2FsdA$ZGlnZXN0$extra",
    ],
)
def test_malformed_hash_never_verifies(encoded):
    assert verify_password(PASSWORD, encoded) is False


def test_hash_rejects_invalid_iterations():
    with pytest.raises(ValueError):
        hash_password(PASSWORD, 0)
    with pytest.raises(ValueError):
        hash_password(PASSWORD, True)


def test_needs_rehash():
    encoded = hash_password(PASSWORD, 1_000)
    assert not needs_rehash(encoded, 1_000)
    assert needs_rehash(encoded, 2_000)
    assert needs_rehash("garbage", 1_000)


# -- registration ----------------------------------------------------------


def test_register_normalizes_email(conn, settings, now):
    user_id = register_user(conn, "  Ada@Example.COM ", PASSWORD, settings, now)
    row = conn.execute("SELECT email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    assert row["email"] == "ada@example.com"
    assert row["created_at"] == "2026-01-05T12:00:00+00:00"
    assert verify_password(PASSWORD, stored_hash(conn, user_id))
    assert f"${settings.pbkdf2_iterations}$" in stored_hash(conn, user_id)


@pytest.mark.parametrize(
    "email", ["", "ada.example.com", "@example.com", "ada@", "a@b@c.com", "ada @example.com"]
)
def test_register_rejects_invalid_email(conn, settings, now, email):
    with pytest.raises(ValueError, match="email"):
        register_user(conn, email, PASSWORD, settings, now)


def test_register_rejects_short_password(conn, settings, now):
    with pytest.raises(ValueError, match="password"):
        register_user(conn, "ada@example.com", "x" * (MIN_PASSWORD_LENGTH - 1), settings, now)
    assert register_user(conn, "ada@example.com", "x" * MIN_PASSWORD_LENGTH, settings, now)


def test_register_rejects_duplicate_email(conn, settings, now):
    register_user(conn, "ada@example.com", PASSWORD, settings, now)
    with pytest.raises(ValueError, match="already registered"):
        register_user(conn, "ADA@example.com", PASSWORD, settings, now)
    (count,) = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    assert count == 1


# -- login and sessions ----------------------------------------------------


def test_authenticate_creates_session(conn, settings, now):
    user_id = register_user(conn, "ada@example.com", PASSWORD, settings, now)
    token = authenticate(conn, "Ada@Example.com", PASSWORD, settings, now)
    assert token
    assert get_user_id_for_session(conn, token, now) == user_id

    row = conn.execute("SELECT * FROM sessions").fetchone()
    assert row["token_sha256"] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in {row["token_sha256"], row["created_at"], row["expires_at"]}
    assert row["expires_at"] == "2026-01-19T12:00:00+00:00"  # 336 hours later


def test_authenticate_rejects_bad_credentials(conn, settings, now):
    register_user(conn, "ada@example.com", PASSWORD, settings, now)
    assert authenticate(conn, "ada@example.com", "wrong password", settings, now) is None
    assert authenticate(conn, "bob@example.com", PASSWORD, settings, now) is None
    (count,) = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
    assert count == 0


def test_unknown_email_costs_a_full_hash(conn, settings, now, monkeypatch):
    iterations_used = []
    real_derive = auth._derive

    def recording_derive(password, salt, iterations):
        iterations_used.append(iterations)
        return real_derive(password, salt, iterations)

    monkeypatch.setattr(auth, "_derive", recording_derive)
    assert authenticate(conn, "nobody@example.com", PASSWORD, settings, now) is None
    assert iterations_used == [settings.pbkdf2_iterations]


def test_login_upgrades_hash_when_cost_changes(conn, settings, now):
    user_id = register_user(conn, "ada@example.com", PASSWORD, settings, now)
    original = stored_hash(conn, user_id)
    assert "$1000$" in original

    stronger = load_settings(pbkdf2_iterations=2_000, database_path=":memory:")
    assert authenticate(conn, "ada@example.com", PASSWORD, stronger, now)

    upgraded = stored_hash(conn, user_id)
    assert upgraded != original
    assert "$2000$" in upgraded
    assert not needs_rehash(upgraded, 2_000)
    assert verify_password(PASSWORD, upgraded)
    # The upgraded hash still works with the old settings object.
    assert authenticate(conn, "ada@example.com", PASSWORD, settings, now)


def test_login_keeps_hash_when_cost_unchanged(conn, settings, now):
    user_id = register_user(conn, "ada@example.com", PASSWORD, settings, now)
    original = stored_hash(conn, user_id)
    assert authenticate(conn, "ada@example.com", PASSWORD, settings, now)
    assert stored_hash(conn, user_id) == original


def test_failed_login_does_not_rehash(conn, settings, now):
    user_id = register_user(conn, "ada@example.com", PASSWORD, settings, now)
    original = stored_hash(conn, user_id)
    stronger = load_settings(pbkdf2_iterations=2_000, database_path=":memory:")
    assert authenticate(conn, "ada@example.com", "wrong password", stronger, now) is None
    assert stored_hash(conn, user_id) == original


def test_session_expires_after_ttl(conn, settings, now):
    user_id = register_user(conn, "ada@example.com", PASSWORD, settings, now)
    token = authenticate(conn, "ada@example.com", PASSWORD, settings, now)
    ttl = timedelta(hours=settings.session_ttl_hours)
    assert get_user_id_for_session(conn, token, now + ttl - timedelta(seconds=1)) == user_id
    assert get_user_id_for_session(conn, token, now + ttl) is None
    assert get_user_id_for_session(conn, "no-such-token", now) is None


def test_revoke_session(conn, settings, now):
    register_user(conn, "ada@example.com", PASSWORD, settings, now)
    first = authenticate(conn, "ada@example.com", PASSWORD, settings, now)
    second = authenticate(conn, "ada@example.com", PASSWORD, settings, now)
    assert first != second

    revoke_session(conn, first)
    assert get_user_id_for_session(conn, first, now) is None
    assert get_user_id_for_session(conn, second, now) is not None
    revoke_session(conn, first)  # revoking twice is harmless

