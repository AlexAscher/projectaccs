# tests/system/test_e2e_purchase.py
import pytest
import requests
import time

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
        "key": "e2e_test", "title": "E2E Test", "price": 10, "is_active": True
    }, headers={"Authorization": f"Bearer {admin_token}"})
    return r.json()["id"]

def add_test_account(admin_token, product_id):
    r = requests.post(f"{POCKETBASE_URL}/api/collections/accounts/records", json={
        "product": product_id, "data": "e2e:pass:test", "sold": False
    }, headers={"Authorization": f"Bearer {admin_token}"})
    return r.json()["id"]

def cleanup(admin_token):
    """Удаляет все тестовые данные, созданные в ходе e2e-теста"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Список коллекций, из которых нужно удалять
    collections = ["sold_accounts", "accounts", "orders", "payments", "carts"]
    
    for coll in collections:
        try:
            # Получаем все записи с фильтром по тестовому ключу или payload
            resp = requests.get(
                f"{POCKETBASE_URL}/api/collections/{coll}/records",
                params={
                    "filter": 'product.key ?= "e2e_test" || cart_payload ?= "%e2e_%" || invoice_id ?= "e2e_%"'
                },
                headers=headers
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for item in items:
                    # Удаляем каждую запись
                    requests.delete(
                        f"{POCKETBASE_URL}/api/collections/{coll}/records/{item['id']}",
                        headers=headers
                    )
        except Exception as e:
            # Игнорируем ошибки (например, если коллекции нет)
            pass

def test_e2e_purchase_flow(admin_token):
    cleanup(admin_token)
    product_id = create_test_product(admin_token)
    account_id = add_test_account(admin_token, product_id)

    cart = requests.post(f"{POCKETBASE_URL}/api/collections/carts/records", json={}).json()
    cart_id = cart["id"]

    reserve = requests.post(f"{API_URL}/cart/reserve", json={
        "cart_id": cart_id, "product_id": product_id, "quantity": 1
    })
    assert reserve.status_code == 200

    webhook = requests.post(f"{API_URL}/payments/webhook", json={
        "status": "paid",
        "invoice_id": "e2e_123",
        "metadata": {"cart_id": cart_id}
    })
    assert webhook.status_code == 200

    time.sleep(1)

    accounts = requests.get(f"{POCKETBASE_URL}/api/collections/accounts/records", params={"filter": f'id="{account_id}"'}).json()
    assert len(accounts["items"]) == 0

    solds = requests.get(f"{POCKETBASE_URL}/api/collections/sold_accounts/records", params={"filter": f'cart="{cart_id}"'}).json()
    assert len(solds["items"]) == 1