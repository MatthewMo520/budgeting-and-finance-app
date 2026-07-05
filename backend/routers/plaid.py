"""Plaid endpoints: linking, syncing, balances, net worth, webhook."""
import json
import os
import time
from datetime import date, datetime, timedelta

import plaid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db, SessionLocal
from models import User, Transaction, LinkedAccount, BalanceSnapshot
import plaid_client as pc
from ml import run_ml_pipeline, run_ml_for_user
from rate_limit import limiter
from webhook_verify import verify_webhook

router = APIRouter(tags=["plaid"])


# ── Plaid Link flow (real bank accounts) ─────────────────────────────────────

@router.post("/plaid/create-link-token")
@limiter.limit("20/minute")
def create_link_token(request: Request, current_user: User = Depends(get_current_user)):
    link_token = pc.create_link_token(str(current_user.id), pc.env_for_user(current_user))
    return {"link_token": link_token}


class ExchangeTokenRequest(BaseModel):
    public_token: str


@router.post("/plaid/exchange-token")
@limiter.limit("10/minute")
def exchange_token(
    request: Request,
    body: ExchangeTokenRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    environment = pc.env_for_user(current_user)
    access_token, item_id = pc.exchange_public_token(body.public_token, environment)
    institution = pc.get_institution_name(access_token, environment)
    _save_linked_account(db, current_user.id, access_token, item_id, institution)
    db.commit()

    end = date.today()
    start = end - timedelta(days=365)
    transactions = _get_transactions_or_none(access_token, start, end, environment)
    if transactions is None:
        # Production: Plaid is still pulling history. The bank is linked; the
        # webhook (or a manual Sync) will load transactions once they're ready.
        return {"transactions_synced": 0, "pending": True,
                "message": "Bank linked! Your transactions are still being prepared — check back in a minute and hit Sync."}
    account_names = _account_names_or_empty(access_token, environment)
    added = _upsert_transactions(db, current_user.id, transactions, account_names, institution)
    background_tasks.add_task(run_ml_for_user, current_user.id)
    return {"transactions_synced": added}


# ── Transaction sync ──────────────────────────────────────────────────────────

@router.post("/plaid/sync")
@limiter.limit("10/minute")
def sync_transactions(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = db.query(LinkedAccount).filter(LinkedAccount.user_id == current_user.id).all()
    if not accounts:
        raise HTTPException(status_code=400, detail="No bank account linked.")

    environment = pc.env_for_user(current_user)
    total_added = 0
    pending = False
    for acct in accounts:
        added = _sync_linked_account(db, acct, environment)
        if added is None:
            pending = True
            continue
        total_added += added

    if total_added > 0:
        background_tasks.add_task(run_ml_for_user, current_user.id)
    if total_added == 0 and pending:
        return {"transactions_synced": 0, "pending": True,
                "message": "Your transactions are still being prepared by your bank — try again in a minute."}
    return {"transactions_synced": total_added, "message": f"Synced {total_added} new transactions"}


# ── Account balances ──────────────────────────────────────────────────────────

# Balance calls hit the bank live (slow + billable), so cache per user briefly.
_balance_cache = {}  # user_id(str) -> (fetched_at, payload)
_BALANCE_TTL_SECONDS = 300


@router.get("/plaid/balances")
@limiter.limit("10/minute")
def get_balances_endpoint(
    request: Request,
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    key = str(current_user.id)
    now = time.time()
    cached = _balance_cache.get(key)
    if cached and not refresh and now - cached[0] < _BALANCE_TTL_SECONDS:
        return cached[1]

    accounts = db.query(LinkedAccount).filter(LinkedAccount.user_id == current_user.id).all()
    environment = pc.env_for_user(current_user)
    result = []
    for acct in accounts:
        institution = acct.institution_name or "Linked bank"
        # One bank failing (e.g. ITEM_LOGIN_REQUIRED) shouldn't take down the rest,
        # but surface the Plaid error code so failures are diagnosable.
        try:
            result.append({"institution": institution, "accounts": pc.get_balances(acct.access_token, environment)})
        except plaid.ApiException as e:
            try:
                code = json.loads(e.body).get("error_code") or "PLAID_ERROR"
            except (ValueError, TypeError):
                code = "PLAID_ERROR"
            print(f"Balance fetch failed for {institution} (item {acct.item_id}, env {environment}): {code}")
            result.append({"institution": institution, "accounts": [], "error": True, "error_code": code})
        except Exception as e:
            print(f"Balance fetch failed for {institution} (item {acct.item_id}, env {environment}): {e!r}")
            result.append({"institution": institution, "accounts": [], "error": True, "error_code": "INTERNAL"})
    _balance_cache[key] = (now, result)
    _record_balance_snapshot(db, current_user.id, result)
    return result


def _record_balance_snapshot(db: Session, user_id, balance_payload):
    """Upsert today's net-worth data point from a fresh balances fetch."""
    accounts = [a for b in balance_payload if not b.get("error") for a in b["accounts"]]
    if not accounts:
        return
    total_available = sum((a["available"] if a["available"] is not None else a["current"]) or 0 for a in accounts)
    total_current = sum(a["current"] or 0 for a in accounts)
    today = date.today()
    snap = db.query(BalanceSnapshot).filter(
        BalanceSnapshot.user_id == user_id, BalanceSnapshot.date == today
    ).first()
    if snap:
        snap.total_available = total_available
        snap.total_current = total_current
    else:
        db.add(BalanceSnapshot(user_id=user_id, date=today,
                               total_available=total_available, total_current=total_current))
    db.commit()


@router.get("/networth")
@limiter.limit("60/minute")
def get_networth(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Daily net-worth snapshots (recorded whenever fresh balances are fetched)."""
    rows = (
        db.query(BalanceSnapshot)
        .filter(BalanceSnapshot.user_id == current_user.id)
        .order_by(BalanceSnapshot.date.asc())
        .all()
    )
    return [
        {"date": r.date.isoformat(), "total_available": round(r.total_available, 2),
         "total_current": round(r.total_current, 2)}
        for r in rows
    ]


# ── Data repair: reconcile against Plaid ─────────────────────────────────────

@router.post("/plaid/reconcile")
@limiter.limit("2/minute")
def reconcile_transactions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete local transactions Plaid no longer reports. Fixes duplicates left
    behind by the old pending-transaction handling (a pending charge got a new
    id when it posted) and rows from re-linked items. Pulls the full current
    id set per account (cursor untouched, so incremental sync is unaffected)."""
    accounts = db.query(LinkedAccount).filter(LinkedAccount.user_id == current_user.id).all()
    if not accounts:
        raise HTTPException(status_code=400, detail="No bank account linked.")

    environment = pc.env_for_user(current_user)
    known_ids = set()
    for acct in accounts:
        # Full pull from a None cursor; do NOT persist it — this is read-only.
        added, modified, _removed, _cursor = pc.sync_transactions(acct.access_token, None, environment)
        known_ids.update(t.transaction_id for t in added + modified)

    if not known_ids:
        # Plaid returned nothing (e.g. history still preparing) — deleting
        # everything on that basis would be catastrophic, so bail out.
        raise HTTPException(status_code=409, detail="Your bank returned no transactions to compare against — try again in a minute.")

    stale = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id,
                Transaction.plaid_transaction_id.notin_(known_ids))
        .all()
    )
    removed_count = len(stale)
    for row in stale:
        db.delete(row)
    db.commit()
    return {
        "removed": removed_count,
        "message": f"Removed {removed_count} transaction(s) your bank no longer reports."
        if removed_count else "Everything matches your bank — nothing to clean up.",
    }


# ── Manage linked accounts ────────────────────────────────────────────────────

@router.get("/plaid/accounts")
@limiter.limit("60/minute")
def list_linked_accounts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = (
        db.query(LinkedAccount)
        .filter(LinkedAccount.user_id == current_user.id)
        .order_by(LinkedAccount.created_at.asc())
        .all()
    )
    return [
        {
            "id": str(a.id),
            "institution_name": a.institution_name or "Linked bank",
            "linked_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in accounts
    ]


@router.delete("/plaid/accounts/{account_id}")
@limiter.limit("10/minute")
def remove_linked_account(
    request: Request,
    account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    acct = (
        db.query(LinkedAccount)
        .filter(LinkedAccount.id == account_id, LinkedAccount.user_id == current_user.id)
        .first()
    )
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    pc.remove_item(acct.access_token, pc.env_for_user(current_user))
    db.delete(acct)
    db.commit()
    return {"message": "Bank disconnected."}


# ── Plaid webhook (auto-sync when transactions are ready) ─────────────────────

@router.post("/plaid/webhook")
async def plaid_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    body_bytes = await request.body()
    payload = json.loads(body_bytes or b"{}")
    item_id = payload.get("item_id")

    acct = db.query(LinkedAccount).filter(LinkedAccount.item_id == item_id).first() if item_id else None
    if not acct:
        return {"status": "ignored"}  # unknown item — nothing to do

    user = db.query(User).filter(User.id == acct.user_id).first()
    environment = pc.env_for_user(user) if user else pc.PLAID_ENV
    if not verify_webhook(request.headers.get("plaid-verification"), body_bytes, environment):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Transaction updates → sync that item in the background, then run ML.
    if payload.get("webhook_type") == "TRANSACTIONS" and payload.get("webhook_code") in (
        "INITIAL_UPDATE", "HISTORICAL_UPDATE", "DEFAULT_UPDATE", "SYNC_UPDATES_AVAILABLE",
    ):
        background_tasks.add_task(_sync_account_async, str(acct.id))
    return {"status": "ok"}


# ── Sandbox setup (dev only) ──────────────────────────────────────────────────

@router.post("/setup-sandbox")
@limiter.limit("5/minute")
def setup_sandbox(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Dev-only: never allow fake data to overwrite a real linked account in prod.
    if os.getenv("PLAID_ENV") == "production":
        raise HTTPException(status_code=403, detail="Sandbox setup is disabled in production.")

    public_token = pc.create_sandbox_token()
    access_token, item_id = pc.exchange_public_token(public_token)
    _save_linked_account(db, current_user.id, access_token, item_id)
    db.commit()

    time.sleep(10)

    end = date.today()
    start = end - timedelta(days=365)
    transactions = pc.get_transactions(access_token, start, end)
    account_names = _account_names_or_empty(access_token, "sandbox")
    added = _upsert_transactions(db, current_user.id, transactions, account_names, "Chase (sandbox)")
    return {"transactions_synced": added}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_linked_account(db: Session, user_id, access_token, item_id, institution_name=None):
    """Insert or update a LinkedAccount, deduping by Plaid item_id."""
    acct = db.query(LinkedAccount).filter(LinkedAccount.item_id == item_id).first()
    if acct:
        acct.access_token = access_token
        acct.user_id = user_id
        if institution_name:
            acct.institution_name = institution_name
    else:
        db.add(LinkedAccount(user_id=user_id, access_token=access_token,
                             item_id=item_id, institution_name=institution_name))


def _sync_account_async(account_id: str):
    """Background sync for one linked account (used by the Plaid webhook)."""
    db = SessionLocal()
    try:
        acct = db.query(LinkedAccount).filter(LinkedAccount.id == account_id).first()
        if not acct:
            return
        user = db.query(User).filter(User.id == acct.user_id).first()
        environment = pc.env_for_user(user) if user else pc.PLAID_ENV
        added = _sync_linked_account(db, acct, environment)
        if added:
            run_ml_pipeline(db, acct.user_id)
    finally:
        db.close()


def _get_transactions_or_none(access_token, start, end, environment):
    """Fetch transactions, returning None if Plaid hasn't finished preparing them
    yet (PRODUCT_NOT_READY) — common in production right after linking."""
    try:
        return pc.get_transactions(access_token, start, end, environment)
    except plaid.ApiException as e:
        try:
            code = json.loads(e.body).get("error_code")
        except (ValueError, TypeError):
            code = None
        if code == "PRODUCT_NOT_READY":
            return None
        raise


def _merchant_fields(t):
    """Best-effort merchant name + logo from a Plaid transaction."""
    merchant = getattr(t, "merchant_name", None)
    logo = getattr(t, "logo_url", None)
    if not logo:
        for cp in getattr(t, "counterparties", None) or []:
            if getattr(cp, "logo_url", None):
                logo = cp.logo_url
                break
    return merchant, logo


def _upsert_transactions(db: Session, user_id, plaid_txns: list,
                         account_names: dict | None = None, institution: str | None = None) -> int:
    """Insert new transactions and update existing ones in place (the sync API
    reports modified rows, e.g. amount corrections). Returns the number added."""
    account_names = account_names or {}
    existing = {
        row.plaid_transaction_id: row
        for row in db.query(Transaction).filter(Transaction.user_id == user_id).all()
    }
    added = 0
    for t in plaid_txns:
        # Skip pending transactions: Plaid assigns them a NEW transaction_id when
        # they post, so storing them now would leave a duplicate row behind.
        if getattr(t, "pending", False):
            continue
        merchant, logo = _merchant_fields(t)
        category = t.personal_finance_category.primary if t.personal_finance_category else None
        account_id = getattr(t, "account_id", None)
        account_name = account_names.get(account_id)
        row = existing.get(t.transaction_id)
        if row:
            row.name = t.name
            row.amount = t.amount
            row.date = datetime.combine(t.date, datetime.min.time())
            row.category = category
            row.merchant_name = merchant or row.merchant_name
            row.logo_url = logo or row.logo_url
            row.plaid_account_id = account_id or row.plaid_account_id
            row.account_name = account_name or row.account_name
            row.institution_name = institution or row.institution_name
            continue
        txn = Transaction(
            user_id=user_id,
            plaid_transaction_id=t.transaction_id,
            name=t.name,
            merchant_name=merchant,
            logo_url=logo,
            plaid_account_id=account_id,
            account_name=account_name,
            institution_name=institution,
            amount=t.amount,
            date=datetime.combine(t.date, datetime.min.time()),
            category=category,
        )
        db.add(txn)
        existing[t.transaction_id] = txn
        added += 1
    db.commit()
    return added


def _account_names_or_empty(access_token: str, environment: str) -> dict:
    """Account labels for tagging transactions; never fails the sync."""
    try:
        return pc.get_account_names(access_token, environment)
    except Exception:
        return {}


def _sync_linked_account(db: Session, acct: LinkedAccount, environment: str):
    """Cursor-based sync for one linked account: upserts added+modified rows,
    deletes removed ones, persists the cursor. Returns the number of new
    transactions, or None when Plaid is still preparing them (PRODUCT_NOT_READY)."""
    try:
        added, modified, removed_ids, cursor = pc.sync_transactions(
            acct.access_token, acct.sync_cursor, environment
        )
    except plaid.ApiException as e:
        try:
            code = json.loads(e.body).get("error_code")
        except (ValueError, TypeError):
            code = None
        if code == "PRODUCT_NOT_READY":
            return None
        raise
    account_names = _account_names_or_empty(acct.access_token, environment) if (added or modified) else {}
    new_count = _upsert_transactions(db, acct.user_id, added + modified,
                                     account_names, acct.institution_name)
    if removed_ids:
        db.query(Transaction).filter(
            Transaction.user_id == acct.user_id,
            Transaction.plaid_transaction_id.in_(removed_ids),
        ).delete(synchronize_session=False)
    acct.sync_cursor = cursor
    db.commit()
    return new_count
