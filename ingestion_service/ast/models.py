from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field

from ingestion_service.v2.contracts import InlineRun, SourceAnchor


class HeadingBlock(BaseModel):
    type: Literal["heading"] = "heading"
    id: str
    level: int = 1
    runs: List[InlineRun] = Field(default_factory=list)


class ParagraphBlock(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    id: str
    runs: List[InlineRun] = Field(default_factory=list)


class QuotationBlock(BaseModel):
    type: Literal["quotation"] = "quotation"
    id: str
    runs: List[InlineRun] = Field(default_factory=list)
    attribution: Optional[List[InlineRun]] = None


class ListBlock(BaseModel):
    type: Literal["list"] = "list"
    id: str
    ordered: bool = False
    items: List[List[Any]] = Field(default_factory=list)


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    id: str
    rows: List[List[List[InlineRun]]] = Field(default_factory=list)
    fallback_image_ref: Optional[str] = None


class FigureBlock(BaseModel):
    type: Literal["figure"] = "figure"
    id: str
    image_ref: str
    caption: Optional[List[InlineRun]] = None
    alt: Optional[str] = None


class FootnoteBlock(BaseModel):
    type: Literal["footnote"] = "footnote"
    id: str
    label: str
    anchors: List[str] = Field(default_factory=list)
    blocks: List[Any] = Field(default_factory=list)


class PageBreakBlock(BaseModel):
    type: Literal["pageBreak"] = "pageBreak"
    id: str
    pdf_page_index: int
    printed_page_label: Optional[str] = None


class DocumentPage(BaseModel):
    page_index: int
    printed_label: Optional[str] = None
    running_headers: List[str] = Field(default_factory=list)
    blocks: List[Any] = Field(default_factory=list)
    footnotes: List[FootnoteBlock] = Field(default_factory=list)
    layout_detected: str = "single_column"
    review_status: str = "verified"
