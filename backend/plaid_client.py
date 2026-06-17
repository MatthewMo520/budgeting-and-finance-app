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

configuration = plaid.Configuration(
    host=_env_map.get(PLAID_ENV, "https://sandbox.plaid.com"),
    api_key={
        "clientId": os.getenv("PLAID_CLIENT_ID"),
        "secret": os.getenv("PLAID_SECRET"),
    },
)

api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)


def create_link_token(user_id: str) -> str:
    """Create a Plaid Link token to initialize the Link widget on the frontend."""
    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
        client_name="Finance App",
        products=[Products("transactions")],
        country_codes=[CountryCode("US"), CountryCode("CA")],
        language="en",
    )
    response = client.link_token_create(request)
    return response.link_token


def exchange_public_token(public_token: str) -> str:
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = client.item_public_token_exchange(request)
    return response.access_token


def get_transactions(access_token: str, start_date: date, end_date: date) -> list:
    """Fetch all transactions in [start_date, end_date], handling Plaid's 500-item pagination."""
    all_transactions = []
    offset = 0

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
    response = client.sandbox_public_token_create(request)
    return response.public_token
