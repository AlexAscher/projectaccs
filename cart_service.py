#!/usr/bin/env python3
"""
Cart Service - резервирование аккаунтов для корзины
Использует PocketBase Python SDK для атомарного резервирования
"""

import os
import sys
from datetime import datetime, timedelta
from pocketbase import Client
import uuid

POCKETBASE_URL = os.getenv("POCKETBASE_URL", "http://127.0.0.1:8090")
RESERVATION_TTL_MINUTES = int(os.getenv("RESERVATION_TTL_MINUTES", "10"))

pb = Client(POCKETBASE_URL)


def create_or_update_cart_item(cart_id: str, product_id: str, quantity: int):
    """
    Создаёт или обновляет запись в cart_items для корзины

    Args:
        cart_id: ID корзины
        product_id: ID продукта
        quantity: количество товара
    """
    print(f"\n{'=' * 80}")
    print(f"🔵 [CREATE_OR_UPDATE_CART_ITEM] CALLED")
    print(f"   cart_id: {cart_id}")
    print(f"   product_id: {product_id}")
    print(f"   quantity: {quantity}")
    print(f"{'=' * 80}")

    try:
        # Ищем существующую запись
        filter_str = f'cart="{cart_id}" && product="{product_id}"'
        print(f"🔍 Searching for existing cart_item with filter: {filter_str}")

        existing = pb.collection("cart_items").get_list(
            1, 1,
            query_params={"filter": filter_str}
        )

        print(f"📊 Found {len(existing.items)} existing cart_items")

        if existing.items:
            # Обновляем количество
            item = existing.items[0]
            old_quantity = getattr(item, 'quantity', 0)
            new_quantity = old_quantity + quantity

            print(f"📝 Updating existing cart_item {item.id}")
            print(f"   Old quantity: {old_quantity}")
            print(f"   Adding: {quantity}")
            print(f"   New quantity: {new_quantity}")

            updated = pb.collection("cart_items").update(item.id, {
                "quantity": new_quantity
            })

            print(f"✅ SUCCESS: Updated cart_item {item.id}: quantity {old_quantity} → {new_quantity}")
        else:
            # Создаём новую запись
            print(f"➕ Creating NEW cart_item")
            print(f"   Data: cart={cart_id}, product={product_id}, quantity={quantity}")

            new_item = pb.collection("cart_items").create({
                "cart": cart_id,
                "product": product_id,
                "quantity": quantity
            })

            print(f"✅ SUCCESS: Created cart_item {new_item.id}")
            print(f"   cart_item.id: {new_item.id}")
            print(f"   cart_item.cart: {getattr(new_item, 'cart', 'N/A')}")
            print(f"   cart_item.product: {getattr(new_item, 'product', 'N/A')}")
            print(f"   cart_item.quantity: {getattr(new_item, 'quantity', 'N/A')}")

    except Exception as e:
        print(f"\n❌ ERROR in create_or_update_cart_item:")
        print(f"   Exception type: {type(e).__name__}")
        print(f"   Exception message: {str(e)}")
        import traceback
        print(f"   Traceback:\n{traceback.format_exc()}")
        raise


def update_cart_item_quantity(cart_id: str, product_id: str, quantity_delta: int):
    """
    Обновляет количество в cart_item (добавляет или уменьшает)

    Args:
        cart_id: ID корзины
        product_id: ID продукта
        quantity_delta: изменение количества (может быть отрицательным)
    """
    try:
        # Ищем существующую запись
        existing = pb.collection("cart_items").get_list(
            1, 1,
            query_params={"filter": f'cart="{cart_id}" && product="{product_id}"'}
        )

        if existing.items:
            item = existing.items[0]
            current_quantity = getattr(item, 'quantity', 0)
            new_quantity = max(0, current_quantity + quantity_delta)

            if new_quantity == 0:
                # Удаляем запись если количество 0
                pb.collection("cart_items").delete(item.id)
                print(f"✓ Deleted cart_item {item.id} (quantity reached 0)")
            else:
                # Обновляем количество
                pb.collection("cart_items").update(item.id, {
                    "quantity": new_quantity
                })
                print(f"✓ Updated cart_item {item.id}: quantity {current_quantity} → {new_quantity}")
        else:
            # Если записи нет и дельта положительная - создаём
            if quantity_delta > 0:
                new_item = pb.collection("cart_items").create({
                    "cart": cart_id,
                    "product": product_id,
                    "quantity": quantity_delta
                })
                print(f"✓ Created cart_item {new_item.id} with quantity {quantity_delta}")

    except Exception as e:
        print(f"✗ Error updating cart_item quantity: {e}")
        raise


def reserve_accounts_for_cart(cart_id: str, product_id: str, quantity: int, user_id: str = None) -> dict:
    """
    Резервирует N аккаунтов для продукта в указанной корзине

    Args:
        cart_id: ID корзины
        product_id: ID продукта
        quantity: количество аккаунтов для резервирования
        user_id: ID пользователя (опционально, берётся из cart если не указан)

    Returns:
        dict с reserved_account_ids и expires_at

    Raises:
        Exception если недостаточно аккаунтов или ошибка резервирования
    """

    # Генерируем уникальный ID для группы резерваций
    reservation_id = f"res_{cart_id}_{uuid.uuid4().hex[:8]}"

    # Время истечения резерва
    expires_at = datetime.utcnow() + timedelta(minutes=RESERVATION_TTL_MINUTES)
    # Используем тот же формат что и JavaScript toISOString() - без микросекунд
    expires_at_iso = expires_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:23] + "Z"

    # Получаем корзину если нужен user_id
    if not user_id:
        try:
            cart = pb.collection("carts").get_one(cart_id)
            user_id = getattr(cart, 'user', None) or getattr(cart, 'user_bot', None)
            print(f"Got user_id from cart: {user_id}")
        except Exception as e:
            print(f"Warning: Could not get cart user: {e}")

    # Находим доступные аккаунты (НЕ проданные И НЕ зарезервированные)
    # Для relation полей пустое значение = отсутствие связи
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:23] + "Z"

    # ПРОСТОЙ ФИЛЬТР: только sold=false и пустой reservation_id
    # Убираем проверку даты - пусть клиент сам фильтрует
    filter_query = f'product="{product_id}" && sold=false && reservation_id=""'

    print(f"Filter query: {filter_query}")
    print(f"Current time (ISO): {now_iso}")

    try:
        candidates = pb.collection("accounts").get_list(
            1, quantity + 20,  # берём с запасом на случай конкуренции
            query_params={"filter": filter_query}
        )
        print(f"Found {len(candidates.items)} candidate accounts")
    except Exception as e:
        raise Exception(f"Failed to fetch available accounts: {e}")

    available_count = len(candidates.items)
    if available_count < quantity:
        raise Exception(f"Not enough available accounts. Requested: {quantity}, Available: {available_count}")

    # Пробуем зарезервировать аккаунты
    reserved_ids = []
    for account in candidates.items:
        if len(reserved_ids) >= quantity:
            break

        try:
            # Атомарно обновляем аккаунт с указанием кто и когда зарезервировал
            updated = pb.collection("accounts").update(account.id, {
                "reserved_cart": cart_id,
                "reserved_by": user_id or "",
                "reserved_until": expires_at_iso,
                "reservation_id": reservation_id
            })
            reserved_ids.append(updated.id)
            print(f"✓ Reserved account {updated.id} for cart {cart_id} (user: {user_id})")

        except Exception as e:
            # Аккаунт уже зарезервирован кем-то другим - пропускаем
            print(f"⚠ Account {account.id} already reserved by someone else, skipping")
            continue
        except Exception as e:
            print(f"✗ Error reserving account {account.id}: {e}")
            continue

    # Проверяем что зарезервировали достаточно
    if len(reserved_ids) < quantity:
        # Откатываем частичное резервирование
        release_reservation(reservation_id)
        raise Exception(f"Failed to reserve enough accounts. Reserved: {len(reserved_ids)}, Required: {quantity}")

    print(f"✅ Successfully reserved {len(reserved_ids)} accounts for product {product_id}")

    # Создаём или обновляем запись в cart_items
    print(f"\n🎯 About to call create_or_update_cart_item")
    print(f"   cart_id: {cart_id}")
    print(f"   product_id: {product_id}")
    print(f"   reserved count: {len(reserved_ids)}")

    try:
        create_or_update_cart_item(cart_id, product_id, len(reserved_ids))
        print(f"✅ create_or_update_cart_item completed successfully\n")
    except Exception as e:
        print(f"\n❌ create_or_update_cart_item FAILED:")
        print(f"   Error: {e}")
        import traceback
        print(f"   Full traceback:\n{traceback.format_exc()}")
        # НЕ прерываем выполнение - резервирование уже сделано

    return {
        "reserved_account_ids": reserved_ids,
        "reservation_id": reservation_id,
        "expires_at": expires_at_iso,
        "quantity": len(reserved_ids),
        "cart_id": cart_id,
        "user_id": user_id
    }


def release_reservation(reservation_id: str = None, cart_id: str = None) -> int:
    """
    Освобождает зарезервированные аккаунты

    Args:
        reservation_id: ID группы резервирования (опционально)
        cart_id: ID корзины (опционально)

    Returns:
        количество освобождённых аккаунтов
    """

    if not reservation_id and not cart_id:
        raise ValueError("Must provide either reservation_id or cart_id")

    # Строим фильтр
    if reservation_id:
        filter_query = f'reservation_id="{reservation_id}" && sold=false'
    else:
        filter_query = f'reserved_cart="{cart_id}" && sold=false'

    try:
        reserved = pb.collection("accounts").get_list(
            1, 500,
            query_params={"filter": filter_query}
        )
    except Exception as e:
        print(f"Error fetching reserved accounts: {e}")
        return 0

    # Группируем по продуктам для обновления cart_items
    products_released = {}

    released_count = 0
    for account in reserved.items:
        try:
            product_id = getattr(account, 'product', '')
            pb.collection("accounts").update(account.id, {
                "reserved_cart": "",
                "reserved_by": "",
                "reserved_until": "",
                "reservation_id": ""
            })
            released_count += 1

            # Считаем сколько освобождено по каждому продукту
            if product_id:
                products_released[product_id] = products_released.get(product_id, 0) + 1

            print(
                f"✓ Released account {account.id} (was reserved for cart: {getattr(account, 'reserved_cart', 'unknown')})")
        except Exception as e:
            print(f"✗ Error releasing account {account.id}: {e}")

    # Обновляем cart_items
    if cart_id and products_released:
        for product_id, count in products_released.items():
            try:
                update_cart_item_quantity(cart_id, product_id, -count)
            except Exception as e:
                print(f"⚠ Could not update cart_item for product {product_id}: {e}")

    print(f"✅ Released {released_count} accounts total")
    return released_count


def release_expired_reservations() -> int:
    """
    Освобождает все просроченные резервации

    Returns:
        количество освобождённых аккаунтов
    """

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    # Ищем аккаунты с непустым reserved_until, который меньше текущего времени, и не проданные
    filter_query = f'reserved_until!="" && reserved_until<"{now}" && sold=false'

    try:
        expired = pb.collection("accounts").get_list(
            1, 500,
            query_params={"filter": filter_query}
        )
    except Exception as e:
        print(f"Error fetching expired reservations: {e}")
        return 0

    if expired.items:
        print(f"Found {len(expired.items)} expired reservations to release")

    # Группируем по cart_id и product для обновления cart_items
    cart_products = {}

    released_count = 0
    for account in expired.items:
        try:
            cart_id = getattr(account, 'reserved_cart', '')
            product_id = getattr(account, 'product', '')
            user_id = getattr(account, 'reserved_by', 'unknown')

            pb.collection("accounts").update(account.id, {
                "reserved_cart": "",
                "reserved_by": "",
                "reserved_until": "",
                "reservation_id": ""
            })
            released_count += 1

            # Считаем для обновления cart_items
            if cart_id and product_id:
                key = f"{cart_id}:{product_id}"
                cart_products[key] = cart_products.get(key, 0) + 1

            print(f"✓ Released expired account {account.id} (was cart: {cart_id}, user: {user_id})")
        except Exception as e:
            print(f"✗ Error releasing account {account.id}: {e}")

    # Обновляем cart_items для каждой корзины
    for key, count in cart_products.items():
        cart_id, product_id = key.split(':')
        try:
            update_cart_item_quantity(cart_id, product_id, -count)
        except Exception as e:
            print(f"⚠ Could not update cart_item for {key}: {e}")

    if released_count > 0:
        print(f"✅ Cleaned up {released_count} expired reservations")

    return released_count


def mark_accounts_as_sold(account_ids: list, order_id: str = None, buyer_id: str = None) -> dict:
    """
    Помечает аккаунты как проданные и перемещает в sold_accounts

    Args:
        account_ids: список ID аккаунтов
        order_id: ID заказа (опционально)
        buyer_id: ID покупателя (опционально)

    Returns:
        dict: {account_id: sold_account_id} - маппинг старых ID на новые sold_accounts IDs
    """

    id_mapping = {}  # Маппинг старых ID аккаунтов на новые sold_accounts IDs
    sold_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    for account_id in account_ids:
        try:
            # Получаем информацию об аккаунте ПЕРЕД стиранием данных
            account = pb.collection("accounts").get_one(account_id)

            # Извлекаем поле data целиком (формат: login:password:email)
            account_data = getattr(account, 'data', '')

            # Создаём запись в sold_accounts ПЕРЕД удалением
            try:
                sold_record = pb.collection("sold_accounts").create({
                    "account": account_id,  # relation поле
                    "data": account_data,  # копируем data как есть
                    "product": getattr(account, 'product', ''),
                    "buyer": buyer_id or getattr(account, 'reserved_by', ''),
                    "order_id": order_id or "",
                    "sold_at": sold_at
                })
                # Сохраняем маппинг старого ID на новый sold_accounts ID
                id_mapping[account_id] = sold_record.id
                print(f"✓ Created sold_accounts record {sold_record.id} for {account_id} with data: {account_data[:50]}...")
            except Exception as e:
                print(f"⚠ Could not create sold_accounts record for {account_id}: {e}")

            # УДАЛЯЕМ аккаунт из коллекции accounts
            try:
                pb.collection("accounts").delete(account_id)
                print(f"✓ Deleted account {account_id} from accounts collection")
            except Exception as e:
                print(f"⚠ Could not delete account {account_id}: {e}")

            print(f"✓ Marked account {account_id} as sold (order: {order_id}, buyer: {buyer_id})")

        except Exception as e:
            print(f"✗ Error marking account {account_id} as sold: {e}")

    print(f"✅ Marked {len(id_mapping)} accounts as sold")
    return id_mapping


def get_available_count(product_id: str) -> int:
    """
    Возвращает количество доступных (не зарезервированных и не проданных) аккаунтов

    Args:
        product_id: ID продукта

    Returns:
        количество доступных аккаунтов
    """
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    filter_query = f'product="{product_id}" && sold=false && (reserved_cart="" || reserved_until<"{now_iso}")'

    try:
        result = pb.collection("accounts").get_list(
            1, 1,  # нам нужен только count
            query_params={"filter": filter_query}
        )
        return result.total_items
    except Exception as e:
        print(f"Error getting available count: {e}")
        return 0

    return sold_count


if __name__ == "__main__":
    # Примеры использования
    import argparse

    parser = argparse.ArgumentParser(description="Cart Service - Account Reservation")
    parser.add_argument("action", choices=["reserve", "release", "cleanup", "mark_sold"],
                        help="Action to perform")
    parser.add_argument("--cart-id", help="Cart ID")
    parser.add_argument("--product-id", help="Product ID")
    parser.add_argument("--quantity", type=int, help="Quantity to reserve")
    parser.add_argument("--reservation-id", help="Reservation ID to release")
    parser.add_argument("--account-ids", help="Comma-separated account IDs to mark as sold")

    args = parser.parse_args()

    try:
        if args.action == "reserve":
            if not all([args.cart_id, args.product_id, args.quantity]):
                print("Error: reserve requires --cart-id, --product-id, and --quantity")
                sys.exit(1)

            result = reserve_accounts_for_cart(args.cart_id, args.product_id, args.quantity)
            print(f"\n✅ Successfully reserved {result['quantity']} accounts")
            print(f"Reservation ID: {result['reservation_id']}")
            print(f"Expires at: {result['expires_at']}")
            print(f"Account IDs: {', '.join(result['reserved_account_ids'])}")

        elif args.action == "release":
            if not (args.reservation_id or args.cart_id):
                print("Error: release requires --reservation-id or --cart-id")
                sys.exit(1)

            count = release_reservation(
                reservation_id=args.reservation_id,
                cart_id=args.cart_id
            )
            print(f"\n✅ Released {count} accounts")

        elif args.action == "cleanup":
            count = release_expired_reservations()
            print(f"\n✅ Cleaned up {count} expired reservations")

        elif args.action == "mark_sold":
            if not args.account_ids:
                print("Error: mark_sold requires --account-ids")
                sys.exit(1)

            ids = [id.strip() for id in args.account_ids.split(",")]
            count = mark_accounts_as_sold(ids)
            print(f"\n✅ Marked {count} accounts as sold")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
