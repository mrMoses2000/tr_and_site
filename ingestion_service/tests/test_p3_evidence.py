import os
import pytest
from pathlib import Path
import fitz

def test_p3_imports():
    from ingestion_service.evidence.models import (
        PageClassification,
        RouterSignals,
        RawCandidate,
        PageEvidenceRecord,
        SourceDocumentRecord,
        ImageEvidence
    )
    from ingestion_service.evidence.classifier import PageClassifier
    from ingestion_service.evidence.corpus import inventory_corpus, CORPUS_REGISTRY
    from ingestion_service.evidence.source_repo import SourceRepository

def test_immutable_source_storage(tmp_path):
    from ingestion_service.evidence.source_repo import SourceRepository

    storage_dir = tmp_path / "sources"
    repo = SourceRepository(storage_dir, allowed_source_roots=[tmp_path])

    # Create dummy PDF
    dummy_pdf = tmp_path / "incoming.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), "Введение в богословие")
    doc.save(str(dummy_pdf))
    doc.close()

    record = repo.store_source(dummy_pdf)
    assert record.sha256 is not None
    assert len(record.sha256) == 64
    assert record.page_count == 1
    assert record.status == "STORED"
    assert Path(record.storage_path).exists()
    assert Path(record.storage_path).name == f"{record.sha256}.pdf"


def test_source_repository_rejects_file_outside_explicit_roots(tmp_path):
    from ingestion_service.evidence.source_repo import SourceRepository

    allowed_dir = tmp_path / "allowed"
    outside_dir = tmp_path / "outside"
    allowed_dir.mkdir()
    outside_dir.mkdir()
    source = outside_dir / "owner.pdf"
    source.write_bytes(b"%PDF-not-used")

    repo = SourceRepository(tmp_path / "sources", allowed_source_roots=[allowed_dir])
    with pytest.raises(ValueError, match="outside configured source roots"):
        repo.store_source(source)


def test_source_repository_rejects_existing_hash_mismatch(tmp_path):
    from ingestion_service.evidence.source_repo import SourceRepository

    source = tmp_path / "owner.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((50, 72), "Owner content")
    doc.save(str(source))
    doc.close()
    repo = SourceRepository(tmp_path / "sources", allowed_source_roots=[tmp_path])
    record = repo.store_source(source)

    Path(record.storage_path).chmod(0o644)
    Path(record.storage_path).write_bytes(b"tampered content")
    with pytest.raises(ValueError, match="hash mismatch"):
        repo.store_source(source)


def test_source_repository_rejects_symlink_storage_dir(tmp_path):
    from ingestion_service.evidence.source_repo import SourceRepository

    real_storage = tmp_path / "real-storage"
    real_storage.mkdir()
    symlink_storage = tmp_path / "storage"
    symlink_storage.symlink_to(real_storage, target_is_directory=True)

    with pytest.raises(ValueError, match="must not be a symlink"):
        SourceRepository(symlink_storage, allowed_source_roots=[tmp_path])


@pytest.mark.parametrize("target_kind", ["symlink", "directory"])
def test_source_repository_rejects_non_regular_cas_target(tmp_path, target_kind):
    from ingestion_service.evidence.source_repo import SourceRepository

    source = tmp_path / "owner.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((50, 72), "Owner content")
    doc.save(str(source))
    doc.close()
    storage_dir = tmp_path / "sources"
    storage_dir.mkdir()
    repo = SourceRepository(storage_dir, allowed_source_roots=[tmp_path])
    expected_hash = repo.calculate_sha256(source)
    target = storage_dir / f"{expected_hash}.pdf"
    if target_kind == "symlink":
        target.symlink_to(source)
    else:
        target.mkdir()

    with pytest.raises(ValueError, match="regular file"):
        repo.store_source(source)


def test_source_repository_collision_verifies_existing_object(tmp_path, monkeypatch):
    from ingestion_service.evidence import source_repo as source_repo_module
    from ingestion_service.evidence.source_repo import SourceRepository

    source = tmp_path / "owner.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((50, 72), "Concurrent owner content")
    doc.save(str(source))
    doc.close()
    repo = SourceRepository(tmp_path / "sources", allowed_source_roots=[tmp_path])

    def publish_racing_object(temp_name, target_name):
        # Simulate another writer winning the atomic create race.
        import shutil
        shutil.copy2(temp_name, target_name)
        raise FileExistsError(target_name)

    monkeypatch.setattr(source_repo_module.os, "link", publish_racing_object)
    record = repo.store_source(source)
    assert record.sha256 == repo.calculate_sha256(Path(record.storage_path))
    assert Path(record.storage_path).stat().st_mode & 0o777 == 0o444

def test_router_classifies_native_good(tmp_path):
    from ingestion_service.evidence.classifier import PageClassifier
    from ingestion_service.evidence.models import PageClassification

    pdf_path = tmp_path / "native.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), "Chapter 1. Historical and theological context of the New Testament.")
    doc.save(str(pdf_path))
    doc.close()

    classifier = PageClassifier()
    doc_in = fitz.open(str(pdf_path))
    evidence = classifier.classify_page(doc_in, 0)
    doc_in.close()

    assert evidence.classification == PageClassification.NATIVE_GOOD
    assert evidence.router_signals.char_count > 10
    assert evidence.router_signals.replacement_char_rate == 0.0
    assert evidence.render_hash is not None
    assert len(evidence.candidates) >= 1
    assert evidence.candidates[0].method == "native"
    assert evidence.candidates[0].candidate_hash is not None


def test_router_preserves_image_evidence(tmp_path):
    from ingestion_service.evidence.classifier import PageClassifier

    import base64
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    pdf_path = tmp_path / "image.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(20, 20, 575, 800), stream=png)
    doc.save(str(pdf_path))
    doc.close()

    doc_in = fitz.open(str(pdf_path))
    evidence = PageClassifier().classify_page(doc_in, 0)
    doc_in.close()

    assert evidence.image_evidence
    assert evidence.image_evidence[0].bbox
    assert evidence.router_signals.image_coverage > 0.5

def test_router_detects_duplicate_spread(tmp_path):
    from ingestion_service.evidence.classifier import PageClassifier
    from ingestion_service.evidence.models import PageClassification

    pdf_path = tmp_path / "dupe.pdf"
    doc = fitz.open()
    # Two identical pages
    p1 = doc.new_page(width=800, height=600)
    p1.insert_text((50, 50), "Duplicate Spread Content")
    p2 = doc.new_page(width=800, height=600)
    p2.insert_text((50, 50), "Duplicate Spread Content")
    doc.save(str(pdf_path))
    doc.close()

    classifier = PageClassifier()
    doc_in = fitz.open(str(pdf_path))
    ev1 = classifier.classify_page(doc_in, 0)
    ev2 = classifier.classify_page(doc_in, 1, prev_render_hash=ev1.render_hash)
    doc_in.close()

    assert ev1.render_hash == ev2.render_hash
    assert ev2.router_signals.is_duplicate_render is True
    assert "duplicate_spread_or_render" in ev2.findings

def test_router_detects_bad_unicode_font_map(tmp_path):
    from ingestion_service.evidence.classifier import PageClassifier
    from ingestion_service.evidence.models import PageClassification

    pdf_path = tmp_path / "bad_uni.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Text with heavy replacement characters
    bad_text = "Т\ufffdкст с \ufffdспорч\ufffdнной к\ufffdдировкой \ufffd\ufffd\ufffd"
    page.insert_text((50, 72), bad_text)
    doc.save(str(pdf_path))
    doc.close()

    classifier = PageClassifier()
    doc_in = fitz.open(str(pdf_path))
    ev = classifier.classify_page(doc_in, 0)
    doc_in.close()

    assert ev.classification == PageClassification.BAD_UNICODE_FONT_MAP
    assert ev.router_signals.replacement_char_rate > 0.05
    assert "bad_unicode_rate_high" in ev.findings

def test_router_detects_metadata_conflict(tmp_path):
    from ingestion_service.evidence.classifier import PageClassifier

    pdf_path = tmp_path / "conflict.pdf"
    doc = fitz.open()
    doc.set_metadata({"author": "Unknown InDesign Admin", "title": "Untitled Book"})
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), "Уолтер Кайзер\nНа пути к экзегетическому богословию")
    doc.save(str(pdf_path))
    doc.close()

    classifier = PageClassifier()
    doc_in = fitz.open(str(pdf_path))
    ev = classifier.classify_page(doc_in, 0)
    doc_in.close()

    assert "metadata_author_title_conflict" in ev.findings

def test_corpus_inventory_marks_missing_sources_correctly(tmp_path):
    from ingestion_service.evidence.corpus import inventory_corpus, CORPUS_REGISTRY

    # Empty incoming dir
    records = inventory_corpus(search_paths=[tmp_path])
    assert len(records) == len(CORPUS_REGISTRY)
    for rec in records:
        assert rec.status == "MISSING_SOURCE"
        assert rec.byte_size == 0

def test_osborne_source_hash_verified_when_present():
    from ingestion_service.evidence.source_repo import SourceRepository
    from ingestion_service.evidence.classifier import PageClassifier
    from ingestion_service.evidence.models import PageClassification

    osborne_path = Path("storage/inbox/681537e1_Озборн_Герменевтическая спираль.pdf")
    if not osborne_path.exists():
        pytest.skip("Osborne PDF not in storage/inbox")

    repo = SourceRepository(
        Path("storage/sources"),
        allowed_source_roots=[osborne_path.parent],
    )
    record = repo.store_source(osborne_path)
    assert record.sha256 == "d2736cb9b551bdeef6a5f7b8078c5c4b9a5ab13e6ae9f44eff63aaebc548ef46"
    assert record.page_count == 736
    assert record.status == "STORED"

    # Test page 10 (0-indexed 9)
    doc = fitz.open(record.storage_path)
    classifier = PageClassifier()
    evidence = classifier.classify_page(doc, 9)
    doc.close()

    assert evidence.classification == PageClassification.NATIVE_GOOD
    assert evidence.router_signals.valid_cyrillic_rate > 0.5
    assert evidence.router_signals.char_count > 1000
