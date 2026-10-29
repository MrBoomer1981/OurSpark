# Closed-test metrics (brief §13)

The queries read the game's Postgres. Most metrics come from the game tables themselves; the `events` table (migration 5, `app/game/metrics.py`) adds what the game does not store: when someone opened the Nest (`open`, once per person per pair-day) and the Pet or Chronicle screen (`screen`, at most once a minute).

The subjective question «Игра помогла вам узнать друг друга или поговорить?» is not asked in the app: the author asks the pairs in person (decision of 2026-10-29).

No targets are set before there is a baseline (brief §13).

## How to run

```bash
railway ssh --service Postgres                       # a shell inside the database container, then: psql
railway ssh --service Postgres -- psql -c "<query>"  # one query; psql takes the connection from the container's PG* variables
```

The database has no public address and needs none. The queries are read-only.

## 1. Pairs where both partners completed the first prompt

```sql
WITH first AS (
  SELECT DISTINCT ON (pair_id) pair_id, id
  FROM prompt_sessions
  ORDER BY pair_id, assigned_at, id
), done AS (
  SELECT f.pair_id, (SELECT count(*) FROM answers a WHERE a.session_id = f.id) = 2 AS answered
  FROM first f
)
SELECT count(*) FILTER (WHERE answered) AS both_answered, count(*) AS pairs,
       round(100.0 * count(*) FILTER (WHERE answered) / nullif(count(*), 0), 1) AS percent
FROM done;
```

Only complete pairs get prompts, so every row is a real pair. A replaced card («Другой вопрос») is deleted, so the first prompt is the first one the pair kept.

## 2. Prompts completed by both

```sql
SELECT count(*) FILTER (WHERE n = 2) AS completed, count(*) AS assigned,
       round(100.0 * count(*) FILTER (WHERE n = 2) / nullif(count(*), 0), 1) AS percent
FROM (
  SELECT s.id, count(a.user_id) AS n
  FROM prompt_sessions s LEFT JOIN answers a ON a.session_id = s.id
  GROUP BY s.id
) t;
```

Today's prompts still wait for answers, so the share is a little lower on any given day.

## 3. Time between the partners' answers

```sql
SELECT count(*) AS prompts,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY gap) AS median,
       percentile_cont(0.75) WITHIN GROUP (ORDER BY gap) AS p75,
       max(gap) AS longest
FROM (
  SELECT max(created_at) - min(created_at) AS gap
  FROM answers GROUP BY session_id HAVING count(*) = 2
) t;
```

## 4. Pairs returning on day 7 and day 30

A pair returned on day N if either partner opened the Nest on the N-th pair-day after the pair was completed. Pairs younger than N days are not counted yet.

```sql
WITH start AS (
  SELECT p.id, (p.completed_at AT TIME ZONE coalesce(s.value, 'Europe/Moscow'))::date AS day
  FROM pairs p LEFT JOIN pair_settings s ON s.pair_id = p.id AND s.key = 'timezone'
  WHERE p.completed_at IS NOT NULL
), checked AS (
  SELECT n.n, EXISTS (
           SELECT 1 FROM events e
           WHERE e.pair_id = st.id AND e.kind = 'open' AND e.day = st.day + n.n
         ) AS came
  FROM start st CROSS JOIN (VALUES (7), (30)) AS n (n)
  WHERE st.day + n.n <= (now() AT TIME ZONE 'Europe/Moscow')::date
)
SELECT n AS day, count(*) FILTER (WHERE came) AS returned, count(*) AS pairs,
       round(100.0 * count(*) FILTER (WHERE came) / nullif(count(*), 0), 1) AS percent
FROM checked GROUP BY n ORDER BY n;
```

## 5. Opening the reaction and the pet after a reward

For every partner of every revealed prompt: did they open the result (`answers.result_seen_at`, set by «Открыть результат») and did they open the Pet screen later that pair-day?

```sql
WITH rewarded AS (
  SELECT a.user_id, s.completed_on, a.result_seen_at
  FROM prompt_sessions s JOIN answers a ON a.session_id = s.id
  WHERE s.completed_at IS NOT NULL
)
SELECT count(*) AS rewards,
       count(*) FILTER (WHERE result_seen_at IS NOT NULL) AS saw_result,
       round(100.0 * count(*) FILTER (WHERE result_seen_at IS NOT NULL) / nullif(count(*), 0), 1) AS result_percent,
       count(*) FILTER (WHERE EXISTS (
         SELECT 1 FROM events e
         WHERE e.user_id = r.user_id AND e.kind = 'screen' AND e.data ->> 'screen' = 'pet'
           AND e.day = r.completed_on AND e.created_at >= r.result_seen_at
       )) AS opened_pet,
       round(100.0 * count(*) FILTER (WHERE EXISTS (
         SELECT 1 FROM events e
         WHERE e.user_id = r.user_id AND e.kind = 'screen' AND e.data ->> 'screen' = 'pet'
           AND e.day = r.completed_on AND e.created_at >= r.result_seen_at
       )) / nullif(count(*), 0), 1) AS pet_percent
FROM rewarded r;
```

## 6. «Игра помогла вам узнать друг друга или поговорить?»

Asked in person, outside the app.
