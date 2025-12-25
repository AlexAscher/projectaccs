#!/usr/bin/env python3
"""
Скрипт для заполнения каталога тестовыми данными
Создает категории (Postogram, TikTok, Snapchat), регионы (US, EUR) и товары
"""

import requests
import json

POCKETBASE_URL = "http://127.0.0.1:8090"


def create_categories():
    """Создание категорий платформ"""
    categories = [
        {
            "name": "Postogram",
            "slug": "postogram",
            "description": "Премиум аккаунты Postogram с подписчиками и историей"
        },
        {
            "name": "TikTok",
            "slug": "tiktok",
            "description": "Готовые аккаунты TikTok для продвижения"
        },
        {
            "name": "Snapchat",
            "slug": "snapchat",
            "description": "Верифицированные аккаунты Snapchat"
        }
    ]

    created_categories = {}

    for cat in categories:
        try:
            response = requests.post(
                f"{POCKETBASE_URL}/api/collections/categories/records",
                json=cat,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                data = response.json()
                created_categories[cat['slug']] = data['id']
                print(f"✓ Создана категория: {cat['name']} (ID: {data['id']})")
            else:
                print(f"✗ Ошибка создания категории {cat['name']}: {response.text}")
        except Exception as e:
            print(f"✗ Исключение при создании категории {cat['name']}: {e}")

    return created_categories


def create_regions():
    """Создание регионов"""
    regions = [
        {
            "name": "US",
            "slug": "us",
            "description": "Аккаунты для США"
        },
        {
            "name": "EUR",
            "slug": "eur",
            "description": "Аккаунты для Европы"
        }
    ]

    created_regions = {}

    for reg in regions:
        try:
            response = requests.post(
                f"{POCKETBASE_URL}/api/collections/region/records",
                json=reg,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                data = response.json()
                created_regions[reg['slug']] = data['id']
                print(f"✓ Создан регион: {reg['name']} (ID: {data['id']})")
            else:
                print(f"✗ Ошибка создания региона {reg['name']}: {response.text}")
        except Exception as e:
            print(f"✗ Исключение при создании региона {reg['name']}: {e}")

    return created_regions


def create_products(categories, regions):
    """Создание товаров для всех комбинаций категорий и регионов"""

    # Postogram и TikTok имеют 3 варианта warmup
    # Snapchat имеет только 1 вариант (30 days rest)

    products_data = {
        'postogram': {
            'us': [
                {"title": "Postogram US", "warmup": "30 days of rest", "price": 2.0, "quantity": 150,
                 "description": "Премиум аккаунт с гарантией"},
                {"title": "Postogram US", "warmup": "Warmed up for 3 days", "price": 3.5, "quantity": 100,
                 "description": "Прогретый аккаунт 3 дня"},
                {"title": "Postogram US", "warmup": "Warmed up for 7 days", "price": 5.0, "quantity": 80,
                 "description": "Прогретый аккаунт 7 дней"},
            ],
            'eur': [
                {"title": "Postogram EUR", "warmup": "30 days of rest", "price": 2.5, "quantity": 120,
                 "description": "Премиум аккаунт с гарантией"},
                {"title": "Postogram EUR", "warmup": "Warmed up for 3 days", "price": 4.0, "quantity": 90,
                 "description": "Прогретый аккаунт 3 дня"},
                {"title": "Postogram EUR", "warmup": "Warmed up for 7 days", "price": 5.5, "quantity": 70,
                 "description": "Прогретый аккаунт 7 дней"},
            ]
        },
        'tiktok': {
            'us': [
                {"title": "TikTok US", "warmup": "30 days of rest", "price": 1.5, "quantity": 200,
                 "description": "Аккаунт для продвижения"},
                {"title": "TikTok US", "warmup": "Warmed up for 3 days", "price": 3.0, "quantity": 120,
                 "description": "Прогретый аккаунт 3 дня"},
                {"title": "TikTok US", "warmup": "Warmed up for 7 days", "price": 4.5, "quantity": 90,
                 "description": "Прогретый аккаунт 7 дней"},
            ],
            'eur': [
                {"title": "TikTok EUR", "warmup": "30 days of rest", "price": 2.0, "quantity": 180,
                 "description": "Аккаунт для продвижения"},
                {"title": "TikTok EUR", "warmup": "Warmed up for 3 days", "price": 3.5, "quantity": 110,
                 "description": "Прогретый аккаунт 3 дня"},
                {"title": "TikTok EUR", "warmup": "Warmed up for 7 days", "price": 5.0, "quantity": 85,
                 "description": "Прогретый аккаунт 7 дней"},
            ]
        },
        'snapchat': {
            'us': [
                {"title": "Snapchat US", "warmup": "30 days of rest", "price": 1.0, "quantity": 250,
                 "description": "Готовый аккаунт"},
            ],
            'eur': [
                {"title": "Snapchat EUR", "warmup": "30 days of rest", "price": 1.5, "quantity": 220,
                 "description": "Готовый аккаунт"},
            ]
        }
    }

    created_count = 0

    for platform_slug, regions_data in products_data.items():
        for region_slug, products in regions_data.items():
            category_id = categories.get(platform_slug)
            region_id = regions.get(region_slug)

            if not category_id or not region_id:
                print(f"⚠ Пропущена комбинация {platform_slug}/{region_slug} - отсутствуют ID")
                continue

            for product in products:
                warmup_slug = product['warmup'].replace(' ', '_').replace('for_', '').lower()
                product_payload = {
                    "title": product['title'],
                    "description": product['description'],
                    "price": product['price'],
                    "quantity": product['quantity'],
                    "warmup": product['warmup'],
                    "category": category_id,
                    "region": region_id,
                    "sku": f"{platform_slug}_{region_slug}_{warmup_slug}",
                    "is_active": True
                }

                try:
                    response = requests.post(
                        f"{POCKETBASE_URL}/api/collections/products/records",
                        json=product_payload,
                        headers={"Content-Type": "application/json"}
                    )
                    if response.status_code == 200:
                        created_count += 1
                        print(f"✓ Создан товар: {product['title']}")
                    else:
                        print(f"✗ Ошибка создания товара {product['title']}: {response.text}")
                except Exception as e:
                    print(f"✗ Исключение при создании товара {product['title']}: {e}")

    print(f"\n✓ Всего создано товаров: {created_count}")


def main():
    print("=== Заполнение каталога тестовыми данными ===\n")

    print("Шаг 1: Создание категорий...")
    categories = create_categories()
    print(f"Создано категорий: {len(categories)}\n")

    print("Шаг 2: Создание регионов...")
    regions = create_regions()
    print(f"Создано регионов: {len(regions)}\n")

    print("Шаг 3: Создание товаров...")
    create_products(categories, regions)

    print("\n=== Готово! ===")
    print("Откройте http://127.0.0.1:8090 для просмотра каталога")


if __name__ == "__main__":
    main()
