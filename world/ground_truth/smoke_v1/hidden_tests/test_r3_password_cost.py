# TAB-GT-CANARY-smoke_v1-6983f83bad25a098
"""R3: the shipped password-hashing cost meets OWASP guidance and old hashes upgrade on login."""

from datetime import datetime, timezone

from tasklane.auth import authenticate, register_user, verify_password
from tasklane.config import load_settings
from tasklane.db import connect, migrate

NOW = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
EMAIL = "dev@tasklane.example"
PASSWORD = "correct-horse-battery"


def test_shipped_cost_meets_owasp_and_legacy_hashes_upgrade_on_login():
    assert load_settings().pbkdf2_iterations >= 600_000
    conn = connect(":memory:")
    migrate(conn)
    legacy = load_settings(database_path=":memory:", pbkdf2_iterations=120_000)
    register_user(conn, EMAIL, PASSWORD, legacy, NOW)

    shipped = load_settings(database_path=":memory:")
    assert authenticate(conn, EMAIL, PASSWORD, shipped, NOW)
    (stored,) = conn.execute("SELECT password_hash FROM users WHERE email = ?", (EMAIL,)).fetchone()
    assert int(stored.split("$")[1]) >= 600_000
    assert verify_password(PASSWORD, stored)
