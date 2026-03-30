import json
import aiosqlite
from content_app.config import get_settings

def _get_db_path() -> str:
    """Get database path from settings."""
    settings = get_settings()
    return settings.database_url.replace("sqlite:///", "")

async def init_db():
    """Initialize the database."""
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                topic TEXT,
                platform TEXT,
                tone TEXT,
                voice_context TEXT,
                draft TEXT,
                previous_drafts TEXT,
                alignment_score INTEGER,
                alignment_feedback TEXT,
                retry_count INTEGER,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def save_run(run: dict):
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute("""
            INSERT INTO runs (run_id, topic, platform, tone, voice_context, draft, 
                            previous_drafts, alignment_score, alignment_feedback, 
                            retry_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run.get("run_id"),
            run.get("topic"),
            run.get("platform"),
            run.get("tone"),
            run.get("voice_context"),
            run.get("draft"),
            json.dumps(run.get("previous_drafts", [])),
            run.get("alignment_score"),
            run.get("alignment_feedback"),
            run.get("retry_count"),
            run.get("status"),
        ))
        await db.commit()


async def get_run(run_id: str) -> dict | None:
    async with aiosqlite.connect(_get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            result["previous_drafts"] = json.loads(result["previous_drafts"] or "[]")
            return result
        return None

async def list_runs(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(_get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            result["previous_drafts"] = json.loads(result["previous_drafts"] or "[]")
            results.append(result)
        return results