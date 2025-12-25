# tests/integration/test_bot_handlers.py
import pytest
from aiogram.types import Message, User, Chat
from aiogram import Bot
from aiogram.testkit import TestBot
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot import router

@pytest.fixture
def dp():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    return dp

@pytest.mark.asyncio
async def test_start_handler(dp):
    bot = TestBot()
    message = Message(
        message_id=1,
        from_user=User(id=123456789, is_bot=False, first_name="Test"),
        chat=Chat(id=123456789, type="private"),
        text="/start"
    )

    async with bot.context():
        await dp.feed_event(bot, message)

    assert len(bot.calls) >= 1
    assert bot.calls[0].method == "sendMessage"