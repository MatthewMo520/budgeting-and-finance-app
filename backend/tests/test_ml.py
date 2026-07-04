from datetime import datetime, timedelta

from ml import rule_category, detect_recurring, _normalize_merchant, is_spend, compute_insights, forecast_month


class FakeTxn:
    def __init__(self, name, amount, date, ml_category="FOOD_AND_DRINK"):
        self.name = name
        self.amount = amount
        self.date = date
        self.ml_category = ml_category


class FakeBudget:
    def __init__(self, category, monthly_limit):
        self.category = category
        self.monthly_limit = monthly_limit


def test_rule_category_known_merchants():
    assert rule_category("McDonald's") == "FOOD_AND_DRINK"
    assert rule_category("Uber 063015 SF**POOL**") == "TRANSPORTATION"
    assert rule_category("United Airlines") == "TRAVEL"
    assert rule_category("ACH Electronic CreditGUSTO PAY 123") == "INCOME"
    assert rule_category("CREDIT CARD 3333 PAYMENT") == "LOAN_PAYMENTS"
    assert rule_category("Touchstone Climbing") == "ENTERTAINMENT"
    assert rule_category("Whole Foods") == "GROCERIES"


def test_rule_category_unknown_returns_none():
    assert rule_category("Zxqw Random Merchant 999") is None
    assert rule_category("") is None


def test_normalize_merchant_strips_digits_and_punctuation():
    assert _normalize_merchant("UBER 063015 SF**POOL**") == "uber sf pool"
    assert _normalize_merchant("Netflix") == "netflix"


def test_detect_recurring_finds_monthly_subscription():
    base = datetime(2026, 1, 15)
    txns = [FakeTxn("Netflix", 15.99, base + timedelta(days=30 * i)) for i in range(4)]
    txns.append(FakeTxn("One Off Store", 200.0, base))  # single → not recurring

    rec = detect_recurring(txns)
    netflix = [r for r in rec if r["name"] == "Netflix"]
    assert netflix, "Netflix should be detected as recurring"
    assert netflix[0]["frequency"] == "monthly"
    assert netflix[0]["occurrences"] == 4
    assert all(r["name"] != "One Off Store" for r in rec)


def test_detect_recurring_ignores_irregular_amounts():
    base = datetime(2026, 1, 1)
    txns = [
        FakeTxn("Random Shop", 10.0, base),
        FakeTxn("Random Shop", 500.0, base + timedelta(days=4)),
        FakeTxn("Random Shop", 30.0, base + timedelta(days=70)),
    ]
    rec = detect_recurring(txns)
    assert all(r["name"] != "Random Shop" for r in rec)


def test_detect_recurring_ignores_income():
    # inflows (negative amount) shouldn't be counted as recurring spend
    base = datetime(2026, 1, 1)
    txns = [FakeTxn("Paycheck", -2000.0, base + timedelta(days=30 * i)) for i in range(4)]
    assert detect_recurring(txns) == []


def test_detect_recurring_ignores_card_payments():
    # a monthly credit-card payment is a transfer, not a subscription
    base = datetime(2026, 1, 1)
    txns = [FakeTxn("CREDIT CARD 3333 PAYMENT", 850.0, base + timedelta(days=30 * i), "LOAN_PAYMENTS") for i in range(4)]
    assert detect_recurring(txns) == []


def test_is_spend_excludes_transfers_and_payments():
    # card payments/transfers would double-count purchases already logged
    assert is_spend(50.0, "FOOD_AND_DRINK")
    assert not is_spend(850.0, "LOAN_PAYMENTS")   # credit card payment
    assert not is_spend(200.0, "TRANSFER_OUT")
    assert not is_spend(200.0, "TRANSFER_IN")
    assert not is_spend(-2000.0, "INCOME")        # inflow
    assert not is_spend(-12.0, "FOOD_AND_DRINK")  # refund is not spend
    assert is_spend(50.0, None)                   # uncategorized outflow counts


def test_compute_insights_flags_category_spike():
    now = datetime(2026, 7, 15)
    txns = [FakeTxn("Cafe", 100.0, datetime(2026, m, 10)) for m in (4, 5, 6)]  # $100/mo average
    txns.append(FakeTxn("Cafe", 300.0, datetime(2026, 7, 5)))                  # 3× this month
    spikes = [i for i in compute_insights(txns, now=now) if i["type"] == "spike"]
    assert spikes and "Dining" in spikes[0]["title"]


def test_forecast_month_projects_run_rate_plus_upcoming_recurring():
    now = datetime(2026, 7, 10)  # July: 31 days, 21 left
    txns = [FakeTxn(f"Shop {i}", 10.0, now - timedelta(days=i)) for i in range(90)]  # $10/day
    # Netflix bills monthly on the 25th — not yet charged this month
    txns += [FakeTxn("Netflix", 15.0, datetime(2026, m, 25), "ENTERTAINMENT") for m in (4, 5, 6)]

    f = forecast_month(txns, now=now)
    assert f["month"] == "2026-07"
    assert f["days_left"] == 21
    assert f["spent_so_far"] == 100.0  # July 1–10 daily spend
    assert any(u["name"] == "Netflix" and u["expected_day"] == 25 for u in f["upcoming_recurring"])
    # ≈ 100 spent + 10/day × 21 days + 15 Netflix
    assert abs(f["projected_spend"] - 325.0) < 30


def test_forecast_month_skips_recurring_already_charged():
    now = datetime(2026, 7, 28)
    txns = [FakeTxn("Netflix", 15.0, datetime(2026, m, 25), "ENTERTAINMENT") for m in (5, 6, 7)]
    f = forecast_month(txns, now=now)
    assert f["upcoming_recurring"] == []  # July 25 already happened


def test_compute_insights_flags_duplicate_and_budget():
    now = datetime(2026, 7, 15)
    txns = [
        FakeTxn("Gym Co", 49.99, datetime(2026, 7, 10)),
        FakeTxn("Gym Co", 49.99, datetime(2026, 7, 11)),  # same amount, next day
    ]
    budgets = [FakeBudget("Dining", 100.0)]
    txns.append(FakeTxn("Cafe", 95.0, datetime(2026, 7, 3)))  # 95% of Dining budget
    types = {i["type"] for i in compute_insights(txns, budgets, now=now)}
    assert "duplicate" in types
    assert "budget" in types
