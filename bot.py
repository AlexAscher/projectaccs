from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile, \
    BotCommand, MenuButtonCommands, BotCommandScopeChat
from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiosend import CryptoPay, TESTNET
import asyncio
from aiogram.fsm.state import State, StatesGroup
from pocketbase import PocketBase
import logging
from datetime import datetime, timedelta, timezone
import schedule
import threading
import os
import traceback
from functools import lru_cache
from typing import Optional, List, Dict, Tuple, Any
import requests
import glob
import secrets
import httpx
import json

from activity_logger import (
    cache_bot_user_record_id,
    resolve_bot_user_record_id,
    log_user_activity,
)

pb = PocketBase("http://127.0.0.1:8090")

# URL веб-сайта для генерации ссылок авторизации
WEBSITE_URL = os.getenv("WEBSITE_URL", "http://127.0.0.1:8090")

API_SERVER_URL = os.getenv("API_SERVER_URL", "http://127.0.0.1:5000").rstrip('/')
SITE_ORDER_POLL_INTERVAL = int(os.getenv("SITE_ORDER_POLL_INTERVAL", "5"))

# Глобальный словарь для хранения информации о заказах
pending_orders = {}

# Global list for storing sales data for reports
sales_data = []

# Глобальные списки для отслеживания пользователей бота
user_activities = []  # User activity data for reports
bot_users = set()  # Множество всех пользователей бота (в памяти)

# Global variable for tracking last report time
last_report_time = None
last_user_report_time = None

# Chat ID пользователя sansiry (будет установлен при первом взаимодействии)
sansiry_chat_id = None

# Глобальная переменная для хранения ожидающей рассылки
pending_broadcast = None

# Кеш для часто используемых данных
_categories_cache = None
_cache_timestamp = None
CACHE_TTL = 60  # 60 секунд кеширования

# Connection pool для оптимизации подключений к БД
_db_connection_pool = None

ACTIVITY_EVENT_LABELS = {
    'command_start': '🚀 Запуск бота',
    'command_menu': '🏠 Главное меню',
    'catalog_opened': '🛒 Каталог',
    'invoice_created': '💳 Счёт создан',
    'order_paid': '✅ Оплата получена',
    'order_delivered': '📦 Доставка выполнена'
}

ORDER_STATUS_LABELS = {
    'pending': 'Ожидание оплаты',
    'awaiting_payment': 'Ожидает оплаты',
    'processing': 'Обработка',
    'paid': 'Оплачен',
    'delivered': 'Доставлен',
    'failed': 'Ошибка'
}

ORDER_STATUS_ICONS = {
    'pending': '⏳',
    'awaiting_payment': '⏳',
    'processing': '⚙️',
    'paid': '✅',
    'delivered': '📦',
    'failed': '❌'
}


def _format_timestamp_short(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value)
        cleaned = text.replace('Z', '+00:00') if isinstance(value, str) and text.endswith('Z') else text
        try:
            dt = datetime.fromisoformat(cleaned)
        except Exception:
            cleaned = cleaned.replace('T', ' ')
            return cleaned[:19]
    return dt.strftime("%Y-%m-%d %H:%M")


def _build_order_items_preview(order_obj: Any, max_items: int = 2) -> str:
    snapshot = _record_to_plain_dict(order_obj)
    items = snapshot.get('items')
    if isinstance(items, list) and items:
        parts: List[str] = []
        for raw in items[:max_items]:
            if not isinstance(raw, dict):
                continue
            title = raw.get('product_title') or raw.get('display_name') or raw.get('product_id') or 'Product'
            quantity = raw.get('quantity')
            if quantity:
                parts.append(f"{title} x{quantity}")
            else:
                parts.append(title)
        remaining = max(len(items) - max_items, 0)
        if remaining:
            parts.append(f"+ ещё {remaining}")
        return ", ".join(parts)
    return ""


async def record_user_activity_event(
        telegram_user_id: int,
        event_type: str,
        details: str,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "bot",
        user_record_id: Optional[str] = None
) -> bool:
    try:
        return await asyncio.to_thread(
            log_user_activity,
            pb,
            telegram_user_id,
            event_type,
            details,
            source,
            metadata,
            user_record_id
        )
    except Exception as e:
        logger.error(f"Failed to record activity '{event_type}' for {telegram_user_id}: {e}")
        return False


async def get_bot_user_record_id_async(telegram_user_id: int) -> Optional[str]:
    return await asyncio.to_thread(resolve_bot_user_record_id, pb, telegram_user_id)


async def fetch_recent_user_activity_entries(telegram_user_id: int, limit: int = 3) -> List[Any]:
    user_key = str(telegram_user_id)

    def _fetch():
        try:
            result = pb.collection('user_activity').get_list(
                1,
                max(limit, 1),
                {
                    'filter': f'telegram_user_id="{user_key}"',
                    'sort': '-created'
                }
            )
            return result.items
        except Exception as fetch_error:
            logger.error(f"Failed to fetch user activity for {telegram_user_id}: {fetch_error}")
            return []

    return await asyncio.to_thread(_fetch)


async def fetch_recent_orders(user_record_id: str, limit: int = 5) -> Tuple[List[Any], int]:
    def _fetch():
        try:
            result = pb.collection('orders').get_list(
                1,
                max(limit, 1),
                {
                    'filter': f'user_bot="{user_record_id}"',
                    'sort': '-created'
                }
            )
            return result.items, result.total_items
        except Exception as fetch_error:
            logger.error(f"Failed to fetch orders for bot_user {user_record_id}: {fetch_error}")
            return [], 0

    return await asyncio.to_thread(_fetch)


async def build_activity_section_text(telegram_user_id: int, limit: int = 3) -> str:
    entries = await fetch_recent_user_activity_entries(telegram_user_id, limit)
    lines = ["📜 История активности (последние 3):"]
    if not entries:
        lines.append("• Пока нет действий")
        return "\n".join(lines)

    for entry in entries:
        event_type = getattr(entry, 'event_type', 'activity') or 'activity'
        created_at = getattr(entry, 'created', None)
        details = getattr(entry, 'details', '') or ''
        label = ACTIVITY_EVENT_LABELS.get(event_type, event_type)
        timestamp = _format_timestamp_short(created_at)
        if details:
            lines.append(f"• {label}\n  {timestamp} — {details}")
        else:
            lines.append(f"• {label}\n  {timestamp}")
    return "\n".join(lines)


async def build_purchase_history_section_text(telegram_user_id: int, limit: int = 5) -> str:
    lines = ["🧾 История покупок:"]
    user_record_id = await get_bot_user_record_id_async(telegram_user_id)
    if not user_record_id:
        lines.append("• Профиль ещё не синхронизирован")
        return "\n".join(lines)

    orders, total_count = await fetch_recent_orders(user_record_id, limit)
    if not orders:
        lines.append("• Заказы отсутствуют")
        return "\n".join(lines)

    for order in orders:
        display_id = getattr(order, 'order_id', None) or getattr(order, 'id', '—')
        status_raw = (getattr(order, 'status', 'unknown') or 'unknown').lower()
        status_icon = ORDER_STATUS_ICONS.get(status_raw, '•')
        status_label = ORDER_STATUS_LABELS.get(status_raw, status_raw.capitalize())
        amount = float(getattr(order, 'total_amount', 0) or 0)
        total_items = getattr(order, 'total_items', None)
        order_time = (
                getattr(order, 'delivered_at', None)
                or getattr(order, 'paid_at', None)
                or getattr(order, 'created', None)
        )
        quantity_fragment = ""
        if isinstance(total_items, (int, float)) and total_items:
            quantity_fragment = f" · {int(total_items)} pcs"

        lines.append(f"{status_icon} #{display_id} · {amount:.2f} USDT{quantity_fragment}")
        preview = _build_order_items_preview(order)
        info_parts = [status_label, _format_timestamp_short(order_time)]
        if preview:
            info_parts.append(preview)
        lines.append("  " + " • ".join(part for part in info_parts if part))

    if total_count > len(orders):
        lines.append(f"• …и ещё {total_count - len(orders)} заказов")

    return "\n".join(lines)


# === ОЧИСТКА SOLD_ACCOUNTS ===
def cleanup_old_sold_accounts():
    """Удаляет записи из sold_accounts старше недели"""
    try:
        logger.info("Starting weekly cleanup of sold_accounts...")

        # Вычисляем дату неделю назад с timezone UTC
        one_week_ago = datetime.now(timezone.utc) - timedelta(weeks=1)
        cutoff_date = one_week_ago.strftime("%Y-%m-%d %H:%M:%S %Z")

        logger.info(f"Cleaning up sold_accounts older than {cutoff_date}")

        # Получаем все записи sold_accounts
        try:
            sold_accounts = pb.collection("sold_accounts").get_full_list()
            logger.info(f"Found {len(sold_accounts)} records in sold_accounts collection")
        except Exception as e:
            logger.error(f"Failed to fetch sold_accounts: {e}")
            return 0

        if not sold_accounts:
            logger.info("No records found in sold_accounts collection")
            return 0

        deleted_count = 0
        errors_count = 0

        for account in sold_accounts:
            try:
                # Логируем информацию о записи
                logger.debug(f"Processing sold_account {account.id}")

                # Проверяем наличие поля sold_at или created
                sold_date = None
                if hasattr(account, 'sold_at') and account.sold_at:
                    sold_date_str = account.sold_at
                    logger.debug(f"Record {account.id} has sold_at: {sold_date_str}")
                elif hasattr(account, 'created') and account.created:
                    sold_date_str = account.created
                    logger.debug(f"Record {account.id} using created date: {sold_date_str}")
                else:
                    logger.warning(f"Record {account.id} has no sold_at or created date, skipping")
                    errors_count += 1
                    continue

                # Парсим дату (поддерживаем разные форматы)
                try:
                    # Обрабатываем ISO формат с миллисекундами и Z
                    cleaned_date = sold_date_str

                    # Убираем Z и заменяем на +00:00
                    if cleaned_date.endswith('Z'):
                        cleaned_date = cleaned_date[:-1] + '+00:00'

                    # Убираем миллисекунды если есть точка
                    if '.' in cleaned_date and ('+' in cleaned_date or '-' in cleaned_date[-6:]):
                        # Формат: 2025-07-23T22:18:03.788+00:00
                        date_part, tz_part = cleaned_date.rsplit('+',
                                                                 1) if '+' in cleaned_date else cleaned_date.rsplit('-',
                                                                                                                    1)
                        if '.' in date_part:
                            date_part = date_part.split('.')[0]  # Убираем миллисекунды
                        cleaned_date = date_part + ('+' + tz_part if '+' in cleaned_date else '-' + tz_part)
                    elif '.' in cleaned_date:
                        # Формат: 2025-07-23T22:18:03.788 (без timezone)
                        cleaned_date = cleaned_date.split('.')[0]

                    # Парсим дату
                    if '+' in cleaned_date or cleaned_date.endswith('Z'):
                        # С timezone
                        sold_at = datetime.fromisoformat(cleaned_date.replace('Z', '+00:00'))
                    else:
                        # Без timezone, считаем UTC
                        sold_at = datetime.fromisoformat(cleaned_date)

                    logger.debug(f"Parsed date for record {account.id}: {sold_at}")

                except Exception as date_error:
                    logger.error(f"Failed to parse date '{sold_date_str}' for record {account.id}: {date_error}")
                    errors_count += 1
                    continue

                # Проверяем, старше ли записи недели
                if sold_at < one_week_ago:
                    try:
                        # Удаляем запись
                        pb.collection("sold_accounts").delete(account.id)
                        deleted_count += 1
                        logger.info(f"✅ Deleted sold_account {account.id} sold at {sold_at} (older than {cutoff_date})")
                    except Exception as delete_error:
                        logger.error(f"Failed to delete record {account.id}: {delete_error}")
                        errors_count += 1
                else:
                    logger.debug(f"Record {account.id} is recent (sold at {sold_at}), keeping")

            except Exception as e:
                logger.error(f"Error processing sold_account {account.id}: {e}")
                errors_count += 1
                continue

        logger.info(f"Weekly cleanup completed successfully!")
        logger.info(
            f"📊 Results: Deleted {deleted_count} old records, {errors_count} errors, {len(sold_accounts) - deleted_count - errors_count} records kept")
        return deleted_count

    except Exception as e:
        logger.error(f"Critical error during weekly cleanup: {e}")
        return 0


def run_weekly_cleanup():
    """Запускает еженедельную очистку sold_accounts"""
    try:
        logger.info("🧹 Starting weekly cleanup task...")
        deleted_count = cleanup_old_sold_accounts()
        logger.info(f"✅ Weekly cleanup task completed. Deleted {deleted_count} records.")
    except Exception as e:
        logger.error(f"❌ Weekly cleanup task failed: {e}")


# === REPORT FUNCTIONS ===
def register_sansiry_chat_id(username, chat_id):
    """Регистрирует chat_id пользователя sansiry"""
    global sansiry_chat_id
    if username == "sansiry":
        sansiry_chat_id = chat_id
        logger.info(f"Registered sansiry chat_id: {chat_id}")

        # Устанавливаем админские команды для sansiry
        async def set_admin_commands():
            try:
                await bot.set_my_commands([
                    BotCommand(command="start", description="🏠 Main menu"),
                    BotCommand(command="id", description="🆔 Get profile information"),
                    BotCommand(command="report", description="📊 Sales report"),
                    BotCommand(command="users", description="👥 Users report"),
                    BotCommand(command="stats", description="📈 Bot statistics"),
                    BotCommand(command="broadcast", description="📢 Send broadcast message"),
                    BotCommand(command="import", description="📦 Import products from txt files"),
                    BotCommand(command="cleanup", description="🧹 Database cleanup"),
                    BotCommand(command="clearcache", description="🗑️ Clear cache")
                ], scope=BotCommandScopeChat(chat_id=chat_id))
                logger.info(f"Admin commands set for sansiry chat_id: {chat_id}")
            except Exception as e:
                logger.error(f"Failed to set admin commands for sansiry: {e}")

        # Запускаем установку команд асинхронно
        asyncio.create_task(set_admin_commands())

        return True
    return False


def add_sale_to_report(user_id, first_name, last_name, username, product_key, quantity, amount):
    """Adds sale information to report"""
    sale_data = {
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user_id': user_id,
        'first_name': first_name,
        'last_name': last_name,
        'username': username,
        'product_key': product_key,
        'quantity': quantity,
        'amount': amount
    }
    sales_data.append(sale_data)
    logger.info(f"Sale added to report: {product_key} x{quantity} - ${amount}")


async def generate_sales_report():
    """Generates sales report"""
    try:
        current_time = datetime.now()
        date_str = current_time.strftime("%Y-%m-%d_%H-%M")

        # Generate report content
        report_content = f"SALES REPORT - {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        report_content += "=" * 60 + "\n\n"

        if not sales_data:
            report_content += "No sales for this period.\n"
        else:
            report_content += "SALES DETAILS:\n"
            report_content += "-" * 40 + "\n"

            # Счетчики для статистики
            product_stats = {}
            total_amount = 0
            total_quantity = 0

            for sale in sales_data:
                buyer_info = f"@{sale['username']}" if sale['username'] else f"ID: {sale['user_id']}"
                buyer_info += f" ({sale['first_name']}"
                if sale.get('last_name'):
                    buyer_info += f" {sale['last_name']}"
                buyer_info += ")"

                report_content += f"Time: {sale['time']}\n"
                report_content += f"Buyer: {buyer_info}\n"
                report_content += f"Product: {sale['product_key']}\n"
                report_content += f"Quantity: {sale['quantity']}\n"
                report_content += f"Amount: ${sale['amount']:.2f}\n"
                report_content += "-" * 40 + "\n"

                # Обновляем статистику
                if sale['product_key'] not in product_stats:
                    product_stats[sale['product_key']] = {'quantity': 0, 'amount': 0}
                product_stats[sale['product_key']]['quantity'] += sale['quantity']
                product_stats[sale['product_key']]['amount'] += sale['amount']

                total_amount += sale['amount']
                total_quantity += sale['quantity']

            # Добавляем статистику по типам товаров
            if product_stats:
                report_content += "\nPRODUCT STATISTICS:\n"
                report_content += "=" * 40 + "\n"
                for product_key, stats in product_stats.items():
                    report_content += f"{product_key}: {stats['quantity']} pcs, ${stats['amount']:.2f}\n"

            # Общая статистика
            report_content += "\nOVERALL STATISTICS:\n"
            report_content += "=" * 40 + "\n"
            report_content += f"Total sales: {len(sales_data)}\n"
            report_content += f"Total items: {total_quantity}\n"
            report_content += f"Total amount: ${total_amount:.2f}\n"

        return report_content, date_str

    except Exception as e:
        logger.error(f"Error generating sales report: {e}")
        return None, None


async def send_report_to_sansiry():
    """Sends sales report to sansiry user"""
    global sansiry_chat_id

    try:
        if not sansiry_chat_id:
            logger.warning("Sansiry chat_id not found. Waiting for first interaction.")
            return

        report_content, date_str = await generate_sales_report()
        if not report_content:
            logger.error("Failed to generate report")
            return

        # Создаем файл отчета
        filename = f"sales_report_{date_str}.txt"

        try:
            file_data = BufferedInputFile(
                report_content.encode('utf-8'),
                filename=filename
            )
            success = await safe_send_document(
                sansiry_chat_id,
                document=file_data,
                caption=f"📊 Sales report for {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

            if success:
                logger.info(f"Report sent to sansiry (chat_id: {sansiry_chat_id})")
                # Очищаем данные о продажах после отправки отчета
                sales_data.clear()
                logger.info("Sales data cleared after sending report")
            else:
                logger.warning(f"Failed to send report to sansiry")

        except Exception as e:
            logger.error(f"Failed to send report to sansiry: {e}")

    except Exception as e:
        logger.error(f"Error sending report to sansiry: {e}")


async def sales_report_task():
    """Asynchronous task for sending reports every 24 hours"""
    global last_report_time

    REPORT_INTERVAL = 86400  # 24 hours in seconds

    while True:
        try:
            current_time = datetime.now()

            # If this is first run or enough time has passed since last report
            if last_report_time is None or (current_time - last_report_time).total_seconds() >= REPORT_INTERVAL:
                logger.info("Sending scheduled sales report to sansiry...")
                await send_report_to_sansiry()
                last_report_time = current_time

            # Wait 1 hour before next check
            await asyncio.sleep(3600)

        except Exception as e:
            logger.error(f"Sales report task error: {e}")
            await asyncio.sleep(60)  # Ждем минуту при ошибке


# === USER TRACKING FUNCTIONS ===

def add_user_activity(user_id, first_name, last_name, username, activity_type):
    """Adds user activity to report"""
    global user_activities

    activity = {
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user_id': user_id,
        'first_name': first_name or '',
        'last_name': last_name or '',
        'username': username or '',
        'activity_type': activity_type  # 'first_start', 'interaction', 'blocked'
    }

    user_activities.append(activity)
    logger.info(f"User activity added to report: {activity_type} by {username or user_id}")


async def generate_users_report():
    """Generates users activity report"""
    try:
        current_time = datetime.now()
        date_str = current_time.strftime("%Y-%m-%d_%H-%M")

        # Generate report content
        report_content = f"USERS REPORT - {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        report_content += "=" * 60 + "\n\n"

        # Анализируем активности пользователей
        first_starts = [a for a in user_activities if a['activity_type'] == 'first_start']
        interactions = [a for a in user_activities if a['activity_type'] == 'interaction']
        blocked_users = [a for a in user_activities if a['activity_type'] == 'blocked']

        # Уникальные пользователи, которые взаимодействовали (не первый раз)
        unique_interaction_users = set()
        for activity in interactions:
            unique_interaction_users.add(activity['user_id'])

        report_content += "USER STATISTICS:\n"
        report_content += "=" * 40 + "\n"
        report_content += f"First-time bot users: {len(first_starts)}\n"
        report_content += f"Users who interacted with bot: {len(unique_interaction_users)}\n"
        report_content += f"Users who blocked bot: {len(blocked_users)}\n"
        report_content += f"Total number of users: {len(bot_users)}\n\n"

        if first_starts:
            report_content += "NEW USERS:\n"
            report_content += "-" * 40 + "\n"

            for activity in first_starts:
                user_info = f"@{activity['username']}" if activity['username'] else f"ID: {activity['user_id']}"
                user_info += f" ({activity['first_name']}"
                if activity.get('last_name'):
                    user_info += f" {activity['last_name']}"
                user_info += ")"

                report_content += f"🆕 {activity['time']} - {user_info}\n"

        if blocked_users:
            report_content += "\nUSERS WHO BLOCKED BOT:\n"
            report_content += "-" * 40 + "\n"

            for activity in blocked_users:
                report_content += f"🚫 {activity['time']} - ID: {activity['user_id']}\n"

        if not first_starts and not blocked_users:
            report_content += "No new activities for this period.\n"

        return report_content, date_str

    except Exception as e:
        logger.error(f"Error generating users report: {e}")
        return None, None


async def send_users_report_to_sansiry():
    """Sends users report to sansiry user"""
    global sansiry_chat_id

    try:
        if not sansiry_chat_id:
            logger.warning("Sansiry chat_id not found. Waiting for first interaction.")
            return

        report_content, date_str = await generate_users_report()
        if not report_content:
            logger.error("Failed to generate users report")
            return

        # Создаем файл отчета
        filename = f"users_report_{date_str}.txt"

        try:
            file_data = BufferedInputFile(
                report_content.encode('utf-8'),
                filename=filename
            )
            success = await safe_send_document(
                sansiry_chat_id,
                document=file_data,
                caption=f"👥 Users report for {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

            if success:
                logger.info(f"Users report sent to sansiry (chat_id: {sansiry_chat_id})")
                # Очищаем данные о пользователях после отправки отчета
                user_activities.clear()
                logger.info("User activities data cleared after sending report")
            else:
                logger.warning(f"Failed to send users report to sansiry")

        except Exception as e:
            logger.error(f"Failed to send users report to sansiry: {e}")

    except Exception as e:
        logger.error(f"Error sending users report to sansiry: {e}")


async def users_report_task():
    """Asynchronous task for sending users reports every 24 hours"""
    global last_user_report_time

    REPORT_INTERVAL = 86400  # 24 hours in seconds

    while True:
        try:
            current_time = datetime.now()

            # If this is first run or enough time has passed since last report
            if last_user_report_time is None or (
                    current_time - last_user_report_time).total_seconds() >= REPORT_INTERVAL:
                logger.info("Sending scheduled users report to sansiry...")
                await send_users_report_to_sansiry()
                last_user_report_time = current_time

            # Ждем 1 час перед следующей проверкой
            await asyncio.sleep(3600)

        except Exception as e:
            logger.error(f"Users report task error: {e}")
            await asyncio.sleep(60)  # Ждем минуту при ошибке


def start_cleanup_scheduler():
    """Запускает планировщик для еженедельной очистки"""
    logger.info("🗓️ Setting up weekly cleanup scheduler...")

    # Планируем очистку каждое воскресенье в 02:00
    schedule.every().sunday.at("02:00").do(run_weekly_cleanup)
    logger.info("📅 Scheduled weekly cleanup: Every Sunday at 02:00")

    def run_scheduler():
        logger.info("⏰ Cleanup scheduler thread started")
        while True:
            try:
                # Проверяем запланированные задачи
                pending_jobs = schedule.get_jobs()
                if pending_jobs:
                    next_run = schedule.next_run()
                    logger.debug(f"Next cleanup scheduled for: {next_run}")

                schedule.run_pending()
                threading.Event().wait(60)  # Проверяем каждую минуту

            except Exception as e:
                logger.error(f"Error in cleanup scheduler: {e}")
                threading.Event().wait(60)  # Ждем минуту при ошибке

    # Запускаем планировщик в отдельном потоке (только для еженедельной очистки)
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("✅ Weekly cleanup scheduler started successfully")
    logger.info("📊 Sales reports will be sent to sansiry every 24 hours")
    logger.info("🧹 Cleanup: Every Sunday at 02:00 (removes sold_accounts >1 week old)")
    logger.info("👤 Admin: Only 'sansiry' user can access admin commands")


# === ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ===
def add_user(user_id, username=None, first_name=None, last_name=None):
    """Добавляет пользователя в список пользователей бота и сохраняет в БД"""
    global bot_users

    # Проверяем, новый ли это пользователь
    is_new_user = user_id not in bot_users

    # Добавляем в память для быстрого доступа
    bot_users.add(user_id)

    # Отслеживаем активность пользователя
    if is_new_user:
        add_user_activity(user_id, first_name, last_name, username, 'first_start')
    else:
        add_user_activity(user_id, first_name, last_name, username, 'interaction')

    # Сохраняем в базу данных
    def save_user_to_db():
        try:
            # Проверяем, существует ли коллекция bot_users
            try:
                # Пытаемся найти существующего пользователя
                existing_users = pb.collection("bot_users").get_list(1, 1, {"filter": f'user_id="{user_id}"'})

                if existing_users.items:
                    # Пользователь уже существует, обновляем информацию
                    user_record = existing_users.items[0]
                    cache_bot_user_record_id(user_id, getattr(user_record, 'id', None))
                    update_data = {
                        'last_activity': datetime.now().isoformat(),
                    }

                    # Обновляем только если есть новая информация
                    if username and username != getattr(user_record, 'username', None):
                        update_data['username'] = username
                    if first_name and first_name != getattr(user_record, 'first_name', None):
                        update_data['first_name'] = first_name
                    if last_name and last_name != getattr(user_record, 'last_name', None):
                        update_data['last_name'] = last_name

                    pb.collection("bot_users").update(user_record.id, update_data)
                    logger.info(f"Updated user {user_id} in database")
                else:
                    # Новый пользователь, создаем запись
                    user_data = {
                        'user_id': str(user_id),  # Сохраняем как строку для совместимости с БД
                        'username': username or '',
                        'first_name': first_name or '',
                        'last_name': last_name or '',
                        'first_interaction': datetime.now().isoformat(),
                        'last_activity': datetime.now().isoformat(),
                        'is_active': True
                    }

                    result = pb.collection("bot_users").create(user_data)
                    cache_bot_user_record_id(user_id, getattr(result, 'id', None))
                    logger.info(f"Created new user {user_id} in database with record ID: {result.id}")

            except Exception as collection_error:
                # Если коллекции не существует, создаем пользователя в памяти
                logger.warning(f"bot_users collection not available: {collection_error}")

        except Exception as e:
            logger.error(f"Error saving user {user_id} to database: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

    # Выполняем сохранение синхронно для отладки
    try:
        save_user_to_db()
    except Exception as e:
        logger.error(f"Failed to save user {user_id}: {e}")

    logger.info(f"Added user {user_id} to bot users list. Total users: {len(bot_users)}")


async def add_user_async(user_id, username=None, first_name=None, last_name=None):
    """Асинхронная версия add_user для использования в обработчиках"""
    global bot_users

    # Проверяем, новый ли это пользователь в памяти
    is_new_in_memory = user_id not in bot_users

    # ЛОГИРУЕМ КАЖДОЕ ВЗАИМОДЕЙСТВИЕ
    logger.info(
        f"🔄 USER INTERACTION: {user_id} ({username}) - {'NEW in memory' if is_new_in_memory else 'EXISTS in memory'}")

    # Добавляем в память для быстрого доступа
    bot_users.add(user_id)

    # Отслеживаем активность пользователя
    if is_new_in_memory:
        add_user_activity(user_id, first_name, last_name, username, 'first_start')
        logger.info(f"New user {user_id} added to memory (first interaction)")
    else:
        add_user_activity(user_id, first_name, last_name, username, 'interaction')
        logger.debug(f"Existing user {user_id} interaction recorded")

    # Сохраняем в базу данных асинхронно
    def save_user_to_db():
        try:
            logger.debug(f"Processing user {user_id} for database sync...")

            # Проверяем подключение к PocketBase
            try:
                # Тестируем подключение простым запросом к коллекции
                test_query = pb.collection("bot_users").get_list(1, 1)
                logger.debug(f"PocketBase connection successful")
            except Exception as conn_error:
                logger.error(f"PocketBase connection failed: {conn_error}")
                logger.error(f"PocketBase URL: {pb.base_url}")
                return

            # Проверяем, существует ли коллекция bot_users
            try:
                # Пытаемся найти существующего пользователя
                logger.info(f"🔍 DATABASE SEARCH: Looking for user {user_id} in bot_users collection...")
                existing_users = pb.collection("bot_users").get_list(1, 1, {"filter": f'user_id="{user_id}"'})
                logger.info(f"🔍 DATABASE RESULT: Found {len(existing_users.items)} records for user {user_id}")

                if existing_users.items:
                    # Пользователь уже существует в БД
                    user_record = existing_users.items[0]
                    cache_bot_user_record_id(user_id, getattr(user_record, 'id', None))
                    current_active_status = getattr(user_record, 'is_active', True)
                    logger.info(f"📄 USER EXISTS IN DB: {user_id}, current is_active={current_active_status}")
                    was_inactive = not getattr(user_record, 'is_active', True)
                    current_username = getattr(user_record, 'username', '')
                    current_first_name = getattr(user_record, 'first_name', '')

                    # ВАЖНО: Всегда устанавливаем is_active = True при любом взаимодействии
                    update_data = {
                        'last_activity': datetime.now().isoformat(),
                        'is_active': True  # Автоматическая реактивация при любом взаимодействии
                    }

                    # Обновляем информацию если есть новые данные
                    if username and username != current_username:
                        update_data['username'] = username
                        logger.info(f"User {user_id} username updated: '{current_username}' -> '{username}'")
                    if first_name and first_name != current_first_name:
                        update_data['first_name'] = first_name
                        logger.info(f"User {user_id} first_name updated: '{current_first_name}' -> '{first_name}'")
                    if last_name and last_name != getattr(user_record, 'last_name', None):
                        update_data['last_name'] = last_name

                    # Специальные логи для реактивации
                    if was_inactive:
                        logger.warning(f"🔄 REACTIVATING USER {user_id}: was inactive, now setting is_active=True")
                        logger.info(
                            f"User {user_id} ({username or 'no_username'}) was blocked but is now interacting again")
                    elif is_new_in_memory:
                        logger.info(
                            f"📱 BOT RESTART DETECTED: User {user_id} was in DB but not in memory (bot was restarted)")
                        logger.info(f"Ensuring user {user_id} is active after bot restart")

                    logger.debug(f"Updating user {user_id} with data: {update_data}")
                    pb.collection("bot_users").update(user_record.id, update_data)

                    if was_inactive:
                        logger.warning(f"✅ User {user_id} SUCCESSFULLY REACTIVATED - will receive broadcasts again!")
                    elif is_new_in_memory:
                        logger.info(f"✅ User {user_id} confirmed active after bot restart")
                    else:
                        logger.debug(f"User {user_id} updated in database")
                else:
                    # Новый пользователь, создаем запись
                    user_data = {
                        'user_id': str(user_id),  # Сохраняем как строку для совместимости с БД
                        'username': username or '',
                        'first_name': first_name or '',
                        'last_name': last_name or '',
                        'first_interaction': datetime.now().isoformat(),
                        'last_activity': datetime.now().isoformat(),
                        'is_active': True
                    }

                    logger.info(f"🆕 Creating NEW USER {user_id} in database with data: {user_data}")
                    result = pb.collection("bot_users").create(user_data)
                    cache_bot_user_record_id(user_id, getattr(result, 'id', None))
                    logger.info(f"✅ Created new user {user_id} in database with record ID: {result.id}")

            except Exception as collection_error:
                # Если коллекции не существует или ошибка доступа
                logger.error(f"bot_users collection error: {collection_error}")
                logger.error(f"This might indicate that the bot_users collection doesn't exist in PocketBase")

                # Пытаемся создать коллекцию (если есть права)
                try:
                    logger.info("Attempting to work without bot_users collection...")
                except Exception as create_error:
                    logger.error(f"Cannot work with bot_users collection: {create_error}")

        except Exception as e:
            logger.error(f"Critical error saving user {user_id} to database: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

    # Сохраняем в отдельном потоке, чтобы не блокировать бот
    await asyncio.to_thread(save_user_to_db)

    logger.debug(f"User {user_id} processing completed. Total users in memory: {len(bot_users)}")
    return True


async def reactivate_user_async(user_id):
    """Принудительно реактивирует пользователя в БД (устанавливает is_active=True)"""

    def reactivate_in_db():
        try:
            logger.debug(f"Attempting to reactivate user {user_id}...")

            # Ищем пользователя в БД
            existing_users = pb.collection("bot_users").get_list(1, 1, {"filter": f'user_id="{user_id}"'})

            if existing_users.items:
                user_record = existing_users.items[0]
                was_inactive = not getattr(user_record, 'is_active', True)

                # Обновляем статус на активный
                update_data = {
                    'is_active': True,
                    'last_activity': datetime.now().isoformat()
                }

                pb.collection("bot_users").update(user_record.id, update_data)

                if was_inactive:
                    logger.info(f"User {user_id} manually reactivated - will receive broadcasts again")
                    return True
                else:
                    logger.debug(f"User {user_id} was already active")
                    return False
            else:
                logger.warning(f"User {user_id} not found in database for reactivation")
                return False

        except Exception as e:
            logger.error(f"Error reactivating user {user_id}: {e}")
            return False

    return await asyncio.to_thread(reactivate_in_db)


def get_user_count():
    """Возвращает количество пользователей бота"""
    return len(bot_users)


def load_users_from_db():
    """Загружает всех пользователей из базы данных при запуске бота"""
    global bot_users

    try:
        logger.info("Loading users from database...")

        # Сначала проверяем подключение к PocketBase простым запросом
        try:
            test_query = pb.collection("bot_users").get_list(1, 1)
            logger.info(
                f"PocketBase connection successful, found {test_query.total_items} users in bot_users collection")
        except Exception as conn_error:
            logger.error(f"PocketBase connection failed: {conn_error}")
            logger.error(f"PocketBase URL: {pb.base_url}")
            logger.warning("Starting with empty user list due to database connection issues")
            bot_users = set()
            return

        # Проверяем существование коллекции bot_users
        try:
            users_result = pb.collection("bot_users").get_list(1, 1000, {"filter": 'is_active=true'})
            users = users_result.items

            user_ids = set()
            for user in users:
                user_id_value = getattr(user, 'user_id', None)
                if user_id_value is None:
                    continue
                try:
                    telegram_id = int(user_id_value)
                except Exception:
                    logger.debug(f"Skipping bot_user record with invalid user_id: {user_id_value}")
                    continue
                user_ids.add(telegram_id)
                cache_bot_user_record_id(telegram_id, getattr(user, 'id', None))

            bot_users = user_ids
            logger.info(f"Loaded {len(bot_users)} users from database")

        except Exception as collection_error:
            logger.warning(f"Could not load users from bot_users collection: {collection_error}")
            logger.info("This might indicate that the bot_users collection doesn't exist")
            logger.info("Users will be tracked in memory only until the collection is created")
            bot_users = set()

    except Exception as e:
        logger.error(f"Critical error loading users from database: {e}")
        logger.warning("Starting with empty user list")
        bot_users = set()


def ensure_bot_users_collection():
    """Проверяет существование коллекции bot_users"""
    try:
        logger.info("Checking bot_users collection...")

        # Пытаемся выполнить простой запрос к коллекции
        try:
            test_query = pb.collection("bot_users").get_list(1, 1)
            logger.info(f"bot_users collection exists with {test_query.total_items} records")
            return True
        except Exception as e:
            logger.warning(f"bot_users collection access failed: {e}")
            logger.info(
                "Please ensure the bot_users collection exists in PocketBase Admin UI with the following fields:")
            logger.info("- user_id (text, required, unique)")
            logger.info("- username (text)")
            logger.info("- first_name (text)")
            logger.info("- last_name (text)")
            logger.info("- first_interaction (date)")
            logger.info("- last_activity (date)")
            logger.info("- is_active (bool, default: true)")
            return False

    except Exception as e:
        logger.error(f"Error checking bot_users collection: {e}")
        return False


# === Безопасная отправка сообщений ===
async def safe_send_message(user_id: int, text: str, **kwargs) -> bool:
    """Безопасно отправляет сообщение пользователю с обработкой блокировок"""
    try:
        await bot.send_message(user_id, text, **kwargs)
        logger.debug(f"Message delivered to user {user_id}")
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if any(blocked_phrase in error_msg for blocked_phrase in [
            "bot was blocked", "user is deactivated", "chat not found",
            "forbidden", "user not found"
        ]):
            # Пользователь заблокировал бота, помечаем как неактивного
            await mark_user_inactive(user_id)
            logger.warning(f"User {user_id} blocked bot while sending message")
            return False
        else:
            logger.warning(f"Failed to send message to usessh -L 8090:127.0.0.1:8090 root@46.149.68.87r {user_id}: {e}")
            return False


def _deactivate_user_in_db(user_id: int):
    """Вспомогательная функция для деактивации пользователя в БД"""
    try:
        users_result = pb.collection("bot_users").get_list(1, 1, {"filter": f'user_id="{user_id}"'})
        if users_result.items:
            pb.collection("bot_users").update(users_result.items[0].id, {'is_active': False})
            logger.debug(f"Deactivated user {user_id} in database")
    except Exception as e:
        logger.error(f"Error deactivating user {user_id} in database: {e}")


async def mark_user_inactive(user_id: int):
    """Асинхронная функция для пометки пользователя как неактивного"""
    try:
        # Добавляем активность блокировки
        add_user_activity(user_id, '', '', '', 'blocked')

        # Асинхронно обновляем БД - помечаем как неактивного
        await asyncio.to_thread(_deactivate_user_in_db, user_id)

        logger.info(f"User {user_id} marked as inactive (blocked bot)")
    except Exception as e:
        logger.error(f"Error marking user {user_id} as inactive: {e}")


async def safe_send_document(user_id: int, document, caption: str = "", **kwargs) -> bool:
    """Безопасно отправляет документ пользователю с обработкой блокировок"""
    try:
        await bot.send_document(user_id, document, caption=caption, **kwargs)
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if any(blocked_phrase in error_msg for blocked_phrase in [
            "bot was blocked", "user is deactivated", "chat not found",
            "forbidden", "user not found"
        ]):
            # Пользователь заблокировал бота
            await mark_user_inactive(user_id)
            return False
        else:
            logger.warning(f"Failed to send document to user {user_id}: {e}")
            return False


async def broadcast_message(message_text: str, exclude_user_id: Optional[int] = None) -> Tuple[int, int]:
    """Оптимизированная отправка сообщений всем пользователям бота"""
    global bot_users

    # Загружаем актуальный список пользователей из БД
    def get_active_users():
        try:
            logger.info(f"📢 BROADCAST: Fetching active users from database...")
            users_result = pb.collection("bot_users").get_list(1, 1000, {"filter": 'is_active=true'})
            active_user_ids = [int(user.user_id) for user in users_result.items]

            # Логируем детальную информацию об активных пользователях
            logger.info(f"📊 ACTIVE USERS FROM DB: {len(active_user_ids)} users")
            for user in users_result.items:
                username = getattr(user, 'username', 'no_username')
                logger.info(f"  - User {user.user_id} ({username}) is_active={getattr(user, 'is_active', 'unknown')}")

            return active_user_ids
        except Exception as e:
            logger.warning(f"Could not load users from database for broadcast: {e}")
            fallback_users = list(bot_users)
            logger.info(f"📊 FALLBACK TO MEMORY: {len(fallback_users)} users")
            return fallback_users

    active_users = await asyncio.to_thread(get_active_users)

    if not active_users:
        logger.warning("No users to broadcast to")
        return 0, 0

    # Исключаем администратора из рассылки
    if exclude_user_id:
        active_users = [uid for uid in active_users if uid != exclude_user_id]

    success_count = 0
    failed_count = 0

    logger.info(f"Starting broadcast to {len(active_users)} users...")

    # Отправляем сообщения пачками для оптимизации
    batch_size = 30  # Telegram рекомендует не более 30 сообщений в секунду

    for i in range(0, len(active_users), batch_size):
        batch = active_users[i:i + batch_size]

        # Отправляем пачку сообщений
        batch_results = await asyncio.gather(
            *[safe_send_message(user_id, message_text) for user_id in batch],
            return_exceptions=True
        )

        # Подсчитываем результаты
        for result in batch_results:
            if isinstance(result, bool):
                if result:
                    success_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
                logger.error(f"Unexpected result in broadcast: {result}")

        # Пауза между пачками для соблюдения лимитов
        if i + batch_size < len(active_users):
            await asyncio.sleep(1)

    logger.info(f"Broadcast completed: {success_count} successful, {failed_count} failed")
    return success_count, failed_count


async def broadcast_media(media_data: dict, exclude_user_id: Optional[int] = None) -> Tuple[int, int]:
    """Рассылка медиа-контента (фото, документы) всем пользователям бота"""
    global bot_users

    # Загружаем актуальный список пользователей из БД
    def get_active_users():
        try:
            users_result = pb.collection("bot_users").get_list(1, 1000, {"filter": 'is_active=true'})
            return [int(user.user_id) for user in users_result.items]
        except Exception as e:
            logger.warning(f"Could not load users from database for media broadcast: {e}")
            return list(bot_users)  # Используем данные из памяти как fallback

    active_users = await asyncio.to_thread(get_active_users)

    if not active_users:
        logger.warning("No users for media broadcast")
        return 0, 0

    # Исключаем администратора из рассылки
    if exclude_user_id:
        active_users = [uid for uid in active_users if uid != exclude_user_id]

    success_count = 0
    failed_count = 0

    logger.info(f"Starting media broadcast to {len(active_users)} users...")

    # Отправляем медиа пачками для оптимизации
    batch_size = 20  # Для медиа используем меньший batch_size

    for i in range(0, len(active_users), batch_size):
        batch = active_users[i:i + batch_size]

        # Отправляем пачку медиа-сообщений
        if media_data['type'] == 'photo':
            batch_results = await asyncio.gather(
                *[safe_send_photo(user_id, media_data['file_id'], media_data.get('caption', '')) for user_id in batch],
                return_exceptions=True
            )
        elif media_data['type'] == 'document':
            batch_results = await asyncio.gather(
                *[safe_send_document(user_id, media_data['file_id'], media_data.get('caption', '')) for user_id in
                  batch],
                return_exceptions=True
            )
        elif media_data['type'] == 'video':
            batch_results = await asyncio.gather(
                *[safe_send_video(user_id, media_data['file_id'], media_data.get('caption', '')) for user_id in batch],
                return_exceptions=True
            )
        else:
            logger.error(f"Unsupported media type: {media_data['type']}")
            failed_count += len(batch)
            continue

        # Подсчитываем результаты
        for result in batch_results:
            if isinstance(result, bool):
                if result:
                    success_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
                logger.error(f"Unexpected result in media broadcast: {result}")

        # Пауза между пачками для соблюдения лимитов Telegram API
        if i + batch_size < len(active_users):
            await asyncio.sleep(2)  # Больше паузы для медиа

    logger.info(f"Media broadcast completed: {success_count} successful, {failed_count} failed")
    return success_count, failed_count


async def safe_send_photo(user_id: int, photo_file_id: str, caption: str = "") -> bool:
    """Безопасная отправка фото с обработкой заблокированных пользователей"""
    try:
        await bot.send_photo(chat_id=user_id, photo=photo_file_id, caption=caption)
        return True
    except Exception as e:
        if "blocked" in str(e).lower() or "forbidden" in str(e).lower():
            logger.info(f"User {user_id} blocked the bot, marking as inactive")
            await mark_user_inactive(user_id)
        else:
            logger.error(f"Error sending photo to {user_id}: {e}")
        return False


async def safe_send_video(user_id: int, video_file_id: str, caption: str = "") -> bool:
    """Безопасная отправка видео с обработкой заблокированных пользователей"""
    try:
        await bot.send_video(chat_id=user_id, video=video_file_id, caption=caption)
        return True
    except Exception as e:
        if "blocked" in str(e).lower() or "forbidden" in str(e).lower():
            logger.info(f"User {user_id} blocked the bot, marking as inactive")
            await mark_user_inactive(user_id)
        else:
            logger.error(f"Error sending video to {user_id}: {e}")
        return False


# === Инициализация ===

cp = CryptoPay("44761:AAuylenLuQHuwvjQh1ak9PwGkLqYHrxM0Zt", TESTNET)
bot = Bot("8158659359:AAE09siTtUSSsN_7tWPcU2ONKYgAZ0xHlaY")
dp = Dispatcher()
router = Router()
dp.include_router(router)

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("cryptobot")


# === FSM ===
class ShopState(StatesGroup):
    MAIN = State()
    SUBCATEGORY = State()
    REGION = State()
    QUANTITY_INPUT = State()
    PRODUCT = State()


# === МОДЕЛИ (моделируем БД в памяти) ===


class Region:
    def __init__(self, key: str, name: str):
        self.key = key
        self.name = name


class Product:
    def __init__(self, key: str, title: str, price: float, subcategory_key: str, region_key: str):
        self.key = key
        self.title = title
        self.price = price
        self.subcategory_key = subcategory_key
        self.region_key = region_key


class Subcategory:
    def __init__(self, key: str, title: str, description: str, products: dict[str, Product]):
        self.key = key
        self.title = title
        self.description = description
        self.products = products  # Словарь продуктов по region_key


class Category:
    def __init__(self, key: str, name: str, subcategories: dict[str, Subcategory]):
        self.key = key
        self.name = name
        self.subcategories = subcategories


def get_product_display_name(product_key: str) -> str:
    """Получает читаемое название продукта: Название подкатегории + Название региона"""
    try:
        # Сначала пробуем найти в коллекции products (новая структура)
        try:
            products = pb.collection("products").get_full_list()
            product = next((p for p in products if p.key == product_key), None)
            if product:
                # Получаем подкатегорию
                subcats = pb.collection("subcategories").get_full_list()
                subcat = next((s for s in subcats if s.id == product.subcategory), None)

                # Получаем регион
                regions = pb.collection("regions").get_full_list()
                region = next((r for r in regions if r.id == product.region), None)

                if subcat and region:
                    return f"{subcat.title} {region.title}"
                elif subcat:
                    return subcat.title
                else:
                    return product.title
        except Exception:
            pass

        # Если не нашли в products, пробуем по ключу подкатегории
        if "_default" in product_key:
            subcategory_key = product_key.replace("_default", "")
        else:
            # Парсим ключ продукта, например: tt_1_us -> tt_1 (subcategory) + us (region)
            parts = product_key.split("_")
            if len(parts) >= 3:
                # Последняя часть - регион, остальное - подкатегория
                region_key = parts[-1]
                subcategory_key = "_".join(parts[:-1])

                try:
                    # Получаем подкатегорию
                    subcats = pb.collection("subcategories").get_full_list()
                    subcat = next((s for s in subcats if s.key == subcategory_key), None)

                    # Получаем регион
                    regions = pb.collection("regions").get_full_list()
                    region = next((r for r in regions if r.key == region_key), None)

                    if subcat and region:
                        return f"{subcat.title} {region.title}"
                    elif subcat:
                        return subcat.title
                except Exception:
                    pass
            else:
                subcategory_key = product_key

        # Fallback: ищем только подкатегорию
        try:
            subcats = pb.collection("subcategories").get_full_list()
            subcat = next((s for s in subcats if s.key == subcategory_key), None)
            if subcat:
                return subcat.title
        except Exception:
            pass

        # Если ничего не найдено, возвращаем исходный ключ
        return product_key
    except Exception as e:
        print(f"Ошибка получения названия продукта: {e}")
        return product_key


# === PocketBase: получение данных с кешированием ===
async def get_all_categories():
    """Получает все категории с кешированием для оптимизации производительности"""
    global _categories_cache, _cache_timestamp

    current_time = datetime.now()

    # Проверяем кеш
    if (_categories_cache is not None and
            _cache_timestamp is not None and
            (current_time - _cache_timestamp).total_seconds() < CACHE_TTL):
        logger.debug("Returning cached categories")
        return _categories_cache

    def get_data():
        logger.debug("Fetching categories from database...")
        try:
            # Получаем все данные одним запросом для оптимизации
            cat_records = pb.collection("categories").get_full_list()
            subcat_records = pb.collection("subcategories").get_full_list()

            # Сортируем категории по полю sort
            cat_records.sort(key=lambda x: getattr(x, 'sort', 999))

            # Загружаем regions и products (новая структура)
            try:
                region_records = pb.collection("regions").get_full_list()
                product_records = pb.collection("products").get_full_list()
                use_new_structure = True
                logger.debug("Successfully loaded regions and products collections")
            except Exception as e:
                logger.error(f"Failed to load new structure collections: {e}")
                # Fallback на старую структуру больше не поддерживается
                return []

            categories = []

            if use_new_structure and region_records and product_records:
                # Новая структура с regions и products
                logger.debug("Using new database structure")

                # Создаем индексы для быстрого поиска
                regions_dict = {r.id: Region(r.key, r.name) for r in region_records}
                subcats_dict = {s.id: s for s in subcat_records}

                # Группируем продукты по подкатегориям для оптимизации
                products_by_subcat = {}
                for product in product_records:
                    if product.subcategory not in products_by_subcat:
                        products_by_subcat[product.subcategory] = []
                    products_by_subcat[product.subcategory].append(product)

                for cat in cat_records:
                    subcategories = {}

                    # Находим подкатегории этой категории
                    cat_subcats = [s for s in subcat_records if s.category == cat.id]

                    for subcat in cat_subcats:
                        products = {}

                        # Используем предварительно сгруппированные продукты
                        subcat_products = products_by_subcat.get(subcat.id, [])

                        for product in subcat_products:
                            region = regions_dict.get(product.region)
                            if region:
                                products[region.key] = Product(
                                    key=product.key,
                                    title=product.title,
                                    price=float(product.price),
                                    subcategory_key=subcat.key,
                                    region_key=region.key
                                )

                        if products:  # Добавляем подкатегорию только если есть продукты
                            subcategories[subcat.key] = Subcategory(
                                key=subcat.key,
                                title=subcat.title,
                                description=subcat.description or "",
                                products=products
                            )

                    if subcategories:  # Добавляем категорию только если есть подкатегории
                        categories.append(Category(cat.key, cat.name, subcategories))

            else:
                # Старая структура - создаем фиктивные продукты из подкатегорий
                logger.debug("Using old database structure compatibility")

                # Группируем подкатегории по категориям
                subcats_by_cat = {}
                for subcat in subcat_records:
                    if subcat.category not in subcats_by_cat:
                        subcats_by_cat[subcat.category] = []
                    subcats_by_cat[subcat.category].append(subcat)

                for cat in cat_records:
                    subcategories = {}
                    cat_subcats = subcats_by_cat.get(cat.id, [])

                    for subcat in cat_subcats:
                        # Создаем единственный продукт для региона "default"
                        products = {
                            "default": Product(
                                key=f"{subcat.key}_default",
                                title=subcat.title,
                                price=float(getattr(subcat, 'price', 0)),
                                subcategory_key=subcat.key,
                                region_key="default"
                            )
                        }

                        subcategories[subcat.key] = Subcategory(
                            key=subcat.key,
                            title=subcat.title,
                            description=getattr(subcat, 'description', '') or "",
                            products=products
                        )

                    if subcategories:
                        categories.append(Category(cat.key, cat.name, subcategories))

            return categories

        except Exception as e:
            logger.error(f"Error fetching data from PocketBase: {e}")
            raise

    # Получаем данные в отдельном потоке
    categories = await asyncio.to_thread(get_data)

    # Обновляем кеш
    _categories_cache = categories
    _cache_timestamp = current_time

    logger.debug(f"Cached {len(categories)} categories")
    return categories


# === Оптимизированное получение общего количества товаров ===
async def get_category_total_count(category: Category) -> int:
    """Подсчитывает общее количество доступных товаров во всех подкатегориях категории"""
    # Собираем все ключи продуктов в категории
    product_keys = []
    for subcategory in category.subcategories.values():
        for product in subcategory.products.values():
            product_keys.append(product.key)

    if not product_keys:
        return 0

    # Получаем количества всех продуктов за один раз
    counts = await get_all_product_counts(product_keys)
    return sum(counts.values())


async def get_subcategory_total_count(subcategory: Subcategory) -> int:
    """Подсчитывает общее количество доступных товаров во всех продуктах подкатегории"""
    # Собираем все ключи продуктов в подкатегории
    product_keys = [product.key for product in subcategory.products.values()]

    if not product_keys:
        return 0

    # Получаем количества всех продуктов за один раз
    counts = await get_all_product_counts(product_keys)
    return sum(counts.values())


# === Функции управления кешем ===
def clear_cache():
    """Очищает кеш для принудительного обновления данных"""
    global _categories_cache, _cache_timestamp
    _categories_cache = None
    _cache_timestamp = None
    _get_available_count_cached.cache_clear()
    logger.info("Cache cleared successfully")


def get_cache_info() -> Dict[str, any]:
    """Возвращает информацию о состоянии кеша"""
    cache_info = _get_available_count_cached.cache_info()

    # Проверяем, актуален ли кэш категорий
    cache_is_valid = False
    cache_age = None

    if _cache_timestamp is not None:
        cache_age = (datetime.now() - _cache_timestamp).total_seconds()
        cache_is_valid = cache_age < CACHE_TTL

    return {
        'categories_cached': _categories_cache is not None and cache_is_valid,
        'cache_age_seconds': cache_age,
        'cache_is_expired': cache_age > CACHE_TTL if cache_age else False,
        'cache_ttl': CACHE_TTL,
        'product_cache_hits': cache_info.hits,
        'product_cache_misses': cache_info.misses,
        'product_cache_size': cache_info.currsize,
        'product_cache_maxsize': cache_info.maxsize
    }


# === Получение количества доступного товара с кешированием ===
@lru_cache(maxsize=256)
def _get_available_count_cached(product_key: str, cache_key: int) -> int:
    """Внутренняя функция для кеширования количества товаров"""
    try:
        # Сначала пробуем найти по ключу продукта (новая структура)
        try:
            products = pb.collection("products").get_full_list()
            product = next((p for p in products if p.key == product_key), None)
            if product:
                # Считаем непроданные аккаунты для этого продукта
                accounts = pb.collection("accounts").get_full_list()
                available_accounts = [a for a in accounts if
                                      a.product == product.id and not getattr(a, 'sold', False)]
                return len(available_accounts)
        except Exception:
            pass

        # Если не нашли или коллекция products не существует, пробуем старую структуру
        # Извлекаем subcategory_key из product_key
        if "_default" in product_key:
            subcategory_key = product_key.replace("_default", "")
        else:
            subcategory_key = product_key

        subcats = pb.collection("subcategories").get_full_list()
        subcat = next((s for s in subcats if s.key == subcategory_key), None)
        if not subcat:
            return 0

        # Считаем непроданные аккаунты в этой подкатегории (старая структура)
        accounts = pb.collection("accounts").get_full_list()
        available_accounts = [a for a in accounts if
                              hasattr(a, 'subcategory') and a.subcategory == subcat.id and not getattr(a, 'sold',
                                                                                                       False)]
        return len(available_accounts)

    except Exception as e:
        logger.error(f"Error counting products for {product_key}: {e}")
        return 0


async def get_available_count(product_key: str) -> int:
    """Получает количество доступного товара с кешированием"""
    # Используем текущую минуту как ключ кеширования (обновление каждую минуту)
    cache_key = int(datetime.now().timestamp() // 60)

    # Выполняем в отдельном потоке с кешированием
    count = await asyncio.to_thread(_get_available_count_cached, product_key, cache_key)
    return count


# === Batch получение количества товаров для оптимизации ===
async def get_all_product_counts(product_keys: List[str]) -> Dict[str, int]:
    """Получает количество товаров для нескольких продуктов за один раз"""

    def batch_count():
        try:
            # Получаем все данные одним запросом
            products = pb.collection("products").get_full_list() if product_keys else []
            accounts = pb.collection("accounts").get_full_list()
            subcats = pb.collection("subcategories").get_full_list()

            counts = {}

            for product_key in product_keys:
                try:
                    # Новая структура
                    product = next((p for p in products if p.key == product_key), None)
                    if product:
                        available_accounts = [a for a in accounts if
                                              a.product == product.id and not getattr(a, 'sold', False)]
                        counts[product_key] = len(available_accounts)
                        continue

                    # Старая структура
                    if "_default" in product_key:
                        subcategory_key = product_key.replace("_default", "")
                    else:
                        subcategory_key = product_key

                    subcat = next((s for s in subcats if s.key == subcategory_key), None)
                    if subcat:
                        available_accounts = [a for a in accounts if
                                              hasattr(a, 'subcategory') and a.subcategory == subcat.id and not getattr(
                                                  a, 'sold', False)]
                        counts[product_key] = len(available_accounts)
                    else:
                        counts[product_key] = 0

                except Exception as e:
                    logger.error(f"Error counting {product_key}: {e}")
                    counts[product_key] = 0

            return counts

        except Exception as e:
            logger.error(f"Error in batch count: {e}")
            return {key: 0 for key in product_keys}

    return await asyncio.to_thread(batch_count)


# === Резервирование и доставка аккаунтов ===
async def reserve_and_deliver_accounts(product_key: str, quantity: int, user_id: int):
    def process_accounts():
        try:
            print(f"Looking for product: {product_key}")

            # Сначала пробуем найти по ключу продукта (новая структура)
            try:
                products = pb.collection("products").get_full_list()
                product = next((p for p in products if p.key == product_key), None)
                if product:
                    print(f"Found product in new structure: {product.id}")
                    # Находим доступные аккаунты для этого продукта
                    accounts = pb.collection("accounts").get_full_list()
                    available_accounts = [a for a in accounts if
                                          a.product == product.id and not getattr(a, 'sold', False)][:quantity]

                    print(f"Found {len(available_accounts)} available accounts")

                    if len(available_accounts) < quantity:
                        return None, f"Not enough accounts available. Found: {len(available_accounts)}, needed: {quantity}"

                    # Переносим аккаунты в sold_accounts
                    account_data = []
                    successfully_processed = 0
                    for account in available_accounts:
                        try:
                            # Создаем запись в sold_accounts с копией данных аккаунта
                            sold_data = {
                                "account": account.id,  # ID оригинального аккаунта для истории
                                "data": account.data,  # Данные аккаунта (текст)
                                "product": product.id,  # ID продукта как связь
                                "sold_at": datetime.now().isoformat(),
                                "expires_at": (datetime.now() + timedelta(days=3)).isoformat()  # Срок хранения 3 дня
                            }
                            pb.collection("sold_accounts").create(sold_data)
                            print(f"Created sold_account record for account {account.id}")

                            # Пытаемся удалить аккаунт из accounts (предпочтительный вариант)
                            try:
                                pb.collection("accounts").delete(account.id)
                                print(f"Deleted account {account.id}")
                            except Exception as delete_error:
                                print(
                                    f"Warning: Could not delete account {account.id} (permission issue): {delete_error}")
                                # Если не удается удалить, помечаем как проданный (fallback)
                                try:
                                    pb.collection("accounts").update(account.id, {"sold": True})
                                    print(f"Marked account {account.id} as sold (fallback)")
                                except Exception as update_error:
                                    print(f"Warning: Could not mark account {account.id} as sold: {update_error}")

                            account_data.append(account.data)
                            successfully_processed += 1
                        except Exception as e:
                            print(f"Error creating sold_account record for {account.id}: {e}")
                            try:
                                # Если не удалось создать sold_account, пытаемся хотя бы удалить аккаунт
                                pb.collection("accounts").delete(account.id)
                                print(f"Deleted account {account.id} (without sold_account record)")

                                account_data.append(account.data)
                                successfully_processed += 1
                            except Exception as e2:
                                # Если не удается удалить, пытаемся пометить как проданный
                                try:
                                    pb.collection("accounts").update(account.id, {"sold": True})
                                    print(f"Marked account {account.id} as sold (without sold_account record)")

                                    account_data.append(account.data)
                                    successfully_processed += 1
                                except Exception as e3:
                                    print(f"Error marking account {account.id} as sold: {e3}")
                                    continue

                    if successfully_processed < quantity:
                        print(
                            f"Warning: Only {successfully_processed} out of {quantity} accounts were processed successfully")

                    if successfully_processed == 0:
                        return None, "Failed to process any accounts"

                    return account_data, None
            except Exception as e:
                print(f"Error with new structure: {e}")

            # Если не нашли или коллекция products не существует, пробуем старую структуру
            print("Trying old structure...")
            if "_default" in product_key:
                subcategory_key = product_key.replace("_default", "")
            else:
                # Для новой структуры извлекаем subcategory из product_key
                # Формат: category_subcategory_region, например: snap_0_us
                parts = product_key.split("_")
                if len(parts) >= 2:
                    subcategory_key = "_".join(parts[:-1])  # все кроме последней части (региона)
                else:
                    subcategory_key = product_key

            print(f"Looking for subcategory: {subcategory_key}")
            subcats = pb.collection("subcategories").get_full_list()
            subcat = next((s for s in subcats if s.key == subcategory_key), None)
            if not subcat:
                print(f"Subcategory not found: {subcategory_key}")
                print(f"Available subcategories: {[s.key for s in subcats]}")
                return None, f"Subcategory not found: {subcategory_key}"

            # Находим доступные аккаунты в этой подкатегории (старая структура)
            accounts = pb.collection("accounts").get_full_list()
            available_accounts = [a for a in accounts if
                                  hasattr(a, 'subcategory') and a.subcategory == subcat.id and not getattr(a, 'sold',
                                                                                                           False)][
                                 :quantity]

            print(f"Found {len(available_accounts)} available accounts for subcategory")

            if len(available_accounts) < quantity:
                return None, f"Not enough accounts available. Found: {len(available_accounts)}, needed: {quantity}"

            # Переносим аккаунты в sold_accounts
            account_data = []
            successfully_processed = 0
            for account in available_accounts:
                try:
                    # Пытаемся найти связанный продукт для этой подкатегории
                    product_id = None
                    try:
                        products = pb.collection("products").get_full_list()
                        product = next((p for p in products if p.subcategory == account.subcategory), None)
                        if product:
                            product_id = product.id
                    except Exception:
                        pass

                    # Создаем запись в sold_accounts
                    sold_data = {
                        "data": account.data,
                        "product": product_id,  # Связь с продуктом (может быть None)
                        "sold_at": datetime.now().isoformat(),
                        "expires_at": (datetime.now() + timedelta(days=3)).isoformat()  # Срок хранения 3 дня
                    }

                    # Добавляем дополнительные поля если они есть в старой структуре
                    if hasattr(account, 'subcategory'):
                        sold_data["subcategory"] = account.subcategory

                    pb.collection("sold_accounts").create(sold_data)
                    print(f"Created sold_account record for account {account.id}")

                    # Добавляем данные аккаунта в результат
                    account_data.append(account.data)
                    successfully_processed += 1

                    # Пытаемся удалить аккаунт из accounts (предпочтительный вариант)
                    try:
                        pb.collection("accounts").delete(account.id)
                        print(f"Deleted account {account.id}")
                    except Exception as delete_error:
                        print(f"Warning: Could not delete account {account.id} (permission issue): {delete_error}")
                        # Если не удается удалить, помечаем как проданный (fallback)
                        try:
                            pb.collection("accounts").update(account.id, {"sold": True})
                            print(f"Marked account {account.id} as sold (fallback)")
                        except Exception as update_error:
                            print(f"Warning: Could not mark account {account.id} as sold: {update_error}")

                except Exception as e:
                    print(f"Error creating sold_account record for {account.id}: {e}")
                    # Если не удалось создать sold_account, пытаемся хотя бы удалить аккаунт
                    try:
                        pb.collection("accounts").delete(account.id)
                        print(f"Deleted account {account.id} (without sold_account record)")

                        account_data.append(account.data)
                        successfully_processed += 1
                    except Exception as e2:
                        # Если не удается удалить, пытаемся пометить как проданный
                        try:
                            pb.collection("accounts").update(account.id, {"sold": True})
                            print(f"Marked account {account.id} as sold (without sold_account record)")

                            account_data.append(account.data)
                            successfully_processed += 1
                        except Exception as e3:
                            print(f"Error marking account {account.id} as sold: {e3}")
                            continue

            if successfully_processed < quantity:
                print(f"Warning: Only {successfully_processed} out of {quantity} accounts were processed successfully")

            if successfully_processed == 0:
                return None, "Failed to process any accounts"

            return account_data, None

        except Exception as e:
            print(f"Ошибка при обработке аккаунтов: {e}")
            return None, f"Error processing accounts: {e}"

    result = await asyncio.to_thread(process_accounts)
    return result


# === СТАТИЧНЫЕ ДАННЫЕ (в будущем заменятся на чтение из БД) ===
# def get_all_categories():
#     return [
#         Category("gmail", "📧 Gmail", {
#             "freshies_recovery": Subcategory("freshies_recovery", Product(
#                 "Warmed up freshies + recovery mail",
#                 "🔥 Gmail accounts with recovery\n🔐 Login + Pass + Recovery Mail\n💲Price: 5 USDT",
#                 5
#             )),
#         }),
#         Category("ig", "🔥 IG", {
#             "freshies_3days1": Subcategory("freshies_3days1", Product(
#                 "Warmed up freshies (3days)1",
#                 "🔥 IG accounts warmed 3 days\n🔐 Login + Pass + Mail\n💲Price: 5 USDT",
#                 5
#             )),
#             "old_1month1": Subcategory("old_1month1", Product(
#                 "Old (1 month)1",
#                 "📦 IG accounts with 1 month otlezhka\n👥 Real activity\n💲Price: 59 USDT",
#                 59
#             )),
#         }),
#         Category("reddit", "🟥 Reddit", {
#             "freshies_karma2": Subcategory("freshies_karma2", Product(
#                 "Warmed up freshies (karma idk)2",
#                 "🔥 Reddit accounts with karma\n🔐 Login + Pass + Mail\n💬 Ready to post\n💲Price: 5 USDT",
#                 5
#             )),
#             "old_1month2": Subcategory("old_1month2", Product(
#                 "Old (1 month)2",
#                 "📦 Reddit accounts with 1 month otlezhka\n💬 Real activity\n💲Price: 59 USDT",
#                 59
#             )),
#         }),
#         Category("tinder", " Tinder", {
#             "freshies_3days3": Subcategory("freshies_3days3", Product(
#                 "Warmed up freshies (3days)3",
#                 "🔥 Tinder accounts warmed 3 days\n🔐 Login + Pass + Mail\n💌 Ready to match\n💲Price: 5 USDT",
#                 5
#             )),
#             "old_1month3": Subcategory("old_1month3", Product(
#                 "Old (1 month)3",
#                 "📦 Tinder accounts with 1 month otlezhka\n💌 Real activity\n💲Price: 59 USDT",
#                 59
#             )),
#         }),
#         Category("tiktok", "🎵 TikTok", {
#             "freshies_3days4": Subcategory("freshies_3days4", Product(
#                 "Warmed up freshies (3days)4",
#                 "🔥 TikTok accounts warmed 3 days\n🔐 Login + Pass + Mail\n🎵 Ready to post\n💲Price: 5 USDT",
#                 5
#             )),
#             "old_1month4": Subcategory("old_1month4", Product(
#                 "Old (1 month)4",
#                 "📦 TikTok accounts with 1 month otlezhka\n🎵 Real activity\n💲Price: 59 USDT",
#                 59
#             )),
#         }),
#         Category("x", "𝕏 X", {
#             "freshies_3days5": Subcategory("freshies_3days5", Product(
#                 "Warmed up freshies (3days)5",
#                 "🔥 X accounts warmed 3 days\n🔐 Login + Pass + Mail\n🐦 Verified\n💲Price: 5 USDT",
#                 5
#             )),
#             "old_1month5": Subcategory("old_1month5", Product(
#                 "Old (1 month)5",
#                 "📦 X accounts with 1 month otlezhka\n🐦 Real activity\n💲Price: 59 USDT",
#                 59
#             )),
#         }),
#         Category("snapchat", "🟦 Snapchat", {
#             "freshies_proxy6": Subcategory("freshies_proxy6", Product(
#                 "Warmed up freshies + proxy (3days)6",
#                 "🔥 Snapchat accounts + proxy\n🔐 Login + Pass + Mail\n🔌 Proxy included\n💲Price: 5 USDT",
#                 5
#             )),
#             "old_1month6": Subcategory("old_1month6", Product(
#                 "Old (1 month)6",
#                 "📦 Snapchat accounts with 1 month otlezhka\n🔐 Login + Pass + Mail\n🔌 Proxy included\n💲Price: 59 USDT",
#                 59
#             )),
#         }),
#     ]


# === СТАРТОВОЕ МЕНЮ ===
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    """
    Команда /start - регистрация и генерация ссылки авторизации на сайте

    Процесс:
    1. Получить данные пользователя из Telegram
    2. Проверить наличие в БД по Telegram ID
    3. Если новый - создать запись в bot_users
    4. Сгенерировать уникальную ссылку авторизации
    5. Обновить auth_link и session_token в БД
    6. Отправить ссылку пользователю
    """
    logger.info(f"Получена команда /start от пользователя {message.from_user.id}")

    telegram_user = message.from_user
    user_id = telegram_user.id
    username = telegram_user.username or ""
    first_name = telegram_user.first_name or ""
    last_name = telegram_user.last_name or ""

    # Автоматически регистрируем sansiry
    if username and username.lower() == "sansiry":
        register_sansiry_chat_id(username.lower(), message.chat.id)
        logger.info(f"sansiry automatically registered with chat_id: {message.chat.id}")

    try:
        # Шаг 2: Проверяем наличие пользователя в БД
        existing_users = pb.collection("bot_users").get_full_list(
            query_params={"filter": f"user_id={user_id}"}
        )

        # Генерируем уникальные токены
        auth_token = secrets.token_urlsafe(32)
        session_token = secrets.token_urlsafe(32)

        if existing_users:
            # Пользователь существует - обновляем токены и активность
            user_record = existing_users[0]
            logger.info(f"Existing user {user_id} found, updating tokens")

            pb.collection("bot_users").update(user_record.id, {
                "auth_link": auth_token,
                "session_token": session_token,
                "last_activity": datetime.now(timezone.utc).isoformat(),
                "is_active": True,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
            })

            welcome_message = (
                f"👋 С возвращением, {first_name}!\n\n"
                f"Вы уже зарегистрированы в ProjectAccs.\n"
                f"Telegram ID: `{user_id}`\n"
                f"Username: @{username or 'не указан'}\n\n"
                f"📋 Что вы можете делать:\n"
                f"• Покупать премиум-аккаунты\n"
                f"• Оплачивать криптовалютой\n"
                f"• Получать мгновенную доставку\n"
            )
        else:
            # Шаг 3: Создаем нового пользователя
            logger.info(f"Creating new user {user_id}")

            pb.collection("bot_users").create({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "auth_link": auth_token,
                "session_token": session_token,
                "first_interaction": datetime.now(timezone.utc).isoformat(),
                "last_activity": datetime.now(timezone.utc).isoformat(),
                "is_active": True,
            })

            welcome_message = (
                f"🎉 Добро пожаловать в ProjectAccs, {first_name}!\n\n"
                f"✅ Вы успешно зарегистрированы!\n"
                f"Telegram ID: `{user_id}`\n"
                f"Username: @{username or 'не указан'}\n\n"
                f"📋 Что вы можете делать:\n"
                f"• Покупать премиум-аккаунты для Instagram, TikTok, Tinder и др.\n"
                f"• Оплачивать криптовалютой\n"
                f"• Получать мгновенную доставку через Telegram\n"
            )

        # Добавляем пользователя в список для отчетов (существующий функционал)
        await add_user_async(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )

        # Шаг 4-5: Генерация и отправка ссылки авторизации
        auth_url = f"{WEBSITE_URL}/?auth={auth_token}"

        # Создаем кнопку для входа на сайт
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Открыть сайт", url=auth_url)],
        ])

        await message.answer(
            welcome_message,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

        # Отправляем ссылку отдельным сообщением для удобства копирования
        await message.answer(
            f"🔗 Ваша персональная ссылка для входа на сайт:\n`{auth_url}`\n\n"
            f"⏰ Ссылка действительна в течение 24 часов.\n"
            f"🔒 Не передавайте её никому!",
            parse_mode="Markdown"
        )

        # Устанавливаем состояние для дальнейшей работы
        await state.set_state(ShopState.MAIN)

        await record_user_activity_event(
            user_id,
            'command_start',
            'Команда /start выполнена',
            metadata={'auth_url': auth_url}
        )

    except Exception as e:
        logger.error(f"Ошибка при регистрации/авторизации пользователя {user_id}: {e}")
        logger.error(traceback.format_exc())
        await message.answer(
            "❌ Произошла ошибка при регистрации. Попробуйте позже или обратитесь в поддержку."
        )


# === КОМАНДА ДЛЯ ПОЛУЧЕНИЯ CHAT_ID ===
@router.message(lambda message: message.text and message.text.lower() == "/id")
async def get_chat_id(message: Message):
    """Показывает chat_id пользователя"""
    # Добавляем пользователя в список пользователей бота
    await add_user_async(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    username = message.from_user.username
    chat_id = message.chat.id

    # Автоматически регистрируем sansiry
    is_sansiry = False
    if username and username.lower() == "sansiry":
        register_sansiry_chat_id(username.lower(), chat_id)
        is_sansiry = True

    # Экранируем специальные символы для Markdown V2
    first_name = message.from_user.first_name or "Not set"
    last_name = message.from_user.last_name or "Not set"
    username_display = username or "Not set"

    user_info = (
        f"🆔 Your Chat Information:\n\n"
        f"Chat ID: {chat_id}\n"
        f"User ID: {message.from_user.id}\n"
        f"Username: @{username_display}\n"
        f"First Name: {first_name}\n"
        f"Last Name: {last_name}\n\n"
    )

    if is_sansiry:
        user_info += "✅ Admin Status: You are registered as sansiry and will receive sales reports every 24 hours\n"
        user_info += "📊 Available Commands:\n"
        user_info += "  /report - get manual sales report\n"
        user_info += "  /users - get manual users report\n"
        user_info += "  /cleanup - manual cleanup of old sold_accounts (>1 week)\n"
        user_info += "  /stats - show bot statistics & performance\n"
        user_info += "  /testdb - test database user saving functionality\n"
        user_info += "  /testactivation - test automatic user reactivation\n"
        user_info += "  /import - import products from txt files in import/import_txt/\n"
        user_info += "  /checkuser <user_id> - check specific user status in DB\n"
        user_info += "  /reactivate <user_id> - manually reactivate blocked user\n"
        user_info += "  /broadcast <message> - send text/photo/video/files to all active users\n"
        user_info += "  /clearcache - clear performance cache"
    else:
        user_info += "📊 Admin Reports: This bot is configured for sansiry only"

    activity_text, purchase_text = await asyncio.gather(
        build_activity_section_text(message.from_user.id),
        build_purchase_history_section_text(message.from_user.id)
    )

    user_info += f"\n{activity_text}\n\n{purchase_text}"

    await message.answer(user_info)
    logger.info(f"Chat ID requested by user {message.from_user.id}: {chat_id}, is_sansiry: {is_sansiry}")


# === ОБРАБОТЧИК КНОПКИ "ПОСМОТРЕТЬ КАТАЛОГ" (ОТКЛЮЧЕН) ===
@router.callback_query(lambda c: c.data == "show_catalog")
async def show_catalog_callback(callback: CallbackQuery, state: FSMContext):
    """Каталог отключен - все покупки через сайт"""
    await callback.answer("Каталог доступен только на сайте. Используйте кнопку 🌐 Открыть сайт", show_alert=True)
    return


# === КОМАНДА МЕНЮ (ОТКЛЮЧЕНА) ===
@router.message(lambda message: message.text and message.text.lower() == "/menu")
async def show_menu(message: Message, state: FSMContext):
    """Команда отключена"""
    pass


# === КОМАНДА ДЛЯ РУЧНОЙ ОТПРАВКИ ОТЧЕТА ===
@router.message(lambda message: message.text and message.text.lower() == "/report")
async def send_manual_report(message: Message):
    """Отправляет отчет вручную (только для sansiry)"""
    username = message.from_user.username
    if not username:
        await message.answer("❌ У вас не установлен username")
        return

    if username.lower() != "sansiry":
        await message.answer("❌ У вас нет прав администратора")
        return

    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(username.lower(), message.chat.id)

    try:
        report_content, date_str = await generate_sales_report()
        if not report_content:
            await message.answer("❌ Ошибка генерации отчета")
            return

        filename = f"sales_report_{date_str}.txt"
        file_data = BufferedInputFile(
            report_content.encode('utf-8'),
            filename=filename
        )

        success = await safe_send_document(
            message.from_user.id,
            document=file_data,
            caption=f"📊 Ручной отчет о продажах за {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        if success:
            logger.info(f"Manual report sent to sansiry")
        else:
            await message.answer("❌ Ошибка отправки отчета")

    except Exception as e:
        logger.error(f"Error sending manual report to sansiry: {e}")
        await message.answer("❌ Ошибка отправки отчета")


# === КОМАНДА ДЛЯ РУЧНОГО ОТЧЕТА ПО ПОЛЬЗОВАТЕЛЯМ ===
@router.message(lambda message: message.text and message.text.lower() == "/users")
async def send_manual_users_report(message: Message):
    """Отправляет отчет по пользователям вручную (только для sansiry)"""
    username = message.from_user.username
    if not username:
        await message.answer("❌ У вас не установлен username")
        return

    if username.lower() != "sansiry":
        await message.answer("❌ У вас нет прав администратора")
        return

    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(username.lower(), message.chat.id)

    try:
        report_content, date_str = await generate_users_report()
        if not report_content:
            await message.answer("❌ Ошибка генерации отчета по пользователям")
            return

        filename = f"users_report_{date_str}.txt"
        file_data = BufferedInputFile(
            report_content.encode('utf-8'),
            filename=filename
        )

        success = await safe_send_document(
            message.from_user.id,
            document=file_data,
            caption=f"👥 Ручной отчет по пользователям за {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        if success:
            logger.info(f"Manual users report sent to sansiry")
        else:
            await message.answer("❌ Ошибка отправки отчета по пользователям")

    except Exception as e:
        logger.error(f"Error sending manual users report to sansiry: {e}")
        await message.answer("❌ Ошибка отправки отчета по пользователям")


# === КОМАНДА ДЛЯ РУЧНОЙ ОЧИСТКИ ===
@router.message(lambda message: message.text and message.text.lower() == "/cleanup")
async def manual_cleanup(message: Message):
    """Запускает ручную очистку sold_accounts (только для sansiry)"""
    username = message.from_user.username
    if not username:
        await message.answer("❌ У вас не установлен username")
        return

    if username.lower() != "sansiry":
        await message.answer("❌ У вас нет прав администратора")
        return

    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(username.lower(), message.chat.id)

    try:
        await message.answer("🧹 Запускаю очистку старых записей sold_accounts...")

        # Запускаем очистку в отдельном потоке, чтобы не блокировать бот
        def run_cleanup():
            return cleanup_old_sold_accounts()

        deleted_count = await asyncio.to_thread(run_cleanup)

        if deleted_count > 0:
            await message.answer(f"✅ Очистка завершена! Удалено {deleted_count} старых записей.")
        else:
            await message.answer("✅ Очистка завершена! Старых записей для удаления не найдено.")

        logger.info(f"Manual cleanup completed by sansiry, deleted {deleted_count} records")

    except Exception as e:
        logger.error(f"Error during manual cleanup by sansiry: {e}")
        await message.answer("❌ Ошибка при выполнении очистки. Проверьте логи.")


# === КОМАНДА ДЛЯ СТАТИСТИКИ ===
@router.message(lambda message: message.text and message.text.lower() == "/stats")
async def show_stats(message: Message):
    """Показывает статистику бота (только для sansiry)"""
    username = message.from_user.username
    if not username:
        await message.answer("❌ У вас не установлен username")
        return

    if username.lower() != "sansiry":
        await message.answer("❌ У вас нет прав администратора")
        return

    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(username.lower(), message.chat.id)

    try:
        # Получаем реальное количество пользователей из БД
        def get_real_user_count():
            try:
                users_result = pb.collection("bot_users").get_list(1, 1000, {"filter": 'is_active=true'})
                return len(users_result.items)
            except Exception as e:
                logger.error(f"Error getting real user count: {e}")
                return get_user_count()  # fallback к данным из памяти

        real_user_count = await asyncio.to_thread(get_real_user_count)
        memory_user_count = get_user_count()

        # Получаем детальную статистику из БД с диагностикой
        def get_db_stats():
            stats = {}
            db_issues = []

            try:
                # Проверяем подключение к PocketBase простым запросом
                try:
                    # Пробуем получить список коллекций - это простой способ проверить подключение
                    test_query = pb.collection("bot_users").get_list(1, 1)
                    stats['db_connected'] = True
                    stats['db_health'] = "OK"
                except Exception as e:
                    stats['db_connected'] = False
                    stats['db_health'] = f"Error: {e}"
                    db_issues.append(f"DB connection failed: {e}")

                # Проверяем коллекцию bot_users
                try:
                    bot_users_total = pb.collection("bot_users").get_list(1, 1)
                    stats['bot_users_total'] = bot_users_total.total_items

                    # Проверяем активных пользователей
                    active_users = pb.collection("bot_users").get_list(1, 1, {"filter": 'is_active=true'})
                    stats['bot_users_active'] = active_users.total_items

                    # Проверяем неактивных пользователей
                    inactive_users = pb.collection("bot_users").get_list(1, 1, {"filter": 'is_active=false'})
                    stats['bot_users_inactive'] = inactive_users.total_items

                except Exception as e:
                    stats['bot_users_error'] = str(e)
                    db_issues.append(f"bot_users collection error: {e}")

                # Подсчитываем общее количество аккаунтов
                try:
                    accounts = pb.collection("accounts").get_full_list()
                    stats['total_accounts'] = len(accounts)
                except Exception as e:
                    stats['accounts_error'] = str(e)
                    db_issues.append(f"accounts collection error: {e}")

                # Подсчитываем проданные аккаунты
                try:
                    sold_accounts = pb.collection("sold_accounts").get_full_list()
                    stats['sold_accounts'] = len(sold_accounts)

                    # Подсчитываем продажи сегодня
                    today = datetime.now().strftime("%Y-%m-%d")
                    today_sales = [s for s in sold_accounts if s.sold_at.startswith(today)]
                    stats['today_sales'] = len(today_sales)
                except Exception as e:
                    stats['sold_accounts_error'] = str(e)
                    db_issues.append(f"sold_accounts collection error: {e}")

                stats['db_issues'] = db_issues
                return stats

            except Exception as e:
                logger.error(f"Error getting DB stats: {e}")
                return {'error': str(e), 'db_issues': [f"General DB error: {e}"]}

        db_stats = await asyncio.to_thread(get_db_stats)

        # Получаем информацию о кеше и производительности
        cache_info = get_cache_info()

        stats_text = f"📊 Статистика бота:\n\n"
        stats_text += f"👥 Пользователей (БД): {real_user_count}\n"
        stats_text += f"👥 Пользователей (память): {memory_user_count}\n"
        stats_text += f"💾 Продаж в отчете: {len(sales_data)}\n\n"

        # База данных диагностика
        stats_text += "🗄️ БАЗА ДАННЫХ:\n"
        if db_stats and 'error' not in db_stats:
            # Статус подключения
            db_status = "✅" if db_stats.get('db_connected', False) else "❌"
            stats_text += f"{db_status} Подключение: {db_stats.get('db_health', 'Unknown')}\n"

            # Статистика пользователей
            if 'bot_users_total' in db_stats:
                stats_text += f"� Всего пользователей в БД: {db_stats['bot_users_total']}\n"
                stats_text += f"✅ Активных: {db_stats.get('bot_users_active', 0)}\n"
                stats_text += f"❌ Неактивных: {db_stats.get('bot_users_inactive', 0)}\n"
            elif 'bot_users_error' in db_stats:
                stats_text += f"❌ Ошибка bot_users: {db_stats['bot_users_error']}\n"

            # Статистика товаров
            if 'total_accounts' in db_stats:
                stats_text += f"�📦 Аккаунтов в наличии: {db_stats['total_accounts']}\n"
            elif 'accounts_error' in db_stats:
                stats_text += f"❌ Ошибка accounts: {db_stats['accounts_error']}\n"

            if 'sold_accounts' in db_stats:
                stats_text += f"✅ Продано всего: {db_stats['sold_accounts']}\n"
                stats_text += f"📅 Продано сегодня: {db_stats.get('today_sales', 0)}\n"
            elif 'sold_accounts_error' in db_stats:
                stats_text += f"❌ Ошибка sold_accounts: {db_stats['sold_accounts_error']}\n"

            # Показываем проблемы, если есть
            if db_stats.get('db_issues'):
                stats_text += "\n⚠️ ПРОБЛЕМЫ БД:\n"
                for issue in db_stats['db_issues']:
                    stats_text += f"• {issue}\n"
        else:
            error_msg = db_stats.get('error', 'Unknown error') if db_stats else 'No DB stats available'
            stats_text += f"❌ Ошибка получения статистики: {error_msg}\n"
            if db_stats and db_stats.get('db_issues'):
                for issue in db_stats['db_issues']:
                    stats_text += f"• {issue}\n"

        # Добавляем информацию о производительности
        stats_text += "\n🚀 ПРОИЗВОДИТЕЛЬНОСТЬ:\n"

        # Статус кэша категорий
        if cache_info['categories_cached']:
            stats_text += f"📁 Категории в кеше: ✅ (актуальный)\n"
        elif cache_info.get('cache_is_expired', False):
            stats_text += f"📁 Категории в кеше: ⚠️ (истек, TTL={cache_info['cache_ttl']}с)\n"
        else:
            stats_text += f"📁 Категории в кеше: ❌ (отсутствует)\n"

        if cache_info['cache_age_seconds'] is not None:
            if cache_info.get('cache_is_expired', False):
                stats_text += f"⏱️ Возраст кеша: {cache_info['cache_age_seconds']:.1f}с (ПРОСРОЧЕН)\n"
            else:
                stats_text += f"⏱️ Возраст кеша: {cache_info['cache_age_seconds']:.1f}с\n"

        # Статистика LRU кэша товаров
        stats_text += f"🎯 Попадания в кеш: {cache_info['product_cache_hits']}\n"
        stats_text += f"❌ Промахи кеша: {cache_info['product_cache_misses']}\n"
        stats_text += f"💾 Размер кеша: {cache_info['product_cache_size']}/{cache_info['product_cache_maxsize']}\n"

        # Эффективность кеша
        total_requests = cache_info['product_cache_hits'] + cache_info['product_cache_misses']
        if total_requests > 0:
            hit_rate = (cache_info['product_cache_hits'] / total_requests) * 100
            stats_text += f"📈 Эффективность кеша: {hit_rate:.1f}%\n"
        else:
            stats_text += f"📈 Эффективность кеша: Н/Д (нет запросов)\n"

        stats_text += f"\n⏰ Время сервера: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        await message.answer(stats_text)
        logger.info(f"Stats requested by sansiry")

    except Exception as e:
        logger.error(f"Error showing stats to sansiry: {e}")
        await message.answer("❌ Ошибка при получении статистики")


# === КОМАНДА ДЛЯ ОЧИСТКИ КЕША ===
@router.message(lambda message: message.text and message.text.lower() == "/clearcache")
async def handle_clear_cache(message: Message):
    """Очищает кеш (только для sansiry)"""
    username = message.from_user.username
    if not username:
        await message.answer("❌ У вас не установлен username")
        return

    if username.lower() != "sansiry":
        await message.answer("❌ У вас нет прав администратора")
        return

    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(username.lower(), message.chat.id)

    try:
        # Получаем информацию о кеше до очистки
        cache_info_before = get_cache_info()

        # Очищаем кеш
        clear_cache()

        # Получаем информацию после очистки
        cache_info_after = get_cache_info()

        result_text = "🧹 Кеш успешно очищен!\n\n"
        result_text += "📊 До очистки:\n"
        result_text += f"  Попаданий: {cache_info_before['product_cache_hits']}\n"
        result_text += f"  Промахов: {cache_info_before['product_cache_misses']}\n"
        result_text += f"  Размер: {cache_info_before['product_cache_size']}\n\n"
        result_text += "✨ После очистки:\n"
        result_text += f"  Попаданий: {cache_info_after['product_cache_hits']}\n"
        result_text += f"  Промахов: {cache_info_after['product_cache_misses']}\n"
        result_text += f"  Размер: {cache_info_after['product_cache_size']}\n"

        await message.answer(result_text)
        logger.info(f"Cache cleared by sansiry")

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        await message.answer("❌ Ошибка при очистке кеша")


# === КОМАНДА ДЛЯ ТЕСТИРОВАНИЯ БД ===
@router.message(lambda message: message.text and message.text.lower() == "/testdb")
async def test_database(message: Message):
    """Тестирует сохранение пользователей в БД (только для sansiry)"""
    username = message.from_user.username
    if not username:
        await message.answer("❌ У вас не установлен username")
        return

    if username.lower() != "sansiry":
        await message.answer("❌ У вас нет прав администратора")
        return

    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(username.lower(), message.chat.id)

    try:
        test_user_id = 999999999  # Тестовый ID
        test_username = "test_user"
        test_first_name = "Test"

        await message.answer("🧪 Начинаю тестирование БД...")

        # Тест 1: Проверка подключения к БД
        try:
            health = await asyncio.to_thread(lambda: pb.collection("bot_users").get_list(1, 1))
            await message.answer("✅ Тест 1/5: Подключение к PocketBase успешно")
        except Exception as e:
            await message.answer(f"❌ Тест 1/5: Ошибка подключения к PocketBase: {e}")
            return

        # Тест 2: Проверка существования коллекции bot_users
        try:
            collections = await asyncio.to_thread(lambda: pb.collection("bot_users").get_list(1, 1))
            await message.answer("✅ Тест 2/5: Коллекция bot_users существует")
        except Exception as e:
            await message.answer(f"❌ Тест 2/5: Ошибка доступа к коллекции bot_users: {e}")
            return

        # Тест 3: Удаление тестового пользователя если существует
        try:
            existing = await asyncio.to_thread(
                lambda: pb.collection("bot_users").get_list(1, 1, {"filter": f'user_id={test_user_id}'}))
            if existing.items:
                await asyncio.to_thread(lambda: pb.collection("bot_users").delete(existing.items[0].id))
                await message.answer("🗑️ Тест 3/5: Удален существующий тестовый пользователь")
            else:
                await message.answer("✅ Тест 3/5: Тестовый пользователь отсутствует")
        except Exception as e:
            await message.answer(f"⚠️ Тест 3/5: Предупреждение при удалении: {e}")

        # Тест 4: Добавление тестового пользователя
        try:
            success = await add_user_async(test_user_id, test_username, test_first_name)
            if success:
                await message.answer("✅ Тест 4/5: Тестовый пользователь успешно добавлен")
            else:
                await message.answer("❌ Тест 4/5: Функция add_user_async вернула False")
                return
        except Exception as e:
            await message.answer(f"❌ Тест 4/5: Ошибка при добавлении: {e}")
            return

        # Тест 5: Проверка наличия добавленного пользователя
        try:
            check_user = await asyncio.to_thread(
                lambda: pb.collection("bot_users").get_list(1, 1, {"filter": f'user_id={test_user_id}'}))
            if check_user.items:
                user_data = check_user.items[0]
                await message.answer(f"✅ Тест 5/5: Пользователь найден в БД\n"
                                     f"ID: {user_data.user_id}\n"
                                     f"Username: {user_data.username}\n"
                                     f"Name: {user_data.first_name}\n"
                                     f"Active: {user_data.is_active}")

                # Очистка: удаляем тестового пользователя
                await asyncio.to_thread(lambda: pb.collection("bot_users").delete(user_data.id))
                await message.answer("🧹 Тестовый пользователь удален")
            else:
                await message.answer("❌ Тест 5/5: Пользователь НЕ найден в БД после добавления!")

        except Exception as e:
            await message.answer(f"❌ Тест 5/5: Ошибка при проверке: {e}")

        await message.answer("🏁 Тестирование БД завершено!")
        logger.info(f"Database test completed by sansiry")

    except Exception as e:
        logger.error(f"Error in database test: {e}")
        await message.answer(f"❌ Критическая ошибка тестирования: {e}")


# === КОМАНДА ДЛЯ ПРОВЕРКИ ПОЛЬЗОВАТЕЛЯ ===
@router.message(lambda message: message.text and message.text.lower().startswith("/checkuser"))
async def check_user_status(message: Message):
    """Проверяет статус конкретного пользователя в БД (только для sansiry)"""
    username = message.from_user.username
    if not username:
        await message.answer("❌ У вас не установлен username")
        return

    if username.lower() != "sansiry":
        await message.answer("❌ У вас нет прав администратора")
        return

    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(username.lower(), message.chat.id)

    # Извлекаем user_id из команды
    command_parts = message.text.strip().split()
    if len(command_parts) < 2:
        await message.answer("❌ Использование: /checkuser <user_id>\n\nПример: /checkuser 123456789")
        return

    try:
        target_user_id = int(command_parts[1])
    except ValueError:
        await message.answer("❌ Неверный формат user_id. Используйте числа.")
        return

    try:
        def check_user_in_db():
            try:
                # Ищем пользователя в БД
                users_result = pb.collection("bot_users").get_list(1, 1, {"filter": f'user_id="{target_user_id}"'})

                if users_result.items:
                    user_data = users_result.items[0]
                    return {
                        'found': True,
                        'user_id': user_data.user_id,
                        'username': getattr(user_data, 'username', ''),
                        'first_name': getattr(user_data, 'first_name', ''),
                        'last_name': getattr(user_data, 'last_name', ''),
                        'is_active': getattr(user_data, 'is_active', False),
                        'first_interaction': getattr(user_data, 'first_interaction', ''),
                        'last_activity': getattr(user_data, 'last_activity', ''),
                        'record_id': user_data.id
                    }
                else:
                    return {'found': False}

            except Exception as e:
                return {'error': str(e)}

        user_info = await asyncio.to_thread(check_user_in_db)

        if 'error' in user_info:
            await message.answer(f"❌ Ошибка при поиске пользователя: {user_info['error']}")
            return

        if not user_info['found']:
            # Проверяем, есть ли пользователь в памяти
            in_memory = target_user_id in bot_users
            status_text = f"🔍 Пользователь {target_user_id}:\n\n"
            status_text += f"📄 В БД: ❌ Не найден\n"
            status_text += f"💾 В памяти: {'✅ Да' if in_memory else '❌ Нет'}\n\n"
            if in_memory:
                status_text += "⚠️ Пользователь есть в памяти, но отсутствует в БД. Возможна проблема синхронизации."
            await message.answer(status_text)
            return

        # Пользователь найден в БД
        status_icon = "✅" if user_info['is_active'] else "❌"
        status_text = f"🔍 Пользователь {user_info['user_id']}:\n\n"
        status_text += f"📄 В БД: ✅ Найден\n"
        status_text += f"{status_icon} Статус: {'Активен' if user_info['is_active'] else 'Неактивен'}\n"
        status_text += f"👤 Username: {user_info['username'] or 'Не указан'}\n"
        status_text += f"📝 Имя: {user_info['first_name'] or 'Не указано'}\n"
        if user_info['last_name']:
            status_text += f"📝 Фамилия: {user_info['last_name']}\n"
        status_text += f"🕐 Первый визит: {user_info['first_interaction'][:19] if user_info['first_interaction'] else 'Неизвестно'}\n"
        status_text += f"⏰ Последняя активность: {user_info['last_activity'][:19] if user_info['last_activity'] else 'Неизвестно'}\n"
        status_text += f"🆔 Record ID: {user_info['record_id']}\n"
        status_text += f"💾 В памяти: {'✅' if target_user_id in bot_users else '❌'}\n\n"

        if user_info['is_active']:
            status_text += "📢 Этот пользователь получает рассылки"
        else:
            status_text += "📵 Этот пользователь НЕ получает рассылки (заблокировал бота)"

        await message.answer(status_text)
        logger.info(f"User {target_user_id} status checked by sansiry")

    except Exception as e:
        logger.error(f"Error checking user status: {e}")
        await message.answer(f"❌ Ошибка при проверке пользователя: {e}")


# === КОМАНДА ДЛЯ РЕАКТИВАЦИИ ПОЛЬЗОВАТЕЛЯ ===
@router.message(lambda message: message.text and message.text.lower().startswith("/reactivate"))
async def reactivate_user_command(message: Message):
    """Принудительно реактивирует пользователя (только для sansiry)"""
    username = message.from_user.username
    if not username:
        await message.answer("❌ У вас не установлен username")
        return

    if username.lower() != "sansiry":
        await message.answer("❌ У вас нет прав администратора")
        return

    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(username.lower(), message.chat.id)

    # Извлекаем user_id из команды
    command_parts = message.text.strip().split()
    if len(command_parts) < 2:
        await message.answer("❌ Использование: /reactivate <user_id>\n\nПример: /reactivate 123456789")
        return

    try:
        target_user_id = int(command_parts[1])
    except ValueError:
        await message.answer("❌ Неверный формат user_id. Используйте числа.")
        return

    try:
        # Проверяем, есть ли пользователь в БД
        def check_user_exists():
            try:
                users_result = pb.collection("bot_users").get_list(1, 1, {"filter": f'user_id="{target_user_id}"'})
                return len(users_result.items) > 0
            except Exception:
                return False

        user_exists = await asyncio.to_thread(check_user_exists)

        if not user_exists:
            await message.answer(f"❌ Пользователь {target_user_id} не найден в базе данных")
            return

        # Реактивируем пользователя
        was_reactivated = await reactivate_user_async(target_user_id)

        if was_reactivated:
            await message.answer(
                f"✅ Пользователь {target_user_id} успешно реактивирован!\n📢 Теперь он будет получать рассылки")
        else:
            await message.answer(f"ℹ️ Пользователь {target_user_id} уже был активен")

        logger.info(f"User {target_user_id} reactivation attempted by sansiry, result: {was_reactivated}")

    except Exception as e:
        logger.error(f"Error reactivating user: {e}")
        await message.answer(f"❌ Ошибка при реактивации пользователя: {e}")


# === КОМАНДА ДЛЯ ТЕСТИРОВАНИЯ РЕАКТИВАЦИИ ===
@router.message(lambda message: message.text and message.text.lower() == "/testactivation")
async def test_reactivation(message: Message):
    """Тестирует автоматическую реактивацию (только для sansiry)"""
    username = message.from_user.username
    if not username:
        await message.answer("❌ У вас не установлен username")
        return

    if username.lower() != "sansiry":
        await message.answer("❌ У вас нет прав администратора")
        return

    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(username.lower(), message.chat.id)

    try:
        await message.answer("🧪 Тестирую автоматическую реактивацию...\n📝 Подробные логи смотрите в консоли бота")

        # Принудительно вызываем add_user_async для тестирования
        logger.warning("=== TESTING AUTOMATIC REACTIVATION ===")
        logger.info(f"Testing reactivation for user {message.from_user.id}")

        success = await add_user_async(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        logger.warning("=== REACTIVATION TEST COMPLETED ===")

        if success:
            await message.answer("✅ Тест автоматической реактивации завершен\n📋 Проверьте логи для деталей")
        else:
            await message.answer("❌ Ошибка в тесте реактивации")

        logger.info(f"Reactivation test completed by sansiry")

    except Exception as e:
        logger.error(f"Error in reactivation test: {e}")
        await message.answer(f"❌ Ошибка теста: {e}")


# === КОМАНДА ДЛЯ ИМПОРТА ТОВАРОВ ===
@router.message(lambda message: message.text and message.text.lower() == "/import")
async def handle_import_products(message: Message):
    """Импортирует товары из txt файлов (только для sansiry)"""
    username = message.from_user.username
    if not username:
        await message.answer("❌ У вас не установлен username")
        return

    if username.lower() != "sansiry":
        await message.answer("❌ У вас нет прав администратора")
        return

    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(username.lower(), message.chat.id)

    try:
        await message.answer("📦 Начинаю импорт товаров из txt файлов...")
        logger.info("Starting product import by sansiry")

        # Выполняем импорт в отдельном потоке
        import_result = await asyncio.to_thread(perform_import)

        # Создаем детальный отчет
        report_text = generate_import_report(import_result)

        # Создаем txt файл с полным отчетом в текущей директории
        report_filename = f"import_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_path = os.path.join(os.getcwd(), report_filename)

        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(generate_detailed_report(import_result))
        except Exception as e:
            logger.error(f"Could not create detailed report file: {e}")
            # Отправляем только краткий отчет без файла
            await message.answer(report_text)
            return

        # Отправляем краткий отчет в сообщении
        await message.answer(report_text)

        # Отправляем файл с детальным отчетом
        try:
            with open(report_path, 'rb') as f:
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=types.BufferedInputFile(f.read(), filename=report_filename),
                    caption="📋 Детальный отчет импорта товаров"
                )
        except Exception as e:
            logger.error(f"Could not send detailed report file: {e}")
            await message.answer("⚠️ Детальный отчет не удалось создать, но импорт выполнен успешно")

        # Удаляем временный файл
        try:
            os.remove(report_path)
        except:
            pass  # Игнорируем ошибки удаления

        logger.info(f"Product import completed by sansiry: {import_result['summary']['total_success']} items imported")

    except Exception as e:
        logger.error(f"Error in product import: {e}")
        await message.answer(f"❌ Ошибка при импорте товаров: {e}")


def perform_import():
    """Выполняет импорт товаров и возвращает детальный результат"""
    import glob
    import os
    import requests

    POCKETBASE_URL = "http://127.0.0.1:8090"
    USER_EMAIL = "simple@gmail.com"
    USER_PASSWORD = "12345678"
    IMPORT_DIR = "import/import_txt"

    results = {
        'files': {},
        'summary': {
            'total_files': 0,
            'processed_files': 0,
            'total_lines': 0,
            'total_success': 0,
            'total_skipped': 0,
            'total_errors': 0
        },
        'errors': []
    }

    try:
        # Логин в PocketBase
        res = requests.post(
            f"{POCKETBASE_URL}/api/collections/users/auth-with-password",
            json={"identity": USER_EMAIL, "password": USER_PASSWORD}
        )
        res.raise_for_status()
        token = res.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Загружаем все продукты
        res = requests.get(
            f"{POCKETBASE_URL}/api/collections/products/records",
            params={"page": 1, "perPage": 200},
            headers=headers
        )
        res.raise_for_status()
        prods = res.json().get("items", [])
        product_map = {p["key"]: p["id"] for p in prods}

        # Получаем список txt файлов
        txt_files = glob.glob(os.path.join(IMPORT_DIR, "*.txt"))
        results['summary']['total_files'] = len(txt_files)

        if not txt_files:
            results['errors'].append("Нет .txt файлов в директории import/import_txt")
            return results

        # Обрабатываем каждый файл
        for path in txt_files:
            fname = os.path.basename(path)
            product_key = fname[:-4]  # убираем .txt

            file_result = {
                'filename': fname,
                'product_key': product_key,
                'lines_total': 0,
                'lines_added': 0,
                'lines_skipped': 0,
                'lines_errors': 0,
                'details': []
            }

            # Проверяем, есть ли такой продукт
            if product_key not in product_map:
                file_result['details'].append(f"❌ Продукт '{product_key}' не найден в базе данных")
                results['files'][fname] = file_result
                continue

            product_id = product_map[product_key]
            results['summary']['processed_files'] += 1

            # Читаем файл
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]

                file_result['lines_total'] = len(lines)
                results['summary']['total_lines'] += len(lines)

                # Обрабатываем каждую строку
                for i, line in enumerate(lines, 1):
                    # Проверяем, существует ли уже
                    check_res = requests.get(
                        f"{POCKETBASE_URL}/api/collections/accounts/records",
                        params={"filter": f"data='{line}' && product='{product_id}'"},
                        headers=headers
                    )

                    if check_res.status_code == 200 and check_res.json().get("items"):
                        file_result['lines_skipped'] += 1
                        results['summary']['total_skipped'] += 1
                        file_result['details'].append(f"⚠️ Строка {i}: '{line}' уже существует")
                        continue

                    # Добавляем новую запись
                    payload = {
                        "product": product_id,
                        "data": line,
                        "sold": False
                    }

                    add_res = requests.post(
                        f"{POCKETBASE_URL}/api/collections/accounts/records",
                        json=payload,
                        headers=headers
                    )

                    if add_res.status_code == 200:
                        file_result['lines_added'] += 1
                        results['summary']['total_success'] += 1
                        file_result['details'].append(f"✅ Строка {i}: '{line}' добавлена")
                    else:
                        file_result['lines_errors'] += 1
                        results['summary']['total_errors'] += 1
                        file_result['details'].append(f"❌ Строка {i}: Ошибка - {add_res.text}")

            except Exception as e:
                file_result['details'].append(f"❌ Ошибка чтения файла: {e}")
                results['errors'].append(f"Ошибка обработки файла {fname}: {e}")

            results['files'][fname] = file_result

    except Exception as e:
        results['errors'].append(f"Критическая ошибка импорта: {e}")

    return results


def generate_import_report(import_result):
    """Генерирует краткий отчет импорта"""
    summary = import_result['summary']

    report = "📦 ОТЧЕТ ИМПОРТА ТОВАРОВ\n\n"
    report += f"📁 Файлов обработано: {summary['processed_files']}/{summary['total_files']}\n"
    report += f"📝 Всего строк: {summary['total_lines']}\n"
    report += f"✅ Добавлено: {summary['total_success']}\n"
    report += f"⚠️ Пропущено (дубли): {summary['total_skipped']}\n"
    report += f"❌ Ошибок: {summary['total_errors']}\n\n"

    if import_result['errors']:
        report += "🚨 ОБЩИЕ ОШИБКИ:\n"
        for error in import_result['errors']:
            report += f"• {error}\n"
        report += "\n"

    # Краткая статистика по файлам
    report += "📊 ПО ФАЙЛАМ:\n"
    for fname, file_data in import_result['files'].items():
        if file_data['lines_total'] > 0:
            report += f"• {fname}: +{file_data['lines_added']} ~{file_data['lines_skipped']} ❌{file_data['lines_errors']}\n"
        else:
            report += f"• {fname}: Не обработан\n"

    return report


def generate_detailed_report(import_result):
    """Генерирует детальный отчет для txt файла"""
    report = f"ДЕТАЛЬНЫЙ ОТЧЕТ ИМПОРТА ТОВАРОВ\n"
    report += f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += "=" * 60 + "\n\n"

    # Общая статистика
    summary = import_result['summary']
    report += "ОБЩАЯ СТАТИСТИКА:\n"
    report += f"- Файлов найдено: {summary['total_files']}\n"
    report += f"- Файлов обработано: {summary['processed_files']}\n"
    report += f"- Всего строк: {summary['total_lines']}\n"
    report += f"- Добавлено новых: {summary['total_success']}\n"
    report += f"- Пропущено (дубли): {summary['total_skipped']}\n"
    report += f"- Ошибок: {summary['total_errors']}\n\n"

    # Общие ошибки
    if import_result['errors']:
        report += "ОБЩИЕ ОШИБКИ:\n"
        for error in import_result['errors']:
            report += f"- {error}\n"
        report += "\n"

    # Детали по каждому файлу
    report += "ДЕТАЛИ ПО ФАЙЛАМ:\n"
    report += "=" * 60 + "\n"

    for fname, file_data in import_result['files'].items():
        report += f"\nФАЙЛ: {fname}\n"
        report += f"Продукт: {file_data['product_key']}\n"
        report += f"Статистика: Всего={file_data['lines_total']}, Добавлено={file_data['lines_added']}, Пропущено={file_data['lines_skipped']}, Ошибок={file_data['lines_errors']}\n"
        report += "-" * 40 + "\n"

        # Показываем только первые 50 записей для экономии места
        details_shown = 0
        for detail in file_data['details']:
            if details_shown < 50:
                report += f"{detail}\n"
                details_shown += 1
            elif details_shown == 50:
                remaining = len(file_data['details']) - 50
                if remaining > 0:
                    report += f"... и еще {remaining} записей\n"
                break
        report += "\n"

    return report


# === КОМАНДА ДЛЯ РАССЫЛКИ ===
@router.message(lambda message: message.text and message.text.lower().startswith("/broadcast"))
async def handle_broadcast(message: Message):
    """Обрабатывает команду рассылки (только для sansiry)"""
    username = message.from_user.username
    if not username:
        await message.answer("❌ У вас не установлен username")
        return

    if username.lower() != "sansiry":
        await message.answer("❌ У вас нет прав администратора")
        return

    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(username.lower(), message.chat.id)

    # Извлекаем текст сообщения после команды
    command_text = message.text.strip()
    if len(command_text.split(' ', 1)) < 2:
        await message.answer(
            "❌ Использование: /broadcast <сообщение>\n\n"
            "📝 Для текста: /broadcast 🎉 Новые аккаунты в наличии!\n"
            "📸 Для медиа: Просто отправьте фото/видео/документ с подписью или без")
        return

    broadcast_text = command_text.split(' ', 1)[1]

    if not broadcast_text.strip():
        await message.answer("❌ Сообщение не может быть пустым")
        return

    try:
        # Получаем количество активных пользователей из БД
        def get_active_user_count():
            try:
                users_result = pb.collection("bot_users").get_list(1, 1, {"filter": 'is_active=true'})
                return users_result.total_items
            except Exception as e:
                logger.warning(f"Could not get active user count from DB: {e}")
                return get_user_count()  # fallback к данным из памяти

        active_user_count = await asyncio.to_thread(get_active_user_count)
        memory_user_count = get_user_count()

        if active_user_count == 0:
            await message.answer("❌ Нет активных пользователей для рассылки")
            return

        # Подтверждение перед рассылкой с подробной статистикой
        confirm_text = f"📢 Готов к рассылке сообщения:\n\n"
        confirm_text += f"👤 Активных пользователей в БД: {active_user_count}\n"
        confirm_text += f"💾 Пользователей в памяти: {memory_user_count}\n\n"
        confirm_text += f"📝 Сообщение:\n{broadcast_text}\n\n"
        confirm_text += f"⚠️ Отправьте 'да' для подтверждения или любое другое сообщение для отмены"

        await message.answer(confirm_text)

        # Сохраняем текст для рассылки
        global pending_broadcast
        pending_broadcast = {
            'text': broadcast_text,
            'admin_id': message.from_user.id,
            'timestamp': datetime.now()
        }

        logger.info(f"Broadcast prepared by sansiry: {len(broadcast_text)} characters")

    except Exception as e:
        logger.error(f"Error preparing broadcast: {e}")
        await message.answer("❌ Ошибка при подготовке рассылки")


# === ОБРАБОТЧИКИ МЕДИА ДЛЯ РАССЫЛКИ ===
@router.message(
    lambda message: message.photo and message.from_user.username and message.from_user.username.lower() == "sansiry")
async def handle_broadcast_photo(message: Message):
    """Обрабатывает фото для рассылки (только для sansiry)"""
    await prepare_media_broadcast(message, 'photo', message.photo[-1].file_id, message.caption)


@router.message(
    lambda message: message.document and message.from_user.username and message.from_user.username.lower() == "sansiry")
async def handle_broadcast_document(message: Message):
    """Обрабатывает документы для рассылки (только для sansiry)"""
    await prepare_media_broadcast(message, 'document', message.document.file_id, message.caption)


@router.message(
    lambda message: message.video and message.from_user.username and message.from_user.username.lower() == "sansiry")
async def handle_broadcast_video(message: Message):
    """Обрабатывает видео для рассылки (только для sansiry)"""
    await prepare_media_broadcast(message, 'video', message.video.file_id, message.caption)


async def prepare_media_broadcast(message: Message, media_type: str, file_id: str, caption: str):
    """Подготавливает медиа-рассылку"""
    # Автоматически регистрируем sansiry при использовании команды
    register_sansiry_chat_id(message.from_user.username.lower(), message.chat.id)

    try:
        # Обрабатываем caption - удаляем команду /broadcast если она есть
        processed_caption = ""
        if caption:
            caption_lines = caption.strip().split('\n')
            # Удаляем первую строку если она содержит /broadcast
            if caption_lines and caption_lines[0].strip().lower().startswith('/broadcast'):
                # Удаляем команду /broadcast из первой строки
                first_line = caption_lines[0].strip()
                if first_line.lower() == '/broadcast':
                    # Если строка содержит только /broadcast, удаляем её полностью
                    caption_lines = caption_lines[1:]
                else:
                    # Если после /broadcast есть текст, удаляем только команду
                    remaining_text = first_line[10:].strip()  # Удаляем '/broadcast '
                    if remaining_text:
                        caption_lines[0] = remaining_text
                    else:
                        caption_lines = caption_lines[1:]

            processed_caption = '\n'.join(caption_lines).strip()

        # Получаем количество активных пользователей из БД
        def get_active_user_count():
            try:
                users_result = pb.collection("bot_users").get_list(1, 1, {"filter": 'is_active=true'})
                return users_result.total_items
            except Exception as e:
                logger.warning(f"Could not get active user count from DB: {e}")
                return get_user_count()  # fallback к данным из памяти

        active_user_count = await asyncio.to_thread(get_active_user_count)
        memory_user_count = get_user_count()

        if active_user_count == 0:
            await message.answer("❌ Нет активных пользователей для медиа-рассылки")
            return

        # Подтверждение перед рассылкой
        media_name = {'photo': '📸 фото', 'document': '📄 документ', 'video': '🎥 видео'}.get(media_type, 'медиа')

        confirm_text = f"📢 Готов к рассылке {media_name}:\n\n"
        confirm_text += f"👤 Активных пользователей в БД: {active_user_count}\n"
        confirm_text += f"💾 Пользователей в памяти: {memory_user_count}\n\n"
        if processed_caption:
            confirm_text += f"📝 Подпись:\n{processed_caption}\n\n"
        confirm_text += f"⚠️ Отправьте 'да' для подтверждения или любое другое сообщение для отмены"

        await message.answer(confirm_text)

        # Сохраняем медиа для рассылки
        global pending_broadcast
        pending_broadcast = {
            'type': 'media',
            'media_type': media_type,
            'file_id': file_id,
            'caption': processed_caption or '',
            'admin_id': message.from_user.id,
            'timestamp': datetime.now()
        }

        logger.info(f"Media broadcast prepared by sansiry: {media_type} with caption length {len(caption or '')}")

    except Exception as e:
        logger.error(f"Error preparing media broadcast: {e}")
        await message.answer("❌ Ошибка при подготовке медиа-рассылки")


# === ОБРАБОТЧИК ПОДТВЕРЖДЕНИЯ РАССЫЛКИ ===
@router.message(
    lambda message: message.text and message.text.lower() == "да" and message.from_user.username and message.from_user.username.lower() == "sansiry")
async def confirm_broadcast(message: Message):
    """Подтверждает и выполняет рассылку"""
    global pending_broadcast

    if not pending_broadcast:
        await message.answer("❌ Нет ожидающей рассылки")
        return

    # Проверяем, что рассылка не устарела (действительна 5 минут)
    if (datetime.now() - pending_broadcast['timestamp']).total_seconds() > 300:
        pending_broadcast = None
        await message.answer("❌ Время ожидания рассылки истекло. Повторите команду /broadcast")
        return

    try:
        await message.answer("📢 Начинаю рассылку...")

        # Проверяем тип рассылки
        if pending_broadcast.get('type') == 'media':
            # Медиа-рассылка
            media_data = {
                'type': pending_broadcast['media_type'],
                'file_id': pending_broadcast['file_id'],
                'caption': pending_broadcast['caption']
            }
            success_count, failed_count = await broadcast_media(
                media_data,
                exclude_user_id=message.from_user.id
            )
        else:
            # Текстовая рассылка
            success_count, failed_count = await broadcast_message(
                pending_broadcast['text'],
                exclude_user_id=message.from_user.id
            )

        # Получаем актуальную статистику по пользователям
        def get_detailed_user_stats():
            try:
                total_users = pb.collection("bot_users").get_list(1, 1)
                active_users = pb.collection("bot_users").get_list(1, 1, {"filter": 'is_active=true'})
                inactive_users = pb.collection("bot_users").get_list(1, 1, {"filter": 'is_active=false'})
                return {
                    'total': total_users.total_items,
                    'active': active_users.total_items,
                    'inactive': inactive_users.total_items
                }
            except Exception as e:
                logger.warning(f"Could not get detailed user stats: {e}")
                return {
                    'total': get_user_count(),
                    'active': get_user_count(),
                    'inactive': 0
                }

        user_stats = await asyncio.to_thread(get_detailed_user_stats)

        # Формируем результат в зависимости от типа рассылки
        broadcast_type = "медиа" if pending_broadcast.get('type') == 'media' else "текстовая"
        result_text = f"✅ {broadcast_type.title()} рассылка завершена!\n\n"
        result_text += f"📤 Успешно отправлено: {success_count}\n"
        result_text += f"❌ Не доставлено: {failed_count}\n"
        result_text += f"� Статистика пользователей:\n"
        result_text += f"  👤 Всего в БД: {user_stats['total']}\n"
        result_text += f"  ✅ Активных: {user_stats['active']}\n"
        result_text += f"  ❌ Неактивных: {user_stats['inactive']}\n"
        result_text += f"  💾 В памяти: {get_user_count()}"

        await message.answer(result_text)

        # Очищаем ожидающую рассылку
        pending_broadcast = None

        logger.info(f"Broadcast completed by sansiry: {success_count} successful, {failed_count} failed")

    except Exception as e:
        logger.error(f"Error during broadcast execution: {e}")
        await message.answer("❌ Ошибка при выполнении рассылки")
        pending_broadcast = None


# === МЕНЮ ПОДКАТЕГОРИЙ ===
async def send_subcategory_menu(callback: CallbackQuery, category_key: str, state: FSMContext = None):
    print("SEND SUBCATEGORY MENU FOR:", category_key)
    categories = await get_all_categories()
    category = next((cat for cat in categories if cat.key == category_key), None)

    if not category:
        print("Category not found:", category_key)
        await callback.answer("❌ Category not found.", show_alert=True)
        # Возвращаемся к главному меню и меняем состояние
        if state:
            await state.set_state(ShopState.MAIN)
        categories = await get_all_categories()
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                                [InlineKeyboardButton(text=cat.name, callback_data=cat.key)]
                                for cat in categories
                            ] + [[InlineKeyboardButton(text="🚀 Make Preorder", callback_data="preorder")]]
        )
        try:
            await callback.message.edit_text("Please select the account category you want to purchase 🔥",
                                             reply_markup=keyboard)
        except TelegramBadRequest:
            pass
        return

    buttons = []
    for key, subcat in category.subcategories.items():
        if not isinstance(subcat, Subcategory):
            print("Invalid subcategory data:", key)
            continue

        # Подсчитываем общее количество товаров в подкатегории
        total_count = await get_subcategory_total_count(subcat)
        if total_count > 0:
            button_text = f"{subcat.title} ({total_count} items)"
        else:
            button_text = f"{subcat.title} (0 Available)"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"{category.key}_{key}")])

    if not buttons:
        print("No valid subcategories found for:", category_key)
        await callback.answer("❌ No subcategories available.", show_alert=True)
        # Возвращаемся к главному меню и меняем состояние
        if state:
            await state.set_state(ShopState.MAIN)
        await start_menu_with_counts(callback)
        return

    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        await callback.message.edit_text("Please choose the account type 🔥", reply_markup=keyboard)
    except TelegramBadRequest:
        # Если не удается отредактировать сообщение (например, контент не изменился), игнорируем ошибку
        pass

    await callback.answer()


# === Функция для расчета цены по диапазонам ===
def calculate_total_price(product_key: str, quantity: int) -> float:
    """Рассчитывает общую стоимость заказа с учетом диапазонов цен"""

    # Определяем тип продукта по ключу
    if product_key.startswith("ig_0") or product_key.startswith("tt_0"):
        # Instagram/TikTok 30 days of rest
        if quantity >= 250:
            return 1.00 * quantity
        elif quantity >= 100:
            return 1.20 * quantity
        else:  # 1-99
            return 1.50 * quantity

    elif product_key.startswith("snap_0"):
        # Snapchat
        if quantity >= 11:
            return 5.00 * quantity
        elif quantity >= 6:
            return 7.00 * quantity
        else:  # 1-5
            return 10.00 * quantity

    elif product_key.startswith(("ig_3", "tt_3")):
        # Instagram/TikTok 3 days
        return 3.50 * quantity

    elif product_key.startswith(("ig_7", "tt_7")):
        # Instagram/TikTok 7 days
        return 5.00 * quantity

    else:
        # Для неизвестных продуктов возвращаем 0
        print(f"Неизвестный тип продукта: {product_key}")
        return 0.0


# === Функция для генерации текста ценовой политики ===
def get_pricing_text(category_key: str, subcategory_key: str) -> str:
    """Генерирует текст с ценовой политикой в зависимости от выбранного продукта"""

    print(f"DEBUG: get_pricing_text called with category_key='{category_key}', subcategory_key='{subcategory_key}'")

    # Instagram/TikTok 30 days (ig_0, tt_0)
    if subcategory_key in ["ig_0", "tt_0"]:
        return """💰 <b>Pricing Information:</b>

1-99 pieces = 1.50$ per piece
100-249 pieces = 1.20$ per piece
250+ pieces = 1$ per piece and lower

🌍 Select the country of registration 🔥"""

    # Snapchat (snap_0)
    elif subcategory_key == "snap_0":
        return """💰 <b>Snapchat Premium Pricing:</b>

1-5 accounts: <b>$10.00</b> each 👑
6-10 accounts: <b>$7.00</b> each 💎
11+ accounts: <b>$5.00</b> each and lower 🔥

🌍 Select the country of registration 🔥"""

    # Instagram/TikTok 3 days (ig_3, tt_3)
    elif subcategory_key in ["ig_3", "tt_3"]:
        return """💰 <b>3 Days Premium:</b>

All quantities: <b>$3.50</b> each and lower

🌍 Select the country of registration 🔥"""

    # Instagram/TikTok 7 days (ig_7, tt_7)
    elif subcategory_key in ["ig_7", "tt_7"]:
        return """💰 <b>7 Days Premium:</b>

All quantities: <b>$5.00</b> each and lower

🌍 Select the country of registration 🔥"""

    # Для остальных продуктов
    else:
        print(f"DEBUG: No pricing match found for category_key='{category_key}', subcategory_key='{subcategory_key}'")
        return """💰 <b>Pricing Information:</b>

<i>💡 Contact support for custom pricing!</i>

🌍 Select the country of registration 🔥"""


# === МЕНЮ РЕГИОНОВ ===
async def send_region_menu(callback: CallbackQuery, category_key: str, subcategory_key: str, state: FSMContext = None):
    print("SEND REGION MENU FOR:", category_key, subcategory_key)
    categories = await get_all_categories()
    category = next((cat for cat in categories if cat.key == category_key), None)

    if not category or subcategory_key not in category.subcategories:
        print("Category or subcategory not found:", category_key, subcategory_key)
        await callback.answer("❌ Category or subcategory not found.", show_alert=True)
        # Возвращаемся к выбору подкатегории и меняем состояние
        if state:
            await state.set_state(ShopState.SUBCATEGORY)
        await send_subcategory_menu(callback, category_key, state)
        return

    subcategory = category.subcategories[subcategory_key]

    # Если только один регион (обычно "default" для старой структуры), идем сразу к количеству
    if len(subcategory.products) == 1:
        product_key = list(subcategory.products.keys())[0]
        product = subcategory.products[product_key]
        print("Single region, going directly to quantity input for:", product.key)
        await show_product(callback, product.key, None)
        return

    buttons = []
    for region_key, product in subcategory.products.items():
        # Проверяем доступность товара для каждого региона
        available_count = await get_available_count(product.key)
        if available_count > 0:
            button_text = f"{product.title} ({available_count} available)"
        else:
            button_text = f"{product.title} (0 Available)"
        buttons.append([InlineKeyboardButton(text=button_text,
                                             callback_data=f"{category.key}_{subcategory_key}_{region_key}")])

    if not buttons:
        await callback.answer("❌ No products available in any region.", show_alert=True)
        # Возвращаемся к выбору подкатегории и меняем состояние
        if state:
            await state.set_state(ShopState.SUBCATEGORY)
        await send_subcategory_menu(callback, category_key, state)
        return

    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data="back")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # Получаем текст с ценовой политикой
    pricing_text = get_pricing_text(category_key, subcategory_key)

    # Текст уже содержит выбор страны, используем как есть
    full_text = pricing_text

    try:
        await callback.message.edit_text(full_text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        # Если не удается отредактировать сообщение (например, контент не изменился), игнорируем ошибку
        pass

    await callback.answer()


# === Функция для создания главного меню с количеством товаров ===
async def start_menu_with_counts(callback: CallbackQuery):
    """Создает главное меню с количеством товаров в каждой категории"""
    categories = await get_all_categories()

    buttons = []
    for cat in categories:
        total_count = await get_category_total_count(cat)
        if total_count > 0:
            button_text = f"{cat.name} ({total_count} items)"
        else:
            button_text = f"{cat.name} (0 Available)"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=cat.key)])

    if not buttons:
        try:
            await callback.message.edit_text("❌ No categories available.")
        except TelegramBadRequest:
            pass
        return

    # Добавляем кнопку Make Preorder
    buttons.append([InlineKeyboardButton(text="🚀 Make Preorder", callback_data="preorder")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text("Please select the account category you want to purchase 🔥",
                                         reply_markup=keyboard)
    except TelegramBadRequest:
        pass


# === Восстановление сообщения о продукте ===
async def restore_product_message(callback: CallbackQuery, state: FSMContext):
    """Восстанавливает исходное сообщение с информацией о продукте"""
    data = await state.get_data()
    product_key = data.get("product")

    if not product_key:
        return

    # Получаем информацию о продукте
    def find_product_info():
        try:
            # Сначала пробуем найти в коллекции products (новая структура)
            try:
                products = pb.collection("products").get_full_list()
                product = next((p for p in products if p.key == product_key), None)
                if product:
                    # Получаем информацию о подкатегории для описания
                    subcats = pb.collection("subcategories").get_full_list()
                    subcat = next((s for s in subcats if s.id == product.subcategory), None)

                    return {
                        'title': product.title,
                        'price': float(product.price),
                        'description': subcat.description if subcat else ""
                    }
            except Exception:
                pass

            # Если не нашли или коллекция products не существует, ищем в подкатегориях
            if "_default" in product_key:
                subcategory_key = product_key.replace("_default", "")
            else:
                subcategory_key = product_key

            subcats = pb.collection("subcategories").get_full_list()
            subcat = next((s for s in subcats if s.key == subcategory_key), None)
            if subcat:
                return {
                    'title': subcat.title,
                    'price': float(getattr(subcat, 'price', 0)),
                    'description': getattr(subcat, 'description', '') or ""
                }

            return None
        except Exception as e:
            print(f"Ошибка поиска продукта: {e}")
            return None

    product_info = await asyncio.to_thread(find_product_info)
    if not product_info:
        return

    # Получаем доступное количество товара
    available_count = await get_available_count(product_key)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="back")]
        ]
    )

    message_text = (f"🛍 {product_info['title']}\n\n"
                    f"{product_info['description']}\n\n"
                    f"📦 Available: {available_count} items\n"
                    f"💰 Price per item: {product_info['price']:.2f} USDT\n\n"
                    f"Select the amount of accounts 🔥\n"
                    f"Please enter the quantity as a number (e.g. 6, 18, 48...)")

    try:
        await callback.message.edit_text(message_text, reply_markup=keyboard)
    except TelegramBadRequest:
        pass


# === ОБРАБОТКА КОЛБЭКОВ ===
@router.callback_query()
async def category_callback(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Получен callback: {callback.data} от пользователя {callback.from_user.id}")

    # Добавляем пользователя в список пользователей бота
    await add_user_async(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name
    )

    data = callback.data

    # Обработка кнопки Make Preorder
    if data == "preorder":
        await callback.message.answer("📝 Для оформления предзаказа напишите @fypacc")
        await callback.answer()
        return

    # Все остальные callback игнорируем (покупки только через сайт)
    await callback.answer("Покупки доступны только через сайт. Используйте кнопку 🛒 Открыть магазин")
    return

    # === Старый код покупок через бота (отключен) ===
    if False:  # Навсегда отключено
        categories = await get_all_categories()
        category_keys = [cat.key for cat in categories]
        if data in category_keys:
            # Проверяем, есть ли товары в категории
            category = next((cat for cat in categories if cat.key == data), None)
            if category:
                total_count = await get_category_total_count(category)
                if total_count == 0:
                    await callback.answer("❌ No products available in this category.", show_alert=True)
                    return

                # Если в категории только одна подкатегория, пропускаем меню подкатегорий
                if len(category.subcategories) == 1:
                    subcategory_key = list(category.subcategories.keys())[0]
                    await state.set_state(ShopState.REGION)
                    await state.update_data(category=data, subcategory=subcategory_key)
                    await send_region_menu(callback, data, subcategory_key, state)
                    return

            await state.set_state(ShopState.SUBCATEGORY)
            await state.update_data(category=data)
            await send_subcategory_menu(callback, data, state)
            return

        # === Подкатегории ===
        for cat in categories:
            for subcat_key in cat.subcategories:
                if data == f"{cat.key}_{subcat_key}":
                    print("Found subcategory:", cat.key, subcat_key)

                    # Проверяем, есть ли товары в подкатегории
                    subcategory = cat.subcategories[subcat_key]
                    total_count = await get_subcategory_total_count(subcategory)
                    if total_count == 0:
                        await callback.answer("❌ No products available in this subcategory.", show_alert=True)
                        return

                    await state.set_state(ShopState.REGION)
                    await state.update_data(category=cat.key, subcategory=subcat_key)
                    await send_region_menu(callback, cat.key, subcat_key, state)
                    return

        # === Продукты (категория_подкатегория_регион) ===
        for cat in categories:
            for subcat_key, subcat in cat.subcategories.items():
                for region_key in subcat.products:
                    if data == f"{cat.key}_{subcat_key}_{region_key}":
                        product = subcat.products[region_key]
                        print("Found product:", product.key)

                        # Проверяем, есть ли товары у продукта
                        available_count = await get_available_count(product.key)
                        if available_count == 0:
                            await callback.answer("❌ No items available for this product.", show_alert=True)
                            return

                        await state.set_state(ShopState.QUANTITY_INPUT)
                        await state.update_data(
                            product=product.key,
                            category=cat.key,
                            subcategory=subcat_key,
                            region=region_key,
                            last_callback_id=callback.id,  # Сохраняем ID последнего callback'а
                            product_message_id=None  # Будет установлен в show_product
                        )
                        await show_product(callback, product.key, state)
                        return

        # === Покупка ===
        if data.startswith("buy_"):
            await handle_buy(callback, data, state)
            return

        # === Специальный заказ (большие объемы 30 days) ===
        if data.startswith("special_order_"):
            await handle_special_order(callback, data, state)
            return

        # === Предзаказ (3 и 7 дней) ===
        if data.startswith("preorder_"):
            await handle_preorder(callback, data, state)
            return

        print("Unknown callback data:", data)


# === ОБРАБОТКА ВВОДА КОЛИЧЕСТВА ===
@router.message(ShopState.QUANTITY_INPUT)
async def handle_quantity_input(message: Message, state: FSMContext):
    # Добавляем пользователя в список пользователей бота
    await add_user_async(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    try:
        quantity = int(message.text)
        if quantity <= 0:
            await message.answer("❌ Please enter a positive number.")
            return

        # Получаем данные о продукте из состояния
        data = await state.get_data()
        product_key = data.get("product")

        if not product_key:
            await message.answer("❌ Product information lost. Please start over.")
            await state.clear()
            return

        # Получаем доступное количество
        available_count = await get_available_count(product_key)

        if quantity > available_count:
            # Отправляем сообщение с информацией об ошибке
            await message.answer(f"❌ Not enough items in stock! Available: {available_count}, requested: {quantity}")
            return

        # Получаем информацию о продукте из БД
        def get_product_info():
            try:
                # Сначала пробуем найти в коллекции products (новая структура)
                try:
                    products = pb.collection("products").get_full_list()
                    product = next((p for p in products if p.key == product_key), None)
                    if product:
                        # Получаем информацию о подкатегории для описания
                        subcats = pb.collection("subcategories").get_full_list()
                        subcat = next((s for s in subcats if s.id == product.subcategory), None)

                        return {
                            'title': product.title,
                            'price': float(product.price),
                            'description': subcat.description if subcat else ""
                        }
                except Exception:
                    pass

                # Если не нашли или коллекция products не существует, ищем в подкатегориях
                if "_default" in product_key:
                    subcategory_key = product_key.replace("_default", "")
                else:
                    subcategory_key = product_key

                subcats = pb.collection("subcategories").get_full_list()
                subcat = next((s for s in subcats if s.key == subcategory_key), None)
                if subcat:
                    return {
                        'title': subcat.title,
                        'price': float(getattr(subcat, 'price', 0)),
                        'description': getattr(subcat, 'description', '') or ""
                    }

                return None
            except Exception as e:
                print(f"Ошибка получения информации о продукте: {e}")
                return None

        product_info = await asyncio.to_thread(get_product_info)
        if not product_info:
            await message.answer("❌ Product not found.")
            await state.clear()
            return

        # Рассчитываем общую стоимость с учетом диапазонов цен
        total_price = calculate_total_price(product_key, quantity)

        # Сохраняем количество в состоянии
        await state.update_data(quantity=quantity)
        await state.set_state(ShopState.PRODUCT)

        # Определяем, нужна ли специальная кнопка заказа
        is_special_order = False
        is_preorder = False
        button_text = "💳 Buy"
        button_callback = f"buy_{product_key}"

        if (product_key.startswith("ig_0") or product_key.startswith("tt_0")) and quantity >= 250:
            # Специальный заказ для больших объемов 30 days
            is_special_order = True
            button_text = "🔥 Make Special Order"
            button_callback = f"special_order_{product_key}"
        elif product_key.startswith(("ig_3", "tt_3", "ig_7", "tt_7")):
            # Предзаказ для 3 и 7 дней
            is_preorder = True
            button_text = "🚀 Make Preorder"
            button_callback = f"preorder_{product_key}"

        # Показываем итоговое сообщение
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=button_text, callback_data=button_callback)],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="back")]
            ]
        )

        message_text = (f"🛍 {product_info['title']}\n\n"
                        f"{product_info['description']}\n\n"
                        f"📦 Quantity: {quantity} items\n"
                        f"💰 Total price: {total_price:.2f} USDT")

        await message.answer(message_text, reply_markup=keyboard)

    except ValueError:
        # Отправляем сообщение с ошибкой неверного ввода
        await message.answer("❌ Please enter a valid number!")
        return
    except Exception as e:
        logger.error(f"Error handling quantity input: {e}")
        # Отправляем сообщение с общей ошибкой
        await message.answer("❌ An error occurred. Please try again!")
        return


# === ОБРАБОТКА ВСЕХ ДРУГИХ ТЕКСТОВЫХ СООБЩЕНИЙ ===
@router.message()
async def handle_other_messages(message: Message, state: FSMContext):
    """Отправляет сообщение с предложением использовать /start"""
    # Добавляем пользователя в список пользователей бота
    await add_user_async(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    # Отправляем сообщение с предложением использовать /start
    await message.answer(
        "👋 Привет! Для начала работы с ботом используйте команду /start"
    )


# === ПОКАЗ ПРОДУКТА ===
async def show_product(callback: CallbackQuery, product_key: str, state: FSMContext = None):
    print("SHOW PRODUCT CALLED WITH KEY:", product_key)

    # Находим продукт по ключу
    def find_product_info():
        try:
            # Сначала пробуем найти в коллекции products (новая структура)
            try:
                products = pb.collection("products").get_full_list()
                product = next((p for p in products if p.key == product_key), None)
                if product:
                    # Получаем информацию о подкатегории для описания
                    subcats = pb.collection("subcategories").get_full_list()
                    subcat = next((s for s in subcats if s.id == product.subcategory), None)

                    return {
                        'title': product.title,
                        'price': float(product.price),
                        'description': subcat.description if subcat else ""
                    }
            except Exception:
                pass

            # Если не нашли или коллекция products не существует, ищем в подкатегориях
            if "_default" in product_key:
                subcategory_key = product_key.replace("_default", "")
            else:
                subcategory_key = product_key

            subcats = pb.collection("subcategories").get_full_list()
            subcat = next((s for s in subcats if s.key == subcategory_key), None)
            if subcat:
                return {
                    'title': subcat.title,
                    'price': float(getattr(subcat, 'price', 0)),
                    'description': getattr(subcat, 'description', '') or ""
                }

            return None
        except Exception as e:
            print(f"Ошибка поиска продукта: {e}")
            return None

    product_info = await asyncio.to_thread(find_product_info)
    if not product_info:
        print("Product not found:", product_key)
        await callback.answer("❌ Product not found.", show_alert=True)
        # Возвращаемся к предыдущему состоянию
        if state:
            await state.set_state(ShopState.REGION)  # Возвращаемся к выбору региона
            ctx = await state.get_data()
            category_key = ctx.get("category")
            subcategory_key = ctx.get("subcategory")
            if category_key and subcategory_key:
                await send_region_menu(callback, category_key, subcategory_key, state)
                return
        # Если нет данных о состоянии, возвращаемся к главному меню
        if state:
            await state.set_state(ShopState.MAIN)
        categories = await get_all_categories()
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                                [InlineKeyboardButton(text=cat.name, callback_data=cat.key)]
                                for cat in categories
                            ] + [[InlineKeyboardButton(text="🚀 Make Preorder", callback_data="preorder")]]
        )
        try:
            await callback.message.edit_text("Please select the account category you want to purchase 🔥",
                                             reply_markup=keyboard)
        except TelegramBadRequest:
            pass
        return

    # Получаем доступное количество товара
    available_count = await get_available_count(product_key)

    if available_count == 0:
        await callback.answer("❌ No items available in stock.", show_alert=True)
        # Возвращаемся к предыдущему состоянию
        if state:
            await state.set_state(ShopState.REGION)  # Возвращаемся к выбору региона
            ctx = await state.get_data()
            category_key = ctx.get("category")
            subcategory_key = ctx.get("subcategory")
            if category_key and subcategory_key:
                await send_region_menu(callback, category_key, subcategory_key, state)
                return
        # Если нет данных о состоянии, возвращаемся к главному меню
        if state:
            await state.set_state(ShopState.MAIN)
        categories = await get_all_categories()
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                                [InlineKeyboardButton(text=cat.name, callback_data=cat.key)]
                                for cat in categories
                            ] + [[InlineKeyboardButton(text="🚀 Make Preorder", callback_data="preorder")]]
        )
        try:
            await callback.message.edit_text("Please select the account category you want to purchase 🔥",
                                             reply_markup=keyboard)
        except TelegramBadRequest:
            pass
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="back")]
        ]
    )

    message_text = (f"🛍 {product_info['title']}\n\n"
                    f"{product_info['description']}\n\n"
                    f"📦 Available: {available_count} items\n\n"
                    f"Select the amount of accounts 🔥\n"
                    f"Please enter the quantity as a number (e.g. 6, 18, 48...)")

    try:
        await callback.message.edit_text(message_text, reply_markup=keyboard)
        # Сохраняем ID сообщения с информацией о продукте для дальнейшего редактирования
        if state:
            await state.update_data(product_message_id=callback.message.message_id)
    except TelegramBadRequest:
        pass  # Message is not modified
    await callback.answer()


# === ОБРАБОТКА ПОКУПКИ ===
async def handle_buy(callback: CallbackQuery, data: str, state: FSMContext = None):
    print("DATA:", data)
    product_key = data.replace("buy_", "", 1)
    print("PRODUCT KEY:", product_key)

    # Получаем количество из состояния, если доступно
    quantity = 1  # по умолчанию
    if state:
        state_data = await state.get_data()
        quantity = state_data.get("quantity", 1)

    # Получаем информацию о продукте из БД
    def get_product_price():
        try:
            # Сначала пробуем найти в коллекции products (новая структура)
            try:
                products = pb.collection("products").get_full_list()
                product = next((p for p in products if p.key == product_key), None)
                if product:
                    return float(product.price)
            except Exception:
                pass

            # Если не нашли или коллекция products не существует, ищем в подкатегориях
            if "_default" in product_key:
                subcategory_key = product_key.replace("_default", "")
            else:
                subcategory_key = product_key

            subcats = pb.collection("subcategories").get_full_list()
            subcat = next((s for s in subcats if s.key == subcategory_key), None)
            if subcat:
                return float(getattr(subcat, 'price', 0))

            return None
        except Exception as e:
            print(f"Ошибка получения цены продукта: {e}")
            return None

    price_per_item = await asyncio.to_thread(get_product_price)
    if not price_per_item:
        print("Product not found or invalid price:", product_key)
        await callback.answer("❌ Product not found or invalid price.", show_alert=True)
        # Возвращаемся к вводу количества
        if state:
            await show_product(callback, product_key, state)
        return

    total_price = price_per_item * quantity

    # Создание инвойса
    try:
        invoice = await cp.create_invoice(total_price, "USDT")
    except Exception as e:
        logger.error(f"Failed to create invoice: {e}")
        await callback.answer("❌ Failed to create invoice.", show_alert=True)
        # Возвращаемся к вводу количества
        if state:
            await show_product(callback, product_key, state)
        return

    # Сохраняем информацию о заказе для обработки после оплаты
    pending_orders[invoice.invoice_id] = {
        'source': 'bot',
        'product_key': product_key,
        'quantity': quantity,
        'user_id': callback.from_user.id,
        'username': callback.from_user.username,
        'first_name': callback.from_user.first_name,
        'last_name': callback.from_user.last_name,
        'price_per_item': price_per_item,
        'total_price': total_price
    }

    print(f"Saved order info for invoice {invoice.invoice_id}: {pending_orders[invoice.invoice_id]}")

    # Добавляем задачу для ручной проверки статуса оплаты через несколько секунд
    asyncio.create_task(check_payment_status(invoice.invoice_id, 30))  # проверим через 30 секунд

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💼 Back to shop", callback_data="back_to_shop")]
        ]
    )
    try:
        await callback.message.edit_text(f"💳 Pay via the link:\n{invoice.bot_invoice_url}", reply_markup=keyboard)
    except TelegramBadRequest:
        pass  # Message is not modified
    await callback.answer()

    await record_user_activity_event(
        callback.from_user.id,
        'invoice_created',
        f"Создан счёт #{invoice.invoice_id}",
        metadata={
            'product_key': product_key,
            'quantity': quantity,
            'total_price': total_price
        }
    )

    # Мониторинг оплаты будет обрабатываться через webhook/polling декоратор


async def _fetch_payments_awaiting_invoice():
    """Синхронный вызов PocketBase завернут в поток для получения платежей без инвойса"""

    def _fetch():
        try:
            return pb.collection('payments').get_full_list(
                query_params={'filter': 'status="awaiting_invoice"'}
            )
        except Exception as e:
            logger.error(f"Failed to fetch payments waiting for invoice: {e}")
            return []

    return await asyncio.to_thread(_fetch)


async def monitor_site_payments():
    """Периодически ищет заказы с сайта и создаёт для них инвойсы через бота"""
    logger.info("Site payment monitor started")

    while True:
        try:
            payments = await _fetch_payments_awaiting_invoice()
            logger.debug(f"Site payment monitor iteration: {len(payments)} records in awaiting_invoice")
            if payments:
                logger.info(f"Found {len(payments)} website payments waiting for invoice")
            for payment_record in payments:
                logger.debug(
                    "Processing awaiting invoice payment",
                    extra={
                        'payment_record_id': payment_record.id,
                        'order': getattr(payment_record, 'order', 'unknown'),
                        'amount': getattr(payment_record, 'amount', 'unknown')
                    }
                )
                await assign_invoice_to_site_payment(payment_record)
        except Exception as e:
            logger.error(f"Site payment monitor error: {e}")

        await asyncio.sleep(SITE_ORDER_POLL_INTERVAL)
        logger.debug("Site payment monitor sleep complete")


@lru_cache(maxsize=256)
def _get_category_name(category_id: str) -> str:
    """Возвращает имя категории по ID с кешированием"""
    if not category_id:
        return ""
    try:
        category = pb.collection('categories').get_one(category_id)
        return getattr(category, 'name', '') or ""
    except Exception as e:
        logger.debug(f"Failed to load category {category_id}: {e}")
        return ""


def _compose_extended_product_title(title: str, type_of_warm: str = "", region: str = "") -> str:
    """Формирует строку "title type_of_warm region" без лишних пробелов"""
    parts = []
    if title and title.strip():
        parts.append(title.strip())
    if type_of_warm and type_of_warm.strip():
        parts.append(type_of_warm.strip())
    if region and region.strip():
        parts.append(region.strip())
    return " ".join(parts) or (title.strip() if title else "")


def _fetch_product_snapshot(product_id: str) -> Dict[str, Any]:
    """Синхронно загружает продукт и возвращает основные поля"""
    try:
        product = pb.collection('products').get_one(product_id)
    except Exception as e:
        logger.error(f"Failed to load product {product_id}: {e}")
        return {
            'title': product_id,
            'description': '',
            'warmup': '',
            'category_name': '',
            'price': 0.0,
            'type_of_warm': '',
            'region_for_filter': '',
            'display_name': product_id
        }

    category_name = _get_category_name(getattr(product, 'category', ''))
    type_of_warm = getattr(product, 'type_of_warm', '') or ""
    region_for_filter = getattr(product, 'region_for_filter', '') or ""
    title = getattr(product, 'title', '') or product_id
    display_name = _compose_extended_product_title(title, type_of_warm, region_for_filter) or title
    return {
        'title': title,
        'description': getattr(product, 'description', '') or "",
        'warmup': getattr(product, 'warmup', '') or "",
        'category_name': category_name,
        'price': float(getattr(product, 'price', 0) or 0),
        'type_of_warm': type_of_warm,
        'region_for_filter': region_for_filter,
        'display_name': display_name
    }


def _record_to_plain_dict(record: Any) -> Dict[str, Any]:
    """Возвращает словарь с полями записи PocketBase, игнорируя методы dict."""
    if isinstance(record, dict):
        return dict(record)

    if hasattr(record, 'to_dict'):
        try:
            return record.to_dict()
        except Exception as snapshot_error:  # pragma: no cover - диагностическое сообщение
            logger.debug(
                "Failed to convert record to dict",
                extra={'error': str(snapshot_error), 'record_type': type(record).__name__}
            )

    try:
        return dict(record)
    except Exception:
        return {}


async def collect_order_items_with_details(order: Any) -> List[Dict[str, Any]]:
    """Возвращает список товаров заказа с расширенной информацией"""
    items: List[Dict[str, Any]] = []
    order_snapshot = _record_to_plain_dict(order)
    order_identifier = order_snapshot.get('order_id') or getattr(order, 'order_id', getattr(order, 'id', ''))
    logger.debug(f"Starting collect_order_items_with_details for order {order_identifier}")

    order_items: Any = order_snapshot.get('items')
    if order_items is None:
        attr_items = getattr(order, 'items', None)
        if attr_items is not None and not callable(attr_items):
            order_items = attr_items

    if isinstance(order_items, list) and order_items:
        logger.debug(f"Found {len(order_items)} items in order")
        for item in order_items:
            if isinstance(item, dict):
                items.append(dict(item))
                logger.debug(f"Added item: {item}")
    elif order_items:
        try:
            items.extend(list(order_items))
        except TypeError:
            logger.debug("Order items are not iterable", extra={'order_id': order_identifier})

    if not items:
        cart_id = order_snapshot.get('cart') or getattr(order, 'cart', '')
        if cart_id:
            def _load_cart_items():
                return pb.collection('cart_items').get_full_list(
                    query_params={'filter': f'cart="{cart_id}"', 'perPage': 200}
                )

            try:
                cart_records = await asyncio.to_thread(_load_cart_items)
                for record in cart_records:
                    items.append({
                        'product_id': getattr(record, 'product', ''),
                        'product_title': getattr(record, 'product_title', '') or getattr(record, 'product', ''),
                        'quantity': getattr(record, 'quantity', 0),
                        'product_price': getattr(record, 'product_price', 0)
                    })
                logger.debug(
                    "Recovered order items from cart",
                    extra={'order_id': order_identifier, 'cart_id': cart_id, 'items': len(items)}
                )
            except Exception as cart_error:
                logger.error(
                    "Failed to load cart items for order",
                    extra={'order_id': order_identifier, 'error': str(cart_error)}
                )

    detailed_items: List[Dict[str, Any]] = []
    logger.debug(f"Processing {len(items)} raw items into detailed items")
    for raw_item in items:
        logger.debug(f"Processing raw_item: {raw_item}")
        product_id = raw_item.get('product_id') or raw_item.get('product')
        if not product_id:
            logger.warning(f"Skipping item without product_id: {raw_item}")
            continue

        quantity = int(raw_item.get('quantity') or 0)
        if quantity <= 0:
            logger.warning(f"Skipping item with invalid quantity: {raw_item}")
            continue

        try:
            product_snapshot = await asyncio.to_thread(_fetch_product_snapshot, product_id)
            logger.debug(
                f"Product snapshot for {product_id}: title={product_snapshot.get('title')}, category={product_snapshot.get('category_name')}")
        except Exception as snapshot_error:
            logger.error(
                "Failed to fetch product snapshot",
                extra={'product_id': product_id, 'error': str(snapshot_error)}
            )
            continue

        price_per_item = raw_item.get('product_price')
        try:
            price_per_item = float(price_per_item)
        except (TypeError, ValueError):
            price_per_item = None

        if price_per_item is None:
            price_per_item = product_snapshot.get('price', 0.0)

        line_total = float(price_per_item) * quantity

        # Получаем доступное количество товара
        try:
            def get_available_count(pid):
                try:
                    result = pb.collection('accounts').get_list(
                        1, 1,
                        {'filter': f'product="{pid}" && sold=false && reservation_id=""'}
                    )
                    return result.total_items
                except Exception as e:
                    logger.error(f"Failed to get available count for product {pid}: {e}")
                    return 0

            available_count = await asyncio.to_thread(get_available_count, product_id)
            logger.debug(f"Available count for {product_id}: {available_count}")
        except Exception as e:
            logger.error(f"Error getting available count: {e}")
            available_count = 0

        display_name = product_snapshot.get('display_name') or _compose_extended_product_title(
            product_snapshot.get('title', ''),
            product_snapshot.get('type_of_warm', ''),
            product_snapshot.get('region_for_filter', '')
        )

        detailed_items.append({
            'product_id': product_id,
            'title': raw_item.get('product_title') or product_snapshot.get('title'),
            'category_name': product_snapshot.get('category_name', ''),
            'description': product_snapshot.get('description', ''),
            'warmup': product_snapshot.get('warmup', ''),
            'type_of_warm': product_snapshot.get('type_of_warm', ''),
            'region_for_filter': product_snapshot.get('region_for_filter', ''),
            'display_name': display_name,
            'quantity': quantity,
            'price_per_item': float(price_per_item),
            'line_total': line_total,
            'available': available_count
        })
        logger.debug(f"Added detailed item: {detailed_items[-1]['title']} (qty: {quantity})")

    logger.info(f"Returning {len(detailed_items)} detailed items for order {order_identifier}")
    return detailed_items


def build_site_invoice_message(order_public_id: str, items: List[Dict[str, Any]], amount: float,
                               invoice_url: str) -> str:
    """Формирует текст сообщения для заказа с сайта в том же стиле, что и в боте"""
    logger.debug(f"Building site invoice message for order {order_public_id} with {len(items)} items")

    if not items:
        logger.warning(f"No items provided for order {order_public_id}, returning empty message")
        return ""

    blocks: List[str] = []

    # Формируем информацию о каждом товаре
    for idx, item in enumerate(items, 1):
        description = (item.get('description') or '').strip()
        display_name = item.get('display_name')
        if not display_name:
            display_name = _compose_extended_product_title(
                item.get('title', ''),
                item.get('type_of_warm', ''),
                item.get('region_for_filter', '')
            ) or (item.get('title') or 'Product')

        # Начало блока товара
        block_lines = [f"🛍 {display_name}"]

        # Добавляем описание, если есть
        if description:
            block_lines.append("")
            block_lines.append(description)

        # Используем уже полученное доступное количество и добавляем текущий заказ
        ordered_quantity = item.get('quantity', 0) or 0
        available = (item.get('available', 0) or 0) + ordered_quantity

        block_lines.extend([
            "",
            f"📦 Available: {available} items",
            f"🔢 Ordered: {ordered_quantity} items",
            f"💰 Price: {item.get('price_per_item', 0):.2f} USDT × {ordered_quantity} = {item.get('line_total', 0):.2f} USDT"
        ])

        blocks.append("\n".join(block_lines).strip())

    total_items = sum(item.get('quantity', 0) or 0 for item in items)

    # Формируем итоговое сообщение
    message_parts = []

    # Добавляем все блоки товаров
    message_parts.append("\n\n".join(blocks))

    # Добавляем итоговую информацию
    footer_lines = [
        "",
        f"💳 Total Amount: {amount:.2f} USDT",
        f"📦 Total Items: {total_items}",
        "",
        "Select the amount of accounts 🔥",
        "Click the link below to pay via Crypto Bot:",
        f"👉 {invoice_url}",
        "",
        "✅ After payment, accounts will be delivered automatically."
    ]

    message_parts.append("\n".join(footer_lines))

    final_message = "\n".join(part for part in message_parts if part).strip()
    logger.info(f"Built message with {len(blocks)} blocks, total length: {len(final_message)} chars")
    return final_message


async def assign_invoice_to_site_payment(payment_record):
    """Создаёт Crypto Bot инвойс для заказа с сайта и отправляет ссылку пользователю"""
    try:
        order = await asyncio.to_thread(pb.collection('orders').get_one, payment_record.order)
    except Exception as e:
        logger.error(f"Failed to load order {getattr(payment_record, 'order', 'unknown')}: {e}")
        return

    order_public_id = getattr(order, 'order_id', order.id)

    logger.info(
        "Assigning invoice to site payment",
        extra={
            'payment_record_id': payment_record.id,
            'order_record_id': order.id,
            'order_public_id': order_public_id
        }
    )

    user_relation = getattr(payment_record, 'user_bot', None) or getattr(order, 'user_bot', None)
    if not user_relation:
        logger.error(f"Payment {payment_record.id} has no user relation; skipping")
        return

    try:
        user_record = await asyncio.to_thread(pb.collection('bot_users').get_one, user_relation)
    except Exception as e:
        logger.error(f"Failed to load bot user {user_relation}: {e}")
        return

    user_chat_id = getattr(user_record, 'user_id', None)
    if not user_chat_id:
        logger.error(f"Bot user {user_relation} has no telegram user_id; cannot send invoice")
        return

    try:
        telegram_chat_id = int(str(user_chat_id))
    except ValueError:
        telegram_chat_id = str(user_chat_id)

    amount = float(getattr(payment_record, 'amount', getattr(order, 'total_amount', 0)) or 0)
    if amount <= 0:
        logger.error(f"Invalid amount {amount} for payment {payment_record.id}")
        return

    try:
        invoice = await cp.create_invoice(amount, "USDT")
        logger.info(
            "Created CryptoBot invoice for site order",
            extra={'invoice_id': invoice.invoice_id, 'payment_record_id': payment_record.id, 'amount': amount}
        )
    except Exception as e:
        logger.error(f"Failed to create invoice for payment {payment_record.id}: {e}")
        return

    # Обновляем запись о платеже
    try:
        await asyncio.to_thread(
            pb.collection('payments').update,
            payment_record.id,
            {
                'payment_id': invoice.invoice_id,
                'payment_url': getattr(invoice, 'bot_invoice_url', ''),
                'status': 'pending'
            }
        )
    except Exception as e:
        logger.error(f"Failed to update payment {payment_record.id} with invoice info: {e}")

    pending_orders[invoice.invoice_id] = {
        'source': 'site',
        'order_record_id': order.id,
        'order_public_id': order_public_id,
        'payment_record_id': payment_record.id,
        'user_id': telegram_chat_id,
        'amount': amount,
        'user_bot_record_id': user_relation
    }
    logger.debug(
        "Registered pending site order",
        extra={'invoice_id': invoice.invoice_id, 'order_record_id': order.id, 'user_id': telegram_chat_id}
    )

    detailed_items: List[Dict[str, Any]] = []
    try:
        detailed_items = await collect_order_items_with_details(order)
        logger.info(f"Collected {len(detailed_items)} detailed items for order {order_public_id}")
        if detailed_items:
            logger.debug(f"First item details: {detailed_items[0]}")
    except Exception as details_error:
        logger.error(
            "Failed to collect order details for invoice",
            extra={'order_id': order_public_id, 'error': str(details_error)}
        )

    message_text = build_site_invoice_message(
        order_public_id,
        detailed_items,
        amount,
        getattr(invoice, 'bot_invoice_url', '')
    )

    logger.info(f"Generated message text length: {len(message_text)} chars for order {order_public_id}")

    # Fallback на случай, если сообщение не сформировалось
    if not message_text:
        order_snapshot = _record_to_plain_dict(order)
        fallback_items = order_snapshot.get('items')
        if fallback_items is None:
            attr_items = getattr(order, 'items', None)
            if attr_items is not None and not callable(attr_items):
                fallback_items = attr_items
        fallback_items = fallback_items or []
        fallback_count = (
            len(fallback_items) if isinstance(fallback_items, list) and fallback_items else getattr(order,
                                                                                                    'total_items', 1)
        )
        if detailed_items:
            fallback_count = len(detailed_items)

        message_text = (
            f"💳 Заказ #{order_public_id}\n"
            f"Сумма: {amount:.2f} USDT\n"
            f"Позиций: {fallback_count}\n\n"
            "Перейдите по ссылке и оплатите в Crypto Bot:\n"
            f"{getattr(invoice, 'bot_invoice_url', '')}\n\n"
            "После оплаты бот автоматически доставит аккаунты."
        )

    message_obj = await bot.send_message(
        telegram_chat_id,
        message_text,
        disable_web_page_preview=True
    )
    message_id = message_obj.message_id if message_obj else None

    logger.info(
        "Sent payment link to user",
        extra={'invoice_id': invoice.invoice_id, 'user_id': telegram_chat_id, 'message_id': message_id}
    )

    # Сохраняем message_id в pending_orders для возможности обновления
    if invoice.invoice_id in pending_orders:
        pending_orders[invoice.invoice_id]['message_id'] = message_id

    # Запускаем фоновую проверку статуса платежа через 10 секунд
    logger.info(f"🕐 [MONITOR] Scheduling payment status check for invoice {invoice.invoice_id} in 10 seconds")
    asyncio.create_task(check_payment_status(invoice.invoice_id, delay=10))

    # Запускаем таймер для обновления сообщения при истечении резервации (60 секунд)
    asyncio.create_task(update_message_on_reservation_expired(
        invoice.invoice_id,
        telegram_chat_id,
        message_id,
        delay=60
    ))


async def update_message_on_reservation_expired(invoice_id: str, chat_id: int, message_id: Optional[int],
                                                delay: int = 60):
    """Обновляет сообщение о платеже, если резервация истекла"""
    logger.info(f"⏰ [RESERVATION] Waiting {delay}s before checking reservation for invoice {invoice_id}")
    await asyncio.sleep(delay)

    try:
        # Проверяем, не был ли уже оплачен заказ
        if invoice_id not in pending_orders:
            logger.info(f"✅ [RESERVATION] Invoice {invoice_id} already processed (paid or removed)")
            return

        # Проверяем статус в БД
        def _check_payment():
            payment = pb.collection('payments').get_first_list_item(f'payment_id="{invoice_id}"')
            return getattr(payment, 'status', 'unknown')

        payment_status = await asyncio.to_thread(_check_payment)

        if payment_status == 'paid':
            logger.info(f"✅ [RESERVATION] Invoice {invoice_id} was paid, skipping expiration message")
            return

        # Если не оплачен - обновляем сообщение
        logger.info(f"⏰ [RESERVATION] Reservation expired for invoice {invoice_id}, updating message")

        expired_message = (
            "⏰ <b>Время резервации истекло</b>\n\n"
            "❌ Ваш заказ был отменён, так как оплата не была получена в течение 1 минуты.\n\n"
            "💡 Товары возвращены в каталог.\n"
            "Пожалуйста, соберите заказ заново, если хотите совершить покупку.\n\n"
            "🔄 Вернуться в каталог: /menu"
        )

        if message_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=expired_message,
                    parse_mode="HTML"
                )
                logger.info(f"✅ [RESERVATION] Message updated for expired reservation {invoice_id}")
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e).lower():
                    logger.warning(f"Failed to edit message {message_id}: {e}")
        else:
            # Если message_id не сохранён, отправляем новое сообщение
            await safe_send_message(chat_id, expired_message, parse_mode="HTML")

        # Удаляем из pending_orders
        if invoice_id in pending_orders:
            del pending_orders[invoice_id]
            logger.info(f"🗑️ [RESERVATION] Removed expired invoice {invoice_id} from pending_orders")

    except Exception as e:
        logger.error(f"❌ [RESERVATION] Error updating message for expired reservation {invoice_id}: {e}")


async def fetch_site_payment_context(invoice_id: str) -> Optional[Dict[str, str]]:
    """Загружает связку платежа/заказа из PocketBase по invoice_id"""

    def _fetch():
        payment = pb.collection('payments').get_first_list_item(f'payment_id="{invoice_id}"')
        order = pb.collection('orders').get_one(payment.order)
        user_record = pb.collection('bot_users').get_one(order.user_bot)
        try:
            telegram_chat_id = int(str(user_record.user_id))
        except Exception:
            telegram_chat_id = user_record.user_id

        return {
            'source': 'site',
            'order_record_id': order.id,
            'order_public_id': getattr(order, 'order_id', order.id),
            'payment_record_id': payment.id,
            'user_id': telegram_chat_id,
            'amount': float(getattr(payment, 'amount', getattr(order, 'total_amount', 0)) or 0),
            'user_bot_record_id': getattr(order, 'user_bot', None)
        }

    try:
        context = await asyncio.to_thread(_fetch)
        logger.debug(
            "Loaded site payment context",
            extra={'invoice_id': invoice_id, 'order_record_id': context['order_record_id']}
        )
        return context
    except Exception as e:
        logger.error(f"Failed to fetch payment context for invoice {invoice_id}: {e}")
        return None


async def post_payment_webhook(invoice_id: str, paid_at: str):
    """Отправляет подтверждение оплаты во Flask API"""
    payload = {
        'status': 'paid',
        'invoice_id': invoice_id,
        'paid_at': paid_at
    }

    logger.info(f"📡 [WEBHOOK POST] Preparing to post webhook to API server")
    logger.info(f"📡 [WEBHOOK POST] URL: {API_SERVER_URL}/api/payments/webhook")
    logger.debug(f"📡 [WEBHOOK POST] Payload: {payload}")

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            logger.info(f"📡 [WEBHOOK POST] Sending POST request...")
            response = await client.post(f"{API_SERVER_URL}/api/payments/webhook", json=payload)
            logger.info(f"📡 [WEBHOOK POST] Response received - status: {response.status_code}")
            logger.debug(f"📡 [WEBHOOK POST] Response body: {response.text[:200]}")
            response.raise_for_status()
            logger.info(f"✅ [WEBHOOK POST] Payment webhook delivered successfully")
        except Exception as e:
            logger.error(f"❌ [WEBHOOK POST] Failed to post webhook: {e}")
            raise


async def finalize_site_payment(invoice, context: Optional[Dict[str, str]] = None) -> bool:
    """Подтверждает оплату сайта и запускает доставку через API"""
    logger.info(f"🌐 [FINALIZE] Starting finalize_site_payment for invoice {invoice.invoice_id}")
    logger.debug(f"🌐 [FINALIZE] Context provided: {context is not None}")

    ctx = context or await fetch_site_payment_context(invoice.invoice_id)
    if not ctx:
        logger.error(f"❌ [FINALIZE] Cannot finalize site payment for invoice {invoice.invoice_id}: missing context")
        return False

    logger.info(f"🌐 [FINALIZE] Context loaded successfully")
    logger.debug(f"🌐 [FINALIZE] Context details: {ctx}")
    logger.info(
        f"🌐 [FINALIZE] Finalizing site payment - invoice: {invoice.invoice_id}, order: {ctx.get('order_record_id')}"
    )

    user_id = ctx.get('user_id')
    order_public_id = ctx.get('order_public_id', invoice.invoice_id)
    paid_at = getattr(invoice, 'paid_at', None) or datetime.now()

    # Convert datetime to ISO string for JSON serialization
    paid_at_str = paid_at.isoformat() if hasattr(paid_at, 'isoformat') else str(paid_at)

    logger.debug(f"🌐 [FINALIZE] user_id: {user_id}, order_public_id: {order_public_id}, paid_at: {paid_at_str}")

    try:
        logger.info(f"📡 [FINALIZE] Posting webhook to API server...")
        await post_payment_webhook(invoice.invoice_id, paid_at_str)
        logger.info(f"✅ [FINALIZE] Webhook posted successfully")
    except Exception as e:
        logger.error(f"❌ [FINALIZE] Failed to notify API about paid invoice {invoice.invoice_id}: {e}")
        logger.exception(f"❌ [FINALIZE] Full webhook error traceback:")
        await safe_send_message(
            user_id,
            "⚠️ Платёж получен, но не удалось подтвердить его автоматически. Пожалуйста, свяжитесь с поддержкой."
        )
        return False

    logger.info(f"📤 [FINALIZE] Sending delivery notice to user {user_id}")
    delivery_notice_sent = await safe_send_message(
        user_id,
        f"✅ Оплата за заказ #{order_public_id} получена! Доставка начнётся в течение минуты."
    )
    logger.info(f"📤 [FINALIZE] Delivery notice sent: {delivery_notice_sent}")
    await record_user_activity_event(
        user_id,
        'order_paid',
        f"Оплачен заказ #{order_public_id}",
        metadata={'source': ctx.get('source', 'site'), 'invoice_id': invoice.invoice_id},
        user_record_id=ctx.get('user_bot_record_id')
    )
    logger.info(
        f"✅ [FINALIZE] Site payment finalized successfully - invoice: {invoice.invoice_id}, order: {order_public_id}"
    )
    return True


# === ОБРАБОТКА СПЕЦИАЛЬНЫХ ЗАКАЗОВ ===
async def handle_special_order(callback: CallbackQuery, data: str, state: FSMContext = None):
    """Обрабатывает специальные заказы (большие объемы 30 days)"""
    product_key = data.replace("special_order_", "", 1)

    # Получаем данные из состояния
    if state:
        state_data = await state.get_data()
        quantity = state_data.get("quantity", 1)
    else:
        quantity = 1

    # Рассчитываем стоимость
    total_price = calculate_total_price(product_key, quantity)

    # Получаем информацию о продукте
    def get_product_info():
        try:
            # Сначала пробуем найти в коллекции products (новая структура)
            try:
                products = pb.collection("products").get_full_list()
                product = next((p for p in products if p.key == product_key), None)
                if product:
                    # Получаем информацию о подкатегории для описания
                    subcats = pb.collection("subcategories").get_full_list()
                    subcat = next((s for s in subcats if s.id == product.subcategory), None)

                    return {
                        'title': product.title,
                        'description': subcat.description if subcat else ""
                    }
            except Exception:
                pass

            # Если не нашли, ищем в подкатегориях
            if "_default" in product_key:
                subcategory_key = product_key.replace("_default", "")
            else:
                subcategory_key = product_key

            subcats = pb.collection("subcategories").get_full_list()
            subcat = next((s for s in subcats if s.key == subcategory_key), None)
            if subcat:
                return {
                    'title': subcat.title,
                    'description': getattr(subcat, 'description', '') or ""
                }

            return None
        except Exception as e:
            print(f"Ошибка получения информации о продукте: {e}")
            return None

    product_info = await asyncio.to_thread(get_product_info)

    # Отправляем сообщение с информацией о заказе
    order_message = (f"� <b>Special Order</b>\n\n"
                     f"� Product: {product_info['title'] if product_info else product_key}\n"
                     f"� Quantity: {quantity} items\n"
                     f"💰 Total price: {total_price:.2f} USDT")

    await callback.message.edit_text(order_message, parse_mode="HTML")

    # Отправляем инструкцию переслать сообщение
    instruction_message = "⬆️ Please forward the message above to @fypacc"
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=instruction_message
    )

    # Отправляем главное меню
    await start_menu_with_counts(callback)

    await callback.answer()


# === ОБРАБОТКА ПРЕДЗАКАЗОВ ===
async def handle_preorder(callback: CallbackQuery, data: str, state: FSMContext = None):
    """Обрабатывает предзаказы (3 и 7 дней)"""
    product_key = data.replace("preorder_", "", 1)

    # Получаем данные из состояния
    if state:
        state_data = await state.get_data()
        quantity = state_data.get("quantity", 1)
    else:
        quantity = 1

    # Рассчитываем стоимость
    total_price = calculate_total_price(product_key, quantity)

    # Получаем информацию о продукте
    def get_product_info():
        try:
            # Сначала пробуем найти в коллекции products (новая структура)
            try:
                products = pb.collection("products").get_full_list()
                product = next((p for p in products if p.key == product_key), None)
                if product:
                    # Получаем информацию о подкатегории для описания
                    subcats = pb.collection("subcategories").get_full_list()
                    subcat = next((s for s in subcats if s.id == product.subcategory), None)

                    return {
                        'title': product.title,
                        'description': subcat.description if subcat else ""
                    }
            except Exception:
                pass

            # Если не нашли, ищем в подкатегориях
            if "_default" in product_key:
                subcategory_key = product_key.replace("_default", "")
            else:
                subcategory_key = product_key

            subcats = pb.collection("subcategories").get_full_list()
            subcat = next((s for s in subcats if s.key == subcategory_key), None)
            if subcat:
                return {
                    'title': subcat.title,
                    'description': getattr(subcat, 'description', '') or ""
                }

            return None
        except Exception as e:
            print(f"Ошибка получения информации о продукте: {e}")
            return None

    product_info = await asyncio.to_thread(get_product_info)

    # Отправляем сообщение с информацией о предзаказе
    preorder_message = (f"🚀 <b>Preorder</b>\n\n"
                        f"� Product: {product_info['title'] if product_info else product_key}\n"
                        f"� Quantity: {quantity} items\n"
                        f"💰 Total price: {total_price:.2f} USDT")

    await callback.message.edit_text(preorder_message, parse_mode="HTML")

    # Отправляем инструкцию переслать сообщение
    instruction_message = "⬆️ Please forward the message above to @fypacc"
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=instruction_message
    )

    # Отправляем главное меню
    await start_menu_with_counts(callback)

    await callback.answer()


async def check_payment_status(invoice_id, delay=30):
    """Ручная проверка статуса оплаты через заданное время"""
    logger.info(f"⏰ [CHECK] Waiting {delay} seconds before checking invoice {invoice_id}")
    await asyncio.sleep(delay)
    try:
        # Получаем информацию об invoice
        logger.info(f"🔍 [CHECK] Fetching invoice {invoice_id} from CryptoPay...")
        invoice = await cp.get_invoice(invoice_id)
        logger.info(f"📊 [CHECK] Invoice {invoice_id} status: {getattr(invoice, 'status', 'unknown')}")
        logger.debug(f"📊 [CHECK] Invoice full data: {invoice}")

        print(f"📊 Manual check - Invoice {invoice_id} status: {getattr(invoice, 'status', 'unknown')}")

        if hasattr(invoice, 'status') and invoice.status == 'paid':
            logger.info(f"💰 [CHECK] Invoice {invoice_id} is PAID! Triggering handle_payment...")
            print(f"💰 Invoice {invoice_id} is paid! Triggering manual delivery...")
            await handle_payment(invoice)
            logger.info(f"✅ [CHECK] handle_payment completed for {invoice_id}")
        else:
            logger.warning(
                f"⏳ [CHECK] Invoice {invoice_id} still not paid, status: {getattr(invoice, 'status', 'unknown')}")
            print(f"⏳ Invoice {invoice_id} still not paid, status: {getattr(invoice, 'status', 'unknown')}")
    except Exception as e:
        print(f"❌ Error checking payment status for invoice {invoice_id}: {e}")


# === ОПЛАТА ===
@cp.invoice_polling()
async def handle_payment(invoice):
    print(f"\n{'=' * 80}")
    print(f"🎉 PAYMENT RECEIVED! Invoice ID: {invoice.invoice_id}, Status: {getattr(invoice, 'status', 'unknown')}")
    print(f"{'=' * 80}\n")
    logger.info(f"💳 [PAYMENT] Received payment for invoice {invoice.invoice_id}")
    logger.debug(f"💳 [PAYMENT] Invoice object attributes: {dir(invoice)}")
    logger.debug(
        f"💳 [PAYMENT] Invoice details - amount: {getattr(invoice, 'amount', 'N/A')}, asset: {getattr(invoice, 'asset', 'N/A')}")

    logger.info(f"🔍 [PAYMENT] Checking pending_orders for invoice {invoice.invoice_id}")
    logger.debug(f"🔍 [PAYMENT] All pending_orders keys: {list(pending_orders.keys())}")
    order_context = pending_orders.get(invoice.invoice_id)
    logger.info(f"🔍 [PAYMENT] Order context found: {order_context is not None}")
    if order_context:
        logger.debug(f"🔍 [PAYMENT] Order context details: {order_context}")

    if order_context and order_context.get('source') == 'site':
        logger.info(f"🌐 [SITE PAYMENT] Invoice {invoice.invoice_id} matched pending site order context")
        logger.debug(f"🌐 [SITE PAYMENT] Context: {order_context}")
        pending_orders.pop(invoice.invoice_id, None)
        logger.info(f"🌐 [SITE PAYMENT] Calling finalize_site_payment...")
        if await finalize_site_payment(invoice, order_context):
            logger.info(f"✅ [SITE PAYMENT] Successfully finalized site payment for {invoice.invoice_id}")
            return
        logger.warning(f"⚠️ [SITE PAYMENT] finalize_site_payment returned False for {invoice.invoice_id}")
        order_context = None

    if not order_context:
        logger.info(f"🔍 [FALLBACK] No pending context, fetching from PocketBase for {invoice.invoice_id}")
        site_context = await fetch_site_payment_context(invoice.invoice_id)
        logger.info(f"🔍 [FALLBACK] PocketBase context found: {site_context is not None}")
        if site_context:
            logger.debug(f"🔍 [FALLBACK] Context details: {site_context}")
        if site_context and site_context.get('source') == 'site':
            logger.info(f"🌐 [FALLBACK SITE] Invoice {invoice.invoice_id} resolved via PocketBase context lookup")
            if await finalize_site_payment(invoice, site_context):
                logger.info(f"✅ [FALLBACK SITE] Successfully finalized site payment for {invoice.invoice_id}")
                pending_orders.pop(invoice.invoice_id, None)
                return
            logger.warning(f"⚠️ [FALLBACK SITE] finalize_site_payment returned False for {invoice.invoice_id}")

    order = order_context or pending_orders.get(invoice.invoice_id)
    logger.info(f"🤖 [BOT ORDER CHECK] Order found: {order is not None}")
    if order:
        logger.debug(f"🤖 [BOT ORDER CHECK] Order details: {order}")
        logger.debug(f"🤖 [BOT ORDER CHECK] Order source: {order.get('source', 'bot')}")
    if order and order.get('source', 'bot') == 'bot':
        logger.info(f"🤖 [BOT ORDER] Invoice {invoice.invoice_id} mapped to bot order {order.get('product_key')}")
        product_key = order['product_key']
        quantity = order['quantity']
        user_id = order['user_id']
        username = order['username']

        user_record_id = await get_bot_user_record_id_async(user_id)
        await record_user_activity_event(
            user_id,
            'order_paid',
            f"Оплачен счёт #{invoice.invoice_id}",
            metadata={'product_key': product_key, 'quantity': quantity},
            user_record_id=user_record_id
        )

        print(f"🔄 Processing order: {product_key} x{quantity} for user {user_id}")
        logger.info(f"🔄 [BOT ORDER] Processing: product={product_key}, qty={quantity}, user={user_id}")

        # Резервируем и доставляем аккаунты
        logger.info(f"📦 [BOT ORDER] Calling reserve_and_deliver_accounts...")
        account_data, error = await reserve_and_deliver_accounts(product_key, quantity, user_id)
        logger.info(
            f"📦 [BOT ORDER] Reserve result - accounts: {len(account_data) if account_data else 0}, error: {error}")

        if error:
            logger.error(f"❌ [BOT ORDER] Error during reservation: {error}")
            await safe_send_message(user_id, f"❌ Error processing your order: {error}")
            logger.error(f"Order processing error for user {user_id}: {error}")
        elif account_data:
            # Добавляем продажу в отчет
            add_sale_to_report(
                user_id=user_id,
                first_name=order['first_name'],
                last_name=order['last_name'],
                username=username,
                product_key=product_key,
                quantity=quantity,
                amount=order['total_price']
            )

            # Создаем txt файл с аккаунтами
            header_text = "Attention, log into your account only from the proxy of the country whose account you purchased.\nFormat\nlogin:password:email\n\n"
            file_content = header_text + "\n".join(account_data)
            filename = f"{product_key}_{quantity}accounts.txt"

            # Отправляем файл пользователю
            file_data = BufferedInputFile(
                file_content.encode('utf-8'),
                filename=filename
            )

            try:
                # Подтверждение оплаты
                logger.info(f"📤 [BOT ORDER] Sending payment confirmation to user {user_id}")
                payment_success = await safe_send_message(user_id, f"✅ Invoice #{invoice.invoice_id} has been paid!")
                logger.debug(f"📤 [BOT ORDER] Payment confirmation sent: {payment_success}")

                # Получаем читаемое название продукта
                logger.debug(f"📤 [BOT ORDER] Getting product display name for {product_key}")
                product_display_name = await asyncio.to_thread(get_product_display_name, product_key)
                logger.debug(f"📤 [BOT ORDER] Product display name: {product_display_name}")

                logger.info(f"📤 [BOT ORDER] Sending document file to user {user_id}")
                document_success = await safe_send_document(
                    user_id,
                    document=file_data,
                    caption=f"🎉 Your order is ready!\n📦 Product: {product_display_name}\n🔢 Quantity: {quantity} accounts\n\nThank you for your purchase!"
                )

                if document_success:
                    logger.info(f"✅ [BOT ORDER] Successfully delivered {quantity} accounts to user {user_id}")
                    print(f"✅ File sent successfully to user {user_id}")
                else:
                    logger.warning(f"⚠️ [BOT ORDER] Document send failed, trying text format")
                    # Если не удалось отправить файл, отправляем текстом
                    text_success = await safe_send_message(user_id, f"🎉 Your accounts:\n\n```\n{file_content}\n```",
                                                           parse_mode="Markdown")
                    logger.info(f"📤 [BOT ORDER] Text format sent: {text_success}")
                    if text_success:
                        logger.info(f"Delivered {quantity} accounts as text to user {user_id}")
                    else:
                        logger.error(f"Failed to deliver accounts to user {user_id} in any format")

            except Exception as e:
                logger.error(f"Failed to send file to user {user_id}: {e}")
                # Если не удалось отправить файл, отправляем текстом
                try:
                    await safe_send_message(user_id, f"🎉 Your accounts:\n\n```\n{file_content}\n```",
                                            parse_mode="Markdown")
                except Exception as e2:
                    logger.error(f"Failed to send text message to user {user_id}: {e2}")
        else:
            await safe_send_message(user_id, "❌ No accounts were processed.")

        # Возвращаем пользователя к главному меню
        try:
            categories = await get_all_categories()

            buttons = []
            for cat in categories:
                total_count = await get_category_total_count(cat)
                if total_count > 0:
                    button_text = f"{cat.name} ({total_count} items)"
                else:
                    button_text = f"{cat.name} (0 Available)"
                buttons.append([InlineKeyboardButton(text=button_text, callback_data=cat.key)])

            if buttons:
                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
                await safe_send_message(user_id, "Welcome back to the shop! Choose category:", reply_markup=keyboard)
            else:
                await safe_send_message(user_id, "❌ No categories available.")
        except Exception as e:
            logger.error(f"Ошибка при возврате в главное меню после оплаты: {e}")
            await safe_send_message(user_id, "Payment confirmed! Use /start to return to the shop.")

        # Удаляем заказ из pending_orders
        logger.info(f"🗑️ [BOT ORDER] Removing invoice {invoice.invoice_id} from pending_orders")
        del pending_orders[invoice.invoice_id]
        logger.info(f"✅ [BOT ORDER] Order processing completed for invoice {invoice.invoice_id}")
        print(f"\n{'=' * 80}")
        print(f"✅ ORDER COMPLETED: {invoice.invoice_id}")
        print(f"{'=' * 80}\n")
    else:
        logger.warning(f"⚠️ [UNKNOWN] No order info found for invoice {invoice.invoice_id}; ignoring")
        logger.debug(f"⚠️ [UNKNOWN] Current pending_orders: {list(pending_orders.keys())}")
        print(f"\n{'=' * 80}")
        print(f"❓ UNKNOWN INVOICE: {invoice.invoice_id}")
        print(f"{'=' * 80}\n")


# === СПЕЦИАЛЬНЫЕ ЗАКАЗЫ ===
async def handle_special_order(callback: CallbackQuery, data: str, state: FSMContext = None):
    """Обработка специального заказа для больших объемов (250+ аккаунтов 30 days)"""
    product_key = data.replace("special_order_", "", 1)

    # Получаем данные о заказе из состояния
    state_data = await state.get_data()
    quantity = state_data.get("quantity", 0)

    # Получаем информацию о продукте
    def get_product_info():
        try:
            # Сначала пробуем найти в коллекции products (новая структура)
            try:
                products = pb.collection("products").get_full_list()
                product = next((p for p in products if p.key == product_key), None)
                if product:
                    # Получаем информацию о подкатегории для описания
                    subcats = pb.collection("subcategories").get_full_list()
                    subcat = next((s for s in subcats if s.id == product.subcategory), None)

                    return {
                        'title': product.title,
                        'description': subcat.description if subcat else ""
                    }
            except Exception:
                pass

            # Если не нашли, ищем в подкатегориях
            if "_default" in product_key:
                subcategory_key = product_key.replace("_default", "")
            else:
                subcategory_key = product_key

            subcats = pb.collection("subcategories").get_full_list()
            subcat = next((s for s in subcats if s.key == subcategory_key), None)
            if subcat:
                return {
                    'title': subcat.title,
                    'description': getattr(subcat, 'description', '') or ""
                }

            return None
        except Exception as e:
            print(f"Ошибка получения информации о продукте: {e}")
            return None

    product_info = await asyncio.to_thread(get_product_info)
    total_price = calculate_total_price(product_key, quantity)

    # Создаем сообщение для пересылки

    # Отправляем пользователю инструкции
    instructions_message = ("🔥 <b>Special Order Request Sent!</b>\n\n"
                            f"📦 Product: {product_info['title'] if product_info else product_key}\n"
                            f"🔢 Quantity: {quantity} accounts\n"
                            f"💰 Total Price: {total_price:.2f} USDT\n\n"
                            f"<i>💡 Large orders require manual processing for quality assurance.</i>")

    # Отправляем пользователю инструкции
    await callback.message.answer(instructions_message, parse_mode="HTML")

    # Отправляем сообщение для пересылки

    await callback.message.answer("⬆️ <b>Please forward the message above to @fypacc</b>", parse_mode="HTML")

    # Отправляем главное меню новым сообщением
    categories = await get_all_categories()

    buttons = []
    for cat in categories:
        total_count = await get_category_total_count(cat)
        if total_count > 0:
            button_text = f"{cat.name} ({total_count} items)"
        else:
            button_text = f"{cat.name} (0 Available)"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=cat.key)])

    if buttons:
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text="Please select the account category you want to purchase 🔥",
            reply_markup=keyboard
        )

    await callback.answer()


async def handle_preorder(callback: CallbackQuery, data: str, state: FSMContext = None):
    """Обработка предзаказа для 3 и 7 дней"""
    product_key = data.replace("preorder_", "", 1)

    # Получаем данные о заказе из состояния
    state_data = await state.get_data()
    quantity = state_data.get("quantity", 0)

    # Получаем информацию о продукте
    def get_product_info():
        try:
            # Сначала пробуем найти в коллекции products (новая структура)
            try:
                products = pb.collection("products").get_full_list()
                product = next((p for p in products if p.key == product_key), None)
                if product:
                    # Получаем информацию о подкатегории для описания
                    subcats = pb.collection("subcategories").get_full_list()
                    subcat = next((s for s in subcats if s.id == product.subcategory), None)

                    return {
                        'title': product.title,
                        'description': subcat.description if subcat else ""
                    }
            except Exception:
                pass

            # Если не нашли, ищем в подкатегориях
            if "_default" in product_key:
                subcategory_key = product_key.replace("_default", "")
            else:
                subcategory_key = product_key

            subcats = pb.collection("subcategories").get_full_list()
            subcat = next((s for s in subcats if s.key == subcategory_key), None)
            if subcat:
                return {
                    'title': subcat.title,
                    'description': getattr(subcat, 'description', '') or ""
                }

            return None
        except Exception as e:
            print(f"Ошибка получения информации о продукте: {e}")
            return None

    product_info = await asyncio.to_thread(get_product_info)
    total_price = calculate_total_price(product_key, quantity)

    # Создаем сообщение для пересылки

    # Отправляем пользователю инструкции
    instructions_message = ("🚀 <b>Preorder Request Sent!</b>\n\n"
                            f"📦 Product: {product_info['title'] if product_info else product_key}\n"
                            f"🔢 Quantity: {quantity} accounts\n"
                            f"💰 Total Price: {total_price:.2f} USDT\n\n"
                            f"<i>💡 Premium accounts require preparation time.</i>")

    # Отправляем пользователю инструкции
    await callback.message.answer(instructions_message, parse_mode="HTML")

    # Отправляем сообщение для пересылки

    await callback.message.answer("⬆️ <b>Please forward the message above to @fypacc</b>", parse_mode="HTML")

    # Отправляем главное меню новым сообщением
    categories = await get_all_categories()

    buttons = []
    for cat in categories:
        total_count = await get_category_total_count(cat)
        if total_count > 0:
            button_text = f"{cat.name} ({total_count} items)"
        else:
            button_text = f"{cat.name} (0 Available)"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=cat.key)])

    if buttons:
        # Добавляем кнопку Make Preorder
        buttons.append([InlineKeyboardButton(text="🚀 Make Preorder", callback_data="preorder")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text="Please select the account category you want to purchase 🔥",
            reply_markup=keyboard
        )

    await callback.answer()


# === ЗАПУСК ===
def start_api_server():
    """Запускает Flask API сервер в отдельном потоке"""
    try:
        from api_server import app as flask_app
        logger.info("Запуск API сервера на порту 5000...")
        flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Ошибка запуска API сервера: {e}")


async def main():
    logger.info("Запуск бота...")

    # Запускаем Flask API сервер в фоновом потоке
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()
    logger.info("API сервер запущен в фоновом потоке")

    # Проверяем и создаем коллекцию bot_users если нужно
    await asyncio.to_thread(ensure_bot_users_collection)

    # Загружаем пользователей из базы данных
    await asyncio.to_thread(load_users_from_db)

    # Устанавливаем базовые команды для всех пользователей
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="🚀 Start bot"),
            BotCommand(command="id", description="🆔 Show your ID")
        ])

        # Устанавливаем кнопку меню
        await bot.set_chat_menu_button(
            menu_button=MenuButtonCommands()
        )

        logger.info("Bot commands and menu button set successfully")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")

    # Запускаем планировщик еженедельной очистки
    start_cleanup_scheduler()

    # Запускаем асинхронные задачи отправки отчетов
    sales_task = asyncio.create_task(sales_report_task())
    users_task = asyncio.create_task(users_report_task())
    site_payments_task = asyncio.create_task(monitor_site_payments())
    logger.info("Sales and users report tasks started")

    try:
        await asyncio.gather(
            dp.start_polling(bot),
            cp.start_polling(),
            sales_task,  # Добавляем задачу отчетов по продажам
            users_task,  # Добавляем задачу отчетов по пользователям
            site_payments_task,
        )
    except Exception as e:
        logger.error(f"Ошибка запуска polling: {e}")
        # Отменяем задачи отчетов при ошибке
        sales_task.cancel()
        users_task.cancel()
        site_payments_task.cancel()


# fdsf

if __name__ == "__main__":
    logger.info("Старт приложения")
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Ошибка при запуске main: {e}")