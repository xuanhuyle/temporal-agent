import json

import pytest

from tasklane.config import DEFAULT_SETTINGS_PATH, Settings, load_settings


def write_settings(tmp_path, **changes):
    data = json.loads(DEFAULT_SETTINGS_PATH.read_text(encoding="utf-8"))
    data.update(changes)
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def test_shipped_settings_load():
    settings = load_settings()
    assert isinstance(settings, Settings)
    assert settings.pbkdf2_iterations >= 100_000  # never ship a toy hashing cost
    assert settings.session_ttl_hours == 336
    assert settings.reconcile_interval_minutes == 15
    assert settings.checkout_grace_minutes == 30
    assert settings.database_path == "var/tasklane.sqlite3"
    assert settings.paygate_api_base == "https://api.paygate.example/v1"


def test_overrides_replace_file_values():
    settings = load_settings(pbkdf2_iterations=1_000, database_path=":memory:")
    assert settings.pbkdf2_iterations == 1_000
    assert settings.database_path == ":memory:"
    assert settings.session_ttl_hours == 336


def test_loads_explicit_path(tmp_path):
    path, _ = write_settings(tmp_path, session_ttl_hours=24)
    assert load_settings(path).session_ttl_hours == 24
    assert load_settings(str(path)).session_ttl_hours == 24


def test_unknown_override_rejected():
    with pytest.raises(ValueError, match="unknown setting"):
        load_settings(pbkdf2_rounds=10)


def test_unknown_key_in_file_rejected(tmp_path):
    path, _ = write_settings(tmp_path, feature_flags={})
    with pytest.raises(ValueError, match="feature_flags"):
        load_settings(path)


def test_missing_key_rejected(tmp_path):
    _, data = write_settings(tmp_path)
    del data["checkout_grace_minutes"]
    path = tmp_path / "partial.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="checkout_grace_minutes"):
        load_settings(path)


def test_non_object_file_rejected(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(path)


@pytest.mark.parametrize(
    "key, value",
    [
        ("pbkdf2_iterations", True),
        ("pbkdf2_iterations", 0),
        ("session_ttl_hours", -1),
        ("reconcile_interval_minutes", "15"),
        ("checkout_grace_minutes", 1.5),
        ("database_path", ""),
        ("paygate_api_base", 42),
    ],
)
def test_invalid_values_rejected(key, value):
    with pytest.raises(ValueError, match=key):
        load_settings(**{key: value})


def test_settings_are_immutable():
    settings = load_settings()
    with pytest.raises(AttributeError):
        settings.pbkdf2_iterations = 1  # type: ignore[misc]
