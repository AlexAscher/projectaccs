# tests/integration/test_api_profile_and_cancel.py
import pytest
import requests

POCKETBASE_URL = "http://127.0.0.1:8090"
API_URL = "http://127.0.0.1:5000/api"
ADMIN_PASSWORD = "Benzomafia1"  # ← ← ← ЗАМЕНИТЕ!

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{POCKETBASE_URL}/api/admins/auth-with-password", json={
        "identity": "admin@example.com", "password": ADMIN_PASSWORD
    })
    assert r.status_code == 200
    return r.json()["token"]

@pytest.fixture(scope="module")
def user_token():
    r = requests.post(f"{POCKETBASE_URL}/api/collections/users/auth-with-password", json={
        "identity": "simple@gmail.com", "password": "12345678"
    })
    assert r.status_code == 200
    return r.json()["token"]

def test_get_user_profile(admin_token, user_token):
    # Создаём пользователя в bot_users
    bot_user = requests.post(f"{POCKETBASE_URL}/api/collections/bot_users/records", json={
        "user_id": "123456789",
        "username": "testuser",
        "is_active": True
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()

    # Вызываем /api/profile
    resp = requests.get(f"{API_URL}/profile", headers={"X-User-ID": "123456789"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram_id"] == "123456789"
    assert "orders" in data

    # Очищаем
    requests.delete(f"{POCKETBASE_URL}/api/collections/bot_users/records/{bot_user['id']}", headers={"Authorization": f"Bearer {admin_token}"})

def test_cancel_unpaid_cart(admin_token, user_token):
    # Создаём продукт + аккаунт
    product = requests.post(f"{POCKETBASE_URL}/api/collections/products/records", json={
        "key": "cancel_test", "title": "Cancel Test", "price": 10, "is_active": True
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()

    account = requests.post(f"{POCKETBASE_URL}/api/collections/accounts/records", json={
        "product": product["id"], "data": "cancel:pass", "sold": False
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()

    cart = requests.post(f"{POCKETBASE_URL}/api/collections/carts/records", json={}).json()

    # Резервируем
    reserve = requests.post(f"{API_URL}/cart/reserve", json={
        "cart_id": cart["id"], "product_id": product["id"], "quantity": 1
    })
    assert reserve.status_code == 200

    # Отменяем
    cancel = requests.post(f"{API_URL}/cart/cancel", json={"cart_id": cart["id"]})
    assert cancel.status_code == 200
    assert cancel.json()["released"] == 1

    # Проверяем, что аккаунт освобождён
    acc = requests.get(f"{POCKETBASE_URL}/api/collections/accounts/records/{account['id']}", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert acc["reserved_cart"] == ""