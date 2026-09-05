import hashlib
from typing import Optional
import fitz

from .models import (
    PageClassification,
    PageEvidenceRecord,
    RawCandidate,
    RouterSignals,
)


class PageClassifier:
    def classify_page(
        self,
        doc: fitz.Document,
        page_index: int,
        prev_render_hash: Optional[str] = None,
    ) -> PageEvidenceRecord:
        page = doc[page_index]
        rect = page.rect
        width_pt = float(rect.width)
        height_pt = float(rect.height)
        rotation = page.rotation

        # Render raster at 72 dpi for deterministic render fingerprinting
        pix = page.get_pixmap(dpi=72)
        render_hash = hashlib.sha256(pix.tobytes()).hexdigest()

        is_spread = (width_pt / max(height_pt, 1.0)) > 1.2
        is_duplicate_render = (prev_render_hash is not None and render_hash == prev_render_hash)

        raw_text = page.get_text("text") or ""
        char_count = len(raw_text)

        # Count replacement & unprintable control characters or unmapped glyph indicator (\u00b7 / \ufffd)
        replacement_chars = sum(
            1 for c in raw_text if c in ("\ufffd", "\u00b7") or (ord(c) < 32 and c not in "\n\r\t")
        )
        replacement_char_rate = replacement_chars / max(char_count, 1)

        cyrillic_chars = sum(1 for c in raw_text if "\u0400" <= c <= "\u04ff")
        valid_cyrillic_rate = cyrillic_chars / max(char_count, 1)

        images = page.get_images()
        image_coverage = 0.0
        if images:
            # Approximate image coverage
            total_img_area = sum(
                float(img[2] * img[3]) for img in images if len(img) >= 4
            )
            page_area = max(width_pt * height_pt, 1.0)
            image_coverage = min(total_img_area / page_area, 1.0)

        fonts = page.get_fonts()
        font_count = len(fonts)

        signals = RouterSignals(
            char_count=char_count,
            valid_cyrillic_rate=valid_cyrillic_rate,
            replacement_char_rate=replacement_char_rate,
            image_coverage=image_coverage,
            has_to_unicode=True,
            font_count=font_count,
            is_duplicate_render=is_duplicate_render,
            is_spread=is_spread,
        )

        findings: list[str] = []
        if is_duplicate_render:
            findings.append("duplicate_spread_or_render")

        if replacement_char_rate > 0.05:
            findings.append("bad_unicode_rate_high")

        # Metadata conflict check on title pages
        if page_index <= 1:
            meta = doc.metadata or {}
            meta_author = (meta.get("author") or "").lower().strip()
            meta_title = (meta.get("title") or "").lower().strip()
            suspicious_authors = ["admin", "administrator", "unknown", "indesign", "adobe"]
            suspicious_titles = ["untitled", "untitled book", "layout", "in print"]
            if any(s in meta_author for s in suspicious_authors) and char_count > 20:
                findings.append("metadata_author_title_conflict")
            elif any(s in meta_title for s in suspicious_titles) and char_count > 20:
                findings.append("metadata_author_title_conflict")

        cand_hash = f"cand-p{page_index}-{hashlib.sha256(raw_text.encode('utf-8')).hexdigest()[:8]}"
        candidates = [
            RawCandidate(
                method="native",
                text=raw_text,
                candidate_hash=cand_hash,
                confidence=1.0 - replacement_char_rate,
            )
        ]

        # Route classification
        if is_duplicate_render:
            classification = PageClassification.IMAGE_ONLY_SPREAD if is_spread else PageClassification.NEEDS_REVIEW
        elif replacement_char_rate > 0.05:
            classification = PageClassification.BAD_UNICODE_FONT_MAP
        elif image_coverage > 0.8 and char_count > 0:
            classification = PageClassification.CLEAR_SCAN_TEXT_LAYER
        elif char_count == 0:
            classification = PageClassification.IMAGE_ONLY_SPREAD if len(images) > 0 else PageClassification.BLANK_OR_TERMINAL
        elif is_spread and char_count < 50 and len(images) > 0:
            classification = PageClassification.IMAGE_ONLY_SPREAD
        else:
            classification = PageClassification.NATIVE_GOOD

        return PageEvidenceRecord(
            pdf_page_index=page_index,
            rendered_side="full",
            rotation=rotation,
            width_pt=width_pt,
            height_pt=height_pt,
            render_hash=render_hash,
            classification=classification,
            router_signals=signals,
            candidates=candidates,
            findings=findings,
        )
