import asyncio

from bson import ObjectId

from app.moderate import approve_resource


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
	assert collection.update["$unset"] == {"submittedDescription": ""}
