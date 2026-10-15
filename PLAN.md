# OurSpark — daily photo for two: plan and spec

A Telegram bot for couples. Every morning it sends a theme, during the day each partner takes a photo and sends it to the bot, in the evening the bot runs the exchange: each partner sees the other's photo. One bot serves any number of pairs. Hosted on Railway.

> Project rule: plan first, then code. No tests; behaviour is checked by hand in Telegram.

---

## 1. A day, step by step

Defaults: theme at 09:00, exchange at 21:00, in the pair's time zone.

| Time | What happens |
|---|---|
| 09:00 | Both get the theme («📸 Тема дня — «Отражения»…», hint, «Жду фото до 21:00», streak line) with a «🔄 Другая тема» button |
| daytime | Each sends a photo. The sender gets «✅ Принято», the partner «👀 <name>: фото готово». When both photos are in, both messages also carry «🔓 Открыть сейчас» |
| 18:00 | Whoever has no photo yet gets a reminder (with «🔥 На кону серия» if there is a streak) |
| 21:00 | If both sent: album + evening card (theme, author, streak, milestones, reaction buttons) |
| 21:00–23:59 | A late photo can still be sent; the exchange then happens immediately |
| 00:00 | The day closes |

---

## 2. Rules

### Pairs: one bot, many pairs
- **Create a pair:** `/start` → «💞 Создать пару» → the bot replies with an invite link `t.me/<bot>?start=<code>`. Every pair has its own code.
- **Join:** the partner opens the link and the pair is complete. A third person gets «В этой паре уже двое» and an offer to create their own pair. A person belongs to at most one pair.
- **Everything is per pair:** schedule and time zone (`/settings`), theme history (used themes never repeat within the pair), streak, theme jar, reactions, history. Pairs never see each other.
- **`/leave`** (with confirmation) dissolves the pair; the partner is notified; the history stays in the database but is no longer reachable; a new pair starts from scratch.
- **The schedule runs only for complete pairs** (two members).
- **Not in a pair:** only `/start`, `/help` and the pair buttons work; everything else gets «Ты пока не в паре…».
- **`NEW_PAIRS=false`** closes registration of new pairs; existing pairs keep playing.
- **Pair #1** is the couple that played before multi-pair support: migration 5 moved them there with their invite code, schedule and full history.
- **Texts never use gendered verb forms** for participants, and names always stay in the nominative case (the bot cannot decline names).

### Themes
- 500 themes in two files, one per line, «Title — hint»:
  - **simple, 350** — `themes/simple.txt`: can be shot within a minute wherever you are, no props, no special light, no searching;
  - **creative, 150** — `themes/creative.txt`: needs some thought, searching or inventing (light, angles, mood, games).
- **A simple theme is picked with probability 70%, a creative one with 30%.** Pool sizes follow the same ratio, so both run out at the same pace.
- **A theme with at least one photo is used up for that pair** and never offered again (derived from the database, no explicit flag). Themes shown without photos (or rerolled away) may come back, but not within the last 30 shows; the least-shown themes go first.
- If a pool is exhausted the other one is used; if everything is used, old themes repeat and a warning is logged (~1.5 years at one theme a day).
- No seasonal themes and no geometry/composition themes. Titles are the theme keys, so they must be unique across both files.

### Theme reroll
- «🔄 Другая тема» under the morning message: anyone may press it while nobody has sent a photo, at most 3 times a day.
- **The new theme is always a simple one.** Both get it, with a note who changed it.

### Photo intake
- Accepts compressed photos and image files; the exchange returns them in the same form.
- One photo per person per day; a new photo before the exchange replaces the old one; the caption is kept and shown in the exchange.
- From an album only one photo is taken (the bot says so).
- The partner is notified only about the first photo of the day.
- Before the theme: «Тема ещё не пришла…»; after the exchange: «Обмен за этот день уже был…»; text/stickers/video get a short hint.
- **The day of a photo is taken from the message send time,** not processing time, so a photo sent at 23:58 during a restart still counts for its day.

### Exchange: mutual only
- At 21:00:
  - **both sent:** each gets an album (each photo captioned with the author's name and caption) and the evening card;
  - **one sent:** «<name> пока без фото…» to the sender, «<name>: фото готово и ждёт тебя — пришли своё до полуночи» to the other;
  - **nobody sent:** «Сегодня обошлось без фото».
- From 21:00 to 23:59 the exchange happens as soon as the second photo arrives.
- At 00:00 the day closes; an unpaired photo is never shown to the partner, including in the history.
- If one photo is a file and the other a compressed photo, the exchange goes as two separate messages (Telegram cannot mix them in one album).

### Open early (both must agree)
- When the second photo arrives, «Принято» and «фото готово» get the line «Оба фото на месте 📸 … или раньше, если вы оба нажмёте «Открыть сейчас»» and the button.
- First press: answer «Ждём, пока <name> тоже нажмёт», the partner gets «🔓 <name> хочет открыть фото сейчас» with the button. Repeated presses change nothing.
- **Both pressed:** album + card immediately. The evening then counts as done (nothing at 21:00, no reminder); the streak counts as usual.
- Otherwise the exchange happens at 21:00. `/today` shows who already wants to open and offers the button.
- Early open sets `revealed_at` first and then exchanges, so "exchanged ⇒ revealed" holds everywhere.

### Reminder
- Three hours before the exchange (18:00 by default), only to those without a photo; skipped if it would fall before the theme time.

### Evening card, reactions and replies
- **After the album comes one card:** theme, date, author (if the theme came from the jar), streak, milestones (7/30/100/365 days) and «🏆 Новый рекорд серии!», plus reaction buttons ❤️ 🔥 😂 😮 👏.
- **Reactions:** the partner gets «<name> ставит 🔥 твоему фото «Тема»»; the choice can be changed; the chosen one is marked on the button.
- **Buttons, not native reactions:** Telegram does not send `message_reaction` updates to a bot in a private chat (the bot would have to be a chat administrator). Verified in the docs and confirmed by third-party tests.
- **Replies:** a text reply to the partner's photo, one's own photo or the card is forwarded: «💬 <name> о твоём фото «Тема»: …». The bot maps sent messages to photos in `sent_messages`; replies to anything else are not forwarded and are not stored.
- The card is re-delivered after a restart together with the album; future features add lines/buttons to it via `Feature.card`.

### Partner themes (`/addtheme`)
- `/addtheme Окно — вид из любого окна` or just `/addtheme` (the bot asks). The hint is optional; the title is 2–50 characters.
- The theme goes into the pair's jar; the partner does not see it in advance; the author sees how many of their themes are waiting; a «🗑 Удалить» button works until the theme is shown.
- **A jar theme is picked at most every other day,** alternating authors, oldest first; on other days the usual 70/30 pick applies.
- The theme message, `/today`, the card and the history show «✍️ Тему предлагает <name>».
- If a jar theme is rerolled, it goes back to the jar.

### History and streak
- `/history`: days as buttons, 10 per page, «15.10 · Отражения · ✅» (✅ exchange, 🌓 only one photo, ▫️ no photos). A day with an exchange is shown as photos + the card (reactions visible, can react to old photos); the mutual rule applies here too.
- **Streak** = consecutive days with an exchange; today does not break it until it ends; days the bot slept through (`skipped`) do not break it either.
- Shown in the morning theme, the reminder («На кону серия»), the card (milestones, record — only when a previous best is beaten, never on the first streak), `/today` and `/history` (with the record).

### Settings (`/settings`)
- Theme time, exchange time and the pair's time zone (common zones as buttons, any IANA name as text). Either partner can change them; both are notified.
- Theme time must be earlier than exchange time. A change applies immediately; if the new time has already passed today, the event happens within a minute (the bot warns). A theme already sent today is not sent again.

---

## 3. Commands

| Command | What it does |
|---|---|
| `/start` | create a pair / join by link; in a pair — short help |
| `/today` | today's theme, who has a photo, time to exchange, streak, early-open button |
| `/history` | history, streak and record |
| `/addtheme` | add a theme to the jar |
| `/settings` | schedule and time zone |
| `/leave` | leave the pair (with confirmation) |
| `/help` | rules in short |
| `/dev` | service buttons for manual checks (theme now · reminder now · exchange now · reset today · clear history). Only with `DEBUG=true` |

---

## 4. Technical

### Stack
- **Python 3.12 + aiogram 3** in polling mode (no web server, no domain).
- **SQLite (aiosqlite) on a Railway Volume.** A separate Postgres is not needed: it would also live on a volume, costs a separate service and does not help against deploy-time losses.
- **pydantic-settings + python-dotenv** for config, **loguru** for logs, **tzdata** for time zones in the slim image.
- Photo files are never stored: Telegram keeps them, the database stores `file_id` only.

### Structure
```
Photochki_bot/
├── PLAN.md · CLAUDE.md · README.md
├── requirements.txt · Dockerfile · .dockerignore · .env.example · .gitignore
├── themes/                 simple.txt — 350 simple themes, creative.txt — 150 creative
└── bot/
    ├── __main__.py         startup: config → db → Core → features → scheduler → polling
    ├── config.py           environment variables
    ├── app.py              Core (shared context) and App (one pair's context)
    ├── feature.py          Feature: router, scheduler jobs, menu commands, card part, hooks
    ├── db.py               SQLite connection, migrations, volume check
    ├── repo.py             all SQL: Registry (pairs and members) and Repo (one pair)
    ├── themes.py           theme sources: two pools from themes/, 70/30 pick
    ├── daily.py            day logic: theme, reroll, photos, reminder, exchange, card, streak
    ├── scheduler.py        every 30 s: all jobs for every complete pair
    ├── access.py           middleware: finds the sender's pair, injects app and user
    ├── ui.py               small shared UI helpers
    ├── texts.py            all bot texts (Russian)
    └── features/
        ├── __init__.py     feature registry; its order = router order
        ├── daily_theme.py  morning theme, «Другая тема», /today
        ├── photos.py       photo intake
        ├── early_open.py   «Открыть сейчас» (both must agree)
        ├── partner_themes.py  /addtheme
        ├── reactions.py    card reactions and reply forwarding
        ├── reminder.py     reminder
        ├── exchange.py     evening exchange, closing days the bot slept through
        ├── history.py      /history
        ├── settings.py     /settings
        ├── onboarding.py   /start, pair creation, joining by link, /leave, /help
        ├── dev.py          /dev (only with DEBUG=true)
        └── fallback.py     answers everything else (always last)
```
The mutual rule lives in exactly one place, `daily.visible_photos()`; the exchange, late photos, the history and `/dev` all use it.

### Pairs inside the code
- `Core` — shared context: bot, connection, `Registry`, config, themes, features, clock (`core.clock`, replaceable in checks).
- `App` — one pair's context with the same interface the day logic and features use (`app.repo`, `app.today()`, `app.invite_link`, …): `Repo(conn, pair_id)` scopes every query to the pair, time is in the pair's zone (pair setting `timezone`, default `TIMEZONE`).
- `access.py` resolves the sender's pair and injects `app`/`user`; the scheduler builds an `App` for every complete pair on each tick. Any new query on pair data must filter by `pair_id`.

### Extensibility
- **A feature is a module in `bot/features/` with a `Feature` object** (router, jobs, menu commands, card part, hooks), enabled by one line in the registry.
- **Scheduler jobs are plain async functions `job(app, now)`** that decide themselves whether it is time and claim the event in the database.
- **Evening card:** the core builds the header (theme, date, author, streak), features add lines and a button row via `Feature.card`.
- **`on_exchange` hook** for side effects after an exchange (e.g. a collage); called once and may be missed if the bot crashes mid-exchange — put important things into the card instead.
- **Theme sources** share one interface: a list now; an AI source with the list as fallback is possible later.
- **Schema changes only through new migrations** appended to `MIGRATIONS` in `bot/db.py`; pair settings are key-value and need no migration.

### Database
```
pairs          id PK · invite_code UNIQUE · created_at · closed_at
pair_settings  PK (pair_id, key) · value         theme_time, reveal_time, timezone
users          user_id PK · name · joined_at · pair_id (NULL — not in a pair)
days           PK (pair_id, date) · theme_title · theme_hint · theme_author
               · theme_sent_at · reminder_sent_at · revealed_at · exchanged_at · skipped
theme_log      id · pair_id · date · title · shown_at       every shown theme, rerolled ones too
submissions    PK (date, user_id) · pair_id · file_id · kind (photo | document) · caption
               · media_group_id · sent_at
deliveries     PK (date, user_id, kind) · pair_id · delivered_at   who really got theme / album / card
custom_themes  id · pair_id · author_id · title · hint · created_at · shown_on   /addtheme jar
reactions      PK (date, user_id) · pair_id · emoji · at
early_open     PK (date, user_id) · pair_id · at              who agreed to open early
sent_messages  PK (chat_id, message_id) · pair_id · date · owner_id   whose photo is in which message
settings       key PK · value                               legacy global settings (unused)
```
- `revealed_at` — the evening event happened; `exchanged_at` — both got each other's photos (may be after 21:00); `skipped` — the bot slept through the theme time until the exchange time.
- **Events are claimed before they are sent:** atomic `UPDATE … WHERE <mark> IS NULL`, only the first caller gets True. The connection runs in autocommit (`isolation_level=None`).
- A person is in one pair at a time, so the old `(date, user_id)` keys stay unique.

### Scheduler
A loop every 30 seconds (not cron) checks the clock of every complete pair against the database: theme due and not sent → pick and send; reminder due → remind those without a photo; exchange due → exchange. State lives in the database, so after a restart nothing is lost or duplicated:
- the bot was down at exchange time and came back after midnight → yesterday's exchange is done at start;
- the bot slept through the morning until the exchange time → the day is skipped so that theme and exchange do not arrive together;
- pending updates are not dropped at start, so photos sent during a deploy are processed.

### Reliability on deploy
Deploys are allowed any time, including during the day when a photo was already sent; no photo may be lost.
- **No volume on Railway → the bot refuses to start** (`RAILWAY_ENVIRONMENT_ID` set and the database not under `RAILWAY_VOLUME_MOUNT_PATH`).
- **Updates are processed one by one** (`handle_as_tasks=False`): Telegram confirms an update only after it was handled; an interrupted update is redelivered and a repeated photo is recognised (`SaveResult` «same», no second notification).
- **`deliveries` records who really got the theme, the album and the card;** `daily.redeliver` (a core scheduler job) re-sends to the rest for events older than a minute (theme until the evening, exchange for two days).
- **If saving a photo fails, the bot asks to resend it** instead of staying silent.
- **The startup log shows the database path, the number of pairs and members.**
- In production logs, tracebacks do not include variable values (`diagnose` only with `DEBUG`).

---

## 5. Railway
- Repository `MrBoomer1981/OurSpark` (public, no secrets in code); every push to `main` deploys.
- Built from `Dockerfile` (python:3.12-slim), detected automatically. Restart on failure — Railway default (up to 10). No healthcheck, no public domain.
- **No Railway config file on purpose:** `railway.toml` (Config as Code) is deprecated (read until 2026-12-01) and only repeated the defaults; Infrastructure as Code (`.railway/railway.ts`) would add an npm package, `railway config apply` instead of push and a risk of deleting the volume if it is not declared.
- Volume `ourspark-volume` mounted at `/app/data` (holds `bot.db`). With a volume Railway never runs two copies at once, so polling never conflicts.
- Region: currently `asia-southeast1` (Singapore); a European region would be closer to Telegram's servers (planned move).

| Variable | Default | Meaning |
|---|---|---|
| `BOT_TOKEN` | — | token from @BotFather |
| `TIMEZONE` | `Europe/Moscow` | time zone of new pairs; each pair can change its own |
| `NEW_PAIRS` | `true` | `false` closes registration of new pairs |
| `DEBUG` | `false` | `true` enables `/dev` and verbose logs |
| `DB_PATH` | `data/bot.db` | SQLite path (`/app/data/bot.db` on Railway) |

A local run needs a separate test bot: one token cannot be polled from two places.

---

## 6. Milestones
1. **v1** — one pair: themes, photos, mutual exchange, reminder, history and streak, settings, `/dev`. Done.
2. **Themes 70/30** — 500 themes, used themes never repeat, reroll gives a simple theme. Done.
3. **Reliability on deploy** — volume check, one-by-one updates, deliveries and re-delivery. Done.
4. **Evening card, reactions and replies, `/addtheme`, streak milestones and record.** Done.
5. **Open early when both agree.** Done.
6. **Many pairs** — pairs, per-pair time zone, `/leave`, `NEW_PAIRS`, migration 5; code cleanup; README for users and self-hosters. Current.
7. **Move to a European Railway region** — after a database backup, in a quiet hour. Next.

---

## 7. Manual check (instead of tests)
Ad-hoc verification scripts stay outside the repository. In Telegram, ideally with two people:
- [ ] `/start` → «Создать пару» → link; the partner joins; a third person cannot join; a broken link is rejected
- [ ] the theme arrives for both; «Другая тема» works until the first photo, at most 3 times
- [ ] compressed photo and file; replacement, caption, album
- [ ] exchange: both / one / nobody; a late photo before midnight; «Открыть сейчас» only when both press
- [ ] the card: reactions, replies to photos and to the card
- [ ] `/addtheme`, deleting a jar theme, a jar theme with the author line
- [ ] a second pair with another time zone gets its theme at its own time; `/leave`
- [ ] a redeploy in the middle of the day: nothing lost or duplicated

---

## 8. Not in scope yet / ideas
- Collage of the day; AI-generated themes; weekly recap album; achievements
- Video and video notes
- A Mini App gallery; archive export
- Photo backups to disk
