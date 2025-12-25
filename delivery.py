#!/usr/bin/env python3
"""
Модуль доставки товаров через Telegram бот
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List
from pocketbase import PocketBase
from aiogram import Bot
from aiogram.types import BufferedInputFile
import logging
from activity_logger import log_user_activity

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8158659359:AAE09siTtUSSsN_7tWPcU2ONKYgAZ0xHlaY")

pb = PocketBase("http://127.0.0.1:8090")


def _format_product_label(title: str, type_of_warm: str = "", region: str = "") -> str:
    parts = []
    if title and title.strip():
        parts.append(title.strip())
    if type_of_warm and type_of_warm.strip():
        parts.append(type_of_warm.strip())
    if region and region.strip():
        parts.append(region.strip())
    return " ".join(parts) or (title.strip() if title else "Product")


def _get_product_label(product_id: str, fallback_title: str, cache: Dict[str, str]) -> str:
    if product_id in cache:
        return cache[product_id]

    label = fallback_title or product_id
    try:
        product = pb.collection('products').get_one(product_id)
        title = getattr(product, 'title', '') or fallback_title or product_id
        type_of_warm = getattr(product, 'type_of_warm', '') or ""
        region = getattr(product, 'region_for_filter', '') or ""
        label = _format_product_label(title, type_of_warm, region)
    except Exception as product_error:
        logger.warning(
            "Failed to build product label",
            extra={'product_id': product_id, 'error': str(product_error)}
        )

    final_label = label.strip() or (fallback_title or product_id)
    cache[product_id] = final_label
    return final_label


async def deliver_order(order_id: str, user_telegram_id: int):
    """Доставляет товары заказа пользователю через Telegram"""
    bot = Bot(token=BOT_TOKEN)
    try:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"📦 [DELIVERY] Starting delivery for order {order_id}")
        logger.info(f"📦 [DELIVERY] Target user: {user_telegram_id}")
        logger.info(f"{'=' * 80}\n")

        # Получаем заказ
        logger.info(f"🔍 [DELIVERY] Loading order from PocketBase: {order_id}")
        order = pb.collection('orders').get_one(order_id)
        logger.info(f"✅ [DELIVERY] Order loaded successfully")
        logger.debug(
            f"🔍 [DELIVERY] Order details - status: {getattr(order, 'status', 'unknown')}, "
            f"total_amount: {getattr(order, 'total_amount', 'unknown')}, "
            f"order_id: {getattr(order, 'order_id', 'unknown')}"
        )

        cart_id = getattr(order, 'cart', '')
        logger.info(f"🔍 [DELIVERY] Cart ID: {cart_id if cart_id else 'None'}")

        def fetch_reserved_accounts(product_id: str, quantity: int) -> list:
            """Возвращает ID уже зарезервированных аккаунтов для cart+product"""
            if not cart_id or not product_id or quantity <= 0:
                return []
            try:
                records = pb.collection('accounts').get_full_list(
                    query_params={
                        'filter': f'product="{product_id}" && reserved_cart="{cart_id}" && sold=false',
                        'perPage': max(quantity, 50)
                    }
                )
                account_ids = [rec.id for rec in records[:quantity]]
                if account_ids:
                    logger.debug(
                        "Recovered reserved accounts for product",
                        extra={'order_id': order_id, 'product_id': product_id, 'count': len(account_ids)}
                    )
                return account_ids
            except Exception as fetch_error:
                logger.error(
                    f"Failed to restore reserved accounts for product {product_id}: {fetch_error}"
                )
                return []

        def rebuild_items_from_cart():
            if not cart_id:
                logger.warning(f"Order {order_id} has no cart reference; cannot rebuild items")
                return []
            try:
                cart_records = pb.collection('cart_items').get_full_list(
                    query_params={'filter': f'cart="{cart_id}"'}
                )
            except Exception as cart_error:
                logger.error(f"Failed to load cart items for order {order_id}: {cart_error}")
                return []

            rebuilt = []
            for cart_item in cart_records:
                product_id = getattr(cart_item, 'product', '')
                quantity = getattr(cart_item, 'quantity', 0) or 0
                if not product_id or quantity <= 0:
                    continue

                product_title = getattr(cart_item, 'product_title', '') or product_id
                type_of_warm = None
                region_for_filter = None

                # Получаем полные данные продукта для type_of_warm и region_for_filter
                try:
                    product = pb.collection('products').get_one(product_id)
                    if not product_title:
                        product_title = getattr(product, 'title', product_id)
                    type_of_warm = getattr(product, 'type_of_warm', None)
                    region_for_filter = getattr(product, 'region_for_filter', None)
                except Exception:
                    if not product_title:
                        product_title = product_id

                account_ids = fetch_reserved_accounts(product_id, quantity)
                rebuilt.append({
                    'product_id': product_id,
                    'product_title': product_title,
                    'quantity': quantity,
                    'account_ids': account_ids,
                    'type_of_warm': type_of_warm,
                    'region_for_filter': region_for_filter
                })

            logger.info(
                "Rebuilt order items from cart snapshot",
                extra={'order_id': order_id, 'items_found': len(rebuilt)}
            )
            return rebuilt

        # Получаем элементы заказа
        cart_items = []
        order_items = getattr(order, 'items', []) or []
        logger.info(f"🔍 [DELIVERY] Order items from order.items: {len(order_items)}")
        if order_items:
            logger.debug(f"🔍 [DELIVERY] Raw order.items: {order_items}")
        if not order_items:
            logger.warning(f"⚠️ [DELIVERY] No items in order.items, rebuilding from cart")
            order_items = rebuild_items_from_cart()
            logger.info(f"🔍 [DELIVERY] Rebuilt items count: {len(order_items)}")
        logger.info(f"📦 [DELIVERY] Processing {len(order_items)} item entries")
        for item in order_items:
            cart_items.append({
                'product_id': item['product_id'],
                'product_title': item['product_title'],
                'quantity': item['quantity'],
                'account_ids': item.get('account_ids', []),
                'type_of_warm': item.get('type_of_warm'),
                'region_for_filter': item.get('region_for_filter')
            })

        if cart_items:
            cart_snapshot = [
                {
                    'product_id': item['product_id'],
                    'qty': item['quantity'],
                    'reserved': len(item.get('account_ids', []))
                }
                for item in cart_items
            ]
            logger.debug(f"📋 [DELIVERY] Cart snapshot for order {order_id}: {cart_snapshot}")
        else:
            logger.warning(f"⚠️ [DELIVERY] No cart items reconstructed for order {order_id}")

        # Собираем все аккаунты для доставки
        product_summaries = []
        product_label_cache: Dict[str, str] = {}
        product_payloads: Dict[str, Dict[str, Any]] = {}

        logger.info(f"🔄 [DELIVERY] Starting account collection loop for {len(cart_items)} items")

        for idx, item in enumerate(cart_items):
            product_id = item['product_id']
            quantity = item['quantity']
            account_ids = item.get('account_ids', [])
            product_label = _get_product_label(product_id, item['product_title'], product_label_cache)
            bucket = product_payloads.setdefault(product_id, {'label': product_label, 'accounts': []})

            logger.info(f"\n📦 [DELIVERY] Item {idx + 1}/{len(cart_items)}: {product_label}")
            logger.info(f"   Product ID: {product_id}")
            logger.info(f"   Quantity: {quantity}")
            logger.info(f"   Account IDs: {len(account_ids)} already reserved")
            if account_ids:
                logger.debug(f"   Reserved IDs: {account_ids}")

            if not account_ids:
                account_ids = fetch_reserved_accounts(product_id, quantity)
                if account_ids:
                    item['account_ids'] = account_ids

            # Если аккаунты уже зарезервированы, получаем их данные
            if account_ids:
                logger.info(f"   ✅ [DELIVERY] Item has {len(account_ids)} reserved accounts, fetching data...")
                accounts_data = []
                for acc_id in account_ids:
                    try:
                        logger.debug(f"      🔍 Fetching account: {acc_id}")
                        account = pb.collection('accounts').get_one(acc_id)
                        accounts_data.append(account.data)
                        logger.debug(f"      ✅ Got account data: {account.data[:50]}...")
                    except Exception as e:
                        logger.error(f"      ❌ Failed to get account {acc_id}: {e}")

                bucket['accounts'].extend(accounts_data)
                logger.info(f"   ✅ [DELIVERY] Added {len(accounts_data)} accounts to delivery")
                product_summaries.append(f"{product_label}: {len(accounts_data)} аккаунтов")
            else:
                # Если аккаунты не зарезервированы, резервируем их сейчас
                logger.info(f"Reserving accounts for product {product_id}, quantity {quantity}")

                # Импортируем функцию резервирования
                from cart_service import reserve_accounts_for_cart

                # Создаем временную корзину для резервирования
                temp_cart = pb.collection('carts').create({
                    'cart_payload': '{"items": []}',
                    'user_bot': order.user_bot
                })

                result = reserve_accounts_for_cart(str(temp_cart.id), product_id, quantity, user_telegram_id)
                logger.debug(f"Reserve result for product {product_id}: {result}")

                if result and 'reserved_account_ids' in result:
                    # Получаем данные аккаунтов
                    for acc_id in result['reserved_account_ids']:
                        try:
                            account = pb.collection('accounts').get_one(acc_id)
                            bucket['accounts'].append(account.data)
                        except Exception as e:
                            logger.error(f"Failed to get reserved account {acc_id}: {e}")

                    product_summaries.append(
                        f"{product_label}: {len(result['reserved_account_ids'])} аккаунтов")

                    # Обновляем cart_items с account_ids
                    item['account_ids'] = result['reserved_account_ids']
                else:
                    logger.error(f"Failed to reserve accounts for product {product_id}")
                    product_summaries.append(f"{product_label}: Ошибка резервирования")

            if not account_ids:
                logger.warning(
                    f"❗ [DELIVERY] No accounts attached after processing product {product_id} (qty {quantity})"
                )

        total_accounts_collected = sum(len(payload['accounts']) for payload in product_payloads.values())

        # Помечаем аккаунты как проданные
        if total_accounts_collected:
            from cart_service import mark_accounts_as_sold

            # Собираем все ID аккаунтов
            all_account_ids = []
            for item in cart_items:
                if 'account_ids' in item:
                    all_account_ids.extend(item['account_ids'])

            if all_account_ids:
                logger.debug(
                    f"Marking {len(all_account_ids)} accounts as sold for order {order_id}"
                )
                id_mapping = mark_accounts_as_sold(all_account_ids, order_id, user_telegram_id)
                logger.info(
                    f"✅ [DELIVERY] mark_accounts_as_sold returned {len(id_mapping)} mappings for order {order_id}"
                )

                # Обновляем account_ids в cart_items на новые sold_accounts IDs
                for item in cart_items:
                    if 'account_ids' in item:
                        old_ids = item['account_ids']
                        new_ids = [id_mapping.get(old_id, old_id) for old_id in old_ids]
                        item['account_ids'] = new_ids
                        logger.debug(f"Updated account_ids for product {item.get('product_id')}: {old_ids} → {new_ids}")

                # Обновляем order.items с новыми sold_accounts IDs
                updated_items = []
                for item in cart_items:
                    updated_items.append({
                        'product_id': item.get('product_id'),
                        'product_title': item.get('product_title'),
                        'product_price': item.get('product_price'),
                        'quantity': item.get('quantity'),
                        'type_of_warm': item.get('type_of_warm'),
                        'region_for_filter': item.get('region_for_filter'),
                        'account_ids': item.get('account_ids', [])
                    })

                # Сохраняем обновлённые items в заказе
                pb.collection('orders').update(order.id, {'items': updated_items})
                logger.info(f"✅ [DELIVERY] Updated order.items with {len(id_mapping)} sold_accounts IDs")
            else:
                logger.warning(f"⚠️ [DELIVERY] No account IDs gathered to mark as sold for order {order_id}")

        # Создаем файл с аккаунтами
        if total_accounts_collected:
            logger.info(f"📊 [DELIVERY] Total accounts collected for delivery: {total_accounts_collected}")
            warning_block = "ВНИМАНИЕ: Входите в аккаунт только через прокси страны, аккаунт которой вы купили.\nФормат: логин:пароль:почта\n\n"
            attachments = []

            for product_id, payload in product_payloads.items():
                accounts_list = payload['accounts']
                if not accounts_list:
                    continue

                label = payload['label']
                filename = f"order_{order.order_id}_{product_id}.txt"
                file_content = f"{label}\n{warning_block}" + "\n".join(accounts_list)
                logger.info(
                    f"📄 [DELIVERY] Prepared file {filename} with {len(accounts_list)} accounts for {label}"
                )
                logger.debug(
                    f"📄 [DELIVERY] File preview (first 200 chars): {file_content[:200]}..."
                )
                attachments.append((filename, file_content, label))

            # Создаем сводку заказа
            summary = f"🎉 Ваш заказ #{order.order_id} готов!\n\n"
            summary += "📦 Состав заказа:\n"
            for prod_summary in product_summaries:
                summary += f"• {prod_summary}\n"
            summary += f"\n💰 Оплачено: {order.total_amount} USDT\n"
            summary += f"📅 Дата оплаты: {order.paid_at[:19] if hasattr(order, 'paid_at') else datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            summary += "📄 Аккаунты во вложении"

            try:
                # Отправляем сообщение с подтверждением
                logger.info(f"📤 [DELIVERY] Sending summary message to user {user_telegram_id}")
                await bot.send_message(
                    chat_id=user_telegram_id,
                    text=summary
                )
                logger.info(f"✅ [DELIVERY] Summary message sent")

                # Отправляем файлы по категориям
                for filename, file_content, label in attachments:
                    file_data = BufferedInputFile(
                        file_content.encode('utf-8'),
                        filename=filename
                    )
                    logger.info(
                        f"📤 [DELIVERY] Sending document {filename} ({label}) to user {user_telegram_id}"
                    )
                    await bot.send_document(
                        chat_id=user_telegram_id,
                        document=file_data,
                        caption=f"🔐 {label}"
                    )
                    logger.info(
                        f"✅ [DELIVERY] Document {filename} for {label} sent"
                    )

                logger.info(f"✅✅✅ [DELIVERY] Successfully delivered order {order_id} to user {user_telegram_id}")

                # Обновляем статус заказа
                logger.info(f"🔄 [DELIVERY] Updating order status to 'delivered'")
                pb.collection('orders').update(order.id, {
                    'status': 'delivered',
                    'delivered_at': datetime.now().isoformat()
                })
                await asyncio.to_thread(
                    log_user_activity,
                    pb,
                    user_telegram_id,
                    'order_delivered',
                    f"Заказ #{getattr(order, 'order_id', order.id)} доставлен",
                    'bot',
                    {
                        'order_id': getattr(order, 'order_id', order.id),
                        'products': product_summaries,
                        'total_accounts': total_accounts_collected
                    },
                    getattr(order, 'user_bot', None)
                )
                logger.info(f"✅ [DELIVERY] Order status updated")
                logger.info(f"{'=' * 80}\n")

            except Exception as e:
                logger.exception(f"Failed to send delivery to user {user_telegram_id}: {e}")

                # Сохраняем файл локально для ручной доставки
                try:
                    for filename, file_content, _ in attachments:
                        with open(f"/tmp/{filename}", 'w', encoding='utf-8') as f:
                            f.write(file_content)
                        logger.info(f"Saved order file to /tmp/{filename} for manual delivery")
                except:
                    pass

        else:
            # Если аккаунты не найдены, отправляем сообщение об ошибке
            logger.error(f"❌ [DELIVERY] No accounts found for order {order_id}!")
            logger.error(f"❌ [DELIVERY] cart_items: {cart_items}")
            logger.error(f"❌ [DELIVERY] product_payloads: {product_payloads}")
            error_msg = f"❌ К сожалению, произошла ошибка при подготовке вашего заказа #{order.order_id}.\n\n"
            error_msg += "Пожалуйста, свяжитесь с поддержкой для решения проблемы."

            try:
                logger.info(f"📤 [DELIVERY] Sending error notification to user {user_telegram_id}")
                await bot.send_message(
                    chat_id=user_telegram_id,
                    text=error_msg
                )
                logger.info(f"✅ [DELIVERY] Error notification sent")
            except Exception as e:
                logger.exception(f"❌ [DELIVERY] Failed to send error message to user {user_telegram_id}: {e}")

    except Exception as e:
        logger.exception(f"Delivery error for order {order_id}: {e}")

        # Пытаемся отправить сообщение об ошибке
        try:
            await bot.send_message(
                chat_id=user_telegram_id,
                text="❌ Произошла ошибка при доставке заказа. Пожалуйста, свяжитесь с поддержкой."
            )
        except Exception as notify_error:
            logger.exception(
                f"❌ [DELIVERY] Failed to notify user {user_telegram_id} about delivery error: {notify_error}"
            )
    finally:
        session = bot.session
        if session and not session.closed:
            logger.debug(f"🧹 [DELIVERY] Closing telegram session for order {order_id}")
            await session.close()


async def test_delivery():
    """Тестовая функция для проверки доставки"""
    # Пример использования
    await deliver_order("test_order_id", 123456789)


if __name__ == "__main__":
    # Тест доставки
    asyncio.run(test_delivery())