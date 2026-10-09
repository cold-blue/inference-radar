from pathlib import Path
import sqlite3

from .config import ROOT

DB_PATH = ROOT / "data" / "radar.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Tolerate brief write contention from concurrent analyzer threads.
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db():
    conn = get_connection()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT,
        content TEXT,
        timestamp TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source, source_id)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS analyses (
        item_id INTEGER PRIMARY KEY,
        category TEXT,
        org TEXT,
        venue TEXT,
        topics TEXT,
        relevance INTEGER,
        impact INTEGER,
        novelty INTEGER,
        personal_interest REAL,
        priority REAL,
        summary TEXT,
        why_it_matters TEXT,
        technical_details TEXT,
        what_changed TEXT,
        implementation TEXT,
        hardware TEXT,
        related_projects TEXT,
        worth_deep_dive INTEGER DEFAULT 0,
        analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(item_id) REFERENCES items(id)
    )
    """)

    # Lightweight migration for databases created before these columns existed.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(analyses)")}
    for col in ("category", "org", "venue"):
        if col not in cols:
            conn.execute(f"ALTER TABLE analyses ADD COLUMN {col} TEXT")

    conn.commit()
    conn.close()


def insert_item(item):
    conn = get_connection()
    cur = conn.execute("""
        INSERT OR IGNORE INTO items
        (source, source_id, title, url, content, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        item["source"],
        item["source_id"],
        item["title"],
        item.get("url", ""),
        item.get("content", ""),
        item.get("timestamp", ""),
    ))
    conn.commit()
    inserted = cur.rowcount == 1
    conn.close()
    return inserted


def get_unanalyzed_items(limit=100):
    conn = get_connection()
    rows = conn.execute("""
        SELECT i.*
        FROM items i
        LEFT JOIN analyses a ON i.id = a.item_id
        WHERE a.item_id IS NULL
        ORDER BY i.timestamp DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def save_analysis(item_id, result):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO analyses
        (item_id, category, org, venue, topics, relevance, impact, novelty,
         personal_interest, priority, summary, why_it_matters,
         technical_details, what_changed, implementation, hardware,
         related_projects, worth_deep_dive)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item_id,
        result.get("category", ""),
        result.get("org", ""),
        result.get("venue", ""),
        ", ".join(result.get("topics", [])),
        int(result.get("relevance", 0)),
        int(result.get("impact", 0)),
        int(result.get("novelty", 0)),
        float(result.get("personal_interest", 1.0)),
        float(result.get("priority", 0.0)),
        result.get("summary", ""),
        result.get("why_it_matters", ""),
        result.get("technical_details", ""),
        result.get("what_changed", ""),
        result.get("implementation", ""),
        ", ".join(result.get("hardware", [])),
        ", ".join(result.get("related_projects", [])),
        int(bool(result.get("worth_deep_dive", False))),
    ))
    conn.commit()
    conn.close()


def get_report_items(min_priority=5, limit=20):
    conn = get_connection()
    rows = conn.execute("""
        SELECT i.*, a.*
        FROM items i
        JOIN analyses a ON i.id = a.item_id
        WHERE a.priority >= ?
        ORDER BY a.priority DESC, i.timestamp DESC
        LIMIT ?
    """, (min_priority, limit)).fetchall()
    conn.close()
    return rows
