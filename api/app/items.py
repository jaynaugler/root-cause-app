"""Starter resource mirroring the `items` collection and the shape used by
web/src/routes/+page.server.ts: { _id (ObjectId -> string), name, createdAt }.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import db

router = APIRouter(tags=["items"])

coll = db["items"]


class ItemIn(BaseModel):
	name: str


@router.get("/items")
async def list_items():
	docs = await coll.find().sort("createdAt", -1).limit(10).to_list(10)
	# ObjectIds are not JSON-serializable — stringify, like web's +page.server.ts does
	return [
		{"_id": str(d["_id"]), "name": d["name"], "createdAt": d["createdAt"]} for d in docs
	]


@router.post("/items", status_code=201)
async def create_item(payload: ItemIn):
	created = datetime.now(timezone.utc)
	res = await coll.insert_one({"name": payload.name, "createdAt": created})
	return {"_id": str(res.inserted_id), "name": payload.name, "createdAt": created}
