import os
import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from datetime import date, timedelta

PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")
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
    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
        client_name="Finance App",
        products=[Products("transactions")],
        country_codes=[CountryCode("US"), CountryCode("CA")],
        language="en",
    )
    response = _client_for(environment).link_token_create(request)
    return response.link_token


def exchange_public_token(public_token: str, environment: str = PLAID_ENV) -> str:
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = _client_for(environment).item_public_token_exchange(request)
    return response.access_token


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
