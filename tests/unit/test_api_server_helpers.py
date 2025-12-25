# tests/unit/test_api_server_helpers.py
from api_server import (
    _coerce_record_value,
    _record_to_plain_dict,
    _sanitize_filter_value,
    _normalize_activity_entry
)
from unittest.mock import Mock

def test_sanitize_filter_value():
    assert _sanitize_filter_value('hello"world') == 'hello\\"world'
    assert _sanitize_filter_value(None) == ''

def test_coerce_record_value():
    from datetime import datetime
    dt = datetime(2025, 1, 1)
    assert "2025-01-01" in _coerce_record_value(dt)

    record = {'id': 'rec1'}
    result = _coerce_record_value(record)
    assert isinstance(result, dict)
    assert result['id'] == 'rec1'

def test_record_to_plain_dict():
    from types import SimpleNamespace
    mock_record = SimpleNamespace(id='test', name='Test')
    result = _record_to_plain_dict(mock_record)
    assert result['id'] == 'test'
    assert result['name'] == 'Test'

def test_normalize_activity_entry():
    entry = {'event_type': 'order_paid', 'details': 'Заказ #123', 'created': '2025-01-01T10:00:00Z'}
    normalized = _normalize_activity_entry(entry, 'user_activity')
    assert "Оплата получена" in normalized['text']