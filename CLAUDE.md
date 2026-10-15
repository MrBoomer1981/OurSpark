# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

The bot runs in production on Railway (repo `MrBoomer1981/OurSpark`, branch `main`). One bot serves many pairs; pair #1 is the user and their partner. `PLAN.md` is the source of truth for product rules, commands, schema and milestones.

## Working rules

- **Plan before code.** Every feature or change starts with a plan: update `PLAN.md` (or describe the plan in chat) and wait for the user's go. Only then write code.
- **No tests in the repo.** No test files, test dependencies or test steps in plans. Behaviour is checked by hand in Telegram with `/dev` (`DEBUG=true` only). Throwaway verification scripts live outside the repository.
- **Push = production deploy.** Commit and push only when the user explicitly says so; after a push, watch the Railway deploy and check the startup log.
- **Languages.** Talk to the user in Russian. Technical docs (`PLAN.md`, `CLAUDE.md`, any other docs) are written in English; `README.md` stays in Russian. Bot texts are Russian and live only in `bot/texts.py`: no gendered verb forms for participants («прислал/прислала» is not allowed), and names always stay in the nominative case because the bot cannot decline them («<b>Саша</b>: фото готово», not «фото от Саши»).
- The user keeps extending the bot — add features as feature modules (see Architecture) instead of growing the core.

## Commands

```bash
pip install -r requirements.txt
python -m bot          # needs .env (see .env.example) with the token of a SEPARATE test bot
railway logs           # production logs (this folder is linked to the OurSpark service)
```

Deploy = push to `main`; Railway builds the `Dockerfile`.

## Architecture

A Telegram bot for couples: morning theme, daytime photos, evening exchange. Python 3.12, aiogram 3 in polling mode, SQLite via aiosqlite on a Railway Volume, pydantic-settings, loguru. One process: polling and the scheduler share one asyncio loop.

**Core, pairs and features.**
- Core modules: `bot/daily.py` (day logic), `bot/repo.py` (all SQL), `bot/scheduler.py`, `bot/app.py`, `bot/access.py`, `bot/ui.py`.
- **Pairs.** `Core` is the shared context (bot, connection, themes, features, clock `core.clock`). `App` is one pair's context with the interface the day logic and features use (`app.repo`, `app.today()`, `app.invite_link`, …): `Repo(conn, pair_id)` scopes every query to the pair, and time is in the pair's zone (pair setting `timezone`, default `TIMEZONE`). `Registry` holds shared operations: create a pair, join by code, `/leave`, list complete pairs. `access.py` resolves the sender's pair and injects `app` and `user` into handlers (both `None` when the sender is not in a pair; then only `/start`, `/help` and `pair:*` buttons pass). The scheduler walks all complete pairs on every tick. **Every new query on pair data must filter by `pair_id`.**
- Everything user-facing is a feature in `bot/features/`: a module with a `Feature` object (router, jobs, commands, `card`, `on_exchange` hook) registered in `bot/features/__init__.py`. Registry order = router order; `fallback` is always last, `dev` is enabled only with `DEBUG=true`. A new feature = a new module + one registry line; touch the core only if the feature needs a new hook.
- **Evening card** — one message after the exchange album. `daily.build_card` builds the header (theme, date, author, streak); features add lines and a button row through `Feature.card` (reactions use it). The card is re-delivered after restarts (delivery kind `card`), `on_exchange` is not — put new evening things into the card.

Invariants:

- **Day state lives in the database, not in memory.** A scheduler job is `job(app, now)`, called every 30 s per pair. It is reconciliation, not cron: the time has come and the mark in `days` is empty → act. Restarts and deploys lose nothing and repeat nothing.
- **Claim first, send second.** `repo.claim_*` is an atomic `UPDATE … WHERE <mark> IS NULL`; only the first caller gets True. Autocommit (`isolation_level=None`) is what makes claims work. New one-off events must follow the same pattern.
- **The mutual rule lives only in `daily.visible_photos()`.** The exchange, late photos, the history and `/dev` call it instead of re-implementing it.
- **A photo's day is taken from `message.date`** in the pair's zone, not processing time. Pending updates are not dropped at startup.
- **Photo files are never stored**, only `file_id` and `kind` (`photo` or `document`). Telegram cannot mix photos and documents in one album — handled in `daily.send_photos`.
- **Schema changes only through a new migration appended to `MIGRATIONS`** (`bot/db.py`). Never edit applied migrations. Pair settings are key-value rows in `pair_settings` and need no migration.
- A pair has exactly two members (`daily.PAIR_SIZE`); the schedule does not run for incomplete pairs. A person belongs to at most one pair.
- **Themes:** simple ones in `themes/simple.txt` (70% of days, `themes.SIMPLE_SHARE`), creative ones in `themes/creative.txt`; a reroll always gives a simple theme. The title is the theme key, so titles must be unique across both files. Used themes (with photos) are derived per pair by `repo.used_themes()` and never offered again. Simple themes need no preparation; do not add geometry/composition themes.
- **Updates are processed one by one** (`handle_as_tasks=False` in `__main__.py`): Telegram confirms an update only after it was handled, so a deploy mid-processing loses no photo — the update is redelivered. Do not bring back concurrent handling. Handlers must tolerate redelivery (a repeated photo yields `SaveResult` «same»).
- **Important sends go through `daily.deliver_*`.** Who got what is recorded in `deliveries`; `daily.redeliver` (a core scheduler job, events older than a minute) re-sends the rest. New sends that must not be lost follow the same pattern.
- **No volume on Railway → the bot refuses to start** (`db.require_volume`).
- **Reactions are buttons only** (`features/reactions.py`). Native Telegram reactions are not delivered to a bot in a private chat (`message_reaction` requires the bot to be a chat administrator, impossible in a DM). Verified in the docs and by third-party tests; do not revisit.
- **Replies to photos are forwarded via `sent_messages`.** `daily.send_photos` and `daily.send_card` record "chat + message → day and photo owner". Any new place that sends day photos must use `send_photos`.
- **Partner themes (`/addtheme`) live in `custom_themes`.** When a jar theme is used is decided by the core (`daily.send_theme`): at most every other day, alternating authors. The day's theme author is `days.theme_author`; a rerolled jar theme goes back to the jar (`repo.return_custom_theme`).
- **Open early** (`daily.request_early_open`): an exchange before the evening happens only when both pressed «Открыть сейчас» (table `early_open`). `revealed_at` is set first, then the exchange — so "exchanged ⇒ revealed" holds everywhere and the evening event and the reminder skip such days.
- **The streak is computed in `daily.compute_streak`** (a pure function). The record fires once, when a streak overtakes the previous best, never on the very first streak.

## Deploy

- The Railway service is connected to `MrBoomer1981/OurSpark` (public — no secrets in code); a push to `main` deploys. The `Dockerfile` (python:3.12-slim) is detected automatically. There is no Railway config in the repo on purpose: `railway.toml` (Config as Code) is deprecated, and Infrastructure as Code (`.railway/railway.ts`) means an npm package, `railway config apply` instead of push and a risk of deleting the volume if it is not declared. The restart policy is Railway's default, `ON_FAILURE` up to 10 times.
- The database is `bot.db` on the volume at `/app/data`. With a volume Railway never runs two copies at once — that is what prevents polling conflicts and double sends.
- Variables: `BOT_TOKEN`; `TIMEZONE` (time zone of new pairs, default `Europe/Moscow`); `NEW_PAIRS` (`false` closes registration of new pairs); `DEBUG`; `DB_PATH` (default `data/bot.db`). There are no invite codes in variables: every pair has its own code in `pairs`.
- Never run locally with the production token: the local copy and production would steal updates from each other (`Conflict` in logs).
- Deploys are fine any time, including during the day when a photo was already sent (see "Reliability on deploy" in `PLAN.md`). A separate database (Postgres) is not needed — this was discussed and decided.
