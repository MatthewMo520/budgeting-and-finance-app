import os
import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from datetime import date, timedelta

PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")
# Absolute https URL Plaid POSTs transaction-update webhooks to (e.g.
# https://<backend>/plaid/webhook). If unset, Link tokens omit the webhook.
PLAID_WEBHOOK_URL = os.getenv("PLAID_WEBHOOK_URL")
_env_map = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}
_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")


def _secret_for(environment: str) -> str:
    """The default env uses PLAID_SECRET. To let a demo account run in sandbox
    while the app runs in production, set PLAID_SANDBOX_SECRET as well."""
    if environment == PLAID_ENV:
        return os.getenv("PLAID_SECRET")
    if environment == "sandbox":
        return os.getenv("PLAID_SANDBOX_SECRET") or os.getenv("PLAID_SECRET")
    return os.getenv("PLAID_SECRET")


_clients = {}


def _client_for(environment: str):
    """Lazily build + cache a Plaid client per environment."""
    if environment not in _clients:
        cfg = plaid.Configuration(
            host=_env_map.get(environment, _env_map["sandbox"]),
            api_key={"clientId": _CLIENT_ID, "secret": _secret_for(environment)},
        )
        _clients[environment] = plaid_api.PlaidApi(plaid.ApiClient(cfg))
    return _clients[environment]


def env_for_user(user) -> str:
    """Demo accounts always use Plaid sandbox; everyone else uses PLAID_ENV."""
    if getattr(user, "is_demo", False):
        return "sandbox"
    return PLAID_ENV


def create_link_token(user_id: str, environment: str = PLAID_ENV) -> str:
    """Create a Plaid Link token to initialize the Link widget on the frontend."""
    kwargs = dict(
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
        client_name="Finance App",
        products=[Products("transactions")],
        country_codes=[CountryCode("US"), CountryCode("CA")],
        language="en",
    )
    if PLAID_WEBHOOK_URL:
        kwargs["webhook"] = PLAID_WEBHOOK_URL
    response = _client_for(environment).link_token_create(LinkTokenCreateRequest(**kwargs))
    return response.link_token


def exchange_public_token(public_token: str, environment: str = PLAID_ENV):
    """Exchange a public token → (access_token, item_id)."""
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = _client_for(environment).item_public_token_exchange(request)
    return response.access_token, response.item_id


def get_item_id(access_token: str, environment: str = PLAID_ENV) -> str:
    """Look up the Plaid item_id for an existing access token (used to migrate
    legacy single-token users into linked_accounts)."""
    response = _client_for(environment).item_get(ItemGetRequest(access_token=access_token))
    return response.item.item_id


def get_institution_name(access_token: str, environment: str = PLAID_ENV):
    """Best-effort friendly bank name for a linked item (None if unavailable)."""
    try:
        item = _client_for(environment).item_get(ItemGetRequest(access_token=access_token))
        inst_id = item.item.institution_id
        if not inst_id:
            return None
        resp = _client_for(environment).institutions_get_by_id(
            InstitutionsGetByIdRequest(
                institution_id=inst_id,
                country_codes=[CountryCode("US"), CountryCode("CA")],
            )
        )
        return resp.institution.name
    except Exception:
        return None


def remove_item(access_token: str, environment: str = PLAID_ENV) -> None:
    """Revoke a linked item at Plaid (stops billing + access). Best-effort."""
    try:
        _client_for(environment).item_remove(ItemRemoveRequest(access_token=access_token))
    except Exception as e:
        print(f"Plaid item_remove failed (continuing): {e}")


def get_balances(access_token: str, environment: str = PLAID_ENV) -> list:
    """Balances for every account under one linked item, as of Plaid's last
    item update. Uses /accounts/get (included with Transactions access) rather
    than /accounts/balance/get, which is a separately-enabled paid product and
    returns INVALID_PRODUCT on Transactions-only production keys."""
    resp = _client_for(environment).accounts_get(
        AccountsGetRequest(access_token=access_token)
    )
    return [
        {
            "name": a.name,
            "mask": a.mask,
            "subtype": str(a.subtype) if a.subtype else None,
            "available": a.balances.available,
            "current": a.balances.current,
            "currency": a.balances.iso_currency_code or "USD",
        }
        for a in resp.accounts
    ]


def get_account_names(access_token: str, environment: str = PLAID_ENV) -> dict:
    """Map of Plaid account_id → display label like "Chequing ••1234"."""
    resp = _client_for(environment).accounts_get(AccountsGetRequest(access_token=access_token))
    names = {}
    for a in resp.accounts:
        label = a.name or (str(a.subtype).title() if a.subtype else "Account")
        if a.mask:
            label = f"{label} ••{a.mask}"
        names[a.account_id] = label
    return names


def sync_transactions(access_token: str, cursor: str | None, environment: str = PLAID_ENV):
    """Cursor-based /transactions/sync. Returns (added, modified, removed_ids,
    next_cursor). A None/empty cursor performs the initial full-history sync.
    Unlike /transactions/get this properly reports modified and removed
    transactions (e.g. pending→posted transitions)."""
    added, modified, removed_ids = [], [], []
    while True:
        kwargs = dict(access_token=access_token, count=500)
        if cursor:
            kwargs["cursor"] = cursor
        resp = _client_for(environment).transactions_sync(TransactionsSyncRequest(**kwargs))
        added.extend(resp.added)
        modified.extend(resp.modified)
        removed_ids.extend(r.transaction_id for r in resp.removed)
        cursor = resp.next_cursor
        if not resp.has_more:
            break
    return added, modified, removed_ids, cursor


def get_transactions(access_token: str, start_date: date, end_date: date, environment: str = PLAID_ENV) -> list:
    """Fetch all transactions in [start_date, end_date], handling Plaid's 500-item pagination."""
    all_transactions = []
    offset = 0
    client = _client_for(environment)

    while True:
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options=TransactionsGetRequestOptions(count=500, offset=offset),
        )
        response = client.transactions_get(request)
        batch = response.transactions
        all_transactions.extend(batch)

        if len(all_transactions) >= response.total_transactions:
            break
        offset += len(batch)

    return all_transactions


# ── Sandbox helpers (dev only) ────────────────────────────────────────────────

def create_sandbox_token() -> str:
    request = SandboxPublicTokenCreateRequest(
        institution_id="ins_109508",
        initial_products=[Products("transactions")],
    )
    response = _client_for("sandbox").sandbox_public_token_create(request)
    return response.public_token
