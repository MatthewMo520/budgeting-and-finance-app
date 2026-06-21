"""Verify Plaid webhooks.

Plaid signs each webhook with a JWT in the `Plaid-Verification` header (ES256).
We fetch the matching public key by `kid`, verify the signature, check the JWT
is recent, and confirm the body hash matches — so an attacker can't forge
webhooks that trigger syncs.

If PLAID_WEBHOOK_URL is unset (local dev, no real webhooks), verification is
skipped so the endpoint can still be exercised manually.
"""
import hashlib
import hmac
import os
import time

from jose import jwt

import plaid_client as pc

_key_cache = {}


def _get_verification_key(kid: str, environment: str):
    if kid in _key_cache:
        return _key_cache[kid]
    from plaid.model.webhook_verification_key_get_request import WebhookVerificationKeyGetRequest
    resp = pc._client_for(environment).webhook_verification_key_get(
        WebhookVerificationKeyGetRequest(key_id=kid)
    )
    key = resp.key.to_dict()
    _key_cache[kid] = key
    return key


def verify_webhook(signed_jwt: str, body_bytes: bytes, environment: str) -> bool:
    # Dev: no webhook configured → don't block manual testing.
    if not os.getenv("PLAID_WEBHOOK_URL"):
        return True
    if not signed_jwt:
        return False
    try:
        header = jwt.get_unverified_header(signed_jwt)
        if header.get("alg") != "ES256":
            return False
        key = _get_verification_key(header["kid"], environment)
        claims = jwt.decode(signed_jwt, key, algorithms=["ES256"])
    except Exception:
        return False

    # Reject stale tokens (>5 min old).
    if time.time() - int(claims.get("iat", 0)) > 300:
        return False

    expected = claims.get("request_body_sha256") or ""
    actual = hashlib.sha256(body_bytes).hexdigest()
    return hmac.compare_digest(expected, actual)
