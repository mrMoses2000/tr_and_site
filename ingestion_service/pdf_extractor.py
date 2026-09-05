import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import fitz  # PyMuPDF
from PIL import Image

class ExtractedPage:
    def __init__(self, page_number: int, text: str, image_path: Optional[str] = None):
        self.page_number = page_number
        self.text = text
        self.image_path = image_path

class PDFExtractor:
    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.doc = fitz.open(str(self.pdf_path))
        self.total_pages = len(self.doc)

    def get_metadata(self) -> Dict[str, Any]:
        meta = self.doc.metadata or {}
        toc = self.doc.get_toc() # [[lvl, title, page], ...]
        
        # Determine title from metadata or fallback to filename
        title = meta.get("title")
        if not title or title.strip() == "":
            title = self.pdf_path.stem.replace("_", " ").replace("-", " ").title()
            
        author = meta.get("author") or "Неизвестный автор"

        formatted_toc = []
        for item in toc:
            if len(item) >= 3:
                formatted_toc.append({
                    "level": item[0],
                    "title": item[1],
                    "pageNumber": item[2]
                })

        return {
            "title": title,
            "author": author,
            "totalPages": self.total_pages,
            "toc": formatted_toc
        }

    def render_page_as_webp(self, page_index: int, output_dir: Path, slug: str, dpi: int = 150) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        page = self.doc[page_index]
        pix = page.get_pixmap(dpi=dpi)
        
        # Save directly as WebP or via PIL
        page_num = page_index + 1
        out_path = output_dir / f"page_{page_num}.webp"
        
        # PyMuPDF pixmap to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.save(out_path, "WEBP", quality=85)
        return out_path

    def extract_page_text(self, page_index: int) -> str:
        page = self.doc[page_index]
        text = page.get_text("text")
        
        # Basic cleanup: remove standalone page numbers and excessive whitespace
        cleaned_lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            # If line is just a single number (page number), we can keep track or trim
            if stripped:
                cleaned_lines.append(stripped)
                
        return "\n".join(cleaned_lines)

    def extract_all_pages(self, scans_dir: Path, slug: str) -> List[ExtractedPage]:
        pages: List[ExtractedPage] = []
        for i in range(self.total_pages):
            text = self.extract_page_text(i)
            img_path = self.render_page_as_webp(i, scans_dir, slug)
            pages.append(ExtractedPage(page_number=i + 1, text=text, image_path=str(img_path)))
        return pages

    def close(self):
        self.doc.close()
