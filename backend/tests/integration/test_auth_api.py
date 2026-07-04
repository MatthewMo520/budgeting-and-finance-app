"""Auth lifecycle: register → verify → login → me, password flows, revocation."""
from datetime import datetime, timedelta

from tests.integration.conftest import PASSWORD


def test_register_is_generic_for_new_and_duplicate(client, sent):
    r1 = client.post("/auth/register", json={"email": "a@example.com", "password": PASSWORD})
    r2 = client.post("/auth/register", json={"email": "a@example.com", "password": PASSWORD})
    assert r1.status_code == r2.status_code == 201
    assert r1.json() == r2.json()  # no user enumeration


def test_register_rejects_weak_password(client):
    r = client.post("/auth/register", json={"email": "b@example.com", "password": "password"})
    assert r.status_code == 422
    assert "weak" in r.json()["detail"].lower()


def test_login_blocked_until_verified(client, sent):
    client.post("/auth/register", json={"email": "c@example.com", "password": PASSWORD})
    r = client.post("/auth/login", json={"email": "c@example.com", "password": PASSWORD})
    assert r.status_code == 403
    assert "verify" in r.json()["detail"].lower()


def test_verify_email_rejects_bad_token(client):
    r = client.post("/auth/verify-email", json={"token": "not-a-real-token"})
    assert r.status_code == 400


def test_verify_email_rejects_expired_token(client, sent, db):
    from models import User
    client.post("/auth/register", json={"email": "d@example.com", "password": PASSWORD})
    user = db.query(User).filter(User.email == "d@example.com").first()
    user.verification_token_expires = datetime.utcnow() - timedelta(hours=1)
    db.commit()
    r = client.post("/auth/verify-email", json={"token": sent["vtoken"]})
    assert r.status_code == 400


def test_full_lifecycle_reaches_me(client, make_user, auth_headers):
    token, email = make_user("e@example.com")
    r = client.get("/auth/me", headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == email
    assert body["totp_enabled"] is False and body["email_otp_enabled"] is False


def test_wrong_password_is_401(client, make_user):
    make_user("f@example.com")
    r = client.post("/auth/login", json={"email": "f@example.com", "password": "Wrong-passw0rd!"})
    assert r.status_code == 401


def test_change_password_revokes_old_tokens(client, make_user, auth_headers):
    old_token, _ = make_user("g@example.com")
    r = client.post("/auth/change-password", headers=auth_headers(old_token),
                    json={"current_password": PASSWORD, "new_password": "An0ther-good-pw!77"})
    assert r.status_code == 200
    new_token = r.json()["access_token"]
    # token_version rotated: the old access token no longer works, the new one does
    assert client.get("/auth/me", headers=auth_headers(old_token)).status_code == 401
    assert client.get("/auth/me", headers=auth_headers(new_token)).status_code == 200


def test_refresh_cookie_mints_access_token(client, make_user, auth_headers):
    make_user("h@example.com")  # login set the httpOnly refresh cookie on this client
    r = client.post("/auth/refresh")
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert client.get("/auth/me", headers=auth_headers(token)).status_code == 200


def test_logout_clears_refresh_cookie(client, make_user):
    make_user("i@example.com")
    client.post("/auth/logout")
    assert client.post("/auth/refresh").status_code == 401


def test_password_reset_flow(client, make_user, sent, auth_headers):
    _, email = make_user("j@example.com")
    client.post("/auth/forgot-password", json={"email": email})
    rtoken = sent["rtoken"]
    # weak replacement rejected
    assert client.post("/auth/reset-password", json={"token": rtoken, "password": "abc"}).status_code == 422
    r = client.post("/auth/reset-password", json={"token": rtoken, "password": "Fresh-new-passw0rd!9"})
    assert r.status_code == 200
    assert client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": "Fresh-new-passw0rd!9"}).status_code == 200
