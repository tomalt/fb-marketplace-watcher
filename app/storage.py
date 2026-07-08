import json
import sqlite3
from pathlib import Path

DATA_DIR = Path("/app/data")
DB_PATH = DATA_DIR / "watcher.db"
STATUS_PATH = DATA_DIR / "status.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_listings (
            search_name TEXT NOT NULL,
            listing_id TEXT NOT NULL,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (search_name, listing_id)
        )
    """)
    return conn


def load_seen():
    conn = connect()
    rows = conn.execute("SELECT search_name, listing_id FROM seen_listings").fetchall()
    conn.close()

    seen = {}
    for search_name, listing_id in rows:
        seen.setdefault(search_name, []).append(listing_id)

    first_run = len(rows) == 0
    return seen, first_run


def save_seen(seen):
    conn = connect()
    for search_name, listing_ids in seen.items():
        for listing_id in listing_ids:
            conn.execute(
                "INSERT OR IGNORE INTO seen_listings (search_name, listing_id) VALUES (?, ?)",
                (search_name, listing_id),
            )
    conn.commit()
    conn.close()


def save_status(status):
    STATUS_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")

def init_searches_from_config(searches):
    conn = connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            name TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            notify_first_run INTEGER DEFAULT 0,
            notify_telegram INTEGER DEFAULT 1,
            notify_email TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1
        )
    """)

    count = conn.execute("SELECT COUNT(*) FROM searches").fetchone()[0]

    if count == 0:
        for search in searches:
            notify = search.get("notify", {})
            conn.execute("""
                INSERT INTO searches
                (name, url, notify_first_run, notify_telegram, notify_email, enabled)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                search["name"],
                search["url"],
                int(search.get("notify_first_run", False)),
                int(notify.get("telegram", True)),
                ",".join(notify.get("email", [])),
                1,
            ))

    conn.commit()
    conn.close()


def load_searches():
    conn = connect()
    rows = conn.execute("""
        SELECT name, url, notify_first_run, notify_telegram, notify_email, enabled
        FROM searches
        WHERE enabled = 1
        ORDER BY name
    """).fetchall()
    conn.close()

    searches = []
    for name, url, notify_first_run, notify_telegram, notify_email, enabled in rows:
        emails = [x.strip() for x in notify_email.split(",") if x.strip()]
        searches.append({
            "name": name,
            "url": url,
            "notify_first_run": bool(notify_first_run),
            "notify": {
                "telegram": bool(notify_telegram),
                "email": emails,
            },
            "enabled": bool(enabled),
        })

    return searches
