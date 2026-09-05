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
    def __init__(self, slug: str = "book", source_sha256: Optional[str] = None):
        self.slug = slug
        self.source_sha256 = source_sha256

    @staticmethod
    def _validate_source_sha256(source_sha256: Optional[str]) -> str:
        if not source_sha256 or not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha256):
            raise ValueError(
                "A verified 64-character source_sha256 is required to build a published AST"
            )
        return source_sha256.lower()

    @staticmethod
    def _normalize_runs(
        runs: List[InlineRun],
        block_id: str,
        normalization_provenance: List[Dict[str, Any]],
    ) -> None:
        """Normalize runs while preserving each run's marks and source anchor.

        PyMuPDF may split a visual line break into two spans, so a soft
        hyphen can be the final characters of one run while the continuation
        word starts in the next run (for example ``арсе#\\n`` + ``нале``).
        Normalizing each run independently misses that case.  Remove only the
        separator from the first run; keeping both runs means their marks and
        source bboxes remain intact and the renderer still joins them into one
        word.
        """
        for run in runs:
            normalized = normalize_text(run.text)
            if normalized.operations:
                normalization_provenance.append(
                    {
                        "block_id": block_id,
                        "run_id": run.id,
                        "raw_text": normalized.raw_text,
                        "normalized_text": normalized.normalized_text,
                        "operations": normalized.operations,
                    }
                )
            run.text = normalized.normalized_text

        for idx in range(1, len(runs) - 1):
            curr = runs[idx]
            if curr.text in ("\x1e", "#", "\x1e\n", "#\n"):
                prev = runs[idx - 1]
                nxt = runs[idx + 1]
                if re.search(r"[а-яА-ЯёЁa-zA-Z]+$", prev.text) and re.match(r"[а-яА-ЯёЁa-zA-Z]+", nxt.text):
                    sep = curr.text
                    curr.text = ""
                    normalization_provenance.append({
                        "block_id": block_id,
                        "run_id": curr.id,
                        "run_ids": [prev.id, curr.id, nxt.id],
                        "raw_text": prev.text + sep + nxt.text,
                        "normalized_text": prev.text + nxt.text,
                        "operations": [{
                            "kind": "line_end_dehyphenation",
                            "raw_range": [len(prev.text), len(prev.text) + len(sep)],
                            "normalized_range": [len(prev.text), len(prev.text)],
                            "original_separator": sep,
                            "reason": "isolated_separator_span",
                            "confidence": 0.99,
                        }],
                    })

        separator_pattern = re.compile(r"(?P<separator>#\n?|\x1e\n?|-\n)$")
        word_pattern = re.compile(r"[а-яА-ЯёЁa-zA-Z]+")
        for previous, following in zip(runs, runs[1:]):
            if not previous.text or not following.text:
                continue
            previous_raw = previous.text
            following_raw = following.text
            separator_match = separator_pattern.search(previous_raw)
            if not separator_match or not re.match(r"[а-яА-ЯёЁa-zA-Z]", following_raw):
                continue

            separator = separator_match.group("separator")
            previous.text = previous_raw[: separator_match.start()]
            prefix_match = re.search(r"[а-яА-ЯёЁa-zA-Z]+$", previous.text)
            following_match = word_pattern.match(following_raw)
            if not prefix_match or not following_match:
                previous.text = previous_raw
                continue

            normalized_start = prefix_match.start()
            normalized_end = len(previous.text) + following_match.end()
            normalization_provenance.append(
                {
                    "block_id": block_id,
                    "run_id": f"{previous.id}+{following.id}",
                    "run_ids": [previous.id, following.id],
                    "raw_text": previous_raw + following_raw,
                    "normalized_text": previous.text + following_raw,
                    "operations": [
                        {
                            "kind": "line_end_dehyphenation",
                            "raw_range": [separator_match.start(), len(previous_raw)],
                            "normalized_range": [normalized_start, normalized_end],
                            "original_separator": separator,
                            "reason": "visual_line_continuation+lexicon",
                            "confidence": 0.98,
                        }
                    ],
                }
            )

    @staticmethod
    def _should_merge_blocks(prev_b: Dict[str, Any], curr_b: Dict[str, Any]) -> bool:
        if prev_b.get("_kind") == "image" or curr_b.get("_kind") == "image":
            return False
        if prev_b.get("type", 0) != 0 or curr_b.get("type", 0) != 0:
            return False

        prev_lines = prev_b.get("lines", [])
        curr_lines = curr_b.get("lines", [])
        if not prev_lines or not curr_lines:
            return False

        prev_spans = [
            s.get("text", "")
            for l in prev_lines
            for s in l.get("spans", [])
            if s.get("text", "")
        ]
        curr_spans = [
            s.get("text", "")
            for l in curr_lines
            for s in l.get("spans", [])
            if s.get("text", "")
        ]
        if not prev_spans or not curr_spans:
            return False

        prev_end_text = prev_spans[-1].strip()
        curr_start_text = curr_spans[0].strip()
        if not prev_end_text or not curr_start_text:
            return False

        prev_max_size = max(
            (float(s.get("size", 10.0)) for l in prev_lines for s in l.get("spans", [])),
            default=10.0,
        )
        curr_max_size = max(
            (float(s.get("size", 10.0)) for l in curr_lines for s in l.get("spans", [])),
            default=10.0,
        )
        if prev_max_size >= 14.0 or curr_max_size >= 14.0:
            return False

        prev_bbox = prev_b.get("bbox", [0, 0, 0, 0])
        curr_bbox = curr_b.get("bbox", [0, 0, 0, 0])
        gap = curr_bbox[1] - prev_bbox[3]

        if abs(prev_bbox[0] - curr_bbox[0]) > 30:
            return False

        ends_with_hyphen = bool(re.search(r"(\x1e|#|-)$", prev_end_text))
        if ends_with_hyphen and gap <= 12.0:
            return True

        starts_lowercase = bool(re.match(r"^[а-яёa-z]", curr_start_text))
        ends_sentence = bool(re.search(r"[\.!\?…:]$", prev_end_text))
        if starts_lowercase and not ends_sentence and gap <= 6.0:
            return True

        return False

    @classmethod
    def _merge_adjacent_blocks(cls, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not blocks:
            return []
        merged: List[Dict[str, Any]] = [blocks[0]]
        for b in blocks[1:]:
            prev = merged[-1]
            if cls._should_merge_blocks(prev, b):
                prev["lines"].extend(b.get("lines", []))
                p_bbox = prev.get("bbox", [0, 0, 0, 0])
                c_bbox = b.get("bbox", [0, 0, 0, 0])
                prev["bbox"] = [
                    min(p_bbox[0], c_bbox[0]),
                    min(p_bbox[1], c_bbox[1]),
                    max(p_bbox[2], c_bbox[2]),
                    max(p_bbox[3], c_bbox[3]),
                ]
            else:
                merged.append(b)
        return merged

    def build_page(
        self,
        page: fitz.Page,
        page_index: int,
        source_sha256: Optional[str] = None,
        printed_page_label: Optional[str] = None,
    ) -> DocumentPage:
        source_hash = self._validate_source_sha256(source_sha256 or self.source_sha256)
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
        normalization_provenance: List[Dict[str, Any]] = []

        image_infos = []
        try:
            image_infos = page.get_image_info(xrefs=True)
        except (AttributeError, TypeError, RuntimeError):
            image_infos = []
        image_xrefs = [info.get("xref") for info in image_infos]
        image_digests = [info.get("digest") for info in image_infos]

        # Header cutoff: top 8% of page
        header_cutoff = page_height * 0.08
        # Footnote cutoff: bottom 25% of page
        fn_cutoff = page_height * 0.75

        for b in raw_blocks:
            b_type = b.get("type", 0)
            bbox = b.get("bbox", [0, 0, 0, 0])
            y0, y1 = bbox[1], bbox[3]

            if b_type == 1:
                # Keep image blocks in source order.  The actual bytes remain
                # in the immutable PDF; image_ref is a stable evidence ref.
                image_index = sum(1 for item in body_blocks if item.get("_kind") == "image")
                xref = image_xrefs[image_index] if image_index < len(image_xrefs) else None
                body_blocks.append(
                    {
                        "_kind": "image",
                        "bbox": bbox,
                        "image_index": image_index,
                        "xref": xref,
                    }
                )
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
                normalized_fn = normalize_text(fn_text)
                if normalized_fn.operations:
                    normalization_provenance.append(
                        {
                            "block_id": fn_id,
                            "run_id": f"{fn_id}-r0",
                            "raw_text": normalized_fn.raw_text,
                            "normalized_text": normalized_fn.normalized_text,
                            "operations": normalized_fn.operations,
                        }
                    )
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
                                    text=normalized_fn.normalized_text,
                                    language="ru",
                                    source=SourceAnchor(
                                        sourceSha256=source_hash,
                                        pdfPageIndex=page_index,
                                        bbox=[float(v) for v in bbox],
                                        extractionMethod="native",
                                        candidateHash=(
                                            f"cand-p{page_index}-"
                                            f"{hashlib.sha256(fn_text.encode('utf-8')).hexdigest()[:8]}"
                                        ),
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
        text_body_blocks = [b for b in body_blocks if b.get("_kind") != "image"]
        if len(text_body_blocks) >= 2:
            midpoint = page_width / 2.0
            col1 = [b for b in text_body_blocks if b.get("bbox", [0])[0] < midpoint and b.get("bbox", [0, 0, 0])[2] <= midpoint * 1.15]
            col2 = [b for b in text_body_blocks if b.get("bbox", [0])[0] >= midpoint * 0.85]

            # If both columns have multiple distinct blocks
            if len(col1) >= 2 and len(col2) >= 2 and (len(col1) + len(col2)) >= len(body_blocks) * 0.75:
                layout_detected = "two_column"
                image_blocks = [b for b in body_blocks if b.get("_kind") == "image"]
                # Keep the original source order when figures are present;
                # moving all figures to the end would silently change their
                # relationship to surrounding text.  A future layout pass
                # can place them by bbox without losing them in the interim.
                if not image_blocks:
                    col1.sort(key=lambda b: b.get("bbox", [0, 0])[1])
                    col2.sort(key=lambda b: b.get("bbox", [0, 0])[1])
                    body_blocks = col1 + col2
            elif any("Схематическое" in b.get("lines", [{}])[0].get("spans", [{}])[0].get("text", "") for b in body_blocks):
                layout_detected = "schematic"
        # 4. Convert body blocks into AST HeadingBlock or ParagraphBlock
        body_blocks = self._merge_adjacent_blocks(body_blocks)
        ast_blocks: List[Any] = []
        for idx, b in enumerate(body_blocks):
            blk_id = f"blk-{self.slug}-p{page_index}-{idx}"

            if b.get("_kind") == "image":
                image_index = b.get("image_index", idx)
                xref = b.get("xref")
                image_token = xref if xref is not None else image_index
                digest = image_digests[image_index] if image_index < len(image_digests) else None
                if isinstance(digest, bytes):
                    digest = digest.hex()
                if not digest and xref is not None:
                    try:
                        parent_doc = page.parent
                        extracted = parent_doc.extract_image(xref) if parent_doc else None
                        image_bytes = (extracted or {}).get("image")
                        if image_bytes:
                            digest = hashlib.sha256(image_bytes).hexdigest()
                    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
                        digest = None
                candidate_hash = (
                    f"cand-image-p{page_index}-"
                    f"{digest or hashlib.sha256(str(image_token).encode('utf-8')).hexdigest()}"
                )
                ast_blocks.append(
                    FigureBlock(
                        id=blk_id,
                        image_ref=f"pdf-page://{page_index}/image/{image_token}",
                        source=SourceAnchor(
                            sourceSha256=source_hash,
                            pdfPageIndex=page_index,
                            bbox=[float(v) for v in b.get("bbox", ())],
                            extractionMethod="native",
                            candidateHash=candidate_hash,
                        ),
                    )
                )
                continue

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
                            sourceSha256=source_hash,
                            pdfPageIndex=page_index,
                            bbox=[float(v) for v in span.get("bbox", ())],
                            extractionMethod="native",
                            candidateHash=cand_hash,
                        ),
                    )
                    runs.append(run)

            full_block_text = full_block_text.strip()
            heading_triggers = ["ГЛАВА", "ЧАСТЬ", "ПРЕДИСЛОВИЕ", "БИБЛИОГРАФИЯ", "Схематическое"]
            if max_font_size >= 14.0 or (len(full_block_text) < 80 and any(t in full_block_text for t in heading_triggers)):
                is_heading = True

            # Normalize run texts reversibly, including separators split across
            # adjacent PyMuPDF spans.  Run-level style and source anchors stay
            # attached to their original run objects.
            self._normalize_runs(runs, blk_id, normalization_provenance)

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
            printed_label=printed_page_label,
            running_headers=running_headers,
            blocks=ast_blocks,
            footnotes=footnote_blocks,
            layout_detected=layout_detected,
            review_status=review_status,
            normalization_provenance=normalization_provenance,
        )
