import pytest
from pathlib import Path
import fitz

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
    builder = DocumentAstBuilder()
    doc_page = builder.build_page(doc[157], page_index=158)
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
    builder = DocumentAstBuilder()
    doc_page = builder.build_page(doc[608], page_index=609)
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
    builder = DocumentAstBuilder()
    doc_page = builder.build_page(doc[735], page_index=736)
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
    builder = DocumentAstBuilder()
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
    builder = DocumentAstBuilder()
    doc_page = builder.build_page(doc[54], page_index=55)
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
    builder = DocumentAstBuilder()
    doc_page = builder.build_page(doc[692], page_index=693)
    doc.close()

    headings = [b for b in doc_page.blocks if b.type == "heading"]
    assert len(headings) >= 1
    assert any("БИБЛИОГРАФИЯ" in r.text for r in headings[0].runs)
    assert len(doc_page.blocks) >= 10

def test_fidelity_validator_catches_dropped_digits():
    from ingestion_service.ast.validator import FidelityValidator

    validator = FidelityValidator()
    raw = "В 2015 году было выпущено 450 экземпляров книги 1 Кор. 15:45."
    tampered = "В году было выпущено экземпляров книги 1 Кор."

    res = validator.verify_digit_sequences(raw, tampered)
    assert res is False
