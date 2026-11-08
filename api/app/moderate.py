"""Curation moderation endpoints for reviewing, approving, and modifying submitted resources."""

import logging
from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.db import db
from app.pdf import _REQUEST_SLOTS, PdfUrlIn, _run_pdf_metadata
from app.video import VideoUrlIn, _run_video_metadata

logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["moderate"])

coll = db["resources"]


class ModifySubmissionPayload(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    link: str | None = Field(default=None, max_length=2000)
    sitelink: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=2000)
    attachment_name: str | None = Field(default=None, max_length=300)
    attachment_url: str | None = Field(default=None, max_length=2000)


def _parse_object_id(doc_id: str) -> ObjectId:
    try:
        return ObjectId(doc_id)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid record identifier format.",
        )


def _ser_date(val: Any) -> str | None:
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val) if val is not None else None


@router.get("/moderate/pending")
async def get_pending_resources(limit: int = 100):
    """Retrieve raw submissions waiting for moderator evaluation."""
    try:
        cursor = (
            coll.find(
                {"status": "pending"},
                {
                    "name": 1,
                    "email": 1,
                    "description": 1,
                    "link": 1,
                    "sitelink": 1,
                    "attachmentName": 1,
                    "attachmentUrl": 1,
                    "attachment_name": 1,
                    "attachment_url": 1,
                    "fileName": 1,
                    "fileUrl": 1,
                    "status": 1,
                    "createdAt": 1,
                },
            )
            .sort("createdAt", -1)
            .limit(limit)
        )
        docs = await cursor.to_list(limit)
    except PyMongoError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch moderation queue: {e!s}",
        ) from e

    pending_records = []
    for doc in docs:
        attachment_name = (
            doc.get("attachmentName")
            or doc.get("attachment_name")
            or doc.get("fileName")
        )
        attachment_url = (
            doc.get("attachmentUrl")
            or doc.get("attachment_url")
            or doc.get("fileUrl")
        )
        pending_records.append(
            {
                "id": str(doc["_id"]),
                "name": doc.get("name"),
                "email": doc.get("email"),
                "description": doc.get("description"),
                "link": doc.get("link"),
                "sitelink": doc.get("sitelink"),
                "attachmentName": attachment_name,
                "attachmentUrl": attachment_url,
                "status": doc.get("status", "pending"),
                "createdAt": _ser_date(doc.get("createdAt")),
            }
        )

    return {"success": True, "count": len(pending_records), "records": pending_records}


@router.post("/moderate/approve/{doc_id}")
async def approve_resource(doc_id: str):
    """Approve a raw submission and execute the source extraction & AI pipeline on it."""
    oid = _parse_object_id(doc_id)

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )

    # Determine document URL to process
    doc_url = doc.get("link") or doc.get("attachmentUrl") or doc.get("fileUrl")

    meta: dict[str, Any] = {}
    if doc_url and str(doc_url).startswith(("http://", "https://")):
        try:
            async with _REQUEST_SLOTS:
                if "youtube.com" in str(doc_url).lower() or "youtu.be" in str(doc_url).lower():
                    meta = await _run_video_metadata(VideoUrlIn(url=doc_url))
                else:
                    meta = await _run_pdf_metadata(PdfUrlIn(url=doc_url))
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — pipeline failure falls back gracefully
            logger.warning("Pipeline execution encountered an error for doc %s: %s", doc_id, exc)

    # Merge extracted metadata with submitter details as fallbacks
    update_data: dict[str, Any] = {
        "status": "approved",
        "title": meta.get("title") or doc.get("name") or "Untitled Document",
        "description": meta.get("description") or doc.get("description"),
        "summary": meta.get("summary"),
        "attribution": meta.get("attribution") or doc.get("name"),
        "contentcategory": meta.get("contentcategory"),
        "resourceformat": meta.get("resourceformat", "pdf"),
        "imgurl": meta.get("imgurl"),
    }

    try:
        await coll.update_one(
            {"_id": oid},
            {"$set": update_data},
        )
    except PyMongoError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database approval operation failed: {e!s}",
        ) from e

    return {
        "success": True,
        "message": "Submission approved and processed through the pipeline.",
        "record": {
            "id": str(oid),
            "title": update_data["title"],
            "contentcategory": update_data["contentcategory"],
            "summary": update_data["summary"],
        },
    }


@router.patch("/moderate/modify/{doc_id}")
async def modify_pending_resource(doc_id: str, payload: ModifySubmissionPayload):
    """Allow an administrator to refine details of a submission."""
    oid = _parse_object_id(doc_id)

    raw_fields = payload.model_dump(exclude_unset=True)
    if not raw_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No field changes provided.",
        )

    update_fields: dict[str, Any] = {}
    for k, v in raw_fields.items():
        if isinstance(v, str):
            v_stripped = v.strip()
            update_fields[k] = v_stripped if v_stripped else None
        else:
            update_fields[k] = v

    # Normalize attachment field names if provided
    if "attachment_name" in update_fields:
        update_fields["attachmentName"] = update_fields.pop("attachment_name")
    if "attachment_url" in update_fields:
        update_fields["attachmentUrl"] = update_fields.pop("attachment_url")

    try:
        result = await coll.update_one({"_id": oid}, {"$set": update_fields})
    except PyMongoError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database modification failed: {e!s}",
        ) from e

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )

    return {"success": True, "message": "Submission details successfully updated."}


@router.delete("/moderate/reject/{doc_id}")
async def reject_and_delete_resource(doc_id: str):
    """Reject and permanently remove a submission from the database."""
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
            detail="Submission not found.",
        )

    return {"success": True, "message": "Submission rejected and removed."}
