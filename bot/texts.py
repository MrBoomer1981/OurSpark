"""Все тексты бота — в одном месте, чтобы тон был единым и их было легко править.

Правила:
- у участников никаких родовых окончаний («прислал/прислала») — пишем в настоящем
  или будущем времени, безлично;
- имена склонять бот не умеет, поэтому имя всегда в именительном падеже:
  «<b>Саша</b>: фото готово», а не «фото от Саши».
"""

from __future__ import annotations

from datetime import date, time, timedelta
from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.daily import Schedule
    from bot.repo import Day
    from bot.themes import Theme

MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)
CAPTION_LIMIT = 900  # Telegram режет подписи длиннее 1024 символов; оставляем место под имя


def hhmm(moment: time) -> str:
    return moment.strftime("%H:%M")


def day_title(day: date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]}"


def bold(text: str) -> str:
    return f"<b>{escape(text)}</b>"


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def hours(n: int) -> str:
    return f"{n} {plural(n, 'час', 'часа', 'часов')}"


def duration(delta: timedelta) -> str:
    minutes = max(1, round(delta.total_seconds() / 60))
    whole_hours, minutes = divmod(minutes, 60)
    if whole_hours and minutes:
        return f"{whole_hours} ч {minutes} мин"
    return f"{whole_hours} ч" if whole_hours else f"{minutes} мин"


# ── Меню команд ──

COMMAND_TODAY = "Тема и статус дня"
COMMAND_HISTORY = "Архив и серия"
COMMAND_SETTINGS = "Расписание"
COMMAND_HELP = "Как всё устроено"


# ── Вход ──

PRIVATE = "Это приватный бот 🔒"
FIRST_THEME_NOW = "уже через минуту"


def first_theme_today(at: time) -> str:
    return f"сегодня в {hhmm(at)}"


def first_theme_tomorrow(at: time) -> str:
    return f"завтра в {hhmm(at)}"


def welcome_first(invite_link: str) -> str:
    return (
        "Привет! Это «Фото дня» на двоих 📸\n\n"
        "Каждое утро я присылаю тему, днём вы фотографируете и присылаете фото мне, "
        "а вечером я устраиваю обмен.\n\n"
        "Осталось позвать второго участника — перешли эту ссылку:\n"
        f"{invite_link}"
    )


def welcome_second(partner: str, first_theme: str) -> str:
    return (
        f"Привет! Пара в сборе: ты и {bold(partner)} 📸\n\n"
        f"Первая тема — {first_theme}. Как всё устроено — /help"
    )


def partner_joined(name: str, first_theme: str) -> str:
    return f"🎉 {bold(name)} тоже в игре! Первая тема — {first_theme}."


def need_partner(invite_link: str) -> str:
    return f"Пока в игре только ты. Перешли второму участнику ссылку — и начнём:\n{invite_link}"


def help_text(schedule: Schedule, max_rerolls: int, reminder_hours: int) -> str:
    return (
        "📸 <b>Фото дня на двоих</b>\n\n"
        f"• В {hhmm(schedule.theme)} приходит тема дня. Пока никто не прислал фото, "
        f"её можно сменить на простую — до {max_rerolls} раз. "
        "Тема, по которой уже есть фото, больше не повторится.\n"
        "• Днём каждый присылает одно фото — обычным фото или файлом без сжатия. "
        "Новое фото заменяет прежнее, подпись к фото тоже увидит партнёр.\n"
        f"• В {hhmm(schedule.reveal)} — обмен. Фото партнёра видит только тот, кто прислал своё. "
        "Не успеваешь — можно дослать до полуночи, и обмен случится сразу.\n"
        f"• За {hours(reminder_hours)} до обмена напомню, если фото ещё нет.\n\n"
        "/today — тема и статус дня\n"
        "/history — архив и серия\n"
        "/settings — расписание"
    )


# ── Тема ──

REROLL_DENIED = {
    "stale": "Эта тема уже неактуальна",
    "has_photo": "Уже нельзя: по этой теме уже есть фото 📸",
    "limit": "Смены темы на сегодня закончились",
    "race": "Тему только что сменили — смотри новое сообщение",
}


def theme_header(theme: Theme) -> str:
    text = f"📸 <b>Тема дня — «{escape(theme.title)}»</b>"
    return f"{text}\n{escape(theme.hint)}" if theme.hint else text


def theme_message(theme: Theme, reveal: time) -> str:
    return f"{theme_header(theme)}\n\nЖду фото до {hhmm(reveal)}."


def theme_changed(by: str, theme: Theme, reveal: time) -> str:
    return f"🔄 {bold(by)} меняет тему.\n\n{theme_message(theme, reveal)}"


def reroll_button(left: int) -> str:
    return f"🔄 Другая тема (ещё {left})"


# ── /today ──

TODAY_SKIPPED = "Сегодня темы не было: бот отдыхал. Новая придёт завтра."
TODAY_EXCHANGED = "Обмен состоялся ✅"
TODAY_LATE = "Вечер уже наступил: ждём второе фото до полуночи — обмен будет сразу."


def today_no_theme(at: time) -> str:
    return f"Тема дня придёт в {hhmm(at)} ☀️"


def today_until(reveal: time, left: timedelta) -> str:
    return f"Обмен в {hhmm(reveal)} — через {duration(left)}"


def today_status(
    theme: Theme, *, mine: bool, partner: str, partner_has: bool, status: str, streak: int
) -> str:
    def mark(has: bool) -> str:
        return "✅ есть" if has else "⏳ пока нет"

    lines = [
        theme_header(theme),
        "",
        f"Твоё фото: {mark(mine)}",
        f"{bold(partner)}: {mark(partner_has)}",
        "",
        status,
    ]
    if streak:
        lines.append(streak_line(streak))
    return "\n".join(lines)


# ── Фото ──

ALBUM_NOTE = "\nИз альбома беру одно фото — если нужно другое, пришли его отдельно."
PHOTO_SAVE_FAILED = "😬 Не получилось сохранить фото — пришли его ещё раз, пожалуйста."
NOT_A_PHOTO = "Жду фото 📸 Можно обычным фото или файлом — без сжатия."
UNKNOWN_COMMAND = "Такой команды нет. Всё, что умею, — в /help"


def photo_before_theme(at: time) -> str:
    return f"Тема дня ещё не пришла — она будет в {hhmm(at)}. Фото пришли после неё 🙂"


def photo_day_skipped(at: time) -> str:
    return f"Сегодня темы нет. Новая придёт завтра в {hhmm(at)}."


def photo_day_closed(at: time) -> str:
    return f"Обмен за этот день уже был 🌙 Новая тема придёт в {hhmm(at)}."


def photo_accepted(reveal: time) -> str:
    return f"✅ Принято! Обмен в {hhmm(reveal)}. Пришлёшь другое фото — заменю."


def photo_replaced(reveal: time) -> str:
    return f"🔄 Фото заменено. Обмен в {hhmm(reveal)}."


def photo_accepted_late(partner: str) -> str:
    return (
        f"✅ Принято! Как только {bold(partner)} пришлёт фото, сразу будет обмен. "
        "Время — до полуночи."
    )


def partner_photo_waiting(name: str) -> str:
    return f"👀 {bold(name)}: фото готово и ждёт обмена"


def partner_photo_waiting_late(name: str) -> str:
    return f"👀 {bold(name)}: фото готово и ждёт тебя. Пришли своё до полуночи — и сразу его увидишь."


def photo_caption(name: str, caption: str | None) -> str:
    text = bold(name)
    if caption:
        text += f"\n{escape(caption[:CAPTION_LIMIT])}"
    return text


# ── Напоминание и вечер ──

def reminder(title: str, reveal: time, left: timedelta, partner_waiting: str | None) -> str:
    text = f"⏰ До обмена {duration(left)}, тема — «{escape(title)}». Жду фото до {hhmm(reveal)}."
    if partner_waiting:
        text += f"\n{bold(partner_waiting)}: фото уже готово 👀"
    return text


def reveal_waiting_partner(partner: str) -> str:
    return (
        f"🌙 Время обмена! Твоё фото на месте, а {bold(partner)} пока без фото. "
        "Если оно появится до полуночи, обмен случится сразу."
    )


def reveal_missing_yours(partner: str) -> str:
    return (
        f"🌙 Обмен начался, а твоего фото нет 🙈 {bold(partner)}: фото готово и ждёт тебя — "
        "пришли своё до полуночи, и сразу его увидишь."
    )


def reveal_nobody(theme_at: time) -> str:
    return f"🌙 Сегодня обошлось без фото. Завтра в {hhmm(theme_at)} — новая тема."


# ── Серия и архив ──

HISTORY_EMPTY = "Архив пока пуст — первая тема ещё впереди."
HISTORY_OLDER = "← Раньше"
HISTORY_NEWER = "Позже →"
HISTORY_DAY_EMPTY = "В этот день фото не было."
HISTORY_DAY_HIDDEN = "Твоего фото в этот день нет, а фото партнёра открывается только в обмен."


def streak_line(n: int) -> str:
    return f"🔥 Серия: {n} {plural(n, 'день', 'дня', 'дней')} подряд"


def exchange_summary(title: str, day: date, streak: int) -> str:
    text = f"📸 «{escape(title)}» · {day_title(day)}"
    if streak >= 2:
        return f"{text}\n{streak_line(streak)}"
    if streak == 1:
        return f"{text}\n✨ Первый день серии"
    return text


def history_header(streak: int, exchanges: int) -> str:
    return f"🗂 <b>Архив</b>\n🔥 Серия: {streak} · обменов всего: {exchanges}\n\nВыбери день:"


def history_button(day: Day, photos: int, is_today: bool) -> str:
    if day.exchanged_at:
        mark = "✅"
    elif is_today and day.revealed_at is None:
        mark = "⏳"
    elif photos:
        mark = "🌓"
    else:
        mark = "▫️"
    title = day.theme_title or ""
    if len(title) > 26:
        title = title[:25] + "…"
    return f"{day.date:%d.%m} · {title} · {mark}"


def history_day_footer(day: Day) -> str:
    text = f"📸 «{escape(day.theme_title or '')}» · {day_title(day.date)}"
    if day.exchanged_at:
        return text
    if day.revealed_at is None:
        return f"{text}\nОбмен ещё впереди — пока здесь только твоё фото."
    return f"{text}\nОбмена в этот день не было — здесь только твоё фото."


# ── Настройки ──

SETTINGS_THEME_BUTTON = "🕘 Время темы"
SETTINGS_REVEAL_BUTTON = "🌙 Время обмена"
ASK_THEME_TIME = "Во сколько присылать тему? Напиши время, например <code>8:30</code>.\n/cancel — отмена"
ASK_REVEAL_TIME = "Во сколько устраивать обмен? Напиши время, например <code>21:00</code>.\n/cancel — отмена"
BAD_TIME = "Не понял время 🤔 Напиши, например, <code>8:30</code> или <code>21</code>.\n/cancel — отмена"
THEME_SOON = "Сегодня это время уже прошло — тема придёт в течение минуты."
REVEAL_SOON = "Сегодня это время уже прошло — обмен случится в течение минуты."
SETTINGS_CANCELLED = "Ок, ничего не меняю."


def settings_text(
    schedule: Schedule, reminder_at: time | None, reminder_hours: int, timezone: str
) -> str:
    if reminder_at:
        reminder_line = f"{hhmm(reminder_at)} (за {hours(reminder_hours)} до обмена)"
    else:
        reminder_line = "не приходит: обмен слишком скоро после темы"
    return (
        "⚙️ <b>Расписание</b>\n\n"
        f"Тема дня — {hhmm(schedule.theme)}\n"
        f"Обмен — {hhmm(schedule.reveal)}\n"
        f"Напоминание — {reminder_line}\n"
        f"Часовой пояс — {escape(timezone)}\n\n"
        "Что поменять?"
    )


def theme_must_precede(schedule: Schedule) -> str:
    return (
        f"Тема должна приходить раньше обмена, а получается тема в {hhmm(schedule.theme)}, "
        f"обмен в {hhmm(schedule.reveal)}. Попробуй другое время."
    )


def schedule_changed(by: str, schedule: Schedule) -> str:
    return (
        f"⚙️ {bold(by)} меняет расписание: тема в {hhmm(schedule.theme)}, "
        f"обмен в {hhmm(schedule.reveal)}."
    )


# ── /dev ──

DEV_BUTTONS = {
    "theme": "Тема сейчас",
    "remind": "Напоминание сейчас",
    "reveal": "Обмен сейчас",
    "reset": "Сбросить сегодня",
    "clear": "Очистить историю",
}
DEV_DONE = "Готово ✅"
DEV_NOT_NOW = "Не сработало: событие уже было или для него нет условий. Помогает «Сбросить сегодня»."


def dev_state(
    day: date,
    current: Day | None,
    photos: int,
    members: list[str],
    schedule: Schedule,
    invite_link: str,
    themes_left: tuple[int, int] | None = None,
) -> str:
    def flag(value: object) -> str:
        return "✅" if value else "—"

    lines = [
        "🛠 <b>Служебное</b> (DEBUG)",
        "",
        f"Сегодня: {day_title(day)}",
        f"Участники: {escape(', '.join(members)) or 'пока никого'}",
        f"Расписание: тема {hhmm(schedule.theme)}, обмен {hhmm(schedule.reveal)}",
    ]
    if themes_left is not None:
        lines.append(f"Новых тем: простых {themes_left[0]}, посложнее {themes_left[1]}")
    if current is None:
        lines.append("День ещё не начался")
    else:
        flags = (
            f"Тема {flag(current.theme_sent_at)} · напоминание {flag(current.reminder_sent_at)} · "
            f"вечер {flag(current.revealed_at)} · обмен {flag(current.exchanged_at)}"
        )
        if current.skipped:
            flags += " · день пропущен"
        lines += [f"Тема: «{escape(current.theme_title or '—')}»", flags, f"Фото: {photos} из 2"]
    lines += ["", f"Приглашение: {invite_link}"]
    return "\n".join(lines)
