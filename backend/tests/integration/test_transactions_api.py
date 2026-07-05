"""Transaction endpoints: scoping, filters, spend accounting, CSV, overrides."""
from datetime import datetime

from tests.integration.conftest import PASSWORD  # noqa: F401  (re-exported fixture constant)


def _seed(db, email, rows):
    """Insert transactions directly for the user with the given email.
    rows: (plaid_id, name, amount, date, ml_category)"""
    from models import User, Transaction
    user = db.query(User).filter(User.email == email).first()
    for pid, name, amount, dt, ml in rows:
        db.add(Transaction(user_id=user.id, plaid_transaction_id=pid, name=name,
                           amount=amount, date=dt, ml_category=ml))
    db.commit()
    return user


def test_transactions_are_scoped_per_user(client, make_user, auth_headers, db):
    tok_a, email_a = make_user("scope-a@example.com")
    tok_b, email_b = make_user("scope-b@example.com")
    _seed(db, email_a, [("a1", "Cafe A", 10.0, datetime(2026, 6, 5), "FOOD_AND_DRINK")])
    _seed(db, email_b, [("b1", "Cafe B", 20.0, datetime(2026, 6, 6), "FOOD_AND_DRINK")])

    names_a = {t["name"] for t in client.get("/transactions", headers=auth_headers(tok_a)).json()}
    names_b = {t["name"] for t in client.get("/transactions", headers=auth_headers(tok_b)).json()}
    assert names_a == {"Cafe A"} and names_b == {"Cafe B"}


def test_month_filter(client, make_user, auth_headers, db):
    tok, email = make_user("months@example.com")
    _seed(db, email, [
        ("m1", "June Txn", 10.0, datetime(2026, 6, 5), "FOOD_AND_DRINK"),
        ("m2", "July Txn", 20.0, datetime(2026, 7, 5), "FOOD_AND_DRINK"),
    ])
    june = client.get("/transactions?month=2026-06", headers=auth_headers(tok)).json()
    assert [t["name"] for t in june] == ["June Txn"]
    months = client.get("/transactions/months", headers=auth_headers(tok)).json()
    assert months == ["2026-07", "2026-06"]


def test_summary_excludes_card_payments_and_transfers(client, make_user, auth_headers, db):
    """The double-count fix: paying a credit card is not spending."""
    tok, email = make_user("spend@example.com")
    _seed(db, email, [
        ("s1", "Groceries", 100.0, datetime(2026, 6, 5), "GROCERIES"),
        ("s2", "CREDIT CARD PAYMENT", 850.0, datetime(2026, 6, 6), "LOAN_PAYMENTS"),
        ("s3", "Transfer to savings", 200.0, datetime(2026, 6, 7), "TRANSFER_OUT"),
        ("s4", "Payroll", -3000.0, datetime(2026, 6, 8), "INCOME"),
    ])
    summary = client.get("/transactions/summary", headers=auth_headers(tok)).json()
    assert len(summary) == 1
    m = summary[0]
    assert m["month"] == "2026-06"
    assert m["spend"] == 100.0      # only the groceries
    assert m["income"] == 3000.0    # payroll counts, transfers don't
    assert m["count"] == 4          # everything is still listed


def test_csv_export_escapes_formulas(client, make_user, auth_headers, db):
    tok, email = make_user("csv@example.com")
    _seed(db, email, [("c1", "=SUM(A1:A9)", 10.0, datetime(2026, 6, 5), "FOOD_AND_DRINK")])
    r = client.get("/transactions/export?month=2026-06", headers=auth_headers(tok))
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert "'=SUM(A1:A9)" in r.text  # formula neutralized


def test_category_override_bulk_applies_and_survives_ml(client, make_user, auth_headers, db):
    tok, email = make_user("override@example.com")
    user = _seed(db, email, [
        ("o1", "Mystery Shop", 10.0, datetime(2026, 6, 5), "GENERAL_MERCHANDISE"),
        ("o2", "Mystery Shop", 12.0, datetime(2026, 6, 15), "GENERAL_MERCHANDISE"),
    ])
    txn_id = client.get("/transactions", headers=auth_headers(tok)).json()[0]["id"]
    r = client.patch(f"/transactions/{txn_id}/category", headers=auth_headers(tok),
                     json={"category": "Dining"})
    assert r.status_code == 200

    txns = client.get("/transactions", headers=auth_headers(tok)).json()
    assert all(t["ml_category"] == "FOOD_AND_DRINK" and t["category_overridden"] for t in txns)

    # Re-running ML must keep the user's correction
    assert client.post("/run-ml", headers=auth_headers(tok)).status_code == 200
    txns = client.get("/transactions", headers=auth_headers(tok)).json()
    assert all(t["ml_category"] == "FOOD_AND_DRINK" for t in txns)


def test_category_update_rejects_unknown_and_foreign(client, make_user, auth_headers, db):
    tok_a, email_a = make_user("owner@example.com")
    tok_b, _ = make_user("intruder@example.com")
    _seed(db, email_a, [("f1", "Cafe", 10.0, datetime(2026, 6, 5), "FOOD_AND_DRINK")])
    txn_id = client.get("/transactions", headers=auth_headers(tok_a)).json()[0]["id"]

    r = client.patch(f"/transactions/{txn_id}/category", headers=auth_headers(tok_a),
                     json={"category": "Nonsense"})
    assert r.status_code == 422
    # Another user can't touch it
    r = client.patch(f"/transactions/{txn_id}/category", headers=auth_headers(tok_b),
                     json={"category": "Dining"})
    assert r.status_code == 404


def test_budgets_crud_and_validation(client, make_user, auth_headers):
    tok, _ = make_user("budget@example.com")
    H = auth_headers(tok)
    assert client.put("/budgets", headers=H, json={"category": "Nonsense", "monthly_limit": 100}).status_code == 422
    assert client.put("/budgets", headers=H, json={"category": "Dining", "monthly_limit": -5}).status_code == 422
    assert client.put("/budgets", headers=H, json={"category": "Dining", "monthly_limit": 300}).status_code == 200
    assert client.put("/budgets", headers=H, json={"category": "Dining", "monthly_limit": 400}).status_code == 200  # upsert
    assert client.get("/budgets", headers=H).json() == [{"category": "Dining", "monthly_limit": 400.0}]
    assert client.delete("/budgets/Dining", headers=H).status_code == 200
    assert client.get("/budgets", headers=H).json() == []


def test_goals_crud_and_progress(client, make_user, auth_headers, db):
    tok, email = make_user("goals@example.com")
    H = auth_headers(tok)
    assert client.post("/goals", headers=H, json={"name": " ", "target_amount": 100}).status_code == 422
    assert client.post("/goals", headers=H, json={"name": "Fund", "target_amount": -5}).status_code == 422
    r = client.post("/goals", headers=H, json={"name": "Emergency fund", "target_amount": 1000})
    assert r.status_code == 201

    # income/spend after goal creation feeds progress; transfers don't count
    now = datetime.utcnow()
    _seed(db, email, [
        ("g1", "Payroll", -2000.0, now, "INCOME"),
        ("g2", "Cafe", 500.0, now, "FOOD_AND_DRINK"),
        ("g3", "Transfer to savings", 300.0, now, "TRANSFER_OUT"),
    ])
    goals = client.get("/goals", headers=H).json()
    assert goals[0]["saved"] == 1500.0  # 2000 income − 500 spend

    gid = goals[0]["id"]
    assert client.delete(f"/goals/{gid}", headers=H).status_code == 200
    assert client.get("/goals", headers=H).json() == []
    assert client.delete(f"/goals/{gid}", headers=H).status_code == 404


def test_forecast_endpoint_shape(client, make_user, auth_headers, db):
    tok, email = make_user("forecast@example.com")
    _seed(db, email, [("fc1", "Cafe", 10.0, datetime.utcnow(), "FOOD_AND_DRINK")])
    r = client.get("/forecast", headers=auth_headers(tok))
    assert r.status_code == 200
    body = r.json()
    assert {"month", "spent_so_far", "projected_spend", "days_left", "upcoming_recurring"} <= set(body)


def test_anomaly_dismissal_sticks_through_ml_rerun(client, make_user, auth_headers, db):
    from models import Transaction
    tok, email = make_user("anomaly@example.com")
    H = auth_headers(tok)
    user = _seed(db, email, [
        ("an1", "Huge Charge", 5000.0, datetime(2026, 6, 5), "FOOD_AND_DRINK"),
        ("an2", "Cafe", 10.0, datetime(2026, 6, 6), "FOOD_AND_DRINK"),
        ("an3", "Cafe", 12.0, datetime(2026, 6, 7), "FOOD_AND_DRINK"),
    ])
    db.query(Transaction).filter(Transaction.plaid_transaction_id == "an1").update(
        {Transaction.is_anomaly: True})
    db.commit()

    txns = client.get("/transactions", headers=H).json()
    flagged = next(t for t in txns if t["name"] == "Huge Charge")
    assert flagged["is_anomaly"] is True

    r = client.patch(f"/transactions/{flagged['id']}/anomaly", headers=H, json={"dismissed": True})
    assert r.status_code == 200 and r.json()["is_anomaly"] is False

    # ML re-run must not re-flag a dismissed transaction
    assert client.post("/run-ml", headers=H).status_code == 200
    txns = client.get("/transactions", headers=H).json()
    flagged = next(t for t in txns if t["name"] == "Huge Charge")
    assert flagged["is_anomaly"] is False and flagged["anomaly_dismissed"] is True

    # bogus ids 404 rather than 500
    assert client.patch("/transactions/not-a-uuid/anomaly", headers=H, json={"dismissed": True}).status_code == 404


def test_notification_preferences(client, make_user, auth_headers):
    tok, _ = make_user("prefs@example.com")
    H = auth_headers(tok)
    me = client.get("/auth/me", headers=H).json()
    assert me["digest_enabled"] is True and me["budget_alerts_enabled"] is True

    r = client.patch("/auth/notifications", headers=H, json={"digest_enabled": False})
    assert r.status_code == 200
    me = client.get("/auth/me", headers=H).json()
    assert me["digest_enabled"] is False and me["budget_alerts_enabled"] is True


def test_insights_endpoint_returns_list(client, make_user, auth_headers, db):
    tok, email = make_user("insights@example.com")
    _seed(db, email, [("i1", "Cafe", 10.0, datetime(2026, 6, 5), "FOOD_AND_DRINK")])
    r = client.get("/insights", headers=auth_headers(tok))
    assert r.status_code == 200
    assert isinstance(r.json(), list)
