# tests/integration/test_api_endpoints.py
import pytest
import requests

POCKETBASE_URL = "http://127.0.0.1:8090"
API_URL = "http://127.0.0.1:5000/api"
ADMIN_EMAIL = "hikka780@gmail.com"
ADMIN_PASSWORD = "Benzomafia1"  # ← ← ← ЗАМЕНИТЕ!

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{POCKETBASE_URL}/api/admins/auth-with-password", json={
        "identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD
    })
    assert r.status_code == 200
    return r.json()["token"]

def create_test_product(admin_token):
    r = requests.post(f"{POCKETBASE_URL}/api/collections/products/records", json={
        "key": "test_api", "title": "Test Product", "price": 10, "is_active": True
    }, headers={"Authorization": f"Bearer {admin_token}"})
    return r.json()["id"]

def add_test_account(admin_token, product_id):
    r = requests.post(f"{POCKETBASE_URL}/api/collections/accounts/records", json={
        "product": product_id, "data": "login:pass:test", "sold": False
    }, headers={"Authorization": f"Bearer {admin_token}"})
    return r.json()["id"]

def test_reserve_and_webhook_flow(admin_token):
    product_id = create_test_product(admin_token)
    account_id = add_test_account(admin_token, product_id)

    cart = requests.post(f"{POCKETBASE_URL}/api/collections/carts/records", json={}).json()
    cart_id = cart["id"]

    r1 = requests.post(f"{API_URL}/cart/reserve", json={
        "cart_id": cart_id, "product_id": product_id, "quantity": 1
    })
    assert r1.status_code == 200

    r2 = requests.post(f"{API_URL}/payments/webhook", json={
        "status": "paid",
        "invoice_id": "test_inv_123",
        "metadata": {"cart_id": cart_id}
    })
    assert r2.status_code == 200

    accounts = requests.get(
        f"{POCKETBASE_URL}/api/collections/accounts/records",
        params={"filter": f'id="{account_id}"'}
    ).json()
    assert len(accounts["items"]) == 0

    solds = requests.get(f"{POCKETBASE_URL}/api/collections/sold_accounts/records").json()
    assert len(solds["items"]) >= 1