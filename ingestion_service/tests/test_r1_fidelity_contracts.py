import pytest
from pathlib import Path
import fitz

from ingestion_service.ast.normalization import normalize_text
from ingestion_service.ast.builder import DocumentAstBuilder
from ingestion_service.ast.models import FigureBlock, ParagraphBlock, HeadingBlock
from ingestion_service.ast.validator import FidelityValidator

OSBORNE_PDF = Path("/home/moses/tr_and_site/storage/inbox/681537e1_Озборн_Герменевтическая спираль.pdf")
OSBORNE_SHA256 = "d2736cb9b551bdeef6a5f7b8078c5c4b9a5ab13e6ae9f44eff63aaebc548ef46"


class TestR1FidelityContractsBackend:
    """
    R1 Contract Test Suite: Defines observable failing contracts for all fidelity defects
    identified in phase R0.
    """

    def test_r1_01_normalization_preserves_compound_words_with_control_char(self):
        """
        R1-01: 'Во\x1eвторых' must NOT become 'Вовторых'.
        It must normalize to 'Во-вторых' with recorded reversible provenance.
        """
        res = normalize_text("Во\x1eвторых, несмотря на то")
        assert "Вовторых" not in res.normalized_text, "Regression: separator was silently dropped"
        assert "Во-вторых" in res.normalized_text, f"Expected 'Во-вторых', got '{res.normalized_text}'"
        assert len(res.operations) > 0, "Expected reversible normalization operation to be recorded"
        op = res.operations[0]
        assert op["kind"] in ("soft_hyphen_dehyphenation", "control_char_hyphen")
        assert op["original_separator"] == "\x1e"

    def test_r1_02_normalization_preserves_numeric_and_scripture_ranges(self):
        """
        R1-02: '2.6\x1e11', '2\x1e5', '7\x1e8', '10\x1e11' must NOT become '2.611', '25', '78', '1011'.
        Range separators must be normalized to en-dash '–' or hyphen '-', never empty string.
        """
        cases = [
            ("Фил. 2.6\x1e11", ["2.6–11", "2.6-11"], "2.611"),
            ("главы 2\x1e5", ["2–5", "2-5"], "25"),
            ("стихах 7\x1e8", ["7–8", "7-8"], "78"),
            ("стихах 10\x1e11", ["10–11", "10-11"], "1011"),
            ("две\x1eтри проповеди", ["две-три", "две–три"], "дветри"),
        ]
        for raw, expected_options, forbidden in cases:
            res = normalize_text(raw)
            assert forbidden not in res.normalized_text, f"Range collapsed: '{forbidden}' found in '{res.normalized_text}'"
            assert any(opt in res.normalized_text for opt in expected_options), (
                f"Range not preserved in '{raw}': got '{res.normalized_text}', expected one of {expected_options}"
            )

    @pytest.mark.skipif(not OSBORNE_PDF.exists(), reason="Osborne PDF required for integration test")
    def test_r1_03_page_46_preserves_continuous_paragraph_and_list_flow(self):
        """
        R1-03: Page 46 must NOT split a single sentence/paragraph into 4 fragmented blocks
        across 'привле'/'кает', 'прилагатель'/'ные', 'разви'/'тие'.
        """
        doc = fitz.open(str(OSBORNE_PDF))
        page = doc[45] # 1-based page 46
        builder = DocumentAstBuilder(slug="osborne", source_sha256=OSBORNE_SHA256)
        ast_page = builder.build_page(page, page_index=45)
        doc.close()

        # Gather all paragraph texts
        body_texts = [
            "".join(r.text for r in b.runs)
            for b in ast_page.blocks
            if isinstance(b, ParagraphBlock)
        ]
        
        # Check that 'привле' is followed by 'кает' in the same paragraph
        broken_fragments = [t for t in body_texts if t.endswith("привле") or t.startswith("кает")]
        assert not broken_fragments, f"Paragraph was cut across line break: {broken_fragments}"
        
        # Must contain the list sequence (1), (2), (3) within proper flow
        full_text = " ".join(body_texts)
        assert "(1)" in full_text and "(2)" in full_text and "(3)" in full_text

    @pytest.mark.skipif(not OSBORNE_PDF.exists(), reason="Osborne PDF required for integration test")
    def test_r1_04_page_50_diagram_precedes_bottom_prose(self):
        """
        R1-04: Page 50 geometry-aware reading order: Diagram (Phil. 2:6-11) is located
        at top of page and MUST precede the bottom prose ('экзегезы. Во-вторых...').
        """
        doc = fitz.open(str(OSBORNE_PDF))
        page = doc[49] # 1-based page 50
        builder = DocumentAstBuilder(slug="osborne", source_sha256=OSBORNE_SHA256)
        ast_page = builder.build_page(page, page_index=49)
        doc.close()

        # Find position of prose paragraph "экзегезы"
        prose_idx = None
        diagram_idx = None

        for idx, block in enumerate(ast_page.blocks):
            if isinstance(block, FigureBlock):
                diagram_idx = idx
            elif isinstance(block, ParagraphBlock):
                text = "".join(r.text for r in block.runs)
                if "экзегезы" in text or "Во-вторых" in text or "Вовторых" in text:
                    prose_idx = idx

        assert diagram_idx is not None, "Page 50 must have at least one FigureBlock"
        assert prose_idx is not None, "Page 50 must contain prose paragraph 'экзегезы'"
        assert diagram_idx < prose_idx, f"Diagram (idx={diagram_idx}) must precede prose (idx={prose_idx})"

    @pytest.mark.skipif(not OSBORNE_PDF.exists(), reason="Osborne PDF required for integration test")
    def test_r1_05_vector_drawings_create_figure_blocks(self):
        """
        R1-05: Pages 45 (43 drawings) and 50 (48 drawings) have 0 raster images,
        but MUST produce FigureBlock representations from vector drawings.
        """
        doc = fitz.open(str(OSBORNE_PDF))
        builder = DocumentAstBuilder(slug="osborne", source_sha256=OSBORNE_SHA256)
        
        ast_p45 = builder.build_page(doc[44], page_index=44)
        ast_p50 = builder.build_page(doc[49], page_index=49)
        ast_p430 = builder.build_page(doc[429], page_index=429)
        doc.close()

        p45_figures = [b for b in ast_p45.blocks if isinstance(b, FigureBlock)]
        p50_figures = [b for b in ast_p50.blocks if isinstance(b, FigureBlock)]
        p430_figures = [b for b in ast_p430.blocks if isinstance(b, FigureBlock)]

        assert len(p45_figures) >= 2, f"Page 45 has 2 diagrams (Рис. 1.5, 1.6), got {len(p45_figures)} figures"
        assert len(p50_figures) >= 1, f"Page 50 has 1 diagram (Рис. 1.7), got {len(p50_figures)} figures"
        assert len(p430_figures) >= 1, f"Page 430 has 1 diagram (Рис. 13.1), got {len(p430_figures)} figures"

    @pytest.mark.skipif(not OSBORNE_PDF.exists(), reason="Osborne PDF required for integration test")
    def test_r1_06_diagram_text_not_duplicated_as_prose(self):
        """
        R1-06: Text inside the diagram region (e.g. 'Рис. 1.5', 'Рис. 1.6' captions or diagram phrases)
        must not be emitted as regular independent body prose.
        """
        doc = fitz.open(str(OSBORNE_PDF))
        builder = DocumentAstBuilder(slug="osborne", source_sha256=OSBORNE_SHA256)
        ast_p45 = builder.build_page(doc[44], page_index=44)
        doc.close()

        # Phrases inside Eph 1:5-7 diagram
        diagram_phrases = ["в похвалу", "славы", "благодати Своей", "в Возлюбленном"]
        for b in ast_p45.blocks:
            if isinstance(b, ParagraphBlock):
                text = "".join(r.text for r in b.runs).strip()
                assert text not in diagram_phrases, f"Diagram phrase '{text}' leaked into prose ParagraphBlock"

    @pytest.mark.skipif(not OSBORNE_PDF.exists(), reason="Osborne PDF required for integration test")
    def test_r1_07_caption_linked_to_figure_block(self):
        """
        R1-07: Captions 'Рис. 1.5' and 'Рис. 1.6' must be bound to the respective FigureBlock.
        """
        doc = fitz.open(str(OSBORNE_PDF))
        builder = DocumentAstBuilder(slug="osborne", source_sha256=OSBORNE_SHA256)
        ast_p45 = builder.build_page(doc[44], page_index=44)
        doc.close()

        figures = [b for b in ast_p45.blocks if isinstance(b, FigureBlock)]
        assert len(figures) >= 2
        for fig in figures:
            assert hasattr(fig, "caption") and fig.caption, f"FigureBlock {fig.id} lacks bound caption"

    def test_r1_08_fidelity_validator_rejects_missing_media_and_dropped_digits(self):
        """
        R1-08: FidelityValidator must reject pages with dropped digits in verse ranges
        or missing figure evidence when drawings exist.
        """
        validator = FidelityValidator()
        
        # 1. Dropped digit test: raw has "2.6-11", normalized has "2.611"
        res_digits = validator.validate_multiset_digits(
            raw_text="Фил. 2.6-11",
            normalized_text="Фил. 2.611"
        )
        assert res_digits["status"] == "FAIL", "Validator must fail when '1' digit count drops"

        # 2. Missing figure test: page has vector drawings but 0 FigureBlocks
        if hasattr(validator, "validate_figures_presence"):
            res_fig = validator.validate_figures_presence(
                drawings_count=43,
                figure_blocks_count=0
            )
            assert res_fig["status"] == "FAIL", "Validator must fail when 43 drawings have 0 FigureBlocks"
