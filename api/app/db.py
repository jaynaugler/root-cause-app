"""MongoDB access for the API.

Mirrors web/src/lib/server/db.ts: resolves the connection config at module
load and fails fast on missing configuration. Motor connects lazily, so no
network I/O happens until the first query.
"""

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import resolve_db_config

uri, db_name, target = resolve_db_config()

# tz_aware=True so datetimes read back from Mongo carry the UTC offset — without
# it POST returns "...+00:00" while GET returns naive strings for the same field.
client = AsyncIOMotorClient(uri, tz_aware=True)
db = client[db_name]
