import asyncio

from bson import ObjectId

from app.moderate import approve_resource


def test_approval_uses_generated_description_and_removes_submitter_notes(monkeypatch):
	oid = ObjectId()
	pending = {
		"_id": oid,
		"link": "https://example.com/test.pdf",
		"description": "Initial generated description",
		"submittedDescription": "Context for the review team",
	}

	class FakeCollection:
		update = None

		async def find_one(self, query):
			return pending

		async def update_one(self, query, update):
			self.update = update

	collection = FakeCollection()

	async def fake_pdf_metadata(payload):
		return {
			"title": "Generated Title",
			"description": "Final generated description",
			"summary": "Generated summary " * 20,
			"attribution": "An Author",
			"contentcategory": "history",
			"resourceformat": "pdf",
			"imgurl": None,
		}

	monkeypatch.setattr("app.moderate.coll", collection)
	monkeypatch.setattr("app.moderate._run_pdf_metadata", fake_pdf_metadata)
	result = asyncio.run(approve_resource(str(oid)))

	assert result["success"] is True
	assert collection.update["$set"]["description"] == "Final generated description"
	assert collection.update["$unset"] == {"submittedDescription": ""}
