from jose import jwt

from auth import (
    ALGORITHM, SECRET_KEY,
    hash_token, hash_password, verify_password,
    create_access_token, create_refresh_token, generate_otp_code,
)


def test_hash_token_is_deterministic_sha256():
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
    assert len(hash_token("abc")) == 64  # sha256 hex


def test_password_hash_roundtrip():
    h = hash_password("S3cret!passphrase")
    assert verify_password("S3cret!passphrase", h)
    assert not verify_password("wrong-password", h)
    assert h != "S3cret!passphrase"  # never stored in plaintext


def test_access_token_carries_claims():
    tok = create_access_token("user-1", token_version=5)
    claims = jwt.decode(tok, SECRET_KEY, algorithms=[ALGORITHM])
    assert claims["sub"] == "user-1"
    assert claims["tv"] == 5
    assert claims["type"] == "access"


def test_refresh_token_type_and_version():
    tok = create_refresh_token("user-2", token_version=3)
    claims = jwt.decode(tok, SECRET_KEY, algorithms=[ALGORITHM])
    assert claims["type"] == "refresh"
    assert claims["tv"] == 3


def test_otp_code_is_six_digits():
    for _ in range(50):
        code = generate_otp_code()
        assert len(code) == 6
        assert code.isdigit()  # leading zeros preserved


def test_otp_code_hashes_like_other_tokens():
    code = generate_otp_code()
    assert hash_token(code) == hash_token(code)
    assert hash_token(code) != code  # never stored in plaintext
