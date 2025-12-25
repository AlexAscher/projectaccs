# tests/unit/test_cart_service.py
import pytest
from unittest.mock import Mock, patch
from cart_service import (
    reserve_accounts_for_cart,
    release_reservation,
    release_expired_reservations,
    mark_accounts_as_sold,
    get_available_count,
    update_cart_item_quantity
)

@pytest.fixture
def mock_pb():
    with patch('cart_service.pb') as mock:
        yield mock

def test_reserve_accounts_for_cart_success(mock_pb):
    mock_cart_items = [Mock(collection_id='col1', quantity=2)]
    # Должно быть 2 аккаунта-объекта с нужными атрибутами
    class Account:
        def __init__(self, id):
            self.id = id
    mock_accounts_col1 = [Account('acc1'), Account('acc2')]
    # Первый вызов get_list для корзины, второй — для аккаунтов
    def get_list_side_effect(*args, **kwargs):
        if kwargs.get('query_params', {}).get('filter'):
            return Mock(items=mock_accounts_col1)
        return Mock(items=mock_cart_items)
    mock_pb.collection().get_list.side_effect = get_list_side_effect
    mock_pb.collection().create.return_value = Mock(id='new_reservation')
    # update должен возвращать объект с id, а не MagicMock
    def update_side_effect(id, data):
        class Updated:
            def __init__(self, id):
                self.id = id
        return Updated(id)
    mock_pb.collection().update.side_effect = update_side_effect
    result = reserve_accounts_for_cart('cart123', 'col1', 2)
    assert result['reserved_account_ids'] == ['acc1', 'acc2']
    assert result["quantity"] == 2
    assert len(result["reserved_account_ids"]) == 2

def test_reserve_accounts_for_cart_not_enough(mock_pb):
    mock_cart_items = [Mock(collection_id='col1', quantity=5)]
    mock_pb.collection().get_list.side_effect = [
        Mock(items=mock_cart_items),
        Mock(items=[{'id': 'acc1'}]),
    ]
    with pytest.raises(Exception, match="Not enough available accounts"):
        reserve_accounts_for_cart('cart123', 'col1', 5)

def test_release_reservation_by_cart_id(mock_pb):
    mock_pb.collection().get_list.return_value = Mock(items=[
        Mock(id='acc1', product='prod1'),
        Mock(id='acc2', product='prod1')
    ])
    count = release_reservation(cart_id='cart123')
    assert count == 2

def test_mark_accounts_as_sold(mock_pb):
    mock_pb.collection().get_one.return_value = Mock(data="login:pass:email", product="prod1")
    mapping = mark_accounts_as_sold(['acc1'], 'order123', 'user789')
    assert 'acc1' in mapping

def test_get_available_count(mock_pb):
    mock_pb.collection().get_list.return_value = Mock(total_items=42)
    count = get_available_count('prod123')
    assert count == 42

def test_update_cart_item_quantity_create(mock_pb):
    mock_pb.collection().get_list.return_value = Mock(items=[])
    update_cart_item_quantity('cart1', 'prod1', 3)
    mock_pb.collection().create.assert_called()

def test_update_cart_item_quantity_delete(mock_pb):
    mock_item = Mock(id='ci1', quantity=2)
    mock_pb.collection().get_list.return_value = Mock(items=[mock_item])
    update_cart_item_quantity('cart1', 'prod1', -2)
    mock_pb.collection().delete.assert_called()