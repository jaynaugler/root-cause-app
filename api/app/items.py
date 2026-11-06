"""Starter resource mirroring the `items` collection and the shape used by
web/src/routes/+page.server.ts: { _id (ObjectId -> string), name, createdAt }.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db import db

router = APIRouter(tags=["items"])

coll = db["items"]


class ItemIn(BaseModel):
	# Mirrors the zod rules in web/src/routes/+page.server.ts
	name: str = Field(min_length=3, max_length=50)


@router.get("/items")
async def list_items():
	docs = await coll.find().sort("createdAt", -1).limit(10).to_list(10)
	# ObjectIds are not JSON-serializable — stringify, like web's +page.server.ts
	# does. Skip docs missing fields rather than 500-ing the whole listing.
	return [
		{"_id": str(d["_id"]), "name": d["name"], "createdAt": d["createdAt"]}
		for d in docs
		if "name" in d and "createdAt" in d
	]


@router.post("/items", status_code=201)
async def create_item(payload: ItemIn):
	created = datetime.now(timezone.utc)
	res = await coll.insert_one({"name": payload.name, "createdAt": created})
	return {"_id": str(res.inserted_id), "name": payload.name, "createdAt": created}
