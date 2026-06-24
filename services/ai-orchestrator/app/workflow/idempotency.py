"""
Idempotency store — prevents duplicate Bedrock calls when LangGraph re-runs a
node after resume (interrupt → replay pattern).

Storage: MongoDB collection `idempotency_store` with TTL index on `expires_at`.
Falls back to in-process dict when MongoDB unavailable (tests / CI).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

log = logging.getLogger("ai-orchestrator.idempotency")

_TTL_HOURS = 48
_MEMORY_FALLBACK: Dict[str, dict] = {}


class IdempotencyStore:
    def get(self, key: str) -> Optional[dict]:
        """Return stored result for key, or None if absent / expired."""
        # MongoDB path
        db = self._db()
        if db is not None:
            try:
                doc = db.idempotency_store.find_one({"key": key}, {"_id": 0})
                if doc:
                    expires_at = doc.get("expires_at")
                    if isinstance(expires_at, datetime) and datetime.now(timezone.utc) > expires_at.replace(tzinfo=timezone.utc):
                        db.idempotency_store.delete_one({"key": key})
                        return None
                    return doc.get("result")
            except Exception as exc:
                log.warning("idempotency get error: %s", exc)

        # In-memory fallback
        entry = _MEMORY_FALLBACK.get(key)
        if entry:
            if datetime.now(timezone.utc) > entry["expires_at"]:
                del _MEMORY_FALLBACK[key]
                return None
            return entry["result"]
        return None

    def set(self, key: str, result: Any) -> None:
        """Store result for key with 48-hour TTL."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=_TTL_HOURS)
        db = self._db()
        if db is not None:
            try:
                db.idempotency_store.replace_one(
                    {"key": key},
                    {"key": key, "result": result, "expires_at": expires_at},
                    upsert=True,
                )
                return
            except Exception as exc:
                log.warning("idempotency set error: %s", exc)

        _MEMORY_FALLBACK[key] = {"result": result, "expires_at": expires_at}

    def _db(self):
        try:
            from app.db import get_db
            return get_db()
        except Exception:
            return None


idempotency_store = IdempotencyStore()
