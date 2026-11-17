import pytest
from app import create_app
from app.extensions import db
from app.keycache import key_cache

PW = "oldpassword1"
NEW = "newpassword2"


@pytest.fixture
def client(monkeypatch):
    from config import Config

    monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    monkeypatch.setattr(Config, "JWT_SECRET_KEY", "test-secret-key-test-secret-key-32")
    monkeypatch.setattr(Config, "SECRET_KEY", "x")
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()
    key_cache.clear()


def signup(client, email="a@b.com"):
    r = client.post(
        "/auth/signup",
        json={"first_name": "A", "last_name": "B", "email": email, "password": PW},
    )
    assert r.status_code == 201
    return r.get_json()["recovery_key"]


def login(client, pw=PW, email="a@b.com"):
    return client.post("/auth/login", json={"email": email, "password": pw})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---- change password ----
def test_change_password_success(client):
    signup(client)
    token = login(client).get_json()["access_token"]
    r = client.post(
        "/auth/change-password",
        json={"old_password": PW, "new_password": NEW},
        headers=auth(token),
    )
    assert r.status_code == 200
    assert login(client, PW).status_code == 401
    assert login(client, NEW).status_code == 200


def test_change_password_wrong_old(client):
    signup(client)
    token = login(client).get_json()["access_token"]
    r = client.post(
        "/auth/change-password",
        json={"old_password": "wrong-pass", "new_password": NEW},
        headers=auth(token),
    )
    assert r.status_code == 400
    assert login(client, PW).status_code == 200


def test_change_password_too_short(client):
    signup(client)
    token = login(client).get_json()["access_token"]
    r = client.post(
        "/auth/change-password",
        json={"old_password": PW, "new_password": "short"},
        headers=auth(token),
    )
    assert r.status_code == 400


def test_change_password_requires_auth(client):
    r = client.post(
        "/auth/change-password", json={"old_password": PW, "new_password": NEW}
    )
    assert r.status_code == 401


def test_change_password_preserves_data_key(client):
    signup(client)
    token = login(client).get_json()["access_token"]
    from app.crypto import decrypt, derive_kek
    from app.models import User

    user = db.session.execute(db.select(User)).scalar_one()
    before = decrypt(derive_kek(PW, user.kdf_salt), user.wrapped_key)
    client.post(
        "/auth/change-password",
        json={"old_password": PW, "new_password": NEW},
        headers=auth(token),
    )
    db.session.refresh(user)
    after = decrypt(derive_kek(NEW, user.kdf_salt), user.wrapped_key)
    assert before == after


# ---- recovery ----
def test_recover_success(client):
    key = signup(client)
    r = client.post(
        "/auth/recover",
        json={"email": "a@b.com", "recovery_key": key, "new_password": NEW},
    )
    assert r.status_code == 200
    assert login(client, PW).status_code == 401
    assert login(client, NEW).status_code == 200


def test_recover_key_format_tolerant(client):
    key = signup(client)
    messy = key.lower().replace("-", " ")
    r = client.post(
        "/auth/recover",
        json={"email": "A@B.com", "recovery_key": messy, "new_password": NEW},
    )
    assert r.status_code == 200


def test_recover_preserves_data_key(client):
    key = signup(client)
    from app.crypto import decrypt, derive_kek
    from app.models import User

    user = db.session.execute(db.select(User)).scalar_one()
    before = decrypt(derive_kek(PW, user.kdf_salt), user.wrapped_key)
    client.post(
        "/auth/recover",
        json={"email": "a@b.com", "recovery_key": key, "new_password": NEW},
    )
    db.session.refresh(user)
    assert decrypt(derive_kek(NEW, user.kdf_salt), user.wrapped_key) == before


def test_recover_wrong_key(client):
    signup(client)
    other = signup(client, "c@d.com")
    r = client.post(
        "/auth/recover",
        json={"email": "a@b.com", "recovery_key": other, "new_password": NEW},
    )
    assert r.status_code == 400
    assert login(client, PW).status_code == 200


def test_recover_garbage_key(client):
    signup(client)
    r = client.post(
        "/auth/recover",
        json={"email": "a@b.com", "recovery_key": "!!!notbase32", "new_password": NEW},
    )
    assert r.status_code == 400


def test_recover_unknown_email(client):
    key = signup(client)
    r = client.post(
        "/auth/recover",
        json={"email": "nobody@x.com", "recovery_key": key, "new_password": NEW},
    )
    assert r.status_code == 400


def test_recover_short_password(client):
    key = signup(client)
    r = client.post(
        "/auth/recover",
        json={"email": "a@b.com", "recovery_key": key, "new_password": "short"},
    )
    assert r.status_code == 400
