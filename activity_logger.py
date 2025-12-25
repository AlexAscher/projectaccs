import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_user_record_cache: Dict[str, str] = {}


def cache_bot_user_record_id(telegram_user_id: Any, record_id: Optional[str]) -> None:
    """Stores bot_users record id for a telegram user id"""
    if telegram_user_id is None or not record_id:
        return
    _user_record_cache[str(telegram_user_id)] = record_id


def invalidate_bot_user_cache_entry(telegram_user_id: Any) -> None:
    if telegram_user_id is None:
        return
    _user_record_cache.pop(str(telegram_user_id), None)


def resolve_bot_user_record_id(pb_client: Any, telegram_user_id: Any) -> Optional[str]:
    """Returns bot_users record id for given telegram user id"""
    if pb_client is None or telegram_user_id is None:
        return None

    user_key = str(telegram_user_id)
    cached = _user_record_cache.get(user_key)
    if cached:
        return cached

    try:
        record = pb_client.collection('bot_users').get_first_list_item(f'user_id="{user_key}"')
        record_id = getattr(record, 'id', None)
        if record_id:
            _user_record_cache[user_key] = record_id
        return record_id
    except Exception as e:
        logger.debug(f"Failed to resolve bot_user record for {user_key}: {e}")
        return None


def log_user_activity(
    pb_client: Any,
    telegram_user_id: Any,
    event_type: str,
    details: str,
    source: str = "bot",
    metadata: Optional[Dict[str, Any]] = None,
    user_record_id: Optional[str] = None
) -> bool:
    """Persists a user activity entry to PocketBase"""
    if pb_client is None or telegram_user_id is None:
        return False

    user_record_id = user_record_id or resolve_bot_user_record_id(pb_client, telegram_user_id)
    if not user_record_id:
        logger.debug(
            f"log_user_activity skipped for user {telegram_user_id}: bot_user record not found"
        )
        return False

    payload: Dict[str, Any] = {
        'user_bot': user_record_id,
        'telegram_user_id': str(telegram_user_id),
        'event_type': event_type,
        'details': details,
        'source': source
    }

    if metadata is not None:
        payload['metadata'] = metadata

    try:
        pb_client.collection('user_activity').create(payload)
        return True
    except Exception as e:
        logger.error(
            f"Failed to log activity '{event_type}' for user {telegram_user_id}: {e}"
        )
        return False
