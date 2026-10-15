"""Реакции в вечерней карточке и пересылка ответов на фото.

Родные реакции Telegram (долгое нажатие на сообщение) бот в личном чате не получает:
для этого он должен быть администратором чата. Поэтому реакции — кнопками в карточке.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import date

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message

from bot import daily, texts
from bot.app import App
from bot.feature import CardPart, Feature
from bot.repo import User

REACTIONS = ("❤️", "🔥", "😂", "😮", "👏")

router = Router(name="reactions")


class ReactionCallback(CallbackData, prefix="react"):
    day: str  # дата в ISO
    index: int  # номер реакции в REACTIONS


async def card(app: App, day: date, viewer: User) -> CardPart:
    """Часть карточки: реакция партнёра на моё фото и кнопки для моей реакции."""
    mine = await app.repo.get_reaction(day, viewer.user_id)
    partner = daily.partner_of(await app.repo.members(), viewer.user_id)
    lines = []
    if partner is not None:
        theirs = await app.repo.get_reaction(day, partner.user_id)
        if theirs:
            lines.append(texts.partner_reacted(partner.name, theirs))
    lines.append(texts.REACTION_PROMPT)
    buttons = [
        InlineKeyboardButton(
            text=f"{emoji} ✓" if emoji == mine else emoji,
            callback_data=ReactionCallback(day=day.isoformat(), index=index).pack(),
        )
        for index, emoji in enumerate(REACTIONS)
    ]
    return CardPart(lines=lines, buttons=buttons)


@router.callback_query(ReactionCallback.filter())
async def on_reaction(
    callback: CallbackQuery, callback_data: ReactionCallback, app: App, user: User
) -> None:
    if not 0 <= callback_data.index < len(REACTIONS):
        await callback.answer()
        return
    day = date.fromisoformat(callback_data.day)
    emoji = REACTIONS[callback_data.index]
    current = await app.repo.get_day(day)
    if current is None or current.exchanged_at is None:
        await callback.answer(texts.REACTION_TOO_EARLY)
        return
    if await app.repo.get_reaction(day, user.user_id) == emoji:
        await callback.answer(texts.REACTION_SAME)
        return

    await app.repo.set_reaction(day, user.user_id, emoji, app.now())
    partner = daily.partner_of(await app.repo.members(), user.user_id)
    if partner is not None:
        when = texts.about_day(day, app.today())
        title = current.theme_title or ""
        await daily.notify(app, partner.user_id, texts.reaction_notice(user.name, emoji, title, when))
    await callback.answer(texts.reaction_sent(emoji))
    # Отмечаем выбор на кнопке: перестраиваем только клавиатуру, текст карточки не трогаем.
    if isinstance(callback.message, Message):
        _, markup = await daily.build_card(app, day, user, archive=True)
        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=markup)


@router.message(F.reply_to_message, F.text, ~F.text.startswith("/"))
async def on_reply(message: Message, app: App, user: User) -> None:
    """Ответ (reply) на фото дня или на карточку бот пересылает партнёру."""
    replied = message.reply_to_message
    target = await app.repo.message_owner(message.chat.id, replied.message_id) if replied else None
    partner = daily.partner_of(await app.repo.members(), user.user_id)
    if target is None or partner is None:
        raise SkipHandler()  # ответ не на фото дня — пусть разбираются другие хендлеры
    day, owner_id = target
    current = await app.repo.get_day(day)
    title = current.theme_title if current and current.theme_title else ""
    text = texts.comment_notice(
        user.name, title, message.text or "", owner_id == user.user_id, texts.about_day(day, app.today())
    )
    delivered = await daily.notify(app, partner.user_id, text)
    await message.answer(texts.COMMENT_SENT if delivered else texts.COMMENT_FAILED)


feature = Feature(name="reactions", router=router, card=card)
