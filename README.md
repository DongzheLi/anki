# Anki Prep

A personal spaced-repetition app for SWE-interview practice. Organise what you
study by category and tags, attach your solutions, and let SM-2 schedule when
to revisit each item.

```
category   leetcode, system design, AI agents, data engineering, …
  └─ item      "Container With Most Water" + tags like two pointers, dfs, …
```

Each practice logs how it felt (`Again / Hard / Good / Easy`) and how long it
took; the feeling drives the schedule, and the log powers the dashboard stats.

## Stack

- **Backend** — FastAPI + Python's stdlib `sqlite3`, in `server_py/app.py`.
- **Frontend** — React + Vite (`client/`), `react-markdown` + `highlight.js`
  for rendering code/markdown solutions.
- **DB** — SQLite at `server/anki.db` (created on first run).

The backend environment is managed with `uv`. Node is only used for the React
frontend build/dev server.

## Run

```bash
UV_CACHE_DIR=.uv-cache uv sync --project server_py
npm install            # root dev script helpers
npm --prefix client install

# ANKI_DEV_EMAIL is REQUIRED locally — see "Identity & per-user data" below.
# Without it the data API returns 401 and the deck shows empty.
ANKI_DEV_EMAIL=you@example.com npm run dev   # FastAPI on :8000, Vite on :5173 (proxies /api)
```

Open http://localhost:5173.

For a single-process production-style run:

```bash
npm run build                                 # builds client into client/dist
ANKI_DEV_EMAIL=you@example.com npm start      # FastAPI serves API + built client on :8000
```

> The run scripts use `uv run python -m uvicorn …` rather than `uv run uvicorn`.
> The bare console-script form fails on some machines with
> `Failed to spawn: uvicorn`; the `python -m` form is equivalent and works
> everywhere, so the npm scripts and `make server-py` all use it.

## Identity & per-user data

Every item is owned by a user (`items.user_email`), and the API scopes reads and
writes to the caller's identity:

- **Production** identity comes from Cloudflare Access, which authenticates at
  the edge and injects a trusted `Cf-Access-Authenticated-User-Email` header.
  The app only reads that header — it does no auth itself.
- **Locally** there is no Access in front, so the server falls back to the
  `ANKI_DEV_EMAIL` env var. It's required for any data endpoint; unset means 401.
- Display names are mapped from email in `DISPLAY_NAMES` (`server_py/app.py`).

Scoping rules a feature author must respect:

- Reads (`/api/items`, `/api/due`, `/api/stats`, `/api/taxonomy`) default to the
  caller's own deck. `/api/items?user=a@x,b@y` widens the view to other people's
  items — **read-only sharing** ("see what I'm learning"), listed by `/api/users`.
- Writes (create / edit / delete / practice) are **owner-only**; acting on
  someone else's item returns 403.

So any new endpoint that touches items must filter by `user_email` (use
`current_email(request)`), or it will leak data across users.

## Using it

1. Add an **item** with a category and tags.
2. Type or select existing tags such as `two pointers`, `dfs`, or `tree`.
3. Add a title plus your solution — paste code/markdown or upload a
   file (`.py`, `.md`, …); the format and language are inferred from the
   extension.
4. Open an item to **practice**: read the title, solve it locally, **Reveal
   solution** to check, then grade how it felt. The grade reschedules the item.
5. **Study** (top nav) walks everything due today, one item at a time.
6. The **stats strip** shows cards due, reviews done today, and your streak;
   each item row shows times practiced, when, last feeling, and last time taken.

## Scheduling notes

An Anki-flavoured SM-2 (`schedule()` in `server_py/app.py`): four grades instead
of the raw 0–5 quality scale, **no sub-day learning steps** (a failed/new card
lands on a day-scale interval immediately), so every interval is a whole number
of days. A brand-new item (`due_date IS NULL`) counts as due so new material
surfaces in the queue.
