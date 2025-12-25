# tests/acceptance/test_business_rules.py
import os
import sys
import pytest
import requests
import importlib.util
from datetime import datetime, timedelta

POCKETBASE_URL = "http://127.0.0.1:8090"
API_URL = "http://127.0.0.1:5000/api"
USER_EMAIL = "simple@gmail.com"
USER_PASSWORD = "12345678"
ADMIN_EMAIL = "hikka780@gmail.com"
ADMIN_PASSWORD = "Benzomafia1"  # ← ← ← ЗАМЕНИТЕ!

def load_import_module():
    spec = importlib.util.spec_from_file_location(
        "import_module",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "import", "import.py"))
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["import_module"] = module
    spec.loader.exec_module(module)
    return module

import_module = load_import_module()
record_exists = import_module.record_exists

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{POCKETBASE_URL}/api/admins/auth-with-password", json={
        "identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD
    })
    assert r.status_code == 200
    return r.json()["token"]

@pytest.fixture(scope="module")
def user_token():
    r = requests.post(f"{POCKETBASE_URL}/api/collections/users/auth-with-password", json={
        "identity": USER_EMAIL, "password": USER_PASSWORD
    })
    assert r.status_code == 200
    return r.json()["token"]

def test_bulk_discount_ig_250():
    from bot import calculate_total_price
    assert calculate_total_price("ig_0_us", 250) == 250.0
    assert calculate_total_price("ig_0_us", 100) == 120.0

def test_reservation_expires(admin_token, user_token):
    """Проверка: резерв автоматически освобождается через 10 минут"""
    # 1. Создаём продукт + аккаунт
    product = requests.post(f"{POCKETBASE_URL}/api/collections/products/records", json={
        "name": "UAT Test Product",
        "key": "uat_expire",
        "price_rub": 10,
        "is_active": True
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()

    account = requests.post(f"{POCKETBASE_URL}/api/collections/accounts/records", json={
        "product": product["id"],
        "data": "login:pass:email",
        "sold": False
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()

    # 2. Создаём корзину
    cart = requests.post(f"{POCKETBASE_URL}/api/collections/carts/records", json={
        "cart_payload": '{"items":[]}'
    }, headers={"Authorization": f"Bearer {user_token}"}).json()

    # 3. Резервируем
    resp = requests.post(f"{API_URL}/cart/reserve", json={
        "cart_id": cart["id"],
        "product_id": product["id"],
        "quantity": 1
    })
    assert resp.status_code == 200

    # 4. Проверим, что аккаунт зарезервирован
    acc_after = requests.get(
        f"{POCKETBASE_URL}/api/collections/accounts/records/{account['id']}",
        headers={"Authorization": f"Bearer {admin_token}"}
    ).json()
    assert acc_after["reserved_cart"] == cart["id"]

    # 5. Устанавливаем reserved_until в прошлое (имитация истечения 10 минут)
    past_time = (datetime.utcnow() - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:23] + "Z"
    requests.patch(
        f"{POCKETBASE_URL}/api/collections/accounts/records/{account['id']}",
        json={"reserved_until": past_time},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # 6. Запускаем cleanup через API
    cleanup_resp = requests.post(f"{API_URL}/cart/cleanup")
    assert cleanup_resp.status_code == 200
    assert cleanup_resp.json()["cleaned"] >= 1

    # 7. Убедимся, что аккаунт освобождён
    acc_final = requests.get(
        f"{POCKETBASE_URL}/api/collections/accounts/records/{account['id']}",
        headers={"Authorization": f"Bearer {admin_token}"}
    ).json()
    assert acc_final["reserved_cart"] == ""

def test_import_skips_duplicates(admin_token, tmp_path):
    product = requests.post(f"{POCKETBASE_URL}/api/collections/products/records", json={
        "key": "uat_dup", "title": "Dup Test", "price": 10, "is_active": True
    }, headers={"Authorization": f"Bearer {admin_token}"}).json()

    requests.post(f"{POCKETBASE_URL}/api/collections/accounts/records", json={
        "product": product["id"], "data": "duplicate_line", "sold": False
    }, headers={"Authorization": f"Bearer {admin_token}"})

    token = requests.post(f"{POCKETBASE_URL}/api/collections/users/auth-with-password", json={
        "identity": USER_EMAIL, "password": USER_PASSWORD
    }).json()["token"]

    exists = record_exists("duplicate_line", product["id"], token)
    assert exists is True

def test_blocked_user_not_in_broadcast(admin_token):
    active = requests.post(f"{POCKETBASE_URL}/api/collections/bot_users/records", json={
        "user_id": "111111", "is_active": True
    }, headers={"Authorization": f"Admin {admin_token}"}).json()
    inactive = requests.post(f"{POCKETBASE_URL}/api/collections/bot_users/records", json={
        "user_id": "222222", "is_active": False
    }, headers={"Authorization": f"Admin {admin_token}"}).json()

    users = requests.get(f"{POCKETBASE_URL}/api/collections/bot_users/records", params={"filter": 'is_active=true'}).json()
    user_ids = [u["user_id"] for u in users["items"]]
    assert "111111" in user_ids
    assert "222222" not in user_ids

    requests.delete(f"{POCKETBASE_URL}/api/collections/bot_users/records/{active['id']}", headers={"Authorization": f"Admin {admin_token}"})
    requests.delete(f"{POCKETBASE_URL}/api/collections/bot_users/records/{inactive['id']}", headers={"Authorization": f"Admin {admin_token}"})