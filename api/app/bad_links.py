"""Background link checking and link repair endpoints for resources in the archive."""

import asyncio
from typing import Any

import httpx
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from pymongo.errors import PyMongoError

from app.db import db

router = APIRouter(tags=["bad-links"])

coll = db["resources"]

# Concurrency semaphore: prevent thousands of simultaneous outgoing HTTP requests
MAX_CONCURRENT_CHECKS = 20
_CHECK_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)


class UpdateLinkPayload(BaseModel):
    link: str | None = None
    sitelink: str | None = None


def _parse_object_id(doc_id: str) -> ObjectId:
    try:
        return ObjectId(doc_id)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The provided ID is not a valid ObjectId format.",
        )


async def is_link_broken(client: httpx.AsyncClient, url: str | None) -> bool:
    """Check if a URL is broken using a fast HEAD request.

    Falls back to a GET request if the server rejects HEAD requests.
    """
    if not url:
        return False

    async with _CHECK_SEMAPHORE:
        try:
            response = await client.head(url, timeout=10.0, follow_redirects=True)
            if response.is_error or response.status_code in (404, 405, 501):
                response = await client.get(url, timeout=10.0, follow_redirects=True)
            return response.is_error
        except (TimeoutError, httpx.HTTPError):
            return True


async def check_record(client: httpx.AsyncClient, doc: dict[str, Any]) -> dict[str, Any] | None:
    """Check both the direct link and sitelink for a single resource record."""
    doc_id = str(doc.get("_id"))
    title = doc.get("title")
    attribution = doc.get("attribution")
    link = doc.get("link")
    sitelink = doc.get("sitelink")

    link_broken_task = is_link_broken(client, link)
    sitelink_broken_task = is_link_broken(client, sitelink)

    link_broken, sitelink_broken = await asyncio.gather(link_broken_task, sitelink_broken_task)

    if link_broken or sitelink_broken:
        return {
            "id": doc_id,
            "title": title,
            "attribution": attribution,
            "link": link,
            "sitelink": sitelink,
            "issues": {
                "link_broken": link_broken,
                "sitelink_broken": sitelink_broken,
            },
        }
    return None


@router.get("/bad-links")
async def get_bad_links(limit: int = 500):
    """Scan archive resource records to detect broken links and sitelinks."""
    try:
        cursor = coll.find({}, {"title": 1, "attribution": 1, "link": 1, "sitelink": 1}).limit(
            limit
        )
        docs = await cursor.to_list(limit)
    except PyMongoError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database aggregation failed: {e!s}",
        ) from e

    async with httpx.AsyncClient() as client:
        tasks = [check_record(client, doc) for doc in docs]
        results = await asyncio.gather(*tasks)
        broken_records = [r for r in results if r is not None]

    return {
        "success": True,
        "count": len(broken_records),
        "broken_records": broken_records,
    }


@router.patch("/bad-links/{doc_id}")
async def update_bad_link(doc_id: str, payload: UpdateLinkPayload):
    """Update destination link and/or host sitelink for a resource."""
    oid = _parse_object_id(doc_id)

    update_fields: dict[str, Any] = {}
    if payload.link is not None:
        link_str = payload.link.strip()
        if not link_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Link cannot be empty.",
            )
        update_fields["link"] = link_str

    if payload.sitelink is not None:
        sitelink_str = payload.sitelink.strip()
        update_fields["sitelink"] = sitelink_str or None

    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields provided to update.",
        )

    try:
        result = await coll.update_one({"_id": oid}, {"$set": update_fields})
    except PyMongoError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database update failed: {e!s}",
        ) from e

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource record could not be found.",
        )

    return {"success": True, "message": "Link successfully updated in database."}


@router.delete("/bad-links/{doc_id}")
async def delete_resource(doc_id: str):
    """Permanently delete a broken resource from the database."""
    oid = _parse_object_id(doc_id)

    try:
        result = await coll.delete_one({"_id": oid})
    except PyMongoError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database deletion failed: {e!s}",
        ) from e

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource record could not be found.",
        )

    return {"success": True, "message": "Resource permanently purged from database."}
