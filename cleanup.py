#!/usr/bin/env python3
"""
Скрипт для очистки старых записей из sold_accounts.
Запускать через cron каждый день для удаления записей старше 3 дней.
"""

from pocketbase import PocketBase
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("cleanup")

# Подключение к PocketBase
pb = PocketBase("http://127.0.0.1:8090")


def cleanup_old_sold_accounts():
    """Удаляет записи из sold_accounts старше 3 дней"""
    try:
        # Вычисляем дату 3 дня назад
        three_days_ago = datetime.now() - timedelta(days=3)
        cutoff_date = three_days_ago.strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"Cleaning up sold_accounts older than {cutoff_date}")

        # Получаем все записи sold_accounts
        sold_accounts = pb.collection("sold_accounts").get_full_list()

        deleted_count = 0
        for account in sold_accounts:
            try:
                # Проверяем дату продажи
                sold_at = datetime.fromisoformat(account.sold_at.replace('Z', '+00:00'))

                if sold_at < three_days_ago:
                    # Удаляем запись
                    pb.collection("sold_accounts").delete(account.id)
                    deleted_count += 1
                    logger.debug(f"Deleted sold_account {account.id} sold at {sold_at}")

            except Exception as e:
                logger.error(f"Error processing sold_account {account.id}: {e}")
                continue

        logger.info(f"Cleanup completed. Deleted {deleted_count} old records from sold_accounts.")
        return deleted_count

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return 0


if __name__ == "__main__":
    deleted = cleanup_old_sold_accounts()
    print(f"Cleanup completed. Deleted {deleted} records.")
