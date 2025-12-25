import pocketbase

pb = pocketbase.PocketBase('http://127.0.0.1:8090')

try:
    # Проверяем все коллекции
    print('Проверка коллекций...')

    categories = pb.collection('categories').get_full_list()
    print(f'✅ categories: {len(categories)} записей')

    subcategories = pb.collection('subcategories').get_full_list()
    print(f'✅ subcategories: {len(subcategories)} записей')

    products = pb.collection('products').get_full_list()
    print(f'✅ products: {len(products)} записей')

    regions = pb.collection('regions').get_full_list()
    print(f'✅ regions: {len(regions)} записей')

    accounts = pb.collection('accounts').get_full_list()
    print(f'✅ accounts: {len(accounts)} записей')

    sold_accounts = pb.collection('sold_accounts').get_full_list()
    print(f'✅ sold_accounts: {len(sold_accounts)} записей')

    bot_users = pb.collection('bot_users').get_full_list()
    print(f'✅ bot_users: {len(bot_users)} записей')

    print('\n✅ Все коллекции доступны и работают корректно!')

except Exception as e:
    print(f'❌ Ошибка: {e}')