from datetime import datetime

from digest import build_digest, last_closed_month, _prev_month
from tests.test_ml import FakeTxn


def test_prev_month_handles_january():
    assert _prev_month("2026-01") == "2025-12"
    assert _prev_month("2026-07") == "2026-06"


def test_last_closed_month():
    assert last_closed_month(datetime(2026, 7, 2)) == "2026-06"
    assert last_closed_month(datetime(2026, 1, 15)) == "2025-12"


def test_build_digest_totals_and_top_categories():
    txns = [
        FakeTxn("Cafe", 100.0, datetime(2026, 6, 5), "FOOD_AND_DRINK"),
        FakeTxn("Grocer", 300.0, datetime(2026, 6, 10), "GROCERIES"),
        FakeTxn("CC PAYMENT", 900.0, datetime(2026, 6, 12), "LOAN_PAYMENTS"),  # not spend
        FakeTxn("Cafe", 200.0, datetime(2026, 5, 5), "FOOD_AND_DRINK"),        # previous month
    ]
    d = build_digest(txns, "2026-06")
    assert d["total_spend"] == 400.0          # card payment excluded
    assert d["mom_pct"] == 100                # 400 vs 200
    assert d["top_categories"][0] == {"category": "Groceries", "amount": 300.0}
    assert d["transaction_count"] == 3


def test_build_digest_without_previous_month():
    txns = [FakeTxn("Cafe", 50.0, datetime(2026, 6, 5), "FOOD_AND_DRINK")]
    d = build_digest(txns, "2026-06")
    assert d["mom_pct"] is None
