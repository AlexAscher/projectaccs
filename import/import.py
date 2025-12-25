import glob, os, requests

POCKETBASE_URL = "http://127.0.0.1:8090"
USER_EMAIL     = "simple@gmail.com"
USER_PASSWORD  = "12345678"
IMPORT_DIR     = "import_txt"

def login_user(email, password):
    res = requests.post(
        f"{POCKETBASE_URL}/api/collections/users/auth-with-password",
        json={"identity": email, "password": password}
    )
    res.raise_for_status()
    return res.json()["token"]

def fetch_records(collection: str, token: str, **params):
    """Возвращает список items из /api/collections/{collection}/records."""
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(
        f"{POCKETBASE_URL}/api/collections/{collection}/records",
        params=params,
        headers=headers
    )
    res.raise_for_status()
    payload = res.json()
    # всегда гарантированно items
    return payload.get("items", [])

def record_exists(data_value: str, product_id: str, token: str) -> bool:
    """Проверяем, есть ли уже запись в accounts с data=data_value и product=product_id."""
    headers = {"Authorization": f"Bearer {token}"}
    filter_q = f"data='{data_value}' && product='{product_id}'"
    res = requests.get(
        f"{POCKETBASE_URL}/api/collections/accounts/records",
        params={"filter": filter_q},
        headers=headers
    )
    res.raise_for_status()
    return len(res.json().get("items", [])) > 0

def import_all():
    token = login_user(USER_EMAIL, USER_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    # 1) Загружаем все продукты и строим mapping key->id
    print("🔄 Загружаем products…")
    prods = fetch_records("products", token, page=1, perPage=200)
    product_map = { p["key"]: p["id"] for p in prods }
    print(f"✅ Найдено {len(product_map)} продуктов\n")

    # 2) Перебираем все txt-файлы
    txt_files = glob.glob(os.path.join(IMPORT_DIR, "*.txt"))
    if not txt_files:
        print("❗ Нет .txt файлов в", IMPORT_DIR)
        return

    total, success = 0, 0
    for path in txt_files:
        fname = os.path.basename(path)
        # имя файла без .txt
        product_key = fname[:-4]
        total += 1

        # Проверяем, есть ли такой product_key в базе
        if product_key not in product_map:
            print(f"⚠️  Файл {fname}: продукт `{product_key}` не найден в PB → пропускаем")
            continue

        product_id = product_map[product_key]

        # Читаем все строки из файла
        with open(path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        for i, line in enumerate(lines, 1):
            # 3) Пропускаем, если уже есть
            if record_exists(line, product_id, token):
                print(f"⚠️ {fname} [{i}]: `{line}` уже в базе")
                continue

            # 4) Создаём запись
            payload = {
                "product": product_id,
                "data": line,
                "sold": False
            }
            res = requests.post(
                f"{POCKETBASE_URL}/api/collections/accounts/records",
                json=payload,
                headers=headers
            )
            if res.status_code == 200:
                print(f"✅ {fname} [{i}]: `{line}` добавлен")
                success += 1
            else:
                print(f"❌ Ошибка {fname} [{i}]:", res.text)

    print(f"\n🎉 Импорт завершён: {success} из {sum(len(open(p).read().splitlines()) for p in txt_files)} строк успешно.")

if __name__ == "__main__":
    import_all()
