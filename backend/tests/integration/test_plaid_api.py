"""Plaid sync engine (mocked Plaid client) + account deletion revocation."""
from datetime import date, datetime

from tests.integration.conftest import PASSWORD


class FakePlaidTxn:
    def __init__(self, txn_id, name, amount, d, pending=False, account_id="acc-1"):
        self.transaction_id = txn_id
        self.name = name
        self.merchant_name = name.title()
        self.logo_url = None
        self.counterparties = []
        self.account_id = account_id
        self.amount = amount
        self.date = d
        self.pending = pending
        self.personal_finance_category = None


def _link_account(db, email, item_id="item-1", institution="TestBank"):
    from models import User, LinkedAccount
    user = db.query(User).filter(User.email == email).first()
    acct = LinkedAccount(user_id=user.id, access_token="tok-123", item_id=item_id,
                         institution_name=institution)
    db.add(acct)
    db.commit()
    return user, acct


def test_sync_upserts_updates_and_removes(client, make_user, auth_headers, db, monkeypatch):
    import plaid_client as pc
    tok, email = make_user("sync@example.com")
    user, acct = _link_account(db, email)
    H = auth_headers(tok)
    monkeypatch.setattr(pc, "get_account_names", lambda token, env: {"acc-1": "Chequing ••1234"})
    calls = []

    t1 = FakePlaidTxn("p1", "Coffee Shop", 4.5, date(2026, 6, 3))
    t2 = FakePlaidTxn("p2", "Bookstore", 20.0, date(2026, 6, 4))
    t_pending = FakePlaidTxn("p3", "Pending Thing", 9.0, date(2026, 6, 5), pending=True)

    def fake_sync_1(access_token, cursor, environment):
        calls.append(cursor)
        return [t1, t2, t_pending], [], [], "cursor-1"

    monkeypatch.setattr(pc, "sync_transactions", fake_sync_1)
    r = client.post("/plaid/sync", headers=H)
    assert r.status_code == 200
    assert r.json()["transactions_synced"] == 2  # pending skipped
    assert calls == [None]  # first sync starts with no cursor

    db.refresh(acct)
    assert acct.sync_cursor == "cursor-1"

    # Second sync: t1 amount corrected, t2 removed; cursor must be passed back.
    t1_fixed = FakePlaidTxn("p1", "Coffee Shop", 6.0, date(2026, 6, 3))

    def fake_sync_2(access_token, cursor, environment):
        calls.append(cursor)
        return [], [t1_fixed], ["p2"], "cursor-2"

    monkeypatch.setattr(pc, "sync_transactions", fake_sync_2)
    r = client.post("/plaid/sync", headers=H)
    assert r.status_code == 200
    assert r.json()["transactions_synced"] == 0
    assert calls[-1] == "cursor-1"

    txns = client.get("/transactions", headers=H).json()
    assert {t["name"] for t in txns} == {"Coffee Shop"}          # p2 removed
    assert txns[0]["amount"] == 6.0                              # p1 updated in place
    assert txns[0]["merchant_name"] == "Coffee Shop"
    assert txns[0]["account_name"] == "Chequing ••1234"          # tagged with its bank account
    assert txns[0]["institution_name"] == "TestBank"
    db.refresh(acct)
    assert acct.sync_cursor == "cursor-2"


def test_sync_without_linked_account_is_400(client, make_user, auth_headers):
    tok, _ = make_user("nolink@example.com")
    assert client.post("/plaid/sync", headers=auth_headers(tok)).status_code == 400


def test_webhook_ignores_unknown_item(client):
    r = client.post("/plaid/webhook", json={"item_id": "nope", "webhook_type": "TRANSACTIONS"})
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}


def test_reconcile_removes_stale_rows_only(client, make_user, auth_headers, db, monkeypatch):
    """Orphaned rows (e.g. old pending duplicates) are deleted; live rows and
    the sync cursor are untouched."""
    import plaid_client as pc
    from models import Transaction
    tok, email = make_user("reconcile@example.com")
    user, acct = _link_account(db, email)
    acct.sync_cursor = "cursor-live"
    # one row Plaid still knows, one orphan (the old pending-id duplicate)
    db.add(Transaction(user_id=user.id, plaid_transaction_id="live-1", name="LCBO",
                       amount=118.0, date=datetime(2026, 6, 15)))
    db.add(Transaction(user_id=user.id, plaid_transaction_id="stale-pending-1", name="LCBO",
                       amount=118.0, date=datetime(2026, 6, 15)))
    db.commit()

    cursors = []

    def fake_full_sync(access_token, cursor, environment):
        cursors.append(cursor)
        return [FakePlaidTxn("live-1", "LCBO", 118.0, date(2026, 6, 15))], [], [], "ignored"

    monkeypatch.setattr(pc, "sync_transactions", fake_full_sync)
    r = client.post("/plaid/reconcile", headers=auth_headers(tok))
    assert r.status_code == 200
    assert r.json()["removed"] == 1
    assert cursors == [None]  # full pull, not incremental

    remaining = db.query(Transaction).filter(Transaction.user_id == user.id).all()
    assert [t.plaid_transaction_id for t in remaining] == ["live-1"]
    db.refresh(acct)
    assert acct.sync_cursor == "cursor-live"  # cursor not clobbered


def test_reconcile_refuses_when_bank_returns_nothing(client, make_user, auth_headers, db, monkeypatch):
    import plaid_client as pc
    from models import Transaction
    tok, email = make_user("reconcile2@example.com")
    user, acct = _link_account(db, email)
    db.add(Transaction(user_id=user.id, plaid_transaction_id="only-1", name="Cafe",
                       amount=10.0, date=datetime(2026, 6, 1)))
    db.commit()

    monkeypatch.setattr(pc, "sync_transactions", lambda t, c, e: ([], [], [], "x"))
    r = client.post("/plaid/reconcile", headers=auth_headers(tok))
    assert r.status_code == 409  # refuses to wipe everything on an empty compare
    assert db.query(Transaction).filter(Transaction.user_id == user.id).count() == 1


def test_delete_account_revokes_plaid_items(client, make_user, auth_headers, db, monkeypatch):
    import plaid_client as pc
    from models import User, LinkedAccount
    tok, email = make_user("bye@example.com")
    _link_account(db, email, item_id="item-bye")
    revoked = []
    monkeypatch.setattr(pc, "remove_item", lambda token, env: revoked.append(token))

    r = client.request("DELETE", "/auth/delete-account", headers=auth_headers(tok),
                       json={"password": PASSWORD})
    assert r.status_code == 200
    assert revoked == ["tok-123"]  # Plaid item revoked, not just deleted locally
    assert db.query(User).filter(User.email == email).first() is None
    assert db.query(LinkedAccount).filter(LinkedAccount.item_id == "item-bye").first() is None
