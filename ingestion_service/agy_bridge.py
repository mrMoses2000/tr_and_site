import json
import re
import subprocess
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .config import AGY_BIN

logger = logging.getLogger(__name__)

class ParagraphPairModel(BaseModel):
    id: str
    en: str
    ru: str

class FootnotePairModel(BaseModel):
    id: int
    textEn: str
    textRu: str

class TranslatedPageModel(BaseModel):
    pageNumber: int
    chapterTitle: Optional[str] = None
    paragraphs: List[ParagraphPairModel] = Field(default_factory=list)
    footnotes: List[FootnotePairModel] = Field(default_factory=list)
    readingTimeMinutes: Optional[int] = 2

class BatchTranslationResult(BaseModel):
    pages: List[TranslatedPageModel]

class AgyBridgeError(Exception):
    pass

class AgyCliBridge:
    """
    Port/Adapter to invoke the agy CLI non-interactively for theological translation,
    paragraph alignment, and footnote extraction.
    """

    def __init__(self, agy_bin: str = AGY_BIN, timeout_seconds: int = 240):
        self.agy_bin = agy_bin
        self.timeout_seconds = timeout_seconds

    def _build_batch_prompt(
        self,
        pages_data: List[Dict[str, Any]],
        book_title: str,
        author: str,
        target_lang: str = "kk"
    ) -> str:
        if target_lang == "kk":
            lang_instruction = (
                "Translate the following excerpt into high-quality, eloquent, academic Kazakh (қазақ тілі). "
                "Ensure accurate theological and scholarly terminology (e.g. Жаңа Өсиет теологиясы, Құдайдың еркі, "
                "құтқарылу тарихы, серт/өсиет теологиясы, реформаттық дәстүр, қағида, Киелі Жазба). "
                "The 'ru' field in JSON must contain the academic Kazakh translation."
            )
        elif target_lang == "ru":
            lang_instruction = (
                "Translate the following excerpt into high-quality, academic theological Russian. "
                "The 'ru' field in JSON must contain the academic Russian translation."
            )
        else:
            lang_instruction = (
                "Preserve the original language without translating. "
                "Put the original paragraph text in both 'en' and 'ru' fields."
            )

        prompt_lines = [
            f"You are an expert academic translator and theological scholar.",
            f"Book: '{book_title}' by {author}.",
            f"Task: {lang_instruction}",
            f"Requirements:",
            f"1. Break the content into parallel paragraph pairs (en: original text, ru: translation/target text).",
            f"2. Paragraph IDs must be formatted as 'p-{{pageNumber}}-{{index}}' starting from 1 for each page.",
            f"3. Extract all numbered footnotes and provide their original text and translated text.",
            f"4. If a page has a chapter or section title, include it in 'chapterTitle'.",
            f"5. Estimate reading time in minutes for each page.",
            f"6. Return ONLY valid JSON matching this schema:",
            f"```json",
            f"[",
            f"  {{",
            f"    \"pageNumber\": 1,",
            f"    \"chapterTitle\": \"...\",",
            f"    \"readingTimeMinutes\": 2,",
            f"    \"paragraphs\": [",
            f"      {{\"id\": \"p-1-1\", \"en\": \"...\", \"ru\": \"...\"}}",
            f"    ],",
            f"    \"footnotes\": [",
            f"      {{\"id\": 1, \"textEn\": \"...\", \"textRu\": \"...\"}}",
            f"    ]",
            f"  }}",
            f"]",
            f"```",
            f"\n--- PAGES TO PROCESS ---"
        ]

        for p in pages_data:
            p_num = p["pageNumber"]
            text = p.get("text", "")
            prompt_lines.append(f"\n[PAGE_START: {p_num}]")
            prompt_lines.append(text)
            prompt_lines.append(f"[PAGE_END: {p_num}]\n")

        return "\n".join(prompt_lines)

    def _clean_json_output(self, raw_output: str) -> Any:
        """
        Extract JSON array or object from raw text or markdown fences.
        """
        raw_output = raw_output.strip()
        # Look for ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_output, re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()
            return json.loads(candidate)
        
        # If no fences, try finding the first [ or { to the last ] or }
        first_bracket = raw_output.find("[")
        first_brace = raw_output.find("{")
        
        start_idx = -1
        if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
            start_idx = first_bracket
            end_idx = raw_output.rfind("]")
        elif first_brace != -1:
            start_idx = first_brace
            end_idx = raw_output.rfind("}")
        else:
            end_idx = -1

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = raw_output[start_idx : end_idx + 1]
            return json.loads(candidate)

        return json.loads(raw_output)

    async def translate_batch(
        self,
        pages_data: List[Dict[str, Any]],
        book_title: str,
        author: str,
        target_lang: str = "kk",
        max_retries: int = 2
    ) -> List[TranslatedPageModel]:
        """
        Executes agy CLI command asynchronously and parses the structured response.
        If target_lang is 'original', generates structured pages locally without translation.
        """
        if target_lang == "original":
            return self._generate_fallback(pages_data)

        prompt = self._build_batch_prompt(pages_data, book_title, author, target_lang=target_lang)

        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                cmd = [
                    self.agy_bin,
                    "-p", prompt,
                    "--output-format", "json",
                    "--dangerously-skip-permissions"
                ]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=self.timeout_seconds
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise AgyBridgeError(f"agy CLI timed out after {self.timeout_seconds}s")

                if proc.returncode != 0:
                    err_msg = stderr.decode("utf-8", errors="replace")
                    raise AgyBridgeError(f"agy CLI exited with code {proc.returncode}: {err_msg}")

                stdout_text = stdout.decode("utf-8", errors="replace")
                
                # agy CLI returns a JSON wrapper containing {"response": "..."}
                try:
                    wrapper = json.loads(stdout_text)
                    model_response = wrapper.get("response", stdout_text)
                except json.JSONDecodeError:
                    model_response = stdout_text

                parsed_data = self._clean_json_output(model_response)

                if isinstance(parsed_data, dict):
                    if "pages" in parsed_data:
                        parsed_data = parsed_data["pages"]
                    else:
                        parsed_data = [parsed_data]

                results: List[TranslatedPageModel] = []
                for item in parsed_data:
                    results.append(TranslatedPageModel(**item))

                return results

            except Exception as e:
                last_err = e
                logger.warning(f"Batch translation attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 * attempt)

        # Fallback if all attempts failed: build structured fallback without crashing the pipeline
        logger.error(f"All {max_retries} attempts failed for batch. Generating fallback.", exc_info=last_err)
        return self._generate_fallback(pages_data)

    def _generate_fallback(self, pages_data: List[Dict[str, Any]]) -> List[TranslatedPageModel]:
        results = []
        for p in pages_data:
            p_num = p["pageNumber"]
            text = p.get("text", "")
            paras = [line.strip() for line in text.split("\n\n") if line.strip()]
            if not paras:
                paras = [text] if text.strip() else ["(Пустая страница)"]
            
            p_pairs = [
                ParagraphPairModel(
                    id=f"p-{p_num}-{idx+1}",
                    en=para,
                    ru=para # Fallback to original text if AI translation unreachable
                )
                for idx, para in enumerate(paras)
            ]
            results.append(TranslatedPageModel(
                pageNumber=p_num,
                chapterTitle=f"Страница {p_num}",
                paragraphs=p_pairs,
                footnotes=[],
                readingTimeMinutes=2
            ))
        return results
