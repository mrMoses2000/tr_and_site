import json
import shutil
import subprocess
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List
from .config import APP_DIR, APP_PUBLIC_SCANS_DIR, APP_DATA_DIR

logger = logging.getLogger(__name__)

class PublisherError(Exception):
    pass

class BookPublisher:
    """
    Publisher service responsible for compiling translated book manifests,
    copying high-res WebP scans, verifying frontend tests (Vitest),
    and deploying the updated reader to Netlify.
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

        # 2. Update imageSrc in pages to match /scans/{slug}/page_{num}.webp
        formatted_pages = []
        for p in pages:
            page_copy = dict(p)
            p_num = page_copy.get("pageNumber", 1)
            page_copy["imageSrc"] = f"/scans/{slug}/page_{p_num}.webp"
            formatted_pages.append(page_copy)

        # 3. Assemble book manifest
        total_pages = len(formatted_pages)
        start_page = formatted_pages[0]["pageNumber"] if formatted_pages else 1
        end_page = formatted_pages[-1]["pageNumber"] if formatted_pages else 1

        toc = metadata.get("toc") or []
        if not toc:
            toc = [{"pageNumber": 1, "titleEn": "Chapter 1", "titleRu": "Глава 1", "level": 1}]

        manifest = {
            "slug": slug,
            "title": metadata.get("title", slug),
            "titleRu": metadata.get("titleRu") or metadata.get("title", slug),
            "subtitle": metadata.get("subtitle", ""),
            "subtitleRu": metadata.get("subtitleRu", ""),
            "author": metadata.get("author", "Unknown"),
            "authorRu": metadata.get("authorRu") or metadata.get("author", "Неизвестный автор"),
            "publisher": metadata.get("publisher", ""),
            "startPage": start_page,
            "endPage": end_page,
            "totalPages": total_pages,
            "tableOfContents": toc,
            "pages": formatted_pages
        }

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
        Enforces test-first quality standard before deploying to production.
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

    async def deploy_to_netlify(self, slug: str) -> str:
        """
        Builds the Vite web application and deploys to Netlify production.
        Returns the direct live reader URL.
        """
        logger.info("Building production assets via npm run build...")
        build_proc = await asyncio.create_subprocess_exec(
            "npm", "run", "build",
            cwd=str(self.app_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        b_stdout, b_stderr = await build_proc.communicate()
        if build_proc.returncode != 0:
            raise PublisherError(f"Vite build failed: {b_stderr.decode('utf-8', errors='replace')}")

        logger.info("Deploying to Netlify Production...")
        deploy_proc = await asyncio.create_subprocess_exec(
            "npx", "netlify", "deploy", "--prod", "--dir=dist",
            cwd=str(self.app_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        d_stdout, d_stderr = await deploy_proc.communicate()
        if deploy_proc.returncode != 0:
            raise PublisherError(f"Netlify deployment failed: {d_stderr.decode('utf-8', errors='replace')}")

        out_text = d_stdout.decode("utf-8", errors="replace")
        
        # Base site URL
        base_url = "https://harmonious-hotteok-0204c0.netlify.app"
        for line in out_text.splitlines():
            if "Website URL:" in line:
                parts = line.split("Website URL:")
                if len(parts) > 1:
                    base_url = parts[1].strip()
                    break

        live_url = f"{base_url}/#book={slug}&page=1"
        logger.info(f"Book deployed successfully to {live_url}")
        return live_url
