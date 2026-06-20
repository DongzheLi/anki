import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from fastapi import HTTPException
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
    category_id     INTEGER REFERENCES categories(id)
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


def init_db():
    global DB_READY
    if DB_READY:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
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
def items():
    today = date.today().isoformat()
    with db() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT i.id, i.title, i.source, i.link, i.content_format, i.language,
                       i.due_date, i.interval, i.repetitions,
                       (i.due_date IS NULL OR i.due_date <= :today) AS is_due,
                       i.category_id AS category_id, c.name AS category_name,
                       (SELECT COUNT(*) FROM practices p WHERE p.item_id = i.id) AS practice_count,
                       (SELECT MAX(practiced_at) FROM practices p WHERE p.item_id = i.id) AS last_practiced,
                       (SELECT feeling FROM practices p WHERE p.item_id = i.id
                         ORDER BY practiced_at DESC LIMIT 1) AS last_feeling
                  FROM items i
                  JOIN categories c ON c.id = i.category_id
                 ORDER BY c.name, i.title
                """,
                {"today": today},
            ).fetchall()
        )
        hydrate_labels(conn, rows)
    for row in rows:
        row["is_due"] = bool(row["is_due"])
    return rows


@app.post("/api/items")
def create_item(payload: ItemIn):
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
            INSERT INTO items (topic_id, category_id, title, description, link, source, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic_id,
                category_id,
                payload.title.strip(),
                payload.description or "",
                payload.link.strip() if payload.link else None,
                payload.source.strip() if payload.source else None,
                ", ".join(label_names) if label_names else None,
            ),
        )
        item_id = cur.lastrowid
        write_labels(conn, item_id, label_names)
        write_solutions(conn, item_id, payload.solutions)
        conn.commit()
    return {"id": item_id}


@app.patch("/api/items/{item_id}")
def update_item(item_id: int, payload: ItemIn):
    with db() as conn:
        existing = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="not found")
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
def delete_item(item_id: int):
    with db() as conn:
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
    return {"ok": True}


@app.get("/api/taxonomy")
def taxonomy():
    with db() as conn:
        categories = [row["name"] for row in conn.execute("SELECT name FROM categories ORDER BY name").fetchall()]
        labels = [row["name"] for row in conn.execute("SELECT name FROM labels ORDER BY name").fetchall()]
    return {"categories": categories, "labels": labels}


@app.get("/api/items/{item_id}")
def item(item_id: int):
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
def due():
    today = date.today().isoformat()
    with db() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT i.id, i.title, i.content_format, i.due_date, i.interval,
                       c.name AS category_name
                  FROM items i
                  JOIN categories c ON c.id = i.category_id
                 WHERE i.due_date IS NULL OR i.due_date <= :today
                 ORDER BY (i.due_date IS NULL) DESC, i.due_date ASC, i.id
                """,
                {"today": today},
            ).fetchall()
        )
        hydrate_labels(conn, rows)
    return rows


@app.get("/api/stats")
def stats():
    today = date.today().isoformat()
    with db() as conn:
        total_items = conn.execute("SELECT COUNT(*) n FROM items").fetchone()["n"]
        due_count = conn.execute(
            "SELECT COUNT(*) n FROM items WHERE due_date IS NULL OR due_date <= ?",
            (today,),
        ).fetchone()["n"]
        reviews_today = conn.execute(
            "SELECT COUNT(*) n FROM practices WHERE date(practiced_at) = ?",
            (today,),
        ).fetchone()["n"]
        days = [
            row["d"]
            for row in conn.execute("SELECT DISTINCT date(practiced_at) d FROM practices ORDER BY d DESC").fetchall()
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
def practice(item_id: int, payload: PracticeIn):
    if payload.feeling not in {"again", "hard", "good", "easy"}:
        raise HTTPException(status_code=400, detail="invalid feeling")
    with db() as conn:
        item_row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not item_row:
            raise HTTPException(status_code=404, detail="not found")
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
