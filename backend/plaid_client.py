import os
import plaid
from plaid.api import plaid_api
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from datetime import date, timedelta
from plaid.model.sandbox_item_fire_webhook_request import SandboxItemFireWebhookRequest
from plaid.model.item_get_request import ItemGetRequest
import time

configuration = plaid.Configuration(
    host=plaid.Environment.Sandbox,
    api_key={
        "clientId": os.getenv("PLAID_CLIENT_ID"),
        "secret": os.getenv("PLAID_SECRET"),
    }
)

api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

def create_sandbox_token():
    request = SandboxPublicTokenCreateRequest(
        institution_id="ins_109508",
        initial_products=[Products("transactions")]
    )
    response = client.sandbox_public_token_create(request)
    return response.public_token

def exchange_public_token(public_token: str):
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = client.item_public_token_exchange(request)
    return response.access_token

def get_transactions(access_token: str, days: int = 30):
    start_date = date.today() - timedelta(days=days)
    end_date = date.today()
    request = TransactionsGetRequest(
        access_token=access_token,
        start_date=start_date,
        end_date=end_date,
        options=TransactionsGetRequestOptions(count=100)
    )
    response = client.transactions_get(request)
    return response.transactions

def refresh_sandbox_transactions(access_token: str):
    from plaid.model.transactions_refresh_request import TransactionsRefreshRequest
    request = TransactionsRefreshRequest(access_token=access_token)
    client.transactions_refresh(request)
    time.sleep(5)