"""Digest sending: once per user per month, only for eligible users."""
from datetime import datetime, timedelta

from tests.integration.conftest import PASSWORD  # noqa: F401


def test_send_month_digests_is_once_per_user(client, make_user, db, monkeypatch):
    import digest as digest_mod
    from models import User, Transaction, DigestLog

    _, email = make_user("digest@example.com")
    user = db.query(User).filter(User.email == email).first()

    # a transaction in the last closed month
    last_month = datetime.utcnow().replace(day=1) - timedelta(days=1)
    db.add(Transaction(user_id=user.id, plaid_transaction_id="dg1", name="Cafe",
                       amount=42.0, date=last_month, ml_category="FOOD_AND_DRINK"))
    db.commit()

    sent = []
    monkeypatch.setattr(digest_mod, "send_monthly_digest", lambda to, d: sent.append((to, d["total_spend"])))

    assert digest_mod.send_month_digests(db) == 1
    assert sent == [(email, 42.0)]
    assert db.query(DigestLog).count() == 1

    # second run: already logged → nothing sent
    assert digest_mod.send_month_digests(db) == 0
    assert len(sent) == 1


def test_digest_respects_opt_out(client, make_user, db, monkeypatch):
    import digest as digest_mod
    from models import User, Transaction

    _, email = make_user("optout@example.com")
    user = db.query(User).filter(User.email == email).first()
    user.digest_enabled = False
    last_month = datetime.utcnow().replace(day=1) - timedelta(days=1)
    db.add(Transaction(user_id=user.id, plaid_transaction_id="oo1", name="Cafe",
                       amount=10.0, date=last_month, ml_category="FOOD_AND_DRINK"))
    db.commit()

    sent = []
    monkeypatch.setattr(digest_mod, "send_monthly_digest", lambda to, d: sent.append(to))
    assert digest_mod.send_month_digests(db) == 0
    assert sent == []


def test_digest_skips_users_without_activity(client, make_user, db, monkeypatch):
    import digest as digest_mod
    make_user("quiet@example.com")  # verified but no transactions
    sent = []
    monkeypatch.setattr(digest_mod, "send_monthly_digest", lambda to, d: sent.append(to))
    assert digest_mod.send_month_digests(db) == 0
    assert sent == []
