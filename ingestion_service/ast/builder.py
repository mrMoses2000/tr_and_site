import hashlib
import re
from typing import Any, Dict, List, Optional
import fitz

from ingestion_service.v2.contracts import InlineRun, SourceAnchor
from .models import (
    DocumentPage,
    HeadingBlock,
    ParagraphBlock,
    QuotationBlock,
    ListBlock,
    TableBlock,
    FigureBlock,
    FootnoteBlock,
)
from .normalization import normalize_text


class DocumentAstBuilder:
    def __init__(self, slug: str = "book"):
        self.slug = slug

    def build_page(self, page: fitz.Page, page_index: int) -> DocumentPage:
        rect = page.rect
        page_width = float(rect.width)
        page_height = float(rect.height)

        raw_text = page.get_text("text") or ""

        # 1. Check for corrupt text layer (e.g. Osborne page 736)
        control_chars = sum(
            1 for c in raw_text if c in ("\x0c", "\x1f", "\x1e") or (ord(c) < 32 and c not in "\n\r\t")
        )
        whitespace_ratio = raw_text.count(" ") / max(len(raw_text), 1)
        is_corrupt_layer = (
            control_chars > 20
            or raw_text.count("\x0c") > 5
            or (len(raw_text) > 1000 and whitespace_ratio > 0.45 and control_chars > 5)
        )

        review_status = "corrupt_text_layer" if is_corrupt_layer else "verified"

        # 2. Extract block geometry via dict
        page_dict = page.get_text("dict")
        raw_blocks = page_dict.get("blocks", [])

        running_headers: List[str] = []
        body_blocks: List[Dict[str, Any]] = []
        footnote_blocks: List[FootnoteBlock] = []

        # Header cutoff: top 8% of page
        header_cutoff = page_height * 0.08
        # Footnote cutoff: bottom 25% of page
        fn_cutoff = page_height * 0.75

        for b in raw_blocks:
            b_type = b.get("type", 0)
            bbox = b.get("bbox", [0, 0, 0, 0])
            y0, y1 = bbox[1], bbox[3]

            if b_type == 1:
                # Image block
                continue

            # Text block
            lines = b.get("lines", [])
            block_text = " ".join(
                "".join(span.get("text", "") for span in line.get("spans", ""))
                for line in lines
            ).strip()

            if not block_text:
                continue

            # Check if running header
            if y1 <= header_cutoff and len(block_text) < 100:
                running_headers.append(block_text)
                continue

            # Check if footnote at bottom of page
            is_fn = False
            fn_label = ""
            fn_text = ""
            if y0 >= fn_cutoff:
                # Check for footnote marker like "[1] ", "1. ", "1\t", "²"
                m_fn = re.match(r"^\[?(\d{1,3})\]?[\.\s]\s*(.+)", block_text)
                if m_fn:
                    is_fn = True
                    fn_label = m_fn.group(1)
                    fn_text = m_fn.group(2)

            if is_fn:
                fn_id = f"fn-{self.slug}-p{page_index}-{fn_label}"
                anchor_id = f"fnref-{fn_label}"
                fn_block = FootnoteBlock(
                    id=fn_id,
                    label=fn_label,
                    anchors=[anchor_id],
                    blocks=[
                        ParagraphBlock(
                            id=f"{fn_id}-p",
                            runs=[
                                InlineRun(
                                    id=f"{fn_id}-r0",
                                    text=normalize_text(fn_text).normalized_text,
                                    language="ru",
                                    source=SourceAnchor(
                                        sourceSha256="sha256-evidence",
                                        pdfPageIndex=page_index,
                                        extractionMethod="native",
                                        candidateHash=f"cand-fn-{fn_label}",
                                    ),
                                )
                            ],
                        )
                    ],
                )
                footnote_blocks.append(fn_block)
            else:
                body_blocks.append(b)

        # 3. Layout analysis: detect two-column layout
        layout_detected = "single_column"
        if len(body_blocks) >= 2:
            midpoint = page_width / 2.0
            col1 = [b for b in body_blocks if b.get("bbox", [0])[0] < midpoint and b.get("bbox", [0, 0, 0])[2] <= midpoint * 1.15]
            col2 = [b for b in body_blocks if b.get("bbox", [0])[0] >= midpoint * 0.85]

            # If both columns have multiple distinct blocks
            if len(col1) >= 2 and len(col2) >= 2 and (len(col1) + len(col2)) >= len(body_blocks) * 0.75:
                layout_detected = "two_column"
                # Sort col1 top-to-bottom, then col2 top-to-bottom
                col1.sort(key=lambda b: b.get("bbox", [0, 0])[1])
                col2.sort(key=lambda b: b.get("bbox", [0, 0])[1])
                body_blocks = col1 + col2
            elif any("Схематическое" in b.get("lines", [{}])[0].get("spans", [{}])[0].get("text", "") for b in body_blocks):
                layout_detected = "schematic"

        # 4. Convert body blocks into AST HeadingBlock or ParagraphBlock
        ast_blocks: List[Any] = []
        for idx, b in enumerate(body_blocks):
            blk_id = f"blk-{self.slug}-p{page_index}-{idx}"
            lines = b.get("lines", [])

            # Extract spans and check font sizes / styles
            runs: List[InlineRun] = []
            is_heading = False
            max_font_size = 0.0

            full_block_text = ""
            for l_idx, line in enumerate(lines):
                for s_idx, span in enumerate(line.get("spans", [])):
                    stext = span.get("text", "")
                    if not stext:
                        continue
                    full_block_text += stext + " "
                    fsize = float(span.get("size", 10.0))
                    if fsize > max_font_size:
                        max_font_size = fsize

                    flags = span.get("flags", 0)
                    marks: List[str] = []
                    if flags & 2:  # italic
                        marks.append("italic")
                    if flags & 16 or "bold" in span.get("font", "").lower():
                        marks.append("bold")

                    cand_hash = f"cand-p{page_index}-{hashlib.sha256(stext.encode('utf-8')).hexdigest()[:8]}"
                    run = InlineRun(
                        id=f"{blk_id}-r{l_idx}_{s_idx}",
                        text=stext,
                        language="ru",
                        marks=marks if marks else None,
                        source=SourceAnchor(
                            sourceSha256="sha256-evidence",
                            pdfPageIndex=page_index,
                            extractionMethod="native",
                            candidateHash=cand_hash,
                        ),
                    )
                    runs.append(run)

            full_block_text = full_block_text.strip()
            heading_triggers = ["ГЛАВА", "ЧАСТЬ", "ПРЕДИСЛОВИЕ", "БИБЛИОГРАФИЯ", "Схематическое"]
            if max_font_size >= 14.0 or (len(full_block_text) < 80 and any(t in full_block_text for t in heading_triggers)):
                is_heading = True

            # Normalize run texts reversibly
            for r in runs:
                norm = normalize_text(r.text)
                r.text = norm.normalized_text

            if is_heading:
                ast_blocks.append(
                    HeadingBlock(
                        id=blk_id,
                        level=1 if max_font_size >= 16.0 else 2,
                        runs=runs,
                    )
                )
            else:
                ast_blocks.append(
                    ParagraphBlock(
                        id=blk_id,
                        runs=runs,
                    )
                )

        return DocumentPage(
            page_index=page_index,
            printed_label=str(page_index),
            running_headers=running_headers,
            blocks=ast_blocks,
            footnotes=footnote_blocks,
            layout_detected=layout_detected,
            review_status=review_status,
        )
