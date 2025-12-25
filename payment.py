import requests
import os
import logging

CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN", "44761:AAuylenLuQHuwvjQh1ak9PwGkLqYHrxM0Zt")
CRYPTO_API_URL = "https://testnet-pay.crypt.bot/api"  # Для тестнета

logger = logging.getLogger(__name__)

def create_invoice(asset: str, amount: float, description: str, payload: str):
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    data = {
        "asset": asset,
        "amount": amount,
        "description": description,
        "hidden_message": "Спасибо за покупку премиум аккаунтов!",
        "payload": payload,
        # Crypto Pay API принимает только фиксированные значения paid_btn_name
        # (callback, open_bot, open_channel, open_link и т.д.)
        "paid_btn_name": "callback",
        "paid_btn_url": "https://t.me/projectaccs_bot"
    }

    logger.info(
        "Creating Crypto Pay invoice",
        extra={
            "asset": asset,
            "amount": amount,
            "payload": payload,
            "description": description
        }
    )

    response = requests.post(f"{CRYPTO_API_URL}/createInvoice", json=data, headers=headers)

    if not response.ok:
        try:
            error_payload = response.json()
        except Exception:
            error_payload = response.text
        logger.error(
            "Crypto Pay API error",
            extra={
                "status": response.status_code,
                "response": error_payload,
                "request_data": data
            }
        )
        response.raise_for_status()

    result = response.json()["result"]

    return {
        'invoice_id': result['invoice_id'],
        'bot_invoice_url': result['bot_invoice_url'],
        'pay_url': result.get('pay_url', ''),
        'amount': amount,
        'asset': asset,
        'description': description
    }


def get_invoice(invoice_id):
    """Возвращает информацию о счёте Crypto Pay по его ID"""
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}

    try:
        normalized_id = int(str(invoice_id).strip())
    except (ValueError, TypeError):
        normalized_id = str(invoice_id).strip()

    data = {
        "invoice_ids": [normalized_id]
    }

    response = requests.post(f"{CRYPTO_API_URL}/getInvoices", json=data, headers=headers)

    if not response.ok:
        try:
            error_payload = response.json()
        except Exception:
            error_payload = response.text
        logger.error(
            "Crypto Pay getInvoice error",
            extra={
                "status": response.status_code,
                "response": error_payload,
                "request_data": data
            }
        )
        response.raise_for_status()

    result = response.json().get("result", {})
    items = result.get("items", [])
    return items[0] if items else None
