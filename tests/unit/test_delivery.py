# tests/unit/test_delivery.py
import pytest
from unittest.mock import AsyncMock, Mock, patch
from delivery import deliver_order

@pytest.mark.asyncio
async def test_deliver_order_success():
    mock_bot = AsyncMock()
    mock_pb = Mock()

    mock_order = Mock()
    mock_order.id = "ord_123"
    mock_order.order_id = "ORD-123"
    mock_order.cart = "cart_456"
    mock_order.items = [
        {"product_id": "prod_ig", "product_title": "IG US", "quantity": 2, "account_ids": ["acc1", "acc2"]}
    ]
    mock_order.total_amount = 10.0
    mock_order.user_bot = "user_bot_789"
    mock_order.paid_at = "2025-01-01T10:00:00Z"

    mock_account_1 = Mock(data="login1:pass1:email1")
    mock_account_2 = Mock(data="login2:pass2:email2")
    with patch("delivery.Bot", return_value=mock_bot), \
         patch("delivery.pb", mock_pb), \
         patch("cart_service.mark_accounts_as_sold", return_value={"acc1": "sold1", "acc2": "sold2"}):
        mock_pb.collection().get_one.side_effect = lambda x: {
            "ord_123": mock_order,
            "acc1": mock_account_1,
            "acc2": mock_account_2,
        }.get(x)
        mock_pb.collection().get_full_list.return_value = []

        await deliver_order("ord_123", 123456789)

        mock_bot.send_message.assert_called()
        mock_bot.send_document.assert_called_once()
        mock_pb.collection().update.assert_called()

@pytest.mark.asyncio
async def test_deliver_order_no_accounts():
    mock_bot = AsyncMock()
    mock_pb = Mock()
    mock_order = Mock()
    mock_order.id = "ord_empty"
    mock_order.items = []
    mock_order.order_id = "ORD-000"

    with patch("delivery.Bot", return_value=mock_bot), \
         patch("delivery.pb", mock_pb):
        mock_pb.collection().get_one.return_value = mock_order
        await deliver_order("ord_empty", 123456789)

        mock_bot.send_message.assert_called()