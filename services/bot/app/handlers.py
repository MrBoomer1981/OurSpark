"""Обработчики: подтверждение входа в PWA и приветствие с кнопкой, которая открывает гнездо."""

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from loguru import logger

from app import texts
from app.api import Api

router = Router()
router.message.filter(F.chat.type == "private")

LOGIN_PREFIX = "login_"
# В callback_data влезает 64 байта: «login:ok:» + nonce из 43 символов.
LOGIN_OK = "login:ok:"
LOGIN_NO = "login:no"


@router.message(CommandStart(deep_link=True, magic=F.args.startswith(LOGIN_PREFIX)))
async def login_request(message: Message, command: CommandObject) -> None:
    # Вход подтверждает только человек: без вопроса чужая ссылка login_… молча
    # открыла бы его аккаунт на устройстве того, кто её прислал.
    nonce = (command.args or "").removeprefix(LOGIN_PREFIX)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts.LOGIN_YES, callback_data=LOGIN_OK + nonce),
                InlineKeyboardButton(text=texts.LOGIN_NO, callback_data=LOGIN_NO),
            ]
        ]
    )
    await message.answer(texts.LOGIN_CONFIRM, reply_markup=keyboard)


@router.callback_query(F.data.startswith(LOGIN_OK))
async def login_confirm(callback: CallbackQuery, api: Api) -> None:
    nonce = (callback.data or "").removeprefix(LOGIN_OK)
    try:
        result = await api.confirm_login(nonce, callback.from_user.id, callback.from_user.first_name)
    except Exception:
        logger.exception("Вход: api не ответил")
        await callback.answer(texts.LOGIN_FAILED, show_alert=True)
        return
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(texts.LOGIN_DONE if result == "ok" else texts.LOGIN_EXPIRED)


@router.callback_query(F.data == LOGIN_NO)
async def login_cancel(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(texts.LOGIN_CANCELLED)


@router.message()
async def greet(message: Message, web_app_url: str) -> None:
    # На любое другое сообщение, в том числе на обычный /start.
    button = InlineKeyboardButton(text=texts.OPEN_NEST, web_app=WebAppInfo(url=web_app_url))
    await message.answer(texts.START, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]))
