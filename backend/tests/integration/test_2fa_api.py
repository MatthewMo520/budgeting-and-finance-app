"""Both 2FA methods end-to-end: TOTP and emailed codes."""
import pyotp

from tests.integration.conftest import PASSWORD


def test_totp_setup_login_and_relock(client, make_user, auth_headers):
    token, email = make_user("totp@example.com")
    H = auth_headers(token)

    r = client.post("/auth/setup-totp", headers=H)
    assert r.status_code == 200
    secret = r.json()["secret"]

    r = client.post("/auth/confirm-totp", headers=H, json={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200

    # Re-setup must be blocked while enabled (stolen token can't swap the secret)
    assert client.post("/auth/setup-totp", headers=H).status_code == 403

    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["totp_required"] is True and "totp" in body["methods"]

    r = client.post("/auth/verify-totp-login",
                    json={"challenge_token": body["challenge_token"], "code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200 and "access_token" in r.json()


def test_totp_login_rejects_bad_code(client, make_user, auth_headers):
    token, email = make_user("totp2@example.com")
    H = auth_headers(token)
    secret = client.post("/auth/setup-totp", headers=H).json()["secret"]
    client.post("/auth/confirm-totp", headers=H, json={"code": pyotp.TOTP(secret).now()})
    challenge = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()["challenge_token"]
    r = client.post("/auth/verify-totp-login", json={"challenge_token": challenge, "code": "000000"})
    assert r.status_code == 401


def test_email_otp_setup_and_login(client, make_user, sent, auth_headers):
    token, email = make_user("otp@example.com")
    H = auth_headers(token)

    assert client.post("/auth/setup-email-otp", headers=H).status_code == 200
    r = client.post("/auth/confirm-email-otp", headers=H, json={"code": sent["otp"]})
    assert r.status_code == 200

    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    body = r.json()
    assert body["totp_required"] is True and body["methods"] == ["email"]

    assert client.post("/auth/send-login-otp", json={"challenge_token": body["challenge_token"]}).status_code == 200
    r = client.post("/auth/verify-email-otp-login",
                    json={"challenge_token": body["challenge_token"], "code": sent["otp"]})
    assert r.status_code == 200 and "access_token" in r.json()


def test_email_otp_attempt_cap(client, make_user, sent, auth_headers):
    token, email = make_user("otpcap@example.com")
    H = auth_headers(token)
    client.post("/auth/setup-email-otp", headers=H)
    client.post("/auth/confirm-email-otp", headers=H, json={"code": sent["otp"]})

    body = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()
    challenge = body["challenge_token"]
    client.post("/auth/send-login-otp", json={"challenge_token": challenge})

    wrong = "000000" if sent["otp"] != "000000" else "111111"
    for _ in range(5):
        r = client.post("/auth/verify-email-otp-login", json={"challenge_token": challenge, "code": wrong})
        assert r.status_code == 401
    # 6th attempt hits the cap even with the right code
    r = client.post("/auth/verify-email-otp-login", json={"challenge_token": challenge, "code": sent["otp"]})
    assert r.status_code == 429


def test_disable_email_otp_requires_password(client, make_user, sent, auth_headers):
    token, _ = make_user("otpoff@example.com")
    H = auth_headers(token)
    client.post("/auth/setup-email-otp", headers=H)
    client.post("/auth/confirm-email-otp", headers=H, json={"code": sent["otp"]})

    r = client.request("DELETE", "/auth/disable-email-otp", headers=H, json={"password": "wrong"})
    assert r.status_code == 401
    r = client.request("DELETE", "/auth/disable-email-otp", headers=H, json={"password": PASSWORD})
    assert r.status_code == 200
