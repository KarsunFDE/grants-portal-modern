"""MongoDB connection for ai-orchestrator. Lazy — no connection until first DB op."""
from __future__ import annotations

import os
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "grantsportal")

# 1 s selection timeout — fast-fail in dev/CI; real deployments have Mongo available
_SERVER_SELECTION_TIMEOUT_MS = int(
    os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "1000")
)


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    return MongoClient(MONGO_URL, serverSelectionTimeoutMS=_SERVER_SELECTION_TIMEOUT_MS)


def get_db() -> Database:
    return get_mongo_client()[DB_NAME]
