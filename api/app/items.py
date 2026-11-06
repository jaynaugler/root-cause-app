"""Resource mirroring the `root_cause_items` collection and the shape used by
web/src/routes/+page.server.ts.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status  # type: ignore
from pydantic import BaseModel, Field, HttpUrl

from app.db import db

# Use standard API tags for automatic documentation
router = APIRouter(tags=["items"])

# Points to your dedicated collection
coll = db["root_cause_items"]


class RootCauseItemIn(BaseModel):
    """Data payload validation rule mapping to your design schema."""
    title: str = Field(..., min_length=1, max_length=200)
    link: HttpUrl
    description: Optional[str] = None
    attribution: str = Field(..., min_length=1)
    resourceformat: str = Field(..., description="e.g., website, pdf, video")
    contentcategory: str = Field(...,
                                 description="e.g., archives, person, place")
    imgurl: HttpUrl


@router.get("/items")
async def list_items():
    """Fetches the 10 most recent root cause items from the database."""
    docs = await coll.find().sort("createdAt", -1).limit(10).to_list(10)

    # ObjectIds are not natively JSON-serializable; stringify them as '_id'.
    # Gracefully filters out broken fields to prevent breaking the full collection view.
    return [
        {
            "_id": str(d["_id"]),
            "title": d.get("title"),
            "link": str(d.get("link")),
            "description": d.get("description"),
            "attribution": d.get("attribution"),
            "createdAt": d.get("createdAt"),
            "resourceformat": d.get("resourceformat"),
            "contentcategory": d.get("contentcategory"),
            "imgurl": str(d.get("imgurl")),
        }
        for d in docs
        if "title" in d and "createdAt" in d
    ]


@router.post("/items", status_code=status.HTTP_201_CREATED)
async def create_item(payload: RootCauseItemIn):
    """Validates submission payloads against the schema and writes directly to MongoDB."""
    created = datetime.now(timezone.utc)

    # Transform the validated Pydantic model into a serializable dictionary
    document_data = {
        "title": payload.title,
        "link": str(payload.link),
        "description": payload.description,
        "attribution": payload.attribution,
        "createdAt": created,
        "resourceformat": payload.resourceformat,
        "contentcategory": payload.contentcategory,
        "imgurl": str(payload.imgurl),
    }

    try:
        res = await coll.insert_one(document_data)
        # Return the final recorded state including the freshly generated Mongo ID
        document_data["_id"] = str(res.inserted_id)
        return document_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database insertion failed: {str(e)}"
        )
