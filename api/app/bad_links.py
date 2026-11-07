import asyncio
import os
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from bson import ObjectId, errors
import httpx
from motor.motor_asyncio import AsyncIOMotorClient

# =====================================================================
# PRODUCTION CONFIGURATION ENGINE
# =====================================================================

# Locate the root folder where your .env file lives relative to this file
# api/app/bad_links.py -> api/app -> api -> root-cause-app/.env
CURRENT_FILE_PATH = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE_PATH.parent.parent.parent
ENV_FILE_PATH = ROOT_DIR / ".env"


class DatabaseSettings(BaseSettings):
    """
    Production settings module. Auto-loads parameters directly from 
    system environment memory, falling back seamlessly to the root
    project .env file definition when run locally.
    """
    # Map fields dynamically to matching keys from your .env file
    atlas_uri: Optional[str] = None
    mongodb_uri: str = "mongodb://localhost:27017"
    atlas_db: Optional[str] = None
    mongodb_db: str = "root-cause_db"

    model_config = SettingsConfigDict(
        # Target the absolute path to your root .env
        env_file=str(ENV_FILE_PATH),
        env_file_extra_ignore=True,  # Safely ignore non-database keys
        extra="ignore"
    )


# Instantiate settings safely across machines
settings = DatabaseSettings()

# Extract variables based on precedence rules
MONGO_URI = settings.atlas_uri or settings.mongodb_uri
DB_NAME = settings.atlas_db or settings.mongodb_db

# Initialize database pool connection safely
client_db = AsyncIOMotorClient(MONGO_URI)
db = client_db[DB_NAME]

router = APIRouter()


class UpdateLinkPayload(BaseModel):
    link: str


async def is_link_broken(client: httpx.AsyncClient, url: Optional[str]) -> bool:
    """
    Checks if a URL is broken using a fast HEAD request.
    Falls back to a GET request if the server rejects HEAD requests.
    """
    if not url:
        return False

    try:
        response = await client.head(url, timeout=10.0, follow_redirects=True)
        if response.is_error or response.status_code == 404 or response.status_code == 405 or response.status_code == 501:
            response = await client.get(url, timeout=10.0, follow_redirects=True)
        return response.is_error
    except (httpx.HTTPError, asyncio.TimeoutError):
        return True


async def check_record(client: httpx.AsyncClient, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """ Checks both the link and sitelink for a single document record. """
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
                "sitelink_broken": sitelink_broken
            }
        }
    return None


@router.get("/bad-links")
async def get_bad_links():
    try:
        # Read from your actual MongoDB resources collection
        cursor = db.resources.find(
            {}, {"title": 1, "attribution": 1, "link": 1, "sitelink": 1})
        docs = await cursor.to_list(length=None)
        broken_records = []

        async with httpx.AsyncClient() as client:
            tasks = [check_record(client, doc) for doc in docs]
            results = await asyncio.gather(*tasks)
            broken_records = [r for r in results if r is not None]

        return {
            "success": True,
            "count": len(broken_records),
            "broken_records": broken_records
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Database aggregation failed: {str(e)}")


@router.patch("/bad-links/{doc_id}")
async def update_bad_link(doc_id: str, payload: UpdateLinkPayload):
    try:
        oid = ObjectId(doc_id)
    except errors.InvalidId:
        raise HTTPException(
            status_code=400, detail="The provided ID is not a valid ObjectId format.")

    try:
        # Commit the modification back into the live Mongo cluster
        result = await db.resources.update_one(
            {"_id": oid},
            {"$set": {"link": payload.link}}
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail="Resource record could not be found.")

        return {"success": True, "message": "Link successfully updated in database."}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Database update failed: {str(e)}")


@router.delete("/bad-links/{doc_id}")
async def delete_resource(doc_id: str):
    try:
        oid = ObjectId(doc_id)
    except errors.InvalidId:
        raise HTTPException(
            status_code=400, detail="The provided ID is not a valid ObjectId format.")

    try:
        # Permanently purge the full record line out of the database matching the UI command
        result = await db.resources.delete_one({"_id": oid})

        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404, detail="Resource record could not be found.")

        return {"success": True, "message": "Resource permanently purged from database."}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Database deletion failed: {str(e)}")
