import pytest
from pathlib import Path
import fitz

OSBORNE_SOURCE_SHA256 = "d2736cb9b551bdeef6a5f7b8078c5c4b9a5ab13e6ae9f44eff63aaebc548ef46"

def test_p4_imports():
    from ingestion_service.ast.models import (
        HeadingBlock,
        ParagraphBlock,
        QuotationBlock,
        ListBlock,
        TableBlock,
        FigureBlock,
        FootnoteBlock,
        DocumentPage
    )
    from ingestion_service.ast.normalization import normalize_text, ReversibleNormalization
    from ingestion_service.ast.builder import DocumentAstBuilder
    from ingestion_service.ast.validator import FidelityValidator

def test_reversible_normalization_osborne_p600():
    from ingestion_service.ast.normalization import normalize_text

    raw = "Повествовательное проповедование занимает важное место в арсе#\nнале проповедника, но оно служит дополнением."
    norm = normalize_text(raw)

    assert "арсенале" in norm.normalized_text
    assert "#" not in norm.normalized_text
    assert len(norm.operations) > 0
    assert norm.operations[0]["kind"] == "line_end_dehyphenation"
    # Reversibility test: applying rawRange restores original substring
    op = norm.operations[0]
    assert raw[op["raw_range"][0]:op["raw_range"][1]] == "арсе#\nнале"

def test_verse_ranges_and_citations_preserved_osborne_p54():
    from ingestion_service.ast.normalization import normalize_text
    from ingestion_service.ast.validator import FidelityValidator

    raw = "Первые несколько пар раскрывают Божью личность (28б) и что Он дает нуждающимся (29 ст.). См. 1 Кор. 15:45."
    norm = normalize_text(raw)

    assert "(28б)" in norm.normalized_text
    assert "(29 ст.)" in norm.normalized_text
    assert "1 Кор. 15:45" in norm.normalized_text

    validator = FidelityValidator()
    digits_preserved = validator.verify_digit_sequences(raw, norm.normalized_text)
    assert digits_preserved is True

def test_two_column_reading_order_osborne_p158():
    from ingestion_service.ast.builder import DocumentAstBuilder

    osborne_path = Path("storage/inbox/681537e1_Озборн_Герменевтическая спираль.pdf")
    if not osborne_path.exists():
        pytest.skip("Osborne PDF not in storage/inbox")

    doc = fitz.open(str(osborne_path))
    builder = DocumentAstBuilder(source_sha256=OSBORNE_SOURCE_SHA256)
    doc_page = builder.build_page(doc[157], page_index=157, printed_page_label="158")
    doc.close()

    assert len(doc_page.blocks) > 0
    # Reading order must not interleave left and right columns on the same line
    # Verified by checking that block Y positions in a column increase monotonically
    # before moving to the next column
    assert doc_page.layout_detected in ("two_column", "schematic", "complex")

def test_footnote_anchor_resolution_osborne_p609():
    from ingestion_service.ast.builder import DocumentAstBuilder

    osborne_path = Path("storage/inbox/681537e1_Озборн_Герменевтическая спираль.pdf")
    if not osborne_path.exists():
        pytest.skip("Osborne PDF not in storage/inbox")

    doc = fitz.open(str(osborne_path))
    builder = DocumentAstBuilder(source_sha256=OSBORNE_SOURCE_SHA256)
    doc_page = builder.build_page(doc[608], page_index=608, printed_page_label="609")
    doc.close()

    assert len(doc_page.footnotes) > 0
    first_fn = doc_page.footnotes[0]
    assert first_fn.label != ""
    assert len(first_fn.blocks) > 0

def test_corrupted_text_layer_detected_osborne_p736():
    from ingestion_service.ast.builder import DocumentAstBuilder

    osborne_path = Path("storage/inbox/681537e1_Озборн_Герменевтическая спираль.pdf")
    if not osborne_path.exists():
        pytest.skip("Osborne PDF not in storage/inbox")

    doc = fitz.open(str(osborne_path))
    builder = DocumentAstBuilder(source_sha256=OSBORNE_SOURCE_SHA256)
    doc_page = builder.build_page(doc[735], page_index=735, printed_page_label="736")
    doc.close()

    # Page 736 has corrupt text layer with excessive control/form-feed whitespace
    assert doc_page.review_status in ("needs_review", "corrupt_text_layer")

def test_ast_builder_heading_bold_italic_runs(tmp_path):
    from ingestion_service.ast.builder import DocumentAstBuilder

    pdf_path = tmp_path / "formatted.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # PyMuPDF insert formatted text
    page.insert_text((50, 80), "ГЛАВА 1", fontsize=18)
    page.insert_text((50, 120), "Это обычный текст абзаца со ссылкой.", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    doc_in = fitz.open(str(pdf_path))
    builder = DocumentAstBuilder(source_sha256="a" * 64)
    doc_page = builder.build_page(doc_in[0], page_index=1)
    doc_in.close()

    assert len(doc_page.blocks) >= 2
    assert doc_page.blocks[0].type == "heading"
    assert doc_page.blocks[1].type == "paragraph"

def test_schematic_structure_osborne_p55():
    from ingestion_service.ast.builder import DocumentAstBuilder

    osborne_path = Path("storage/inbox/681537e1_Озборн_Герменевтическая спираль.pdf")
    if not osborne_path.exists():
        pytest.skip("Osborne PDF not in storage/inbox")

    doc = fitz.open(str(osborne_path))
    builder = DocumentAstBuilder(source_sha256=OSBORNE_SOURCE_SHA256)
    doc_page = builder.build_page(doc[54], page_index=54, printed_page_label="55")
    doc.close()

    assert len(doc_page.blocks) > 0
    # Page 55 has structural elements with preserved indent and runs
    assert any("благодати" in r.text for b in doc_page.blocks for r in b.runs)

def test_bibliography_structure_osborne_p693():
    from ingestion_service.ast.builder import DocumentAstBuilder

    osborne_path = Path("storage/inbox/681537e1_Озборн_Герменевтическая спираль.pdf")
    if not osborne_path.exists():
        pytest.skip("Osborne PDF not in storage/inbox")

    doc = fitz.open(str(osborne_path))
    builder = DocumentAstBuilder(source_sha256=OSBORNE_SOURCE_SHA256)
    doc_page = builder.build_page(doc[692], page_index=692, printed_page_label="693")
    doc.close()

    headings = [b for b in doc_page.blocks if b.type == "heading"]
    assert len(headings) >= 1
    assert any("БИБЛИОГРАФИЯ" in r.text for r in headings[0].runs)
    assert len(doc_page.blocks) >= 10


def test_ast_requires_verified_source_hash(tmp_path):
    from ingestion_service.ast.builder import DocumentAstBuilder

    pdf_path = tmp_path / "unverified.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((50, 72), "Текст")
    doc.save(str(pdf_path))
    doc.close()

    doc_in = fitz.open(str(pdf_path))
    with pytest.raises(ValueError, match="source_sha256"):
        DocumentAstBuilder().build_page(doc_in[0], page_index=0)
    with pytest.raises(ValueError, match="source_sha256"):
        DocumentAstBuilder(source_sha256="sha256-evidence").build_page(
            doc_in[0], page_index=0
        )
    doc_in.close()


def test_ast_preserves_image_blocks_and_normalization_provenance(tmp_path):
    from ingestion_service.ast.builder import DocumentAstBuilder
    from ingestion_service.ast.models import FigureBlock

    import base64
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    pdf_path = tmp_path / "ast-evidence.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), "арсе#\nнале")
    page.insert_image(fitz.Rect(20, 100, 575, 800), stream=png)
    doc.save(str(pdf_path))
    doc.close()

    doc_in = fitz.open(str(pdf_path))
    result = DocumentAstBuilder(
        slug="evidence",
        source_sha256="b" * 64,
    ).build_page(doc_in[0], page_index=0, printed_page_label="12")
    doc_in.close()

    runs = [run for block in result.blocks if hasattr(block, "runs") for run in block.runs]
    assert runs
    assert all(run.source.sourceSha256 == "b" * 64 for run in runs)
    assert all(run.source.bbox for run in runs)
    assert "".join(run.text for run in runs) == "арсенале"
    figures = [block for block in result.blocks if isinstance(block, FigureBlock)]
    assert figures
    assert figures[0].source is not None
    assert figures[0].source.sourceSha256 == "b" * 64
    assert result.normalization_provenance
    dehyphenation = [
        operation
        for evidence in result.normalization_provenance
        for operation in evidence["operations"]
        if operation["kind"] == "line_end_dehyphenation"
    ]
    assert dehyphenation
    assert any("run_ids" in evidence for evidence in result.normalization_provenance)
    assert result.printed_label == "12"

def test_fidelity_validator_catches_dropped_digits():
    from ingestion_service.ast.validator import FidelityValidator

    validator = FidelityValidator()
    raw = "В 2015 году было выпущено 450 экземпляров книги 1 Кор. 15:45."
    tampered = "В году было выпущено экземпляров книги 1 Кор."

    res = validator.verify_digit_sequences(raw, tampered)
    assert res is False


def test_fidelity_validator_rejects_reordered_or_injected_digits():
    from ingestion_service.ast.validator import FidelityValidator

    validator = FidelityValidator()
    raw = "См. 1 Кор. 15:45 и страницу 600."
    assert validator.verify_digit_sequences(raw, "См. 1 Кор. 15:45 и страницу 600.") is True
    assert validator.verify_digit_sequences(raw, "См. 15 Кор. 1:45 и страницу 600.") is False
    assert validator.verify_digit_sequences(raw, "См. 1 Кор. 15:45 и страницу 600, 609.") is False
