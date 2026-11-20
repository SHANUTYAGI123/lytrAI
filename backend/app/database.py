import json
import os
import aiosqlite
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.config import settings


def get_db_path() -> str:
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        # Handles sqlite:////data/app.db -> /data/app.db
        # and sqlite:///./data/app.db -> ./data/app.db
        clean_path = url[len("sqlite:///"):]
    elif url.startswith("sqlite://"):
        clean_path = url[len("sqlite://"):]
    else:
        clean_path = url

    # Ensure parent directory exists
    abs_path = os.path.abspath(clean_path)
    parent_dir = os.path.dirname(abs_path)
    if parent_dir and not os.path.exists(parent_dir):
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except OSError:
            pass
    return clean_path


async def init_db() -> None:
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            );
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages (session_id);
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                system_prompt TEXT,
                created_at TEXT NOT NULL
            );
        """)
        await db.commit()


async def check_db_health() -> bool:
    try:
        db_path = get_db_path()
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT 1") as cursor:
                row = await cursor.fetchone()
                return row is not None and row[0] == 1
    except Exception:
        return False


async def get_session_system_prompt(session_id: str) -> Optional[str]:
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT system_prompt FROM sessions WHERE session_id = ?",
            (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]
    return None


async def set_session_system_prompt(session_id: str, system_prompt: str) -> None:
    db_path = get_db_path()
    now_iso = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO sessions (session_id, system_prompt, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET system_prompt = excluded.system_prompt;
            """,
            (session_id, system_prompt, now_iso)
        )
        await db.commit()


async def get_session_messages(session_id: str) -> List[Dict[str, Any]]:
    """
    Returns the stored history of one session from SQLite, oldest first, without the system prompt.
    """
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, session_id, role, content, metadata, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                parsed_meta = None
                if row["metadata"]:
                    try:
                        parsed_meta = json.loads(row["metadata"])
                    except Exception:
                        parsed_meta = None
                results.append({
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "role": row["role"],
                    "content": row["content"],
                    "metadata": parsed_meta,
                    "created_at": row["created_at"]
                })
            return results


async def session_exists(session_id: str) -> bool:
    """
    Checks if session exists (either has messages or in sessions table).
    """
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT 1 FROM messages WHERE session_id = ? LIMIT 1",
            (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return True
        async with db.execute(
            "SELECT 1 FROM sessions WHERE session_id = ? LIMIT 1",
            (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None


async def save_turn(
    session_id: str,
    user_content: str,
    assistant_content: str,
    assistant_metadata: Dict[str, Any],
    system_prompt: Optional[str] = None
) -> None:
    """
    Persists a user message and assistant message in a single atomic transaction.
    If system_prompt is given, ensures session record is saved/updated.
    """
    db_path = get_db_path()
    now_iso = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(assistant_metadata)

    async with aiosqlite.connect(db_path) as db:
        if system_prompt:
            await db.execute(
                """
                INSERT INTO sessions (session_id, system_prompt, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET system_prompt = excluded.system_prompt;
                """,
                (session_id, system_prompt, now_iso)
            )

        # Insert user message
        await db.execute(
            """
            INSERT INTO messages (session_id, role, content, metadata, created_at)
            VALUES (?, 'user', ?, NULL, ?);
            """,
            (session_id, user_content, now_iso)
        )

        # Insert assistant message
        await db.execute(
            """
            INSERT INTO messages (session_id, role, content, metadata, created_at)
            VALUES (?, 'assistant', ?, ?, ?);
            """,
            (session_id, assistant_content, meta_json, now_iso)
        )

        await db.commit()
