import hashlib
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator

LanguageCode = Literal["ru", "kk", "en", "grc", "he", "und"]
ExtractionMethod = Literal["native", "ocr", "vision", "manual"]


class SourceAnchor(BaseModel):
    sourceSha256: str = "sha256-untracked"
    pdfPageIndex: int
    printedPageLabel: Optional[str] = None
    renderedSide: Optional[Literal["left", "right", "full"]] = None
    bbox: Optional[list[float]] = None
    extractionMethod: ExtractionMethod = "native"
    candidateHash: str
    confidence: Optional[float] = None


class InlineRun(BaseModel):
    id: str
    text: str
    language: str = "ru"
    marks: Optional[list[str]] = None
    source: SourceAnchor


class DocumentBlock(BaseModel):
    type: Literal["heading", "paragraph", "quotation", "list", "table", "figure", "footnote", "pageBreak"]
    id: str
    level: Optional[int] = None
    runs: list[InlineRun] = Field(default_factory=list)
    label: Optional[str] = None
    anchors: Optional[list[str]] = None
    blocks: Optional[list["DocumentBlock"]] = None
    ordered: Optional[bool] = None
    items: Optional[list[list["DocumentBlock"]]] = None
    imageRef: Optional[str] = None
    alt: Optional[str] = None


class PageRange(BaseModel):
    start: int
    end: int

    @model_validator(mode="after")
    def check_range(self):
        if self.start > self.end:
            raise ValueError(f"Invalid pageRange: start ({self.start}) must be <= end ({self.end})")
        return self


class PageV2(BaseModel):
    pageNumber: int
    printedPageLabel: Optional[str] = None
    chapterTitle: Optional[str] = None
    imageSrc: str
    blocks: list[DocumentBlock] = Field(default_factory=list)
    readingTimeMinutes: int = 2


class TocNode(BaseModel):
    id: str
    level: int
    title: dict[str, str]
    pageIndex: int
    printedPageLabel: Optional[str] = None
    targetBlockId: Optional[str] = None
    children: Optional[list["TocNode"]] = None


class Contributor(BaseModel):
    role: str
    name: str
    language: Optional[str] = None


class Citation(BaseModel):
    shortTitle: str
    publisher: Optional[str] = None
    place: Optional[str] = None
    year: Optional[str] = None
    edition: Optional[str] = None


class BookManifestV2(BaseModel):
    schemaVersion: Literal["2.0"] = "2.0"
    slug: str
    releaseId: str
    sourceRevision: str = "rev-v1-baseline"
    title: dict[str, str]
    subtitle: Optional[dict[str, str]] = None
    contributors: list[Contributor] = Field(default_factory=list)
    citation: Citation
    sourceLanguage: str = "ru"
    availableLanguages: list[str] = Field(default_factory=lambda: ["ru"])
    availableViews: list[str] = Field(default_factory=lambda: ["adapted", "scan", "compare"])
    pageRange: PageRange
    assets: dict[str, Any] = Field(default_factory=dict)
    toc: list[TocNode] = Field(default_factory=list)
    pagesIndexUrl: str = ""
    pages: list[PageV2] = Field(default_factory=list)
    audioEditions: Optional[list[dict[str, Any]]] = None

    @model_validator(mode="before")
    @classmethod
    def check_schema_version(cls, data: Any):
        if isinstance(data, dict):
            if data.get("schemaVersion") != "2.0":
                raise ValueError("Unsupported schemaVersion: expected '2.0'")
        return data


def validate_manifest_v2(data: dict) -> BookManifestV2:
    if not isinstance(data, dict):
        raise ValueError("Manifest data must be a dictionary")
    if data.get("schemaVersion") != "2.0":
        raise ValueError("Unsupported schemaVersion: expected '2.0'")
    return BookManifestV2.model_validate(data)


def adapt_manifest_v1_to_v2(v1_data: dict) -> BookManifestV2:
    slug = v1_data.get("slug") or "book"
    source_lang = v1_data.get("sourceLanguage") or "ru"

    pages_data = v1_data.get("pages", [])
    has_distinct_en = False
    for p in pages_data:
        for para in p.get("paragraphs", []):
            en_val = (para.get("en") or "").strip()
            ru_val = (para.get("ru") or "").strip()
            if en_val and ru_val and en_val != ru_val:
                has_distinct_en = True
                break
        if has_distinct_en:
            break

    available_languages = ["en", "ru"] if has_distinct_en else [source_lang]

    contributors = []
    author = v1_data.get("author")
    if author:
        contributors.append(Contributor(role="author", name=author, language=source_lang))

    pages_v2: list[PageV2] = []
    for p in pages_data:
        p_num = p.get("pageNumber", 1)
        blocks: list[DocumentBlock] = []
        for idx, para in enumerate(p.get("paragraphs", [])):
            blk_id = f"blk-{slug}-p{p_num}-{idx}"
            text = para.get("ru") or para.get("en") or ""
            cand_hash = f"cand-p{p_num}-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]}"
            anchor = SourceAnchor(
                sourceSha256="sha256-v1-untracked",
                pdfPageIndex=p_num,
                extractionMethod="native",
                candidateHash=cand_hash,
            )
            run = InlineRun(
                id=f"{blk_id}-r0",
                text=text,
                language="ru",
                source=anchor,
            )
            blocks.append(DocumentBlock(type="paragraph", id=blk_id, runs=[run]))

        pages_v2.append(
            PageV2(
                pageNumber=p_num,
                chapterTitle=p.get("chapterTitle"),
                imageSrc=p.get("imageSrc", ""),
                blocks=blocks,
                readingTimeMinutes=p.get("readingTimeMinutes", 2),
            )
        )

    start_p = v1_data.get("startPage", 1)
    end_p = v1_data.get("endPage", start_p)
    total_p = v1_data.get("totalPages", end_p - start_p + 1)
    rel_id = f"rel-{slug}-p{start_p}-{total_p}"

    manifest = BookManifestV2(
        schemaVersion="2.0",
        slug=slug,
        releaseId=rel_id,
        sourceRevision="rev-v1-baseline",
        title={"ru": v1_data.get("titleRu") or v1_data.get("title", ""), "en": v1_data.get("title", "")},
        contributors=contributors,
        citation=Citation(shortTitle=v1_data.get("titleRu") or v1_data.get("title", "")),
        sourceLanguage=source_lang,
        availableLanguages=available_languages,
        availableViews=["adapted", "scan", "compare"],
        pageRange=PageRange(start=start_p, end=end_p),
        pagesIndexUrl=f"/books/{slug}/{rel_id}/pages.json",
        pages=pages_v2,
    )
    return manifest
