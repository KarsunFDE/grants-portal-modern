"""MongoDB connection for ai-orchestrator. Lazy — no connection until first DB op."""
from __future__ import annotations

import os
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "grantsportal")


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    return MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)


def get_db() -> Database:
    return get_mongo_client()[DB_NAME]
