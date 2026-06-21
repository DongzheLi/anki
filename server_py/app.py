import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("ANKI_DB_PATH", ROOT / "server" / "anki.db"))
CLIENT_DIST = ROOT / "client" / "dist"

app = FastAPI()
DB_READY = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    position   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id        INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    content_format  TEXT NOT NULL DEFAULT 'markdown',
    language        TEXT,
    source_filename TEXT,
    ease_factor     REAL    NOT NULL DEFAULT 2.5,
    interval        INTEGER NOT NULL DEFAULT 0,
    repetitions     INTEGER NOT NULL DEFAULT 0,
    due_date        TEXT,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description     TEXT NOT NULL DEFAULT '',
    link            TEXT,
    source          TEXT,
    tags            TEXT,
    category_id     INTEGER REFERENCES categories(id),
    user_email      TEXT
);
CREATE TABLE IF NOT EXISTS practices (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id            INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    practiced_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    feeling            TEXT NOT NULL,
    time_taken_seconds INTEGER,
    notes              TEXT,
    prev_interval      INTEGER,
    new_interval       INTEGER,
    prev_ease          REAL,
    new_ease           REAL
);
CREATE TABLE IF NOT EXISTS solutions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    format          TEXT NOT NULL DEFAULT 'code',
    language        TEXT,
    content         TEXT NOT NULL DEFAULT '',
    source_filename TEXT,
    position        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS labels (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS item_labels (
    item_id  INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    label_id INTEGER NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, label_id)
);
CREATE INDEX IF NOT EXISTS idx_topics_category ON topics(category_id);
CREATE INDEX IF NOT EXISTS idx_items_topic ON items(topic_id);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category_id);
CREATE INDEX IF NOT EXISTS idx_items_user ON items(user_email);
CREATE INDEX IF NOT EXISTS idx_practices_item ON practices(item_id);
CREATE INDEX IF NOT EXISTS idx_solutions_item ON solutions(item_id);
CREATE INDEX IF NOT EXISTS idx_item_labels_label ON item_labels(label_id);
"""


class SolutionIn(BaseModel):
    format: str = "code"
    language: Optional[str] = None
    content: str = ""
    source_filename: Optional[str] = None


class ItemIn(BaseModel):
    category: Optional[str] = None
    labels: Optional[list[str]] = None
    topic: Optional[str] = None
    tags: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    link: Optional[str] = None
    source: Optional[str] = None
    solutions: Optional[list[SolutionIn]] = None


class PracticeIn(BaseModel):
    feeling: str
    time_taken_seconds: Optional[int] = None
    notes: Optional[str] = None


@app.get("/api/health")
def health():
    return {"ok": True}


# Real display names, keyed by the Cloudflare Access email (the stable identity).
# Unknown emails fall back to the email's local-part, so anyone else in the
# Access policy still gets a sensible name.
DISPLAY_NAMES = {
    "dongzhewei37@gmail.com": "魏东哲",
    "zhangj199408@gmail.com": "张静",
}


def display_name(email: str) -> str:
    if email in DISPLAY_NAMES:
        return DISPLAY_NAMES[email]
    return email.split("@", 1)[0] if email else "guest"


def resolve_email(request: Request) -> str:
    """The authenticated email from Cloudflare Access. Locally there is no Access
    in front, so fall back to ANKI_DEV_EMAIL to give dev an identity."""
    return (
        request.headers.get("Cf-Access-Authenticated-User-Email")
        or request.headers.get("X-Forwarded-Email")
        or os.environ.get("ANKI_DEV_EMAIL", "")
    )


def current_email(request: Request) -> str:
    """Same as resolve_email but required — data endpoints must know who you are."""
    email = resolve_email(request)
    if not email:
        raise HTTPException(status_code=401, detail="no authenticated user")
    return email


@app.get("/api/me")
def me(request: Request):
    email = resolve_email(request)
    return {"email": email, "username": display_name(email)}


@app.get("/api/users")
def users(request: Request):
    """Distinct item owners, for the dashboard's user filter. Always includes you
    so the filter has a 'me' option even before you've added anything."""
    me_email = current_email(request)
    with db() as conn:
        owners = [
            row["user_email"]
            for row in conn.execute(
                "SELECT DISTINCT user_email FROM items "
                "WHERE user_email IS NOT NULL AND user_email != '' ORDER BY user_email"
            ).fetchall()
        ]
    if me_email not in owners:
        owners.insert(0, me_email)
    return {
        "me": me_email,
        "users": [{"email": e, "name": display_name(e)} for e in owners],
    }


def init_db():
    global DB_READY
    if DB_READY:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        # Migration: DBs created before per-user ownership won't get the new
        # column from CREATE TABLE IF NOT EXISTS, so add it explicitly. Existing
        # rows stay NULL until backfilled to an owner (see ADDING ownership /
        # deploy notes); a NULL-owner item belongs to nobody and is hidden.
        cols = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
        if "user_email" not in cols:
            conn.execute("ALTER TABLE items ADD COLUMN user_email TEXT")
    DB_READY = True


def db():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rows_to_dicts(rows):
    return [dict(row) for row in rows]


def labels_by_item(conn, item_ids):
    if not item_ids:
        return {}
    placeholders = ",".join("?" for _ in item_ids)
    rows = conn.execute(
        f"""
        SELECT il.item_id, l.name
          FROM item_labels il
          JOIN labels l ON l.id = il.label_id
         WHERE il.item_id IN ({placeholders})
         ORDER BY l.name
        """,
        item_ids,
    ).fetchall()
    out = {}
    for row in rows:
        out.setdefault(row["item_id"], []).append(row["name"])
    return out


def hydrate_labels(conn, rows):
    by_item = labels_by_item(conn, [row["id"] for row in rows])
    for row in rows:
        labels = by_item.get(row["id"], [])
        row["labels"] = labels
        row["tags"] = ", ".join(labels) if labels else None
        row["topic_name"] = labels[0] if labels else ""
    return rows


def normalize_labels(labels):
    if labels is None:
        raw = []
    elif isinstance(labels, str):
        raw = labels.split(",")
    else:
        raw = labels
    seen = set()
    out = []
    for label in raw:
        name = str(label or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def find_or_create_category(conn, name):
    clean = name.strip()
    row = conn.execute("SELECT id FROM categories WHERE name = ?", (clean,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (clean,))
    return cur.lastrowid


def find_or_create_topic(conn, category_id, name):
    clean = name.strip()
    row = conn.execute(
        "SELECT id FROM topics WHERE category_id = ? AND name = ?",
        (category_id, clean),
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO topics (category_id, name) VALUES (?, ?)", (category_id, clean))
    return cur.lastrowid


def find_or_create_label(conn, name):
    clean = name.strip()
    row = conn.execute("SELECT id FROM labels WHERE lower(name) = lower(?)", (clean,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO labels (name) VALUES (?)", (clean,))
    return cur.lastrowid


def legacy_topic_id(conn, category_id, labels):
    return find_or_create_topic(conn, category_id, labels[0] if labels else "uncategorized")


def write_labels(conn, item_id, labels):
    conn.execute("DELETE FROM item_labels WHERE item_id = ?", (item_id,))
    for label in normalize_labels(labels):
        conn.execute(
            "INSERT OR IGNORE INTO item_labels (item_id, label_id) VALUES (?, ?)",
            (item_id, find_or_create_label(conn, label)),
        )


def write_solutions(conn, item_id, solutions):
    conn.execute("DELETE FROM solutions WHERE item_id = ?", (item_id,))
    if solutions is None:
        return
    for i, solution in enumerate(solutions):
        content = solution.content or ""
        if not content.strip():
            continue
        fmt = solution.format if solution.format in {"code", "markdown", "text"} else "code"
        conn.execute(
            """
            INSERT INTO solutions (item_id, format, language, content, source_filename, position)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                fmt,
                solution.language if fmt == "code" else None,
                content,
                solution.source_filename,
                i,
            ),
        )


def schedule(item, grade):
    ease = item["ease_factor"] or 2.5
    interval = item["interval"] or 0
    reps = item["repetitions"] or 0

    if grade == "again":
        reps = 0
        interval = 1
        ease = max(1.3, ease - 0.2)
    else:
        if reps == 0:
            interval = 4 if grade == "easy" else 1
        elif reps == 1:
            interval = 7 if grade == "easy" else 6
        else:
            mult = 1.2 if grade == "hard" else ease * 1.3 if grade == "easy" else ease
            interval = max(1, round(interval * mult))
        if grade == "hard":
            ease = max(1.3, ease - 0.15)
        elif grade == "easy":
            ease += 0.15
        reps += 1

    due = date.today() + timedelta(days=interval)
    return {
        "ease_factor": ease,
        "interval": interval,
        "repetitions": reps,
        "due_date": due.isoformat(),
    }


def preview_intervals(item):
    return {grade: schedule(item, grade)["interval"] for grade in ["again", "hard", "good", "easy"]}


@app.get("/api/items")
def items(request: Request, user: Optional[str] = None):
    me = current_email(request)
    # Default to your own deck. An explicit ?user=a@x,b@y widens the view to
    # include other people's items (read-only sharing — "see what I'm learning").
    emails = [e.strip() for e in user.split(",") if e.strip()] if user else [me]
    today = date.today().isoformat()
    params: dict[str, Any] = {"today": today}
    keys = []
    for idx, email in enumerate(emails):
        params[f"u{idx}"] = email
        keys.append(f":u{idx}")
    in_clause = ",".join(keys) if keys else "NULL"
    with db() as conn:
        rows = rows_to_dicts(
            conn.execute(
                f"""
                SELECT i.id, i.title, i.source, i.link, i.content_format, i.language,
                       i.due_date, i.interval, i.repetitions, i.user_email,
                       (i.due_date IS NULL OR i.due_date <= :today) AS is_due,
                       i.category_id AS category_id, c.name AS category_name,
                       (SELECT COUNT(*) FROM practices p WHERE p.item_id = i.id) AS practice_count,
                       (SELECT MAX(practiced_at) FROM practices p WHERE p.item_id = i.id) AS last_practiced,
                       (SELECT feeling FROM practices p WHERE p.item_id = i.id
                         ORDER BY practiced_at DESC LIMIT 1) AS last_feeling
                  FROM items i
                  JOIN categories c ON c.id = i.category_id
                 WHERE i.user_email IN ({in_clause})
                 ORDER BY c.name, i.title
                """,
                params,
            ).fetchall()
        )
        hydrate_labels(conn, rows)
    for row in rows:
        row["is_due"] = bool(row["is_due"])
    return rows


@app.post("/api/items")
def create_item(request: Request, payload: ItemIn):
    me = current_email(request)
    if not payload.title or not payload.title.strip():
        raise HTTPException(status_code=400, detail="title required")
    if not payload.category or not payload.category.strip():
        raise HTTPException(status_code=400, detail="category required")

    label_names = normalize_labels(payload.labels if payload.labels is not None else [payload.topic, *normalize_labels(payload.tags)])
    with db() as conn:
        category_id = find_or_create_category(conn, payload.category)
        topic_id = legacy_topic_id(conn, category_id, label_names)
        cur = conn.execute(
            """
            INSERT INTO items (topic_id, category_id, title, description, link, source, tags, user_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic_id,
                category_id,
                payload.title.strip(),
                payload.description or "",
                payload.link.strip() if payload.link else None,
                payload.source.strip() if payload.source else None,
                ", ".join(label_names) if label_names else None,
                me,
            ),
        )
        item_id = cur.lastrowid
        write_labels(conn, item_id, label_names)
        write_solutions(conn, item_id, payload.solutions)
        conn.commit()
    return {"id": item_id}


@app.patch("/api/items/{item_id}")
def update_item(request: Request, item_id: int, payload: ItemIn):
    me = current_email(request)
    with db() as conn:
        existing = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="not found")
        # You can view others' items, but only the owner may edit them.
        if existing["user_email"] != me:
            raise HTTPException(status_code=403, detail="not your item")
        current_labels = labels_by_item(conn, [item_id]).get(item_id, [])
        next_labels = (
            normalize_labels(payload.labels)
            if payload.labels is not None
            else normalize_labels(payload.tags)
            if payload.tags is not None
            else current_labels
        )
        category_id = find_or_create_category(conn, payload.category) if payload.category and payload.category.strip() else existing["category_id"]
        topic_id = legacy_topic_id(conn, category_id, next_labels)
        conn.execute(
            """
            UPDATE items
               SET topic_id = ?, category_id = ?, title = ?, description = ?, link = ?,
                   source = ?, tags = ?, updated_at = datetime('now')
             WHERE id = ?
            """,
            (
                topic_id,
                category_id,
                payload.title.strip() if payload.title is not None else existing["title"],
                payload.description if payload.description is not None else existing["description"],
                payload.link.strip() if payload.link else None if payload.link is not None else existing["link"],
                payload.source.strip() if payload.source else None if payload.source is not None else existing["source"],
                ", ".join(next_labels) if next_labels else None,
                item_id,
            ),
        )
        if payload.labels is not None or payload.tags is not None:
            write_labels(conn, item_id, next_labels)
        if payload.solutions is not None:
            write_solutions(conn, item_id, payload.solutions)
        conn.commit()
    return {"ok": True}


@app.delete("/api/items/{item_id}")
def delete_item(request: Request, item_id: int):
    me = current_email(request)
    with db() as conn:
        row = conn.execute("SELECT user_email FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        if row["user_email"] != me:
            raise HTTPException(status_code=403, detail="not your item")
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
    return {"ok": True}


@app.get("/api/taxonomy")
def taxonomy(request: Request):
    # Autocomplete options for the editor — only the categories/labels you
    # actually use, so it doesn't leak another user's taxonomy.
    me = current_email(request)
    with db() as conn:
        categories = [
            row["name"]
            for row in conn.execute(
                "SELECT DISTINCT c.name FROM categories c "
                "JOIN items i ON i.category_id = c.id WHERE i.user_email = ? ORDER BY c.name",
                (me,),
            ).fetchall()
        ]
        labels = [
            row["name"]
            for row in conn.execute(
                "SELECT DISTINCT l.name FROM labels l "
                "JOIN item_labels il ON il.label_id = l.id "
                "JOIN items i ON i.id = il.item_id WHERE i.user_email = ? ORDER BY l.name",
                (me,),
            ).fetchall()
        ]
    return {"categories": categories, "labels": labels}


@app.get("/api/items/{item_id}")
def item(request: Request, item_id: int):
    current_email(request)  # require login; viewing is shared across users
    with db() as conn:
        row = conn.execute(
            """
            SELECT i.*, c.name AS category_name
              FROM items i
              JOIN categories c ON c.id = i.category_id
             WHERE i.id = ?
            """,
            (item_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        item_row = dict(row)
        hydrate_labels(conn, [item_row])
        item_row["solutions"] = rows_to_dicts(
            conn.execute("SELECT * FROM solutions WHERE item_id = ? ORDER BY position, id", (item_id,)).fetchall()
        )
        item_row["history"] = rows_to_dicts(
            conn.execute("SELECT * FROM practices WHERE item_id = ? ORDER BY practiced_at DESC", (item_id,)).fetchall()
        )
        item_row["intervals"] = preview_intervals(item_row)
    return item_row


@app.get("/api/due")
def due(request: Request):
    # Study is personal: only your own due items, never a shared deck.
    me = current_email(request)
    today = date.today().isoformat()
    with db() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT i.id, i.title, i.content_format, i.due_date, i.interval,
                       c.name AS category_name
                  FROM items i
                  JOIN categories c ON c.id = i.category_id
                 WHERE (i.due_date IS NULL OR i.due_date <= :today)
                   AND i.user_email = :me
                 ORDER BY (i.due_date IS NULL) DESC, i.due_date ASC, i.id
                """,
                {"today": today, "me": me},
            ).fetchall()
        )
        hydrate_labels(conn, rows)
    return rows


@app.get("/api/stats")
def stats(request: Request):
    # Stats are personal: counts and streak over your own deck only.
    me = current_email(request)
    today = date.today().isoformat()
    with db() as conn:
        total_items = conn.execute(
            "SELECT COUNT(*) n FROM items WHERE user_email = ?", (me,)
        ).fetchone()["n"]
        due_count = conn.execute(
            "SELECT COUNT(*) n FROM items WHERE (due_date IS NULL OR due_date <= ?) AND user_email = ?",
            (today, me),
        ).fetchone()["n"]
        reviews_today = conn.execute(
            "SELECT COUNT(*) n FROM practices p JOIN items i ON i.id = p.item_id "
            "WHERE date(p.practiced_at) = ? AND i.user_email = ?",
            (today, me),
        ).fetchone()["n"]
        days = [
            row["d"]
            for row in conn.execute(
                "SELECT DISTINCT date(p.practiced_at) d FROM practices p "
                "JOIN items i ON i.id = p.item_id WHERE i.user_email = ? ORDER BY d DESC",
                (me,),
            ).fetchall()
        ]

    streak = 0
    cursor = datetime.fromisoformat(today).date()
    if days and days[0] != today:
        cursor -= timedelta(days=1)
    while cursor.isoformat() in days:
        streak += 1
        cursor -= timedelta(days=1)

    return {
        "totalItems": total_items,
        "dueCount": due_count,
        "reviewsToday": reviews_today,
        "streak": streak,
    }


@app.post("/api/items/{item_id}/practice")
def practice(request: Request, item_id: int, payload: PracticeIn):
    me = current_email(request)
    if payload.feeling not in {"again", "hard", "good", "easy"}:
        raise HTTPException(status_code=400, detail="invalid feeling")
    with db() as conn:
        item_row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not item_row:
            raise HTTPException(status_code=404, detail="not found")
        # Practicing reschedules the item, so only the owner may practice it.
        if item_row["user_email"] != me:
            raise HTTPException(status_code=403, detail="not your item")
        item_dict: dict[str, Any] = dict(item_row)
        next_schedule = schedule(item_dict, payload.feeling)
        conn.execute(
            """
            INSERT INTO practices
              (item_id, feeling, time_taken_seconds, notes,
               prev_interval, new_interval, prev_ease, new_ease)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                payload.feeling,
                payload.time_taken_seconds,
                payload.notes,
                item_dict["interval"],
                next_schedule["interval"],
                item_dict["ease_factor"],
                next_schedule["ease_factor"],
            ),
        )
        conn.execute(
            """
            UPDATE items
               SET ease_factor = ?, interval = ?, repetitions = ?,
                   due_date = ?, updated_at = datetime('now')
             WHERE id = ?
            """,
            (
                next_schedule["ease_factor"],
                next_schedule["interval"],
                next_schedule["repetitions"],
                next_schedule["due_date"],
                item_id,
            ),
        )
        conn.commit()
    return {"ok": True, **next_schedule}


if CLIENT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=CLIENT_DIST / "assets"), name="assets")


@app.get("/{path:path}")
def client_app(path: str):
    index = CLIENT_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="client build not found")
