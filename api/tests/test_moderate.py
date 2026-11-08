import asyncio

from bson import ObjectId

from app.moderate import (
    ModifySubmissionPayload,
    approve_resource,
    modify_pending_resource,
    reject_resource,
)


def test_approval_preserves_reviewed_metadata_and_removes_submitter_notes(monkeypatch):
	oid = ObjectId()
	pending = {
		"_id": oid,
		"title": "Reviewed Title",
		"link": "https://www.youtube.com/watch?v=5P7MbyQAa9Q",
		"description": "Reviewed generated description",
		"summary": "Reviewed generated summary",
		"submittedDescription": "Context for the review team",
	}

	class FakeCollection:
		update = None

		async def find_one(self, query):
			return pending

		async def update_one(self, query, update):
			self.update = update

	collection = FakeCollection()
	monkeypatch.setattr("app.moderate.coll", collection)
	result = asyncio.run(approve_resource(str(oid)))

	assert result["success"] is True
	assert result["record"]["summary"] == "Reviewed generated summary"
	assert collection.update["$set"] == {"status": "approved"}
	assert collection.update["$unset"] == {
		"name": "",
		"email": "",
		"submittedDescription": "",
		"submittedSummary": "",
	}


def test_moderator_can_edit_generated_metadata_separately_from_notes(monkeypatch):
	oid = ObjectId()

	class FakeResult:
		matched_count = 1

	class FakeCollection:
		update = None

		async def update_one(self, query, update):
			self.update = update
			return FakeResult()

	collection = FakeCollection()
	monkeypatch.setattr("app.moderate.coll", collection)
	payload = ModifySubmissionPayload(
		description="Updated submitter notes",
		submitted_summary="U" * 250,
		generated_description="Edited public description",
		summary="S" * 250,
	)
	result = asyncio.run(modify_pending_resource(str(oid), payload))

	assert result["success"] is True
	assert collection.update["$set"] == {
		"submittedDescription": "Updated submitter notes",
		"submittedSummary": "U" * 250,
		"description": "Edited public description",
		"summary": "S" * 250,
	}


def test_rejecting_feed_entry_marks_it_unapproved(monkeypatch):
	oid = ObjectId()

	class FakeCollection:
		update = None

		async def find_one(self, query, projection):
			return {"resourceformat": "podcast"}

		async def update_one(self, query, update):
			self.update = update

		async def delete_one(self, query):
			raise AssertionError("Feed exclusions must not be deleted")

	collection = FakeCollection()
	monkeypatch.setattr("app.moderate.coll", collection)
	result = asyncio.run(reject_resource(str(oid)))
	assert collection.update["$set"] == {"status": "unapproved"}
	assert "future checks" in result["message"]


def test_rejecting_non_feed_submission_still_deletes_it(monkeypatch):
	oid = ObjectId()

	class FakeResult:
		deleted_count = 1

	class FakeCollection:
		deleted = False

		async def find_one(self, query, projection):
			return {"resourceformat": "pdf"}

		async def delete_one(self, query):
			self.deleted = True
			return FakeResult()

	collection = FakeCollection()
	monkeypatch.setattr("app.moderate.coll", collection)
	result = asyncio.run(reject_resource(str(oid)))
	assert collection.deleted is True
	assert result["success"] is True
