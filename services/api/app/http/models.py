"""Модели запросов и ответов. По ним FastAPI строит схему OpenAPI, а web генерирует свои типы."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.game.prompts import TEXT_LIMIT

Kind = Literal["light", "closeness", "guess", "choice"]


class ApiError(BaseModel):
    detail: str  # код ошибки, например pair_full; текст для человека — в web


class ScreenEvent(BaseModel):
    screen: Literal["pet", "chronicle"]  # какой экран открыт: для метрик ТЗ §13


class AppConfig(BaseModel):
    debug: bool
    new_pairs: bool
    vapid_public_key: str | None  # ключ для подписки на web push; нет — push выключен


class Partner(BaseModel):
    name: str


class PairView(BaseModel):
    status: Literal["waiting", "complete"]
    invite_code: str
    invite_link: str | None  # t.me/<бот>?startapp=<код>; без BOT_TOKEN ссылки нет
    partner: Partner | None


class TraitValue(BaseModel):
    key: str
    name: str
    value: int
    next_at: int | None  # следующий порог: на нём откроется привычка; None — открыто всё


class StageView(BaseModel):
    key: str
    name: str
    sparks: int  # столько искр нужно заработать за всё время
    reached: bool


class HabitView(BaseModel):
    trait: str  # название шкалы
    text: str


class SlotView(BaseModel):
    key: str
    name: str


class TraitRequirement(BaseModel):
    name: str  # название шкалы
    at: int


class ItemView(BaseModel):
    key: str
    slot: str
    name: str
    price: int
    state: Literal["owned", "available", "locked"]  # куплен · в продаже · условие ещё не выполнено
    worn: bool
    requires_stage: str | None  # название стадии, с которой предмет появится в продаже
    requires_trait: TraitRequirement | None  # или порог шкалы
    line: str  # реакция питомца на обнову


class RelicView(BaseModel):
    theme: str  # название темы
    name: str
    text: str
    found: bool
    progress: int  # завершённых посланий темы, не больше needed
    needed: int


class PetView(BaseModel):
    hatched_at: datetime
    sparks: int  # общий кошелёк пары
    earned: int  # заработано за всё время, без трат: по нему растёт стадия
    stage: str  # ключ текущей стадии
    stages: list[StageView]
    traits: list[TraitValue]
    habits: list[HabitView]
    slots: list[SlotView]
    items: list[ItemView]
    relics: list[RelicView]


class OptionView(BaseModel):
    key: str
    text: str


class CardView(BaseModel):
    key: str
    kind: Kind
    text: str
    options: list[OptionView]  # у вопроса о близости вариантов нет — отвечают текстом
    max_length: int | None  # предел свободного ответа; None — отвечают вариантом


class AnswerView(BaseModel):
    option: str | None  # ключ варианта; None — ответ текстом
    text: str  # текст варианта или сам ответ


class GuessView(BaseModel):
    """Прогноз в «Угадай партнёра»: какой вариант выберет другой и сбылось ли."""

    text: str
    correct: bool


class TraitShift(BaseModel):
    key: str
    name: str
    delta: int


class NewsView(BaseModel):
    """Что открылось при раскрытии."""

    kind: Literal["stage", "habit", "relic"]
    name: str  # стадия · шкала · реликвия
    text: str  # реакция питомца на рост · привычка · описание реликвии


class ResultView(BaseModel):
    partner: AnswerView
    same: bool  # выбран один и тот же вариант
    my_guess: GuessView | None  # «Угадай партнёра»: мой прогноз ответа партнёра
    partner_guess: GuessView | None  # и прогноз партнёра о моём ответе
    line: str  # общая реакция питомца
    sparks: int
    traits: list[TraitShift]
    news: list[NewsView]
    chronicle: str | None  # новая страница летописи: совпавший выбор


class PromptView(BaseModel):
    session_id: int
    day: date
    state: Literal["ASSIGNED", "WAITING_FOR_PARTNER", "READY_TO_REVEAL", "COMPLETED"]
    card: CardView
    mine: AnswerView | None
    prediction: AnswerView | None  # мой прогноз ответа партнёра («Угадай партнёра»)
    changes_left: int  # «Другой вопрос»: сколько раз ещё можно сменить послание сегодня; 0 — нельзя
    reaction: str | None  # реакция питомца на мой ответ
    answer_sparks: int | None  # сколько искр дал мой ответ
    partner_answered: bool  # что выбрал партнёр — только в result, когда ответили оба
    seen: bool  # я уже открывал результат: раскрытие больше не проигрывается
    result: ResultView | None


class NotificationsView(BaseModel):
    telegram: Literal["on", "off", "unknown"]
    push: bool


class Me(BaseModel):
    id: int
    name: str
    pair: PairView | None
    pet: PetView | None
    prompt: PromptView | None
    pet_line: str | None  # реплика питомца в Гнезде
    notifications: NotificationsView


class ChronicleEntryView(BaseModel):
    id: int
    kind: Literal["hatch", "choice", "stage", "habit", "relic"]
    text: str
    created_at: datetime


class ChronicleView(BaseModel):
    entries: list[ChronicleEntryView]  # от новых к старым


class JoinRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class AnswerRequest(BaseModel):
    """Ответ по типу карточки: option — вариант; text — ответ о близости; option и prediction — «Угадай партнёра»."""

    session_id: int
    option: str | None = Field(default=None, min_length=1, max_length=64)
    text: str | None = Field(default=None, max_length=TEXT_LIMIT)
    prediction: str | None = Field(default=None, min_length=1, max_length=64)


class ChangeRequest(BaseModel):
    session_id: int


class RevealRequest(BaseModel):
    session_id: int


class BuyRequest(BaseModel):
    item: str = Field(min_length=1, max_length=64)


class WearRequest(BaseModel):
    item: str = Field(min_length=1, max_length=64)
    worn: bool  # true — надеть, false — снять


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=10, max_length=100)


class PushSubscription(BaseModel):
    endpoint: str = Field(max_length=1000)
    keys: PushKeys


class LoginStart(BaseModel):
    nonce: str
    link: str  # t.me/<бот>?start=login_<nonce>


class LoginExchange(BaseModel):
    nonce: str = Field(max_length=64)


class LoginResult(BaseModel):
    status: Literal["pending", "ok"]
    token: str | None = None


class LoginConfirm(BaseModel):
    nonce: str = Field(max_length=64)
    user_id: int
    name: str = Field(max_length=256)


class LoginConfirmResult(BaseModel):
    result: Literal["ok", "expired"]
