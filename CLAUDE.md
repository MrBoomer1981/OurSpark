# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

- **Rebuild in progress.** The project is being rebuilt into «Воронье гнездо»: an asynchronous game in which a couple grows a shared pet. One web app runs as a Telegram Mini App and as a PWA, backed by the services `web`, `api`, `bot` and Railway Postgres. `PLAN.md` is the rebuild plan and the source of truth (decisions, rules, schema, milestones). The product brief is `voronye_gnezdo_mvp_spec.md`; `PLAN.md` wins where they differ.
- **Next: milestone 0.** `services/` does not exist yet; commands and architecture notes for the new services are added here as milestones land.
- **The OurSpark photo bot stays in production, unchanged, until milestone 6** (repo `MrBoomer1981/OurSpark`, branch `main`; one bot serves many pairs; pair #1 is the user and their partner). Its code is `bot/`, `themes/` and the root `Dockerfile`; its spec is `docs/photo-bot.md`. Change it only to fix bugs.

## Working rules

- **Plan before code.** Every feature or change starts with a plan: update `PLAN.md` (`docs/photo-bot.md` for the photo bot) or describe the plan in chat, and wait for the user's go. Only then write code. Every rebuild milestone starts with a plan update.
- **No tests in the repo** — this also overrides brief §15.7. No test files, test dependencies or test steps in plans. Behaviour is checked by hand: the photo bot with `/dev`, the game with the debug panel (both only with `DEBUG=true`). Throwaway verification scripts live outside the repository.
- **Push = production deploy.** A push to `main` redeploys every Railway service whose Watch Paths changed. Commit and push only when the user explicitly says so; after a push, watch the Railway deploy and check the startup log. For the photo bot: `База: … · пар: … · участников: …` (counts must not drop — nothing was lost), then `Темы: …`, `Фичи: … · новые пары: …`, `Планировщик: задач …`.
- **Languages.** Talk to the user in Russian. `PLAN.md` is written in Russian (the user's request, 2026-10-19), as is `README.md`; the other technical docs (`CLAUDE.md`, `docs/`) are written in English. Code comments and docstrings stay in Russian — do not translate them.
- **User-facing texts** are Russian and live in one place per kind:
  - `bot/texts.py` — the photo bot;
  - `services/web/src/texts.ts` — the game UI;
  - the texts module of `api` — notifications;
  - `services/api/content/` — prompt cards and pet lines.

  No gendered verb forms for participants («прислал/прислала», «выбрал(а)» are not allowed). Names always stay in the nominative case because the bot cannot decline them («<b>Саша</b>: фото готово», not «фото от Саши»). Prompt cards follow the same rules.
- The user keeps extending the product — add features as modules (photo bot: feature modules; game: domain modules in `api`) instead of growing the core.

## Commands

Photo bot:

```bash
pip install -r requirements.txt
python -m bot          # needs .env (see .env.example) with the token of a SEPARATE test bot
railway logs           # production logs (this folder is linked to the OurSpark service)
```

Deploy = push to `main`; Railway builds the root `Dockerfile` for the photo bot. Commands for `services/*` are added in milestone 0.

## Game architecture (target — details in `PLAN.md` §3)

- **Services by runtime role, not by domain:**
  - `web` — React Mini App and PWA from one build; Caddy serves it and proxies `/api`;
  - `api` — FastAPI: the whole game, auth, the outbox relay;
  - `bot` — aiogram: `/start`, the menu button, confirmation of PWA logins;
  - Railway Postgres.

  Only `web` is public.
- **Domains live inside `api`** as modules (`pairs`, `prompts`, `pet`, `rewards`, `chronicle`). Each owns its tables; other modules call its functions, never its SQL. `game/reveal.py` is the only cross-domain step and runs in one transaction. Do not split domains into separate services without a plan.
- **Postgres, not SQLite, for the game** (decided 2026-10-19): a Railway volume attaches to one service only, and a service with a volume goes down briefly on every deploy.
- **Auth:**
  - inside Telegram, every request carries initData, checked with the bot token (aiogram `safe_parse_webapp_init_data`);
  - the PWA logs in through the bot (`/start login_<nonce>` plus an explicit confirmation) and keeps a session token.

  The user and their pair always come from server-side auth, never from the client.
- **Invariants:**
  - The server decides: the client sends intents, never amounts or states.
  - Exactly once: every reward, trait change, unlock, chronicle entry and notification has a unique key.
  - The partner's answer never leaves `api` before both answered; one function owns this rule.
  - Every pair query filters by `pair_id`.
  - Important sends go through the outbox.
  - Schema changes only by appended migrations.
  - Assets are referenced by logical names through the manifest.

## Photo bot architecture (production until milestone 6)

A Telegram bot for couples: morning theme, daytime photos, evening exchange. Python 3.12, aiogram 3 in polling mode, SQLite via aiosqlite on a Railway Volume, pydantic-settings, loguru. One process: polling and the scheduler share one asyncio loop.

**Core, pairs and features.**
- Core modules: `bot/daily.py` (day logic), `bot/repo.py` (all SQL), `bot/scheduler.py`, `bot/app.py`, `bot/access.py`, `bot/ui.py`.
- **Pairs.** `Core` is the shared context (bot, connection, themes, features, clock `core.clock`). `App` is one pair's context with the interface the day logic and features use (`app.repo`, `app.today()`, `app.invite_link`, …): `Repo(conn, pair_id)` scopes every query to the pair, and time is in the pair's zone (pair setting `timezone`, default `TIMEZONE`). `Registry` holds shared operations: create a pair, join by code, `/leave`, list complete pairs. `access.py` resolves the sender's pair and injects `app` and `user` into handlers (both `None` when the sender is not in a pair; then only `/start`, `/help` and `pair:*` buttons pass). `AccessMiddleware` is attached only to `message` and `callback_query` (it also drops groups and channels): a handler for any other update type gets no `app`/`user` and no access check. The scheduler walks all complete pairs on every tick. **Every new query on pair data must filter by `pair_id`.**
- Everything user-facing is a feature in `bot/features/`: a module with a `Feature` object (router, jobs, commands, `card`, `on_exchange` hook) registered in `bot/features/__init__.py`. Registry order = router order (the first matching handler takes the update) and the order of scheduler jobs (after the core job `daily.redeliver`); `fallback` is always last, `dev` is enabled only with `DEBUG=true`. `Feature.commands` reach the Telegram command menu through `set_my_commands` at startup — nothing else to register. A new feature = a new module + one registry line; touch the core only if the feature needs a new hook.
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

- **Photo bot.** The Railway service is connected to `MrBoomer1981/OurSpark` (public — no secrets in code); a push to `main` deploys. The root `Dockerfile` (python:3.12-slim) is detected automatically. There is no Railway config in the repo on purpose: `railway.toml` (Config as Code) is deprecated, and Infrastructure as Code (`.railway/railway.ts`) means an npm package, `railway config apply` instead of push and a risk of deleting the volume if it is not declared. The restart policy is Railway's default, `ON_FAILURE` up to 10 times.
- The photo bot's database is `bot.db` on the volume at `/app/data`. With a volume Railway never runs two copies at once — that is what prevents polling conflicts and double sends.
- Photo bot variables: `BOT_TOKEN`; `TIMEZONE` (time zone of new pairs, default `Europe/Moscow`); `NEW_PAIRS` (`false` closes registration of new pairs); `DEBUG` (also turns on loguru `diagnose`: variable values in tracebacks, which include names and photo captions — keep it off in production); `DB_PATH` (default `data/bot.db`). There are no invite codes in variables: every pair has its own code in `pairs`.
- Never run locally with the production token: the local copy and production would steal updates from each other (`Conflict` in logs).
- Deploys of the photo bot are fine any time, including during the day when a photo was already sent (see "Reliability on deploy" in `docs/photo-bot.md`). The photo bot stays on SQLite; Postgres is for the game only.
- **Game services** are set up in milestone 0 as described in `PLAN.md` §4: Root Directory and Watch Paths per service, Railway Postgres, only `web` public, a separate test bot until milestone 6.
