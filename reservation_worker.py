#!/usr/bin/env python3
"""
Reservation Worker - автоматическое освобождение просроченных резервов
Запускается как background процесс или cron job
"""

import os
import time
import logging
from datetime import datetime
from cart_service import release_expired_reservations, POCKETBASE_URL

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Интервал проверки (в секундах)
CHECK_INTERVAL = int(os.getenv("RESERVATION_CHECK_INTERVAL", "60"))  # по умолчанию каждую минуту


def run_worker():
    """
    Основной цикл worker-а
    Периодически проверяет и освобождает просроченные резервации
    """

    logger.info(f"Starting reservation worker")
    logger.info(f"PocketBase URL: {POCKETBASE_URL}")
    logger.info(f"Check interval: {CHECK_INTERVAL} seconds")

    iteration = 0

    while True:
        iteration += 1
        try:
            logger.info(f"[Iteration {iteration}] Checking for expired reservations...")

            start_time = time.time()
            released_count = release_expired_reservations()
            elapsed = time.time() - start_time

            if released_count > 0:
                logger.info(
                    f"[Iteration {iteration}] ✅ Released {released_count} expired reservations in {elapsed:.2f}s")
            else:
                logger.debug(f"[Iteration {iteration}] No expired reservations found ({elapsed:.2f}s)")

        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
            break
        except Exception as e:
            logger.error(f"[Iteration {iteration}] Error during cleanup: {e}", exc_info=True)

        # Ждём до следующей проверки
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Reservation Worker - Auto-release expired reservations")
    parser.add_argument("--interval", type=int, help=f"Check interval in seconds (default: {CHECK_INTERVAL})")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for cron)")

    args = parser.parse_args()

    if args.interval:
        CHECK_INTERVAL = args.interval

    if args.once:
        # Однократный запуск для cron
        logger.info("Running in one-shot mode")
        try:
            count = release_expired_reservations()
            logger.info(f"Released {count} expired reservations")
        except Exception as e:
            logger.error(f"Error: {e}")
            exit(1)
    else:
        # Непрерывный режим
        run_worker()
