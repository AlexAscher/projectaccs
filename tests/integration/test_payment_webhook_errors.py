# tests/integration/test_payment_webhook_errors.py
import pytest
import requests

API_URL = "http://127.0.0.1:5000/api"

def test_webhook_invalid_status():
    resp = requests.post(f"{API_URL}/payments/webhook", json={
        "status": "expired",
        "invoice_id": "inv_123",
        "metadata": {"cart_id": "cart_123"}
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"

def test_webhook_missing_cart_id():
    resp = requests.post(f"{API_URL}/payments/webhook", json={
        "status": "paid",
        "invoice_id": "inv_123",
        "metadata": {}  # нет cart_id
    })
    assert resp.status_code == 400