# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

- **Rebuild in progress.** The project is being rebuilt into «Воронье гнездо»: an asynchronous game in which a couple grows a shared pet. One web app runs as a Telegram Mini App and as a PWA, backed by the services `web`, `api`, `bot` and Railway Postgres. `PLAN.md` is the rebuild plan and the source of truth (decisions, rules, schema, milestones). The product brief is `voronye_gnezdo_mvp_spec.md`; `PLAN.md` wins where they differ.
- **Milestones 0–4 are deployed and checked (2026-10-29)** with the test bot @Ushousebot, whose Main Mini App is `https://our-home.up.railway.app`. Milestones 2–4 were pushed during a Railway outage and deployed by hand later (`railway redeploy --from-source`). **Now: milestone 5** (`PLAN.md` §5, approved 2026-10-29 with the recommended options: free asset packs, manual `pg_dump` backups, the in-app survey): 5.1 the pixel-gothic theme (done, checked by the user 2026-10-29) → 5.2 error states (pushed 2026-10-29) → 5.3 metrics → 5.4 the closed test on pair #1.

  **Visual design starts with milestone 5.1.** Until the functional milestones were done, screens stayed plain (the user, 2026-10-21). Commands and architecture notes for the new services are added here as milestones land.
- **The OurSpark photo bot stays in production, unchanged, until milestone 6** (repo `MrBoomer1981/OurSpark`, branch `main`; one bot serves many pairs; pair #1 is the user and their partner). Its code is `bot/`, `themes/` and the root `Dockerfile`; its spec is `docs/photo-bot.md`. Change it only to fix bugs.

## Working rules

- **Plan before code.** Every feature or change starts with a plan: update `PLAN.md` (`docs/photo-bot.md` for the photo bot) or describe the plan in chat, and wait for the user's go. Only then write code. Every rebuild milestone starts with a plan update.
- **No tests in the repo** — this also overrides brief §15.7. No test files, test dependencies or test steps in plans. Behaviour is checked by hand: the photo bot with `/dev`, the game with the debug panel (both only with `DEBUG=true`). Throwaway verification scripts live outside the repository.
- **Push = production deploy.** A push to `main` redeploys every Railway service whose Watch Paths match the changed files: the photo bot watches its own files, and `api`, `web` and `bot` each watch `services/<name>/**`. A push that changes only docs redeploys nothing. Commit and push only when the user explicitly says so; after a push, watch the Railway deploy and check the startup log. For the photo bot: `База: применена миграция N` only when the deploy brings a new migration (expected, not an error), then `База: … · пар: … · участников: …` (counts must not drop — nothing was lost), `Темы: …`, `Фичи: … · новые пары: …`, `Планировщик: задач …`. For the game: `api: порт …`, `База: схема vN`, `Telegram: @… · новые пары: … · DEBUG: …` and `Контент: карточек N · web push: включён` (`api`; `выключен` means a VAPID variable is missing), `Бот: @… · Mini App: … · api: …` (`bot`).
- **Languages.** Talk to the user in Russian. `PLAN.md` is written in Russian (the user's request, 2026-10-19), as is `README.md`; the other technical docs (`CLAUDE.md`, `docs/`) are written in English. Code comments and docstrings stay in Russian — do not translate them.
- **User-facing texts** are Russian and live in one place per kind:
  - `bot/texts.py` — the photo bot;
  - `services/web/src/texts.ts` — the game UI;
  - `services/bot/app/texts.py` — the game bot;
  - `services/api/app/texts.py` — notifications (templates use only `<b>`: the relay strips it for web push);
  - `services/api/content/` — prompt cards and pet lines.

  No gendered verb forms for participants («прислал/прислала», «выбрал(а)» are not allowed). Names always stay in the nominative case because the bot cannot decline them («<b>Саша</b>: фото готово», not «фото от Саши»). Prompt cards follow the same rules.
- The user keeps extending the product — add features as modules (photo bot: feature modules; game: domain modules in `api`) instead of growing the core.

## Commands

Photo bot:

```bash
pip install -r requirements.txt
python -m bot              # needs .env (see .env.example) with the token of a SEPARATE test bot
railway logs --lines 100   # production logs (this folder is linked to OurSpark); without --lines it streams and never returns
```

Deploy = push to `main`; Railway builds the root `Dockerfile` for the photo bot. No linter, formatter or type checker is configured (no `pyproject.toml` or `ruff.toml`).

Game, locally (checks inside Telegram run on Railway with the test bot after a push):

```bash
docker compose up -d              # Postgres 18, the same major version as Railway's
# services/api: python3.12 -m venv .venv, pip install -r requirements.txt, cp .env.example .env
uvicorn app.main:app --reload     # api on :8000; /api/docs and the OpenAPI schema only with DEBUG=true
# services/web
npm install && npm run dev        # Vite; proxies /api to API_UPSTREAM (default localhost:8000)
npm run api:types                 # after api changes: src/api/schema.d.ts from the running api (DEBUG=true); commit it
npm run build                     # tsc for the app and for src/sw.ts, then vite build — the only type checks
# services/bot: venv and requirements as for api; .env with the game's TEST bot token
python -m app                     # never while the Railway `bot` polls the same token
# Railway
railway deployment list --service api      # did a push reach the service (SKIPPED: Watch Paths did not match)
railway logs --service api --lines 100     # startup log; also web, bot
railway redeploy --service api --from-source --yes   # deploy the latest main by hand when a push was not picked up
```

Without `BOT_TOKEN` the api starts only with `DEBUG=true`: no Telegram, so the UI is used in a desktop browser through the debug login (stub users).

## Game architecture (target — details in `PLAN.md` §3)

- **Services by runtime role, not by domain:**
  - `web` — React Mini App and PWA from one build; Caddy serves it and proxies `/api`;
  - `api` — FastAPI: the whole game, auth, the outbox relay;
  - `bot` — aiogram: `/start`, the menu button, confirmation of PWA logins;
  - Railway Postgres.

  Only `web` is public.
- **Domains live inside `api`** as modules (`pairs`, `prompts`, `pet`, `rewards`, `chronicle`). Each owns its tables; other modules call its functions, never its SQL. `game/reveal.py` is the main cross-domain step and runs in one transaction; a purchase (`pet.buy`) also spends sparks and unlocks the item in one transaction. Do not split domains into separate services without a plan.
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

What already exists (milestones 0–4):

- **Layers in `api`:** `http/` (routes, models, auth) → `game/` (rules) → `store/` (SQL). `GET /api/me` and every route that changes something return `Me`, built in one place (`http/views.py`), and `web` replaces its state with it; a new field goes into `http/models.py` and `views.py`, then `npm run api:types`. Rule violations come back as 409 with `{"detail": "<code>"}`; `web` turns codes into texts through `texts.errors`, so a new code needs a line there (otherwise the generic error is shown).
- **Auth** (`services/api/app/http/deps.py`) accepts three schemes:
  - `tma <initData>` — checked with `BOT_TOKEN`, at most a day old;
  - `Bearer <token>` — a PWA session; only its sha256 is stored;
  - `debug <negative id>` — only with `DEBUG`. Telegram ids are never negative, so a real person cannot be impersonated.

  PWA login: `POST /api/auth/login` → `t.me/<bot>?start=login_<nonce>` → the bot asks, then calls `POST /api/internal/login/confirm` with `X-Internal-Secret` → the PWA polls `POST /api/auth/login/exchange`. Caddy answers 404 to `/api/internal/*` from outside.
- **Pairs** (`game/pairs.py`): locks are taken in one order, the pair row first and then the user row. Joining one's own pair again is not an error. The pet row and the `partner_joined` notification are written in the transaction that completes the pair.
- **Outbox:** `notify.enqueue` writes into the caller's transaction with a unique key. `notify/relay.py` claims due rows every 2 s (`FOR UPDATE SKIP LOCKED`) and sends them (web push first, otherwise the bot; see **Channels**). Network errors are retried with backoff; on 403 or «chat not found» it sets `users.tg_reachable = false` and does not retry. A claim older than 2 minutes is taken again, so delivery is at-least-once. Rows for stub users (negative ids) are just marked sent. A new kind needs a constant in `app/notify/__init__.py`, a template in `app/texts.py` and an entry in `relay.TEMPLATES` (`render` fills only `{name}`); a kind without a template is marked failed, not retried.
- **Content** lives in `services/api/content/*.yaml` and is loaded and validated at startup (`app/content`): a broken file stops `api` from starting instead of failing for a pair later.
  - `prompts.yaml` holds the cards; each has a kind and a theme, and an option may carry a chronicle line for when both partners pick it. Kinds:
    - `light` — an option about oneself;
    - `closeness` — free text with no options, and it never shifts traits;
    - `guess` — one's own option plus a prediction of the partner's;
    - `choice` — an option for the pair, and every option needs a trait.

    Their shares among assigned prompts are `KINDS` in `app/content`.
  - `themes.yaml` holds the themes and their relics. The loader rejects a theme with fewer than three cards, because its relic could never be earned.
  - `pet.yaml` holds the stages, the trait levels (habit text plus a Nest line), the cosmetic slots and the items.
  - `lines.yaml` holds the pet's lines (reactions without a trait and reveal lines per kind) and the chronicle templates.

  All keys are permanent; texts and numbers may change. A YAML string that contains `: ` must be quoted, otherwise it is read as a mapping (the loader rejects that).
- **Prompt of the day** (`game/prompts.py`):
  - `GET /api/me` assigns it. A pair has one active session; the next one is assigned only on a later pair-day than the reveal (`completed_on`).
  - The card is picked by kind share first, among kinds with uncompleted cards, then at random within the kind; cards shown to the pair that day are skipped.
  - The state is derived (`Today.state`), never stored.
  - The mutual rule lives only in `Today.partner_answer`. It covers the option, the text and the prediction.
  - An answer is checked against the card's kind (`_check`); a prediction is written together with one's own answer and never changes.
  - Answers lock the session row, so exactly one of two simultaneous answers sees the partner's and sends «результат готов».
  - «Другой вопрос» (`POST /api/prompt/change`) works only while nobody has answered, `CHANGES_PER_DAY` times per pair-day. It locks the same row and replaces the session with a new id, so an answer sent to the old card gets `prompt_changed` instead of landing on the new one. Every shown card goes to `prompt_log`.
- **Reveal** (`game/reveal.py`) is the main cross-domain transaction. The session row is locked and `completed_at` claimed; the +10 sparks, the trait shifts and the snapshot in `prompt_sessions.result` happen once; each viewer's `result_seen_at` is set.
- **Rewards:** `reward_ledger` with unique event keys (`answer:<session>:<user>`, `reveal:<session>`, `buy:<pair>:<item>` for spending); the balance is the sum, and "earned" is the sum of positive rows only. Amounts live in `game/rewards.py` and are sent to `web` (`answer_sparks`), never hard-coded there. Traits are columns of `pets`, changed only under the reveal claim and never down.
- **Progression** (`game/pet.py`) is checked only inside the reveal transaction:
  - stages open by earned sparks, so spending never slows growth;
  - habits open at trait thresholds;
  - a relic comes with the third completed card of a theme;
  - chronicle entries are written for these events and for a matching choice.

  Everything opened is a row in `unlocks` (`stage:`, `habit:`, `item:`, `relic:` keys, unique per pair). The current stage is the last one unlocked, so raising thresholds later never shrinks a pet. The reveal snapshot gets `news`, so both partners see the same.
- **Cosmetics:**
  - `POST /api/pet/buy` locks the pet row, checks the requirement (a stage or a trait level) and the balance, writes the negative ledger row, unlocks the item and wears it.
  - `POST /api/pet/wear` puts an owned item on or takes it off (`pets.equipped`, one item per slot).
  - Try-on exists only in `web`.
- **Chronicle** (`game/chronicle.py`): entries are unique per `(pair_id, event_key)` and store a kind plus content keys; the text is rendered from content when shown. The first entry, `hatch`, is written in the transaction that completes the pair (migration 3 added it for existing pairs). `GET /api/chronicle` serves it apart from `/me`, which only carries bounded data.
- **Pair clock** (`game/clock.py`): the day is the date in the pair's zone (`TIMEZONE`) plus a `DEBUG` day offset stored in `pair_settings` («следующий день» in the debug panel).
- **Debug panel** (`src/debug/DebugPanel.tsx` in `web`, shown when `GET /api/config` says `debug`; the `/api/debug/*` routes are mounted only with `DEBUG`): a stub partner joins (id `-(1000 + pair_id)`), the partner answers at random, next day, +100 sparks, reset today's prompt, reset the pair's progress (the `hatch` entry stays). It answers for a real partner too, since the stand is a test one. Outside Telegram it also logs in as stub users -1 and -2 and switches between them.
- **Channels:** the relay tries web push first (`notify/push.py`, VAPID; 404/410 disables a subscription) and falls back to the bot. `POST /api/notifications/push` accepts only endpoints of browser push services. A `tma` request with `allows_write_to_pm` marks the Telegram channel as working.
- **`web` client:** `src/api/client.ts` adds the auth header, and `call()` returns `{ok, data}` or `{ok: false, status, code}`. Screen actions that return `Me` go through `api/useAction`: it tracks which action is pending (its button gets `aria-busy` and running dots), shows the error next to it, sends 401 to login and treats `prompt_changed`, `prompt_answered` and `not_ready` as a stale screen — `App` refreshes `/me` and shows a `ui/Toast`. A failed background refresh keeps the shown Nest and toasts instead of switching to the offline screen; render crashes end in `ui/ErrorBoundary`. The PWA keeps a pending login (`credentials.pendingLogin`, 10 minutes) so a reload by iOS while the user confirms in Telegram resumes the same nonce. Screens: `Nest`, then `Message`, `Result`, `Pet` and `Chronicle` as secondary screens with the Telegram back button (`ui/BackLink`). `pet/PetView` draws the pet in layers from the manifest (`src/assets.ts`; how to replace art — `docs/assets.md`): `pet.<stage>` (`pet.<stage>.cheer` while it cheers after one's own answer and on the result screen), then each worn item as `item.<key>` or, until it has its own art, the placeholder `slot.<slot>`, ordered by `z`. Frames lie side by side in one image and are animated in CSS (`steps()`; still with `prefers-reduced-motion`). Icons (`ui/Icon`, `icon.<name>`) and the Nest background (`scene.nest`) come from the same manifest. The pixel-gothic theme is tokens in `index.css`; frames are `box-shadow` steps of `--px`, and the Nest scene and the message parchment get the ornate gold frame (`.gilded`, `border-image`); the pixel font (Press Start 2P) is only for headings, the stage and sparks, at 16 or 24 px, and buttons and body text use the system font. The service worker is `src/sw.ts` (vite-plugin-pwa `injectManifest`, its own `tsconfig.sw.json`): precache plus the push and notification-click handlers. The service worker is registered only in PWA mode, never inside Telegram. Vite emits the bundle to `/static/` (immutable in Caddy). `public/assets/` holds game art, which is revalidated and referenced only through `src/assets.ts`.
- **Every `api` route starts with `/api`.** Caddy (`services/web/Caddyfile`) proxies `/api/*` without stripping the prefix, and Vite does the same in dev. `GET /api/health` also checks the database; it is the Railway healthcheck.
- **`python -m app` (`services/api/app/__main__.py`) binds one dual-stack socket** on `PORT` (8000 locally and on Railway). `uvicorn --host ::` would listen on IPv6 only, and `--host 0.0.0.0` on IPv4 only, while Railway's private network is IPv6-only in legacy environments. Keep the socket.
- **Migrations:** `MIGRATIONS` in `services/api/app/store/migrations.py`; the version is the position in the list (from 1), tracked in `schema_migrations`. They are applied at startup in one transaction under a Postgres advisory lock, so two `api` copies during a deploy apply each migration once.
- **Logs:** loguru writes INFO and below to stdout and WARNING and above to stderr, because Railway shows everything on stderr as an error. uvicorn logs warnings only, with no access log.
- **`web` mode:** `src/platform/` picks the mode at startup: Telegram launch params mean Telegram mode (tma.js, `@tma.js/sdk-react`), anything else is PWA mode. Caddy serves `/static/*` (the hashed Vite bundle) as immutable and everything else, including the art in `/assets/*`, as `no-cache`, so replaced art shows up at the same path.

## Photo bot architecture (production until milestone 6)

A Telegram bot for couples: morning theme, daytime photos, evening exchange. Python 3.12, aiogram 3 in polling mode, SQLite via aiosqlite on a Railway Volume, pydantic-settings, loguru. One process: polling and the scheduler share one asyncio loop.

**Core, pairs and features.**
- Core modules: `bot/daily.py` (day logic), `bot/repo.py` (all SQL), `bot/scheduler.py`, `bot/app.py`, `bot/access.py`, `bot/ui.py`.
- **Pairs.** `Core` is the shared context (bot, connection, themes, features, clock `core.clock`). `App` is one pair's context with the interface the day logic and features use (`app.repo`, `app.today()`, `app.invite_link`, …): `Repo(conn, pair_id)` scopes every query to the pair, and time is in the pair's zone (pair setting `timezone`, default `TIMEZONE`). `Registry` holds shared operations: create a pair, join by code, `/leave`, list complete pairs. `access.py` resolves the sender's pair and injects `app` and `user` into handlers (both `None` when the sender is not in a pair; then only `/start`, `/help` and `pair:*` buttons pass). `AccessMiddleware` is attached only to `message` and `callback_query` (it also drops groups and channels): a handler for any other update type gets no `app`/`user` and no access check. The scheduler walks all complete pairs on every tick. **Every new query on pair data must filter by `pair_id`.**
- Everything user-facing is a feature in `bot/features/`: a module with a `Feature` object (`bot/feature.py` defines it and the hook signatures: router, jobs, commands, `card`, `on_exchange`) registered in `bot/features/__init__.py`. Registry order = router order (the first matching handler takes the update) and the order of scheduler jobs (after the core job `daily.redeliver`); `fallback` is always last, `dev` is enabled only with `DEBUG=true`. `Feature.commands` reach the Telegram command menu through `set_my_commands` at startup — nothing else to register. A new feature = a new module + one registry line; touch the core only if the feature needs a new hook.
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
- **Game services** live in the photo bot's Railway project (`adaptable-kindness`): `api`, `web`, `bot` and `Postgres` (template image `postgres-ssl:18`), all in EU West (`europe-west4-drams3a`). Each has Root Directory `services/<name>` and Watch Paths `/services/<name>/**`. Only `web` is public, at `our-home.up.railway.app`. A separate test bot is used until milestone 6.
- **Railway gotchas, learned while setting up:**
  - The workspace's default region is Singapore, and the Postgres template ignores a region in its config. Pin a new service with `railway service scale --service <name> europe-west4-drams3a=1 asia-southeast1-eqsg3a=0`, or with `multiRegionConfig` in `serviceInstanceUpdate` before a source is connected.
  - Create a repo service empty (`railway add --service <name>`), set Root Directory and Watch Paths, then connect the repo. Otherwise its first build uses the root `Dockerfile`, which builds the photo bot.
  - `railway add` relinks this folder to the new service, so run `railway service link OurSpark` afterwards.
  - Reference variables (`${{api.RAILWAY_PRIVATE_DOMAIN}}`) resolve at deploy time. A service deployed together with the one it references can get an empty value, as `web`'s `API_UPSTREAM` did (Caddy dialled `:8000`); redeploy it once.
  - Backup schedules need the Pro plan. The project is on Hobby, so neither the game's Postgres nor the photo bot's volume has scheduled backups.
- Game variables are listed in `PLAN.md` §4. Set on Railway as of milestone 4 (checked 2026-10-29):
  - `api`: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (milestone 2; without all three web push is off), `DATABASE_URL` (a reference to the Postgres variable), `PORT=8000`, `BOT_TOKEN` (a reference, `${{bot.BOT_TOKEN}}`: the token is pasted once, into `bot`), `INTERNAL_SECRET`, `DEBUG=true` while only the test bot exists;
  - `web`: `API_UPSTREAM`;
  - `bot`: `BOT_TOKEN`, `WEB_APP_URL`, `API_URL`, and `INTERNAL_SECRET` as a reference to `api`'s.
- **The photo bot is isolated from the game:** its Watch Paths cover only its own files (`bot/`, `themes/`, `Dockerfile`, `.dockerignore`, `requirements.txt`; set 2026-10-21), and the root `.dockerignore` keeps `services/` and `docs/` out of its image.
