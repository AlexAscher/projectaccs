from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import get_main_menu
from payment import create_invoice

router = Router()

@router.message(F.text == "/start")
async def start_handler(message: Message):
    await message.answer(
        "Привет! Выбери категорию аккаунтов 👇",
        reply_markup=get_main_menu()
    )

@router.callback_query(F.data.startswith("type:"))
async def type_selected(callback: CallbackQuery):
    _, category, acc_type = callback.data.split(":")

    price_usd = 7.0
    asset = "USDT"
    description = f"{category} — {acc_type}"
    payload = f"{callback.from_user.id}:{category}:{acc_type}"

    try:
        invoice = create_invoice(asset, price_usd, description, payload)
        invoice_url = invoice["pay_url"]

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💸 Оплатить", url=invoice_url)]
            ]
        )

        await callback.message.edit_text(
            f"🧾 Ваш заказ:\n{description}\n💰 Сумма: {price_usd} {asset}\n\n👇 Нажмите кнопку ниже, чтобы оплатить:",
            reply_markup=kb
        )
    except Exception as e:
        await callback.message.answer("❌ Ошибка при создании инвойса. Попробуйте позже.")
        print(e)

def register_handlers(dp):
    dp.include_router(router)
