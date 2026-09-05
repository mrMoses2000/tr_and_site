import json
import shutil
import subprocess
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Mapping
from .config import APP_DIR, APP_PUBLIC_SCANS_DIR, APP_DATA_DIR

logger = logging.getLogger(__name__)

class PublisherError(Exception):
    pass


def build_manifest_data(
    slug: str,
    metadata: Mapping[str, Any],
    pages: List[Dict[str, Any]],
    *,
    release_id: str | None = None,
) -> Dict[str, Any]:
    """Build a reader manifest without writing to the active checkout.

    The ingestion pipeline still exposes the historical V1-shaped fields for
    the current reader.  The release contract fields are included alongside
    them so the staged validator can fence a complete artifact and the V2
    reader can migrate without rewriting every existing book at once.
    """
    formatted_pages = []
    for page in pages:
        page_copy = dict(page)
        page_number = page_copy.get("pageNumber", 1)
        page_copy["imageSrc"] = f"/scans/{slug}/page_{page_number}.webp"
        formatted_pages.append(page_copy)

    total_pages = len(formatted_pages)
    start_page = formatted_pages[0]["pageNumber"] if formatted_pages else 1
    end_page = formatted_pages[-1]["pageNumber"] if formatted_pages else 1
    toc = metadata.get("tableOfContents") or metadata.get("toc") or []
    if not toc:
        toc = [{
            "pageNumber": start_page,
            "titleEn": "Chapter 1",
            "titleRu": "Глава 1",
            "level": 1,
        }]

    return {
        "schemaVersion": "2.0",
        "releaseId": release_id or f"rel-{slug}-unpublished",
        "slug": slug,
        "title": metadata.get("title", slug),
        "titleRu": metadata.get("titleRu") or metadata.get("title", slug),
        "subtitle": metadata.get("subtitle", ""),
        "subtitleRu": metadata.get("subtitleRu", ""),
        "author": metadata.get("author", "Unknown"),
        "authorRu": metadata.get("authorRu") or metadata.get("author", "Неизвестный автор"),
        "publisher": metadata.get("publisher", ""),
        "targetLanguage": metadata.get("targetLanguage", "kk"),
        "sourceLanguage": metadata.get("sourceLanguage", "auto"),
        "startPage": start_page,
        "endPage": end_page,
        "totalPages": total_pages,
        "pageRange": {"start": start_page, "end": end_page},
        "tableOfContents": toc,
        "pages": formatted_pages,
    }

class BookPublisher:
    """
    Publisher service responsible for compiling translated book manifests,
    copying high-res WebP scans, verifying frontend tests (Vitest),
    and preparing reader artifacts for a separate release adapter.
    """

    def __init__(self, app_dir: Path = APP_DIR):
        self.app_dir = app_dir
        self.public_scans_dir = app_dir / "public" / "scans"
        self.books_data_dir = app_dir / "src" / "data" / "books"

    async def compile_manifest(
        self,
        slug: str,
        metadata: Dict[str, Any],
        pages: List[Dict[str, Any]],
        scans_source_dir: Path
    ) -> Path:
        """
        Copies scans and generates manifest.json for the reader.
        """
        # 1. Target scan directory in public/scans/{slug}
        target_scans_dir = self.public_scans_dir / slug
        target_scans_dir.mkdir(parents=True, exist_ok=True)

        if scans_source_dir.exists():
            for scan_file in scans_source_dir.glob("*.webp"):
                shutil.copy2(scan_file, target_scans_dir / scan_file.name)

        # 3. Assemble book manifest.  This method intentionally preserves its
        # historical checkout-writing behavior; production uses the staged
        # builder below the release boundary.
        manifest = build_manifest_data(slug, metadata, pages)

        # 4. Save manifest in app/src/data/books/{slug}/manifest.json
        target_book_dir = self.books_data_dir / slug
        target_book_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = target_book_dir / "manifest.json"
        
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        logger.info(f"Manifest successfully written to {manifest_file}")
        return manifest_file

    async def run_quality_gate(self) -> bool:
        """
        Executes Vitest test suite.
        Enforces test-first quality standard before release promotion.
        """
        logger.info("Running Vitest test suite quality gate...")
        proc = await asyncio.create_subprocess_exec(
            "npm", "test",
            cwd=str(self.app_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")
            out_msg = stdout.decode("utf-8", errors="replace")
            raise PublisherError(f"Quality gate failed (npm test exited with {proc.returncode}):\n{out_msg}\n{err_msg}")
        
        logger.info("Quality gate passed: all tests green.")
        return True
