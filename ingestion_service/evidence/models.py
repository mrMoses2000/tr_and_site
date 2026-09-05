from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class PageClassification(str, Enum):
    NATIVE_GOOD = "native_good"
    CLEAR_SCAN_TEXT_LAYER = "clear_scan_text_layer"
    BAD_UNICODE_FONT_MAP = "bad_unicode_font_map"
    IMAGE_ONLY_SPREAD = "image_only_spread"
    MIXED = "mixed"
    VECTOR_OR_LAYOUT_FIGURE = "vector_or_layout_figure"
    BLANK_OR_TERMINAL = "blank_or_terminal"
    NEEDS_REVIEW = "needs_review"


class RouterSignals(BaseModel):
    char_count: int = 0
    valid_cyrillic_rate: float = 0.0
    replacement_char_rate: float = 0.0
    image_coverage: float = 0.0
    # This is an observed property of the page's font resources.  It must not
    # default to True merely because a text layer exists.
    has_to_unicode: bool = False
    font_count: int = 0
    is_duplicate_render: bool = False
    is_spread: bool = False


class RawCandidate(BaseModel):
    method: Literal["native", "ocr", "vision", "manual"]
    text: str
    candidate_hash: str
    confidence: float = 1.0


class ImageEvidence(BaseModel):
    """A reference to an image resource preserved from a PDF page."""

    index: int
    xref: Optional[int] = None
    bbox: list[float] = Field(default_factory=list)
    width: Optional[int] = None
    height: Optional[int] = None
    image_hash: Optional[str] = None


class PageEvidenceRecord(BaseModel):
    pdf_page_index: int
    rendered_side: Literal["left", "right", "full"] = "full"
    printed_label: Optional[str] = None
    rotation: int = 0
    width_pt: float
    height_pt: float
    render_hash: str
    classification: PageClassification
    router_signals: RouterSignals
    candidates: list[RawCandidate] = Field(default_factory=list)
    image_evidence: list[ImageEvidence] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)


class SourceDocumentRecord(BaseModel):
    sha256: str
    original_filename: str
    storage_path: str
    byte_size: int
    page_count: int
    created_at: str
    status: Literal["STORED", "MISSING_SOURCE"] = "STORED"
