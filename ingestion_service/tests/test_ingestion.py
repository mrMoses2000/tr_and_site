import pytest
import tempfile
import json
from pathlib import Path
from ingestion_service.db import init_db, create_job, get_job, update_job
from ingestion_service.agy_bridge import AgyCliBridge, ParagraphPairModel, TranslatedPageModel
from ingestion_service.publisher import BookPublisher

def test_db_job_lifecycle(tmp_path, monkeypatch):
    test_db = tmp_path / "test_ingestion.db"
    monkeypatch.setattr("ingestion_service.db.DB_PATH", test_db)
    init_db()

    job = create_job(
        job_id="test-123",
        telegram_user_id=111,
        telegram_chat_id=222,
        telegram_message_id=333,
        file_name="test.pdf",
        file_path="/tmp/test.pdf",
        book_slug="test-slug"
    )

    assert job.id == "test-123"
    assert job.status == "QUEUED"

    update_job("test-123", status="EXTRACTING", total_pages=10, processed_pages=2)
    fetched = get_job("test-123")
    assert fetched is not None
    assert fetched.status == "EXTRACTING"
    assert fetched.total_pages == 10
    assert fetched.processed_pages == 2

    update_job("test-123", status="DEPLOYED", live_url="https://example.com")
    fetched_done = get_job("test-123")
    assert fetched_done.status == "DEPLOYED"
    assert fetched_done.live_url == "https://example.com"

def test_agy_bridge_clean_json():
    bridge = AgyCliBridge()

    # Case 1: Markdown code fences
    fence_input = """
    Here is the translation:
    ```json
    [
      {
        "pageNumber": 1,
        "chapterTitle": "Intro",
        "readingTimeMinutes": 2,
        "paragraphs": [{"id": "p-1-1", "en": "Hello", "ru": "Привет"}],
        "footnotes": [{"id": 1, "textEn": "Note", "textRu": "Сноска"}]
      }
    ]
    ```
    """
    cleaned = bridge._clean_json_output(fence_input)
    assert isinstance(cleaned, list)
    assert cleaned[0]["pageNumber"] == 1
    assert cleaned[0]["paragraphs"][0]["ru"] == "Привет"

    # Case 2: Raw JSON array
    raw_input = '[{"pageNumber": 2, "paragraphs": [], "footnotes": []}]'
    cleaned_raw = bridge._clean_json_output(raw_input)
    assert len(cleaned_raw) == 1
    assert cleaned_raw[0]["pageNumber"] == 2

    # Case 3: Prompt builder
    prompt = bridge._build_batch_prompt(
        pages_data=[{"pageNumber": 5, "text": "Some text"}],
        book_title="NT Theology",
        author="Schreiner"
    )
    assert "[PAGE_START: 5]" in prompt
    assert "NT Theology" in prompt

@pytest.mark.asyncio
async def test_publisher_compile_manifest(tmp_path):
    app_dir = tmp_path / "app"
    publisher = BookPublisher(app_dir=app_dir)
    
    scans_dir = tmp_path / "scans"
    scans_dir.mkdir(parents=True)
    (scans_dir / "page_1.webp").write_bytes(b"dummy")

    pages = [{
        "pageNumber": 1,
        "chapterTitle": "Chapter One",
        "paragraphs": [{"id": "p-1-1", "en": "Test", "ru": "Тест"}],
        "footnotes": []
    }]

    manifest_file = await publisher.compile_manifest(
        slug="dummy-book",
        metadata={"title": "Test Title", "author": "Test Author"},
        pages=pages,
        scans_source_dir=scans_dir
    )

    assert manifest_file.exists()
    content = json.loads(manifest_file.read_text("utf-8"))
    assert content["slug"] == "dummy-book"
    assert content["title"] == "Test Title"
    assert content["pages"][0]["imageSrc"] == "/scans/dummy-book/page_1.webp"

def test_pdf_extractor_flow(tmp_path):
    import fitz
    from ingestion_service.pdf_extractor import PDFExtractor

    # Create a small dummy PDF in memory
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "In the beginning was the Word, and the Word was with God.")
    doc.set_metadata({"title": "Sample Gospel", "author": "John"})
    doc.save(str(pdf_path))
    doc.close()

    extractor = PDFExtractor(pdf_path)
    meta = extractor.get_metadata()
    assert meta["title"] == "Sample Gospel"
    assert meta["author"] == "John"
    assert meta["totalPages"] == 1

    text = extractor.extract_page_text(0)
    assert "In the beginning was the Word" in text

    scans_out = tmp_path / "scans"
    img_path = extractor.render_page_as_webp(0, scans_out, "sample-gospel")
    assert img_path.exists()
    assert img_path.suffix == ".webp"
    extractor.close()

def test_agy_bridge_fallback():
    bridge = AgyCliBridge()
    pages_data = [{
        "pageNumber": 1,
        "text": "First paragraph.\n\nSecond paragraph."
    }]
    fallback_res = bridge._generate_fallback(pages_data)
    assert len(fallback_res) == 1
    assert fallback_res[0].pageNumber == 1
    assert len(fallback_res[0].paragraphs) == 2
    assert fallback_res[0].paragraphs[0].id == "p-1-1"
    assert fallback_res[0].paragraphs[0].en == "First paragraph."

