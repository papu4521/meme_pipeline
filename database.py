import aiosqlite
import json
import math
from contextlib import asynccontextmanager
from config import settings
import hashlib

@asynccontextmanager
async def get_db_connection():
    # Use the filename from the URL, or default to meme_pipeline.db
    db_file = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    if db_file.startswith("./"):
        db_file = db_file[2:]
    
    conn = await aiosqlite.connect(db_file, timeout=30.0)
    try:
        yield conn
    finally:
        await conn.close()

async def init_db():
    async with get_db_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title_hash TEXT UNIQUE,
                title TEXT,
                embedding_blob BLOB,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.commit()

def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

async def is_duplicate(title: str, embedding: list[float]) -> bool:
    title_hash = hashlib.sha256(title.encode('utf-8')).hexdigest()
    embedding_blob = json.dumps(embedding).encode('utf-8')

    async with get_db_connection() as conn:
        await conn.execute("BEGIN EXCLUSIVE")
        async with conn.execute(
            "SELECT embedding_blob FROM seen_trends WHERE title_hash != ? AND created_at > datetime('now', '-30 days')", (title_hash,)
        ) as cur:
            async for row in cur:
                if _cosine_similarity(embedding, json.loads(row[0].decode('utf-8'))) > 0.85:
                    await conn.execute("ROLLBACK")
                    return True
        try:
            await conn.execute(
                "INSERT INTO seen_trends (title_hash, title, embedding_blob) VALUES (?,?,?)",
                (title_hash, title, embedding_blob)
            )
            await conn.commit()
            return False
        except aiosqlite.IntegrityError:
            await conn.execute("ROLLBACK")
            return True
