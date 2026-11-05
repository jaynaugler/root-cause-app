"""MongoDB access for the API.

Mirrors web/src/lib/server/db.ts: resolves the connection config at module
load and fails fast on missing configuration. Motor connects lazily, so no
network I/O happens until the first query.
"""

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import resolve_db_config

uri, db_name, target = resolve_db_config()

client = AsyncIOMotorClient(uri)
db = client[db_name]
