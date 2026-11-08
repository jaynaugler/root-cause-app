from types import SimpleNamespace

from app.pdf import _extract_text


class FakePage:
	def __init__(self, text: str):
		self.text = text

	def extract_text(self) -> str:
		return self.text


def test_extract_text_reads_beyond_opening_pages(monkeypatch):
	monkeypatch.setattr("app.pdf.shutil.which", lambda _: None)  # disable OCR for this text-layer test
	reader = SimpleNamespace(pages=[FakePage(f"Page {index} content.") for index in range(10)])
	texts = _extract_text(reader, data=b"%PDF-test")
	assert len(texts) == 10
	assert texts[-1] == "Page 9 content."
