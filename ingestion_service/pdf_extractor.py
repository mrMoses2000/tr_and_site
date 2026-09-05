import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import fitz  # PyMuPDF
from PIL import Image

from .lang_detector import detect_language
from .ast.normalization import normalize_text


CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    # Kazakh letters
    'ә': 'a', 'ғ': 'g', 'қ': 'q', 'ң': 'ng', 'ө': 'o', 'ұ': 'u', 'ү': 'u', 'һ': 'h', 'і': 'i'
}

def slugify_cyrillic(text: str) -> str:
    """
    Transliterates Russian/Kazakh Cyrillic to URL-safe Latin slug.
    Example: 'Озборн_Герменевтическая спираль' -> 'ozborn-germenevticheskaya-spiral'
    """
    stem = Path(text).stem
    result = []
    for ch in stem.lower():
        if ch in CYRILLIC_TO_LATIN:
            result.append(CYRILLIC_TO_LATIN[ch])
        elif re.match(r'[a-z0-9]', ch):
            result.append(ch)
        elif ch in [' ', '_', '-', '.']:
            result.append('-')
    
    slug = "".join(result)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug or "book"

class PDFExtractor:
    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        self.doc = fitz.open(str(self.pdf_path))
        self.total_pages = len(self.doc)

    def is_artifact_metadata(self, val: Optional[str]) -> bool:
        if not val or not val.strip():
            return True
        v = val.strip().lower()
        artifacts = ["administrator", "in print", "part_1", "untitled", "adobe", ".indd", ".pdf", "layout"]
        return any(a in v for a in artifacts)

    def extract_metadata_from_pages(self) -> Dict[str, Any]:
        """
        Parses title and imprint pages (first 4 pages) to extract actual title,
        author, subtitle, publisher, and year.
        """
        metadata = {
            "title": "",
            "titleEn": "",
            "author": "",
            "authorEn": "",
            "subtitle": "",
            "publisher": "",
            "year": ""
        }
        
        sample_pages = [self.doc[pno].get_text("text") for pno in range(min(4, self.total_pages))]
        combined_text = "\n---PAGE---\n".join(sample_pages)

        # 1. Russian author + title pattern on imprint page (page 2 or 3)
        # Format: "Грант Р. Осборн\nГерменевтическая спираль: общее введение в библейское\nтолкование / Пер. с англ."
        m_rus = re.search(
            r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.?\s+[А-ЯЁ][а-яё]+)\s*\n\s*([^/—–\n]+(?:\n[^/—–\n]+)*?)\s*(?:/|\s*—|\s*–)',
            combined_text
        )
        if m_rus:
            metadata["author"] = m_rus.group(1).strip()
            full_title = " ".join(m_rus.group(2).split()).strip()
            if ":" in full_title:
                t, sub = full_title.split(":", 1)
                metadata["title"] = t.strip()
                metadata["subtitle"] = sub.strip().capitalize()
            else:
                metadata["title"] = full_title

        # 2. English title & author if present on copyright page
        m_en_author = re.search(r'(?:by|Copyright\s+©\s*\d{4}\s+by)\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)*\s+[A-Z][a-z]+)', combined_text)
        if m_en_author:
            metadata["authorEn"] = m_en_author.group(1).strip()
            if not metadata["author"]:
                metadata["author"] = metadata["authorEn"]

        m_en_title = re.search(r'The\s+([A-Z][a-z]+(?:\s+[A-Za-z]+)*):?\s*\n?\s*([A-Z][a-z]+(?:\s+[A-Za-z]+)*)?', combined_text)
        if m_en_title:
            metadata["titleEn"] = m_en_title.group(0).replace("\n", " ").strip()

        # 3. Publisher
        m_pub = re.search(r'[—–]\s*([А-ЯЁа-яё\s\x0c-]+:\s*[А-ЯЁа-яё\s\x0c-]+,\s*\d{4})', combined_text)
        if m_pub:
            clean_pub = m_pub.group(1).replace("\x0c", "-").replace("\xa0", " ").strip()
            metadata["publisher"] = clean_pub
        else:
            # Check known publishers
            for line in combined_text.split("\n"):
                if any(p in line.lower() for p in ["аккредитационная ассоциация", "baker academic", "intervarsity press", "издательство"]):
                    metadata["publisher"] = line.replace("\x0c", "-").strip()
                    break

        # Fallback if title still empty: check prominent uppercase line on page 1
        if not metadata["title"]:
            p1_lines = [l.strip() for l in self.doc[0].get_text("text").split("\n") if l.strip()]
            for l in p1_lines:
                if len(l) > 6 and l.isupper() and not any(ch.isdigit() for ch in l):
                    if not metadata["author"] or l.lower() not in metadata["author"].lower():
                        metadata["title"] = l.capitalize()
                        break

        return metadata

    def extract_printed_toc(self) -> List[Dict[str, Any]]:
        """
        Parses printed table of contents from initial pages (pages 2 to 12).
        """
        toc_items = []
        toc_pages = []
        for pno in range(min(15, self.total_pages)):
            txt = self.doc[pno].get_text("text").lower()
            if "оглавление" in txt or "содержание" in txt or "contents" in txt:
                toc_pages.append(pno)

        if not toc_pages:
            toc_pages = list(range(2, min(9, self.total_pages)))

        for pno in toc_pages:
            lines = [l.strip() for l in self.doc[pno].get_text("text").split("\n") if l.strip()]
            i = 0
            while i < len(lines):
                line = lines[i]
                if line.lower() in ["оглавление", "содержание", "contents", "герменевтическая спираль"]:
                    i += 1
                    continue
                # Pattern 1: Title on line i, page number on line i+1
                if i + 1 < len(lines) and re.match(r'^\d{1,4}$', lines[i+1]):
                    p_num = int(lines[i+1])
                    if 1 <= p_num <= self.total_pages:
                        level = 1 if ("ЧАСТЬ" in line or line.isupper() or re.match(r'^[IVXLCDM]+\.', line)) else 2
                        toc_items.append({"title": line, "pageNumber": p_num, "level": level})
                        i += 2
                        continue
                # Pattern 2: Title and page number on the same line (e.g. "Предисловие ..... 10")
                match_inline = re.match(r'^(.*?)\s*[\.\s…_-]{2,}\s*(\d{1,4})$', line)
                if match_inline:
                    t = match_inline.group(1).strip()
                    p_num = int(match_inline.group(2))
                    if 1 <= p_num <= self.total_pages:
                        level = 1 if ("ЧАСТЬ" in t or t.isupper()) else 2
                        toc_items.append({"title": t, "pageNumber": p_num, "level": level})
                        i += 1
                        continue
                i += 1

        return toc_items

    def get_metadata(self) -> Dict[str, Any]:
        doc_meta = self.doc.metadata or {}
        page_meta = self.extract_metadata_from_pages()

        # Title
        raw_title = doc_meta.get("title")
        if self.is_artifact_metadata(raw_title):
            title = page_meta.get("title") or self.pdf_path.stem.replace("_", " ").replace("-", " ").title()
        else:
            title = raw_title.strip()

        # Author
        raw_author = doc_meta.get("author")
        if self.is_artifact_metadata(raw_author):
            author = page_meta.get("author") or "Неизвестный автор"
        else:
            author = raw_author.strip()

        # Table of contents
        raw_toc = self.doc.get_toc()
        formatted_toc = []
        has_invalid_toc = False

        if raw_toc:
            for item in raw_toc:
                if len(item) >= 3:
                    lvl, t_str, p_num = item[0], str(item[1]), item[2]
                    # Check if invalid (negative page number or file artifact)
                    if p_num <= 0 or ".pdf" in t_str.lower() or "part_" in t_str.lower():
                        has_invalid_toc = True
                        break
                    formatted_toc.append({
                        "level": lvl,
                        "title": t_str.strip(),
                        "pageNumber": p_num
                    })

        if has_invalid_toc or not formatted_toc:
            printed_toc = self.extract_printed_toc()
            if printed_toc:
                formatted_toc = printed_toc

        # Sample text for language detection
        sample_text = ""
        for pno in range(min(10, self.total_pages)):
            sample_text += " " + self.doc[pno].get_text("text")
        detected_lang = detect_language(sample_text)

        title_en = page_meta.get("titleEn") or title
        author_en = page_meta.get("authorEn") or author

        return {
            "title": title,
            "titleRu": title,
            "titleEn": title_en,
            "subtitle": page_meta.get("subtitle", ""),
            "author": author_en,
            "authorRu": author,
            "publisher": page_meta.get("publisher", ""),
            "sourceLanguage": detected_lang,
            "totalPages": self.total_pages,
            "toc": formatted_toc
        }

    def render_page_as_webp(self, page_index: int, output_dir: Path, slug: str, dpi: int = 150) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        page = self.doc[page_index]
        pix = page.get_pixmap(dpi=dpi)
        
        page_num = page_index + 1
        out_path = output_dir / f"page_{page_num}.webp"
        
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.save(out_path, "WEBP", quality=85)
        return out_path

    def extract_page_structure(self, page_index: int) -> Dict[str, Any]:
        """
        Extracts structured page content:
        - Filters running headers and footers
        - Extracts bottom footnotes into structured {id, textRu, textEn}
        - Segments text into logical paragraphs
        - Reconstructs soft hyphens (\x1e)
        """
        page = self.doc[page_index]
        rect = page.rect
        blocks = page.get_text("blocks")
        page_num = page_index + 1

        body_paragraphs: List[Dict[str, str]] = []
        footnotes: List[Dict[str, Any]] = []
        chapter_title: Optional[str] = None

        p_idx = 1
        for b in blocks:
            # b: (x0, y0, x1, y1, text, block_no, block_type)
            if len(b) < 5 or b[6] != 0: # 0 = text block
                continue
            y0, y1 = b[1], b[3]
            raw_text = b[4].strip()
            if not raw_text:
                continue

            # 1. Filter running header at top of page (y1 < 50)
            if y1 < 50:
                continue

            # 2. Filter running footer at very bottom if it is just a page number
            if y0 > rect.height - 40 and re.match(r'^\d{1,4}$', raw_text):
                continue

            # 3. Detect footnotes at bottom of page (y0 > 75% height)
            if y0 > rect.height * 0.75:
                fn_match = re.match(r'^(?:\[(\d+)\]|(\d+)\s+([А-ЯЁA-Z].*))', raw_text, re.DOTALL)
                if fn_match:
                    fn_id = int(fn_match.group(1) or fn_match.group(2))
                    fn_text = (fn_match.group(3) if fn_match.group(2) else raw_text[len(f"[{fn_id}]"): ]).strip()
                    fn_clean = normalize_text(fn_text).normalized_text
                    fn_clean = re.sub(r'\n(?!\n)', ' ', fn_clean).strip()
                    footnotes.append({
                        "id": fn_id,
                        "textRu": fn_clean,
                        "textEn": fn_clean
                    })
                    continue

            # 4. Clean body text: soft hyphens, excessive spaces with reversible normalization
            cleaned = normalize_text(raw_text).normalized_text
            cleaned = re.sub(r'\n(?!\n)', ' ', cleaned).strip()

            # 5. Check if block is a short heading
            if len(cleaned) < 80 and not cleaned.endswith(('.', '!', '?')) and not chapter_title:
                if re.match(r'^[А-ЯЁA-Z0-9\s—–IVXLCDM.:]+$', cleaned):
                    chapter_title = cleaned

            body_paragraphs.append({
                "id": f"p-{page_num}-{p_idx}",
                "en": cleaned,
                "ru": cleaned
            })
            p_idx += 1

        if not body_paragraphs:
            body_paragraphs.append({
                "id": f"p-{page_num}-1",
                "en": "(Пустая страница)",
                "ru": "(Пустая страница)"
            })

        return {
            "pageNumber": page_num,
            "chapterTitle": chapter_title,
            "paragraphs": body_paragraphs,
            "footnotes": footnotes,
            "readingTimeMinutes": max(1, len(body_paragraphs) // 2)
        }

    def extract_page_text(self, page_index: int) -> str:
        page = self.doc[page_index]
        text = page.get_text("text")
        cleaned_lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped:
                cleaned_lines.append(stripped)
        return "\n".join(cleaned_lines)

    def close(self):
        self.doc.close()
