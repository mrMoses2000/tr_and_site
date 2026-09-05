import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
import fitz

from .models import SourceDocumentRecord

CORPUS_REGISTRY: List[Dict[str, Any]] = [
    {
        "title": "Merrill C. Tenney, «Обзор Нового Завета»",
        "sha256": "20eb70f061dfd70fab33157f4b93579ed900588fad73f2a161f504b09651029f",
        "pages": 492,
        "risk": "image-only двухстраничные развороты и дубликаты",
    },
    {
        "title": "«Деяния Апостолов»",
        "sha256": "b7cc8d4c3e2edb6a1af221736c8dedcb5236be9106ea754707967413a9368cc8",
        "pages": 91,
        "risk": "native good; авторство нельзя выводить из filename",
    },
    {
        "title": "George Eldon Ladd, «Богословие Нового Завета»",
        "sha256": "a937e6782d423f2a3d11955575c5b958f6b8b68584be0c40e05192785a916b91",
        "pages": 802,
        "risk": "ClearScan, intrusive spacing, footnotes",
    },
    {
        "title": "Leon Morris, «Теология Нового Завета»",
        "sha256": "8d5286389d86dbbdfb8559c0a623ac0dc0912145744b36a0d850b966512a1588",
        "pages": 394,
        "risk": "bad Unicode/font map",
    },
    {
        "title": "Fee/Stewart, «Как читать Библию…»",
        "sha256": "9276959c80dc700f43eca305224a96612eb08e28c7d6b2d8c6f0f0c6ce218823",
        "pages": 146,
        "risk": "native good, quotations, TOC в конце",
    },
    {
        "title": "Walter Kaiser Jr., «На пути к экзегетическому богословию»",
        "sha256": "ad031f02204d5e8c91eecfbcc7e0f83a2131b6a3c1664ac8c3d9ff7fcad24b39",
        "pages": 144,
        "risk": "metadata author конфликтует с title page",
    },
]


def compute_file_sha256(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def inventory_corpus(search_paths: List[Path]) -> List[SourceDocumentRecord]:
    """
    Discovers available sources across incoming and processed paths by strict SHA-256 matching.
    Missing sources are recorded as MISSING_SOURCE without raising errors or downloading.
    """
    found_by_hash: Dict[str, Path] = {}
    for search_dir in search_paths:
        if not search_dir.exists():
            continue
        for pdf_file in search_dir.rglob("*.pdf"):
            try:
                file_hash = compute_file_sha256(pdf_file)
                found_by_hash[file_hash] = pdf_file
            except Exception:
                pass

    now_iso = datetime.now(timezone.utc).isoformat()
    records: List[SourceDocumentRecord] = []

    for item in CORPUS_REGISTRY:
        target_hash = item["sha256"]
        if target_hash in found_by_hash:
            actual_path = found_by_hash[target_hash]
            doc = fitz.open(str(actual_path))
            pages = len(doc)
            doc.close()
            records.append(
                SourceDocumentRecord(
                    sha256=target_hash,
                    original_filename=actual_path.name,
                    storage_path=str(actual_path),
                    byte_size=actual_path.stat().st_size,
                    page_count=pages,
                    created_at=now_iso,
                    status="STORED",
                )
            )
        else:
            records.append(
                SourceDocumentRecord(
                    sha256=target_hash,
                    original_filename=item["title"],
                    storage_path="",
                    byte_size=0,
                    page_count=item["pages"],
                    created_at=now_iso,
                    status="MISSING_SOURCE",
                )
            )

    return records
