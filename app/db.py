import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from app.config import DB_PATH, DEFAULT_PATH_TEMPLATE

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS media_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_type TEXT NOT NULL DEFAULT 'epub',
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    format TEXT NOT NULL,
    added_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS epub_metadata (
    media_item_id INTEGER PRIMARY KEY REFERENCES media_items(id) ON DELETE CASCADE,
    author TEXT NOT NULL DEFAULT '',
    series TEXT NOT NULL DEFAULT '',
    series_index TEXT NOT NULL DEFAULT '',
    isbn TEXT NOT NULL DEFAULT '',
    publisher TEXT NOT NULL DEFAULT '',
    pub_date TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT '',
    cover_path TEXT NOT NULL DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS media_items_fts USING fts5(
    title, author, series, publisher, description, category, subject,
    tokenize='porter'
);
"""

DEFAULT_SETTINGS = {
    "organize_enabled": "0",
    "organize_copy_mode": "0",
    "path_template": DEFAULT_PATH_TEMPLATE,
}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate_add_status_column(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(media_items)")}
    if "status" not in columns:
        conn.execute("ALTER TABLE media_items ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(SCHEMA)
        _migrate_add_status_column(conn)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_items_status ON media_items(status)")
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )


def reset_library(conn: sqlite3.Connection) -> None:
    """Wipe every catalog record (media items + epub metadata + search
    index) and reset the id counter. Files on disk (inbox, library,
    covers) are left in place."""
    conn.execute("DELETE FROM media_items_fts")
    conn.execute("DELETE FROM media_items")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'media_items'")


def reset_settings(conn: sqlite3.Connection) -> None:
    """Reset all settings to their defaults."""
    conn.execute("DELETE FROM settings")
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))


def get_setting(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sync_fts(conn: sqlite3.Connection, media_item_id: int) -> None:
    conn.execute("DELETE FROM media_items_fts WHERE rowid = ?", (media_item_id,))
    row = conn.execute(
        """
        SELECT m.title, m.description, m.category, m.subject,
               COALESCE(e.author, '') AS author, COALESCE(e.series, '') AS series,
               COALESCE(e.publisher, '') AS publisher
        FROM media_items m
        LEFT JOIN epub_metadata e ON e.media_item_id = m.id
        WHERE m.id = ?
        """,
        (media_item_id,),
    ).fetchone()
    if row is None:
        return
    conn.execute(
        """
        INSERT INTO media_items_fts (rowid, title, author, series, publisher, description, category, subject)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            media_item_id,
            row["title"],
            row["author"],
            row["series"],
            row["publisher"],
            row["description"],
            row["category"],
            row["subject"],
        ),
    )


def insert_media_item(
    conn: sqlite3.Connection,
    *,
    media_type: str,
    title: str,
    category: str,
    subject: str,
    description: str,
    file_path: str,
    file_hash: str,
    file_size: int,
    format: str,
    status: str,
) -> int:
    now = _now()
    cur = conn.execute(
        """
        INSERT INTO media_items
            (media_type, title, category, subject, description, file_path,
             file_hash, file_size, format, status, added_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (media_type, title, category, subject, description, file_path,
         file_hash, file_size, format, status, now, now),
    )
    media_item_id = cur.lastrowid
    _sync_fts(conn, media_item_id)
    return media_item_id


def upsert_epub_metadata(
    conn: sqlite3.Connection,
    media_item_id: int,
    *,
    author: str = "",
    series: str = "",
    series_index: str = "",
    isbn: str = "",
    publisher: str = "",
    pub_date: str = "",
    language: str = "",
    cover_path: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO epub_metadata
            (media_item_id, author, series, series_index, isbn, publisher, pub_date, language, cover_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(media_item_id) DO UPDATE SET
            author = excluded.author,
            series = excluded.series,
            series_index = excluded.series_index,
            isbn = excluded.isbn,
            publisher = excluded.publisher,
            pub_date = excluded.pub_date,
            language = excluded.language,
            cover_path = excluded.cover_path
        """,
        (media_item_id, author, series, series_index, isbn, publisher, pub_date, language, cover_path),
    )
    _sync_fts(conn, media_item_id)


def update_media_item_fields(conn: sqlite3.Connection, media_item_id: int, fields: dict) -> None:
    if not fields:
        return
    fields = {**fields, "updated_at": _now()}
    columns = ", ".join(f"{col} = ?" for col in fields)
    conn.execute(
        f"UPDATE media_items SET {columns} WHERE id = ?",
        (*fields.values(), media_item_id),
    )
    _sync_fts(conn, media_item_id)


def update_media_item_file_path(conn: sqlite3.Connection, media_item_id: int, file_path: str) -> None:
    conn.execute(
        "UPDATE media_items SET file_path = ?, updated_at = ? WHERE id = ?",
        (file_path, _now(), media_item_id),
    )


def get_media_item(conn: sqlite3.Connection, media_item_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT m.*, e.author, e.series, e.series_index, e.isbn, e.publisher,
               e.pub_date, e.language, e.cover_path
        FROM media_items m
        LEFT JOIN epub_metadata e ON e.media_item_id = m.id
        WHERE m.id = ?
        """,
        (media_item_id,),
    ).fetchone()


def get_media_item_by_hash(conn: sqlite3.Connection, file_hash: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM media_items WHERE file_hash = ?", (file_hash,)
    ).fetchone()


def get_media_item_by_file_path(conn: sqlite3.Connection, file_path: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT m.*, e.author, e.series, e.series_index, e.cover_path
        FROM media_items m
        LEFT JOIN epub_metadata e ON e.media_item_id = m.id
        WHERE m.file_path = ? AND m.status = 'active'
        """,
        (file_path,),
    ).fetchone()


def list_media_items(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT m.*, e.author, e.series, e.series_index, e.cover_path
        FROM media_items m
        LEFT JOIN epub_metadata e ON e.media_item_id = m.id
        WHERE m.status = 'active'
        ORDER BY m.added_at DESC
        """
    ).fetchall()


def list_queue_items(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT m.*, e.author, e.series, e.series_index, e.cover_path
        FROM media_items m
        LEFT JOIN epub_metadata e ON e.media_item_id = m.id
        WHERE m.status IN ('pending', 'manual_review')
        ORDER BY m.added_at ASC
        """
    ).fetchall()


def delete_media_item(conn: sqlite3.Connection, media_item_id: int) -> None:
    conn.execute("DELETE FROM media_items_fts WHERE rowid = ?", (media_item_id,))
    conn.execute("DELETE FROM media_items WHERE id = ?", (media_item_id,))


def search_media_items(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT m.*, e.author, e.series, e.series_index, e.cover_path
        FROM media_items_fts f
        JOIN media_items m ON m.id = f.rowid
        LEFT JOIN epub_metadata e ON e.media_item_id = m.id
        WHERE media_items_fts MATCH ? AND m.status = 'active'
        ORDER BY rank
        """,
        (query,),
    ).fetchall()
