from bot import config, session_store


def test_save_and_load_session_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BOT_DB_PATH", str(tmp_path / "sessions.db"))

    session_store.save_session(1, "user-uuid", "a@b.com", "access-token", "refresh-token")
    loaded = session_store.load_session(1)

    assert loaded is not None
    assert loaded.user_id == "user-uuid"
    assert loaded.email == "a@b.com"
    assert loaded.access_token == "access-token"
    assert loaded.refresh_token == "refresh-token"


def test_load_session_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BOT_DB_PATH", str(tmp_path / "sessions.db"))
    assert session_store.load_session(999) is None


def test_clear_session_removes_it(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BOT_DB_PATH", str(tmp_path / "sessions.db"))
    session_store.save_session(2, "u2", "b@c.com", "at", "rt")
    session_store.clear_session(2)
    assert session_store.load_session(2) is None


def test_login_lockout_after_max_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BOT_DB_PATH", str(tmp_path / "sessions.db"))
    for _ in range(config.MAX_LOGIN_ATTEMPTS):
        session_store.register_failed_login(3)
    assert session_store.seconds_locked_out(3) > 0


def test_clear_failed_logins_lifts_lockout(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BOT_DB_PATH", str(tmp_path / "sessions.db"))
    for _ in range(config.MAX_LOGIN_ATTEMPTS):
        session_store.register_failed_login(4)
    session_store.clear_failed_logins(4)
    assert session_store.seconds_locked_out(4) == 0


def test_daily_digest_toggle(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BOT_DB_PATH", str(tmp_path / "sessions.db"))
    session_store.set_daily_digest(5, True)
    assert 5 in session_store.list_daily_digest_subscribers()
    session_store.set_daily_digest(5, False)
    assert 5 not in session_store.list_daily_digest_subscribers()
