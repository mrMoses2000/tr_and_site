import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .models import BatchTranslationResponse, TranslationEnvelope


def compute_batch_hash(
    envelope: TranslationEnvelope,
    prompt_version: str = "v1",
    model: str = "gemini-flash",
) -> str:
    """
    Computes deterministic SHA-256 for translation batch payload.
    Includes contractVersion, book ID, languages, prompt version, model, and all block IDs and text.
    """
    tokens = [
        envelope.contractVersion,
        envelope.book.get("id", ""),
        envelope.book.get("sourceLanguage", ""),
        envelope.book.get("targetLanguage", ""),
        prompt_version,
        model,
    ]
    for b in envelope.blocks:
        tokens.append(f"{b.id}:{b.text}")

    serialized = "|".join(tokens)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class TranslationCache:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS translation_cache (
                    batch_hash TEXT PRIMARY KEY,
                    results_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            conn.commit()

    def get(self, batch_hash: str) -> Optional[BatchTranslationResponse]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT results_json FROM translation_cache WHERE batch_hash = ?", (batch_hash,))
            row = cur.fetchone()
            if row:
                try:
                    data = json.loads(row["results_json"])
                    return BatchTranslationResponse.model_validate(data)
                except Exception:
                    pass
        return None

    def set(self, batch_hash: str, response: BatchTranslationResponse):
        now_iso = datetime.now(timezone.utc).isoformat()
        serialized = json.dumps(response.model_dump())
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO translation_cache (batch_hash, results_json, created_at)
                VALUES (?, ?, ?)
            """, (batch_hash, serialized, now_iso))
            conn.commit()
