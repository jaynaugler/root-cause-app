"""Curation moderation endpoints for reviewing, approving, and modifying submitted resources."""

from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.db import db

router = APIRouter(tags=["moderate"])

coll = db["resources"]


class ModifySubmissionPayload(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    link: str | None = Field(default=None, max_length=2000)
    sitelink: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=2000)
    generated_description: str | None = Field(default=None, max_length=150)
    submitted_summary: str | None = Field(default=None, min_length=250, max_length=2000)
    summary: str | None = Field(default=None, min_length=250, max_length=2000)
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
                    "submittedDescription": 1,
                    "submittedSummary": 1,
                    "summary": 1,
                    "resourceformat": 1,
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
                # Legacy pending records kept submitter text in description.
                "description": doc.get("submittedDescription", doc.get("description")),
                "generatedDescription": doc.get("description"),
                "submittedSummary": doc.get("submittedSummary"),
                "summary": doc.get("summary"),
                "resourceformat": doc.get("resourceformat"),
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
    """Approve the reviewed record without rerunning extraction or AI cleanup."""
    oid = _parse_object_id(doc_id)

    doc = await coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )

    update_data = {"status": "approved"}

    try:
        await coll.update_one(
            {"_id": oid},
            {
                "$set": update_data,
                "$unset": {
                    "name": "",
                    "email": "",
                    "submittedDescription": "",
                    "submittedSummary": "",
                },
            },
        )
    except PyMongoError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database approval operation failed: {e!s}",
        ) from e

    return {
        "success": True,
        "message": "Submission approved.",
        "record": {
            "id": str(oid),
            "title": doc.get("title") or doc.get("name") or "Untitled Document",
            "contentcategory": doc.get("contentcategory"),
            "summary": doc.get("summary"),
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

    # Normalize public metadata, submission-only, and attachment field names.
    if "submitted_summary" in update_fields:
        update_fields["submittedSummary"] = update_fields.pop("submitted_summary")
    if "description" in update_fields:
        update_fields["submittedDescription"] = update_fields.pop("description")
    if "generated_description" in update_fields:
        update_fields["description"] = update_fields.pop("generated_description")
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
async def reject_resource(doc_id: str):
    """Exclude rejected feed entries; permanently delete other submission types."""
    oid = _parse_object_id(doc_id)

    try:
        doc = await coll.find_one({"_id": oid}, {"resourceformat": 1})
        if not doc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found.")
        if doc.get("resourceformat") in ("article", "podcast"):
            await coll.update_one({"_id": oid}, {"$set": {"status": "unapproved"}})
            return {
                "success": True,
                "message": "Feed entry rejected; it will be excluded from future checks.",
            }
        result = await coll.delete_one({"_id": oid})
    except PyMongoError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database rejection failed: {e!s}",
        ) from e

    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found.")
    return {"success": True, "message": "Submission rejected and removed."}
