#!/usr/bin/env python3
"""
Simple Flask API для резервирования аккаунтов
Обёртка над cart_service.py для вызова из фронтенда
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from cart_service import (
    reserve_accounts_for_cart,
    release_reservation,
    release_expired_reservations,
    mark_accounts_as_sold,
    get_available_count
)
from pocketbase import Client
from pocketbase.models.record import Record
from pocketbase.utils import camel_to_snake
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для локальной разработки

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POCKETBASE_URL = os.getenv("POCKETBASE_URL", "http://127.0.0.1:8090")


def _coerce_record_value(value: Any) -> Any:
    """Подготавливает значение для JSON-совместимого ответа."""
    if isinstance(value, Record):
        return _record_to_plain_dict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_coerce_record_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _coerce_record_value(val) for key, val in value.items()}
    return value


def _record_to_plain_dict(record: Any) -> Dict[str, Any]:
    """Возвращает словарь с полями записи PocketBase."""
    if isinstance(record, dict):
        return {key: _coerce_record_value(val) for key, val in record.items()}

    if isinstance(record, Record):
        payload: Dict[str, Any] = {}
        for key, value in vars(record).items():
            if key.startswith('_'):
                continue
            payload[key] = _coerce_record_value(value)

        expand_data = payload.get('expand')
        if isinstance(expand_data, dict):
            normalized_expand = {}
            for expand_key, expand_value in expand_data.items():
                normalized_key = camel_to_snake(expand_key).replace('@', '')
                normalized_expand[normalized_key] = _coerce_record_value(expand_value)
            payload['expand'] = normalized_expand

        return payload

    if hasattr(record, '__dict__'):
        return {key: _coerce_record_value(val) for key, val in vars(record).items() if not key.startswith('_')}

    try:
        return {key: _coerce_record_value(val) for key, val in dict(record).items()}  # type: ignore[arg-type]
    except Exception:
        return {}


def _sanitize_filter_value(value: str) -> str:
    """Экранирует кавычки для PocketBase фильтра."""
    return (value or "").replace('"', '\\"')


ACTIVITY_EVENT_LABELS = {
    'command_start': 'Запуск бота',
    'command_menu': 'Главное меню',
    'catalog_opened': 'Открытие каталога',
    'invoice_created': 'Создан счёт',
    'order_paid': 'Оплата получена',
    'order_delivered': 'Доставка выполнена'
}


def _normalize_activity_entry(entry: Dict[str, Any], source: str = 'user_activity') -> Dict[str, str]:
    created = entry.get('created') or entry.get('updated') or datetime.utcnow().isoformat()
    if source == 'user_activity':
        event_type = entry.get('event_type') or 'activity'
        label = ACTIVITY_EVENT_LABELS.get(event_type, 'Активность')
        details = entry.get('details')
        text = f"{label}: {details}" if details else label
    else:
        text = entry.get('action') or entry.get('details') or entry.get('event_type') or 'Активность'
    return {
        'created': created,
        'text': text
    }


def _find_user_by_session_token(pb_client: Client, session_token: str):
    filter_value = _sanitize_filter_value(session_token)
    return pb_client.collection('bot_users').get_first_list_item(f'session_token="{filter_value}"')


def _fetch_orders_for_user(pb_client: Client, user_record_id: str, limit: int = 20) -> Tuple[List[Dict[str, Any]], int]:
    try:
        result = pb_client.collection('orders').get_list(
            1,
            limit,
            {
                'filter': f'user_bot="{user_record_id}"',
                'sort': '-created',
                'expand': 'order_items,order_items.product'
            }
        )
        items = [_record_to_plain_dict(item) for item in result.items]
        total = getattr(result, 'total_items', len(items))
        return items, total
    except Exception as orders_error:
        logger.error(f"Failed to load orders for {user_record_id}: {orders_error}")
        return [], 0


def _fetch_activity_for_user(pb_client: Client, user_record_id: str, last_activity: str = None, limit: int = 20) -> \
List[Dict[str, str]]:
    try:
        primary = pb_client.collection('user_activity').get_list(
            1,
            limit,
            {
                'filter': f'user_bot="{user_record_id}"',
                'sort': '-created'
            }
        )
        if primary.items:
            return [_normalize_activity_entry(_record_to_plain_dict(entry), 'user_activity') for entry in primary.items]
    except Exception as primary_error:
        logger.warning(f"user_activity fetch failed for {user_record_id}: {primary_error}")

    try:
        fallback = pb_client.collection('audit_logs').get_list(
            1,
            limit,
            {
                'filter': f'entity_type="bot_user" && entity_id="{user_record_id}"',
                'sort': '-created'
            }
        )
        if fallback.items:
            return [_normalize_activity_entry(_record_to_plain_dict(entry), 'audit_logs') for entry in fallback.items]
    except Exception as fallback_error:
        logger.warning(f"audit_logs fetch failed for {user_record_id}: {fallback_error}")

    if last_activity:
        return [{'created': last_activity, 'text': 'Последняя активность'}]
    return []


@app.route('/api/cart/reserve', methods=['POST'])
def reserve():
    """Резервирует аккаунты для корзины"""
    try:
        data = request.get_json()
        cart_id = data.get('cart_id')
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        user_id = data.get('user_id')  # Опционально

        if not cart_id or not product_id:
            return jsonify({'error': 'Missing cart_id or product_id'}), 400

        result = reserve_accounts_for_cart(cart_id, product_id, quantity, user_id)
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Reserve error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/cart/release', methods=['POST'])
def release():
    """Освобождает резервацию"""
    try:
        data = request.get_json()
        reservation_id = data.get('reservation_id')
        cart_id = data.get('cart_id')

        if not reservation_id and not cart_id:
            return jsonify({'error': 'Missing reservation_id or cart_id'}), 400

        count = release_reservation(
            reservation_id=reservation_id,
            cart_id=cart_id
        )
        return jsonify({'released': count}), 200

    except Exception as e:
        logger.error(f"Release error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/cart/release-accounts', methods=['POST'])
def release_accounts():
    """Освобождает конкретные аккаунты"""
    try:
        data = request.get_json()
        account_ids = data.get('account_ids', [])

        if not account_ids:
            return jsonify({'error': 'Missing account_ids'}), 400

        # Освобождаем каждый аккаунт и обновляем cart_items
        from pocketbase import Client
        from cart_service import update_cart_item_quantity
        pb = Client('http://127.0.0.1:8090')

        # Группируем по cart и product для обновления cart_items
        cart_product_counts = {}
        released = 0

        for acc_id in account_ids:
            try:
                # Получаем информацию об аккаунте перед освобождением
                account = pb.collection('accounts').get_one(acc_id)
                cart_id = getattr(account, 'reserved_cart', '')
                product_id = getattr(account, 'product', '')

                # Освобождаем аккаунт
                pb.collection('accounts').update(acc_id, {
                    'reserved_cart': '',
                    'reserved_by': '',
                    'reserved_until': '',
                    'reservation_id': ''
                })
                released += 1

                # Считаем для обновления cart_items
                if cart_id and product_id:
                    key = f"{cart_id}:{product_id}"
                    cart_product_counts[key] = cart_product_counts.get(key, 0) + 1

                logger.info(f"Released account {acc_id}")
            except Exception as e:
                logger.error(f"Failed to release account {acc_id}: {e}")

        # Обновляем cart_items
        for key, count in cart_product_counts.items():
            cart_id, product_id = key.split(':')
            try:
                update_cart_item_quantity(cart_id, product_id, -count)
            except Exception as e:
                logger.error(f"Failed to update cart_item for {key}: {e}")

        return jsonify({'released': released}), 200

    except Exception as e:
        logger.error(f"Release accounts error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/cart/cleanup', methods=['POST'])
def cleanup():
    """Очищает просроченные резервации"""
    try:
        count = release_expired_reservations()
        return jsonify({'cleaned': count}), 200
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/cart/mark-sold', methods=['POST'])
def mark_sold():
    """Помечает аккаунты как проданные"""
    try:
        data = request.get_json()
        account_ids = data.get('account_ids', [])
        order_id = data.get('order_id')
        buyer_id = data.get('buyer_id')

        if not account_ids:
            return jsonify({'error': 'Missing account_ids'}), 400

        count = mark_accounts_as_sold(account_ids, order_id, buyer_id)
        return jsonify({'marked_sold': count}), 200

    except Exception as e:
        logger.error(f"Mark sold error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/products/<product_id>/available', methods=['GET'])
def get_product_available(product_id):
    """Возвращает количество доступных аккаунтов для продукта"""
    try:
        count = get_available_count(product_id)
        return jsonify({'product_id': product_id, 'available': count}), 200
    except Exception as e:
        logger.error(f"Get available error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/profile/history', methods=['POST'])
def get_profile_history():
    """Возвращает историю заказов и активности по session_token"""
    data = request.get_json(silent=True) or {}
    session_token = data.get('session_token') or request.headers.get('X-Session-Token')

    if not session_token:
        return jsonify({'error': 'Missing session_token'}), 400

    try:
        pb = Client(POCKETBASE_URL)
    except Exception as conn_error:
        logger.error(f"Failed to initialize PocketBase client: {conn_error}")
        return jsonify({'error': 'PocketBase unavailable'}), 503

    try:
        user = _find_user_by_session_token(pb, session_token)
    except Exception as resolve_error:
        logger.warning(f"User lookup by session_token failed: {resolve_error}")
        return jsonify({'error': 'User not found'}), 404

    user_id = getattr(user, 'id', None)
    if not user_id:
        logger.warning('User record missing id during profile history lookup')
        return jsonify({'error': 'User not found'}), 404

    orders, total_orders = _fetch_orders_for_user(pb, user_id)
    activity = _fetch_activity_for_user(pb, user_id, getattr(user, 'last_activity', None))

    return jsonify({
        'user': {
            'id': user_id,
            'telegram_id': getattr(user, 'user_id', None),
            'username': getattr(user, 'username', None)
        },
        'orders': orders,
        'activity': activity,
        'meta': {
            'orders_total': total_orders
        }
    }), 200


@app.route('/api/orders/create', methods=['POST'])
def create_order():
    """Создает заказ и платеж"""
    try:
        data = request.get_json()
        cart_id = data.get('cart_id')
        user_id = data.get('user_id')
        items = data.get('items', [])
        total_amount = data.get('total_amount', 0)

        if not cart_id or not user_id or not items:
            return jsonify({'error': 'Missing required fields: cart_id, user_id, items'}), 400

        # Генерируем уникальный ID заказа
        order_id = str(uuid.uuid4())[:8].upper()

        # Создаем заказ в PocketBase
        from pocketbase import Client
        pb = Client('http://127.0.0.1:8090')

        # Получаем информацию о пользователе
        user = None
        try:
            # Пытаемся найти по ID записи (его присылает сайт)
            user = pb.collection('bot_users').get_one(user_id)
            logger.debug(f"Found bot_user by record id: {user_id}")
        except Exception:
            try:
                # Фолбэк: ищем по Telegram user_id для совместимости с ботом
                user = pb.collection('bot_users').get_first_list_item(f'user_id="{user_id}"')
                logger.debug(f"Found bot_user by telegram user_id: {user_id}")
            except Exception:
                return jsonify({'error': 'User not found'}), 404

        # Создаем заказ
        order_data = {
            'order_id': order_id,
            'user_bot': user.id,
            'cart': cart_id,
            'items': items,
            'total_amount': total_amount,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }

        order = pb.collection('orders').create(order_data)

        description = f"Заказ #{order_id} - {len(items)} товаров"

        # Фиксируем платеж, который позже обработает Telegram-бот
        payment_record = pb.collection('payments').create({
            'order': order.id,
            'user_bot': user.id,
            'payment_id': '',
            'amount': total_amount,
            'currency': 'USDT',
            'status': 'awaiting_invoice',
            'payment_url': '',
            'paid_at': '',
            'created_at': datetime.now().isoformat()
        })

        logger.info(f"Created order {order_id} waiting for Telegram invoice (payment record {payment_record.id})")

        return jsonify({
            'order_id': order_id,
            'status': 'awaiting_invoice',
            'amount': total_amount,
            'currency': 'USDT',
            'description': description,
            'message': 'Ссылка на оплату придёт в Telegram-боте'
        }), 200

    except Exception as e:
        logger.error(f"Create order error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/payments/webhook', methods=['POST'])
def payment_webhook():
    """Обрабатывает вебхуки от Crypto Bot"""
    try:
        data = request.get_json()
        logger.info(f"\n{'=' * 80}")
        logger.info(f"📥 [WEBHOOK] Payment webhook received")
        logger.info(f"📥 [WEBHOOK] Data: {data}")
        logger.info(f"{'=' * 80}\n")

        # Проверяем статус платежа
        if data.get('status') == 'paid':
            logger.info(f"✅ [WEBHOOK] Status is 'paid', processing...")
            invoice_id = data.get('invoice_id')
            if not invoice_id:
                logger.error(f"❌ [WEBHOOK] Missing invoice_id in webhook data")
                return jsonify({'error': 'Missing invoice_id'}), 400

            logger.info(f"🔍 [WEBHOOK] Looking for payment with invoice_id: {invoice_id}")

            # Находим платеж в PocketBase
            from pocketbase import Client
            pb = Client('http://127.0.0.1:8090')

            try:
                logger.debug(f"🔍 [WEBHOOK] Querying PocketBase: payment_id=\"{invoice_id}\"")
                payment = pb.collection('payments').get_first_list_item(f'payment_id="{invoice_id}"')
                logger.info(f"✅ [WEBHOOK] Payment found: {payment.id}")
                logger.debug(f"🔍 [WEBHOOK] Payment details: order={payment.order}, status={payment.status}")
            except Exception as e:
                logger.error(f"❌ [WEBHOOK] Payment not found for invoice {invoice_id}: {e}")
                return jsonify({'error': 'Payment not found'}), 404

            # Переводим платеж в промежуточный статус, чтобы исключить двойную обработку
            try:
                logger.info(f"🔄 [WEBHOOK] Setting payment status to 'processing'")
                pb.collection('payments').update(payment.id, {'status': 'processing'})
                logger.info(f"✅ [WEBHOOK] Payment status updated to processing")
            except Exception as e:
                logger.warning(f"⚠️ [WEBHOOK] Failed to update payment status to processing: {e}")
                pass

            logger.info(f"🚀 [WEBHOOK] Calling _finalize_paid_payment...")
            _finalize_paid_payment(pb, payment, invoice_payload=data)
            logger.info(f"✅ [WEBHOOK] _finalize_paid_payment completed")
        else:
            logger.warning(f"⚠️ [WEBHOOK] Status is not 'paid': {data.get('status')}")

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Payment webhook error: {e}")
        logger.exception(f"❌ [WEBHOOK] Full traceback:")
        return jsonify({'error': str(e)}), 500


def _finalize_paid_payment(pb: Client, payment_record, invoice_payload=None):
    """Обновляет статусы заказа/платежа и запускает доставку"""
    invoice_id = getattr(payment_record, 'payment_id', 'unknown')
    paid_at = (invoice_payload or {}).get('paid_at') or datetime.now().isoformat()

    logger.info(f"\n{'=' * 80}")
    logger.info(f"🎯 [FINALIZE] Finalizing payment {invoice_id}")
    logger.info(f"🎯 [FINALIZE] Order: {payment_record.order}")
    logger.info(f"🎯 [FINALIZE] Paid at: {paid_at}")
    logger.info(f"{'=' * 80}\n")

    # Обновляем статус платежа
    logger.info(f"🔄 [FINALIZE] Updating payment status to 'paid'")
    pb.collection('payments').update(payment_record.id, {
        'status': 'paid',
        'paid_at': paid_at
    })
    logger.info(f"✅ [FINALIZE] Payment status updated")

    # Обновляем заказ
    logger.info(f"🔍 [FINALIZE] Loading order: {payment_record.order}")
    order = pb.collection('orders').get_one(payment_record.order)
    logger.info(f"✅ [FINALIZE] Order loaded: {order.id}")
    logger.debug(f"🔍 [FINALIZE] Order details: order_id={order.order_id}, total_amount={order.total_amount}")

    logger.info(f"🔄 [FINALIZE] Updating order status to 'paid'")
    pb.collection('orders').update(order.id, {
        'status': 'paid',
        'paid_at': paid_at
    })
    logger.info(f"✅ [FINALIZE] Order status updated")

    # Доставляем заказ пользователю
    user_relation_id = (
            getattr(order, 'user_bot', None)
            or getattr(payment_record, 'user_bot', None)
    )

    logger.info(f"🔍 [FINALIZE] User relation ID: {user_relation_id}")

    if not user_relation_id:
        logger.error(
            f"❌ [FINALIZE] Cannot deliver order {order.id}: user relation missing"
        )
        logger.error(f"❌ [FINALIZE] Order user_bot: {getattr(order, 'user_bot', None)}")
        logger.error(f"❌ [FINALIZE] Payment user_bot: {getattr(payment_record, 'user_bot', None)}")
        return

    logger.info(f"🔍 [FINALIZE] Loading user from bot_users: {user_relation_id}")
    user = pb.collection('bot_users').get_one(user_relation_id)
    logger.info(f"✅ [FINALIZE] User loaded: {user.user_id}")
    logger.debug(f"🔍 [FINALIZE] User details: username={getattr(user, 'username', 'N/A')}")

    from delivery import deliver_order
    import asyncio

    logger.info(f"📦 [FINALIZE] Starting delivery process...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        logger.info(
            f"📦 [FINALIZE] Calling deliver_order({order.id}, {user.user_id}) on loop {id(loop)}"
        )
        loop.run_until_complete(deliver_order(order.id, user.user_id))
        logger.info(f"✅ [FINALIZE] Payment {invoice_id} processed successfully")
        logger.info(f"{'=' * 80}\n")
    except Exception as e:
        logger.error(f"❌ [FINALIZE] Delivery failed: {e}")
        logger.exception(f"❌ [FINALIZE] Full delivery error traceback:")
    finally:
        logger.debug(f"🧹 [FINALIZE] Closing delivery loop {id(loop)} for invoice {invoice_id}")
        loop.close()


@app.route('/api/orders/<order_id>/cancel', methods=['POST'])
def cancel_order(order_id):
    """Отменяет неоплаченный заказ и освобождает резерв"""
    try:
        logger.info(f"[CANCEL ORDER] Starting cancellation for order {order_id}")

        # Создаем клиент PocketBase
        pb = Client('http://127.0.0.1:8090')

        # Находим заказ
        order = pb.collection('orders').get_first_list_item(f'order_id="{order_id}"')

        # Проверяем статус - отменять можно только pending/awaiting_payment
        order_status = getattr(order, 'status', 'unknown')
        if order_status in ['paid', 'delivered']:
            logger.warning(f"[CANCEL ORDER] Cannot cancel order {order_id} with status {order_status}")
            return jsonify({'error': f'Cannot cancel order with status {order_status}'}), 400

        # Получаем список зарезервированных аккаунтов из заказа
        cart_id = getattr(order, 'cart', '')
        released_count = 0

        if cart_id:
            # Находим все зарезервированные аккаунты для этой корзины
            try:
                reserved_accounts = pb.collection('accounts').get_full_list(
                    query_params={
                        'filter': f'reserved_cart="{cart_id}"',
                        'perPage': 500
                    }
                )

                logger.info(f"[CANCEL ORDER] Found {len(reserved_accounts)} reserved accounts for cart {cart_id}")

                # Освобождаем каждый аккаунт
                for account in reserved_accounts:
                    pb.collection('accounts').update(account.id, {
                        'reserved_cart': '',
                        'reservation_id': '',
                        'reserved_until': '',
                        'reserved_by': ''
                    })
                    released_count += 1
                    logger.debug(f"[CANCEL ORDER] Released account {account.id}")

                logger.info(f"[CANCEL ORDER] Released {released_count} accounts")

            except Exception as release_error:
                logger.error(f"[CANCEL ORDER] Failed to release accounts: {release_error}")

        # Обновляем статус заказа
        pb.collection('orders').update(order.id, {
            'status': 'cancelled'
        })

        # Обновляем статус платежа если есть
        try:
            payment = pb.collection('payments').get_first_list_item(f'order="{order.id}"')
            pb.collection('payments').update(payment.id, {
                'status': 'cancelled'
            })
        except Exception:
            pass  # Платёж может не существовать

        logger.info(f"[CANCEL ORDER] Order {order_id} cancelled successfully, released {released_count} accounts")

        return jsonify({
            'success': True,
            'order_id': order_id,
            'status': 'cancelled',
            'released_accounts': released_count
        }), 200

    except Exception as e:
        logger.error(f"[CANCEL ORDER] Error cancelling order {order_id}: {e}")
        import traceback
        logger.error(f"[CANCEL ORDER] Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/orders/<order_id>/payment-status', methods=['GET'])
def check_order_payment_status(order_id):
    """Проверяет статус оплаты заказа"""
    try:
        from payment import get_invoice

        # Создаем клиент PocketBase
        pb = Client('http://127.0.0.1:8090')

        # Находим заказ
        order = pb.collection('orders').get_first_list_item(f'order_id="{order_id}"')

        # Находим платёж
        payment = pb.collection('payments').get_first_list_item(f'order="{order.id}"')

        payment_status = getattr(payment, 'status', 'unknown')
        invoice_id = getattr(payment, 'payment_id', '')

        result = {
            'order_id': order_id,
            'payment_status': payment_status,
            'order_status': getattr(order, 'status', 'unknown'),
            'invoice_id': invoice_id
        }

        # Если есть invoice_id, проверяем статус в CryptoBot
        if invoice_id and payment_status not in ['paid', 'delivered']:
            try:
                invoice_data = get_invoice(invoice_id)
                if invoice_data:
                    crypto_status = invoice_data.get('status', 'unknown')
                    result['crypto_status'] = crypto_status

                    # Если CryptoBot показывает paid, а у нас нет - обновляем
                    if crypto_status == 'paid' and payment_status != 'paid':
                        logger.info(f"Payment {invoice_id} is paid in CryptoBot but not in DB, triggering webhook")
                        # Вызываем webhook для обработки оплаты
                        paid_at = invoice_data.get('paid_at', datetime.now().isoformat())
                        pb.collection('payments').update(payment.id, {
                            'status': 'paid',
                            'paid_at': paid_at
                        })
                        pb.collection('orders').update(order.id, {
                            'status': 'paid',
                            'paid_at': paid_at
                        })
                        result['payment_status'] = 'paid'
                        result['order_status'] = 'paid'
                        result['updated'] = True
            except Exception as crypto_error:
                logger.error(f"Failed to check CryptoBot status: {crypto_error}")

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Check payment status error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    logger.info("Starting API server on http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)
