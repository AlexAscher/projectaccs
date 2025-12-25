from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Gmails", callback_data="type:Gmails:new")],
            [InlineKeyboardButton(text="Instagram warmed up", callback_data="type:Instagram:warmed")],
            [InlineKeyboardButton(text="Reddit warmed up", callback_data="type:Reddit:warmed")],
            [InlineKeyboardButton(text="Tinder", callback_data="type:Tinder:new")],
            [InlineKeyboardButton(text="TikTok warmed up", callback_data="type:TikTok:warmed")],
            [InlineKeyboardButton(text="X accounts", callback_data="type:X:new")],
        ]
    )
