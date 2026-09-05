"""Translation boundary for the agy CLI.

The CLI adapter deliberately knows nothing about pages or the reader's legacy
manifest format. It accepts a typed data envelope on stdin and returns only a
typed translation response. ``AgyCliBridge`` is the compatibility adapter
around that boundary.
"""

import asyncio
import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel, Field

from .config import AGY_BIN
from .translation.adapter import TranslationAdapter
from .translation.models import BatchTranslationResponse, TranslationBlock, TranslationEnvelope

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
    """Raised when the local agy process cannot produce a response."""


class TranslationExecutor(Protocol):
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one isolated translation request."""


class AgyCliExecutor:
    """Least-privilege synchronous executor for one agy translation request.

    The document is sent as JSON data over stdin. No shell is involved and no
    permission bypass is allowed. The bridge runs this adapter in a worker
    thread so its public API remains asynchronous without blocking the event
    loop during a model call. The CLI is invoked in print mode; its NDJSON
    stream is accepted only when it contains a direct response or an explicit
    ``result``/``final`` event carrying that response.
    """

    def __init__(self, agy_bin: str = AGY_BIN, timeout_seconds: int = 240):
        self.agy_bin = agy_bin
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _schema_path(workdir: Path) -> Path:
        """Write the response schema inside the empty, disposable workdir."""
        schema_path = workdir / "translation-response.schema.json"
        schema_path.write_text(
            json.dumps(BatchTranslationResponse.model_json_schema(), ensure_ascii=False),
            encoding="utf-8",
        )
        return schema_path

    @staticmethod
    def _unwrap_json(value: Any, *, allow_direct: bool = True) -> Optional[Dict[str, Any]]:
        """Extract only a direct response or an explicitly final/result event."""
        if isinstance(value, dict):
            if allow_direct and "contractVersion" in value and "results" in value:
                return value
            event_type = value.get("type")
            if event_type not in {"result", "final", "final_result"}:
                return None
            for key in ("result", "response", "output", "data"):
                candidate = value.get(key)
                if isinstance(candidate, dict):
                    unwrapped = AgyCliExecutor._unwrap_json(candidate)
                    if unwrapped is not None:
                        return unwrapped
                if isinstance(candidate, str):
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        continue
                    unwrapped = AgyCliExecutor._unwrap_json(parsed)
                    if unwrapped is not None:
                        return unwrapped
        return None

    @classmethod
    def _parse_stream_json(cls, stdout: str) -> Dict[str, Any]:
        """Parse newline-delimited JSON without trusting log/event lines."""
        candidates: List[Any] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                candidates.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        for candidate in reversed(candidates):
            unwrapped = cls._unwrap_json(candidate)
            if unwrapped is not None:
                return unwrapped

        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise AgyBridgeError("agy returned no valid stream-json response") from exc
        unwrapped = cls._unwrap_json(parsed)
        if unwrapped is not None:
            return unwrapped
        raise AgyBridgeError("agy returned an unsupported response shape")

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Never inherit the repository as cwd: the model process receives only
        # the JSON envelope and a disposable schema file in this directory.
        with tempfile.TemporaryDirectory(prefix="agy-translation-") as workdir_name:
            workdir = Path(workdir_name)
            schema_path = self._schema_path(workdir)
            command = [
                self.agy_bin,
                "--print",
                "--input-format",
                "stream-json",
                "--output-format",
                "stream-json",
                "--sandbox",
                "--disable-slash-commands",
                "--json-schema",
                str(schema_path),
            ]
            try:
                try:
                    completed = subprocess.run(
                        command,
                        input=json.dumps(payload, ensure_ascii=False) + "\n",
                        capture_output=True,
                        text=True,
                        shell=False,
                        cwd=str(workdir),
                        timeout=self.timeout_seconds,
                        check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise TimeoutError(f"agy CLI timed out after {self.timeout_seconds}s") from exc

                if completed.returncode != 0:
                    stderr = (completed.stderr or "").strip()
                    raise AgyBridgeError(
                        f"agy CLI exited with code {completed.returncode}"
                        + (f": {stderr}" if stderr else "")
                    )
                return self._parse_stream_json(completed.stdout or "")
            finally:
                schema_path.unlink(missing_ok=True)


class AgyCliBridge:
    """Compatibility adapter from extracted pages to the typed translation port."""

    def __init__(
        self,
        agy_bin: str = AGY_BIN,
        timeout_seconds: int = 240,
        executor: Optional[TranslationExecutor] = None,
    ):
        self.agy_bin = agy_bin
        self.timeout_seconds = timeout_seconds
        self.executor = executor or AgyCliExecutor(agy_bin, timeout_seconds)
        self.translation_adapter = TranslationAdapter(executor=self.executor)
        # Short alias retained for callers that treat the bridge as an adapter.
        self.adapter = self.translation_adapter

    def _build_batch_prompt(
        self,
        pages_data: List[Dict[str, Any]],
        book_title: str,
        author: str,
        target_lang: str = "kk",
    ) -> str:
        """Build the legacy prompt retained for callers that inspect it.

        Production translation does not use this method: it sends page text
        only in the envelope's ``blocks`` data field.
        """
        if target_lang == "kk":
            lang_instruction = (
                "Translate into high-quality academic Kazakh (қазақ тілі), preserving theological terminology."
            )
        elif target_lang == "ru":
            lang_instruction = "Translate into high-quality academic theological Russian."
        else:
            lang_instruction = "Preserve the original language without translating."

        prompt_lines = [
            "You are an expert academic translator and theological scholar.",
            f"Book: '{book_title}' by {author}.",
            f"Task: {lang_instruction}",
            "Return only the requested structured result.",
        ]
        for page in pages_data:
            page_number = page["pageNumber"]
            prompt_lines.extend(
                [f"[PAGE_START: {page_number}]", page.get("text", ""), f"[PAGE_END: {page_number}]", ""]
            )
        return "\n".join(prompt_lines)

    def _clean_json_output(self, raw_output: str) -> Any:
        """Extract a JSON value from a legacy response or markdown fence."""
        raw_output = raw_output.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_output, re.IGNORECASE)
        if fence_match:
            return json.loads(fence_match.group(1).strip())

        first_bracket = raw_output.find("[")
        first_brace = raw_output.find("{")
        if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
            candidate = raw_output[first_bracket : raw_output.rfind("]") + 1]
        elif first_brace != -1:
            candidate = raw_output[first_brace : raw_output.rfind("}") + 1]
        else:
            candidate = raw_output
        return json.loads(candidate)

    @staticmethod
    def _source_language(pages_data: List[Dict[str, Any]]) -> str:
        for page in pages_data:
            value = page.get("sourceLanguage")
            if value:
                return str(value)
        return "en"

    @staticmethod
    def _page_blocks(page: Dict[str, Any]) -> List[TranslationBlock]:
        page_number = int(page["pageNumber"])
        text = str(page.get("text", ""))
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
        return [
            TranslationBlock(
                id=f"p-{page_number}-{index}",
                text=paragraph,
                pageNumber=page_number,
                blockType="paragraph",
            )
            for index, paragraph in enumerate(paragraphs, start=1)
        ]

    def _build_envelope(
        self,
        pages_data: List[Dict[str, Any]],
        book_title: str,
        author: str,
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> TranslationEnvelope:
        blocks: List[TranslationBlock] = []
        for page in pages_data:
            blocks.extend(self._page_blocks(page))
        return TranslationEnvelope(
            book={
                "id": book_title,
                "title": book_title,
                "author": author,
                "sourceLanguage": source_lang or self._source_language(pages_data),
                "targetLanguage": target_lang,
            },
            blocks=blocks,
        )

    @staticmethod
    def _reading_time(page: Dict[str, Any], blocks: List[TranslationBlock]) -> int:
        configured = page.get("readingTimeMinutes")
        if configured is not None:
            return int(configured)
        words = sum(len(block.text.split()) for block in blocks)
        return max(1, (words + 199) // 200)

    def _to_legacy_pages(
        self,
        pages_data: List[Dict[str, Any]],
        envelope: TranslationEnvelope,
        response: BatchTranslationResponse,
    ) -> List[TranslatedPageModel]:
        translations = {result.id: result for result in response.results}
        output: List[TranslatedPageModel] = []
        for page in pages_data:
            page_number = int(page["pageNumber"])
            page_blocks = [block for block in envelope.blocks if block.pageNumber == page_number]
            paragraphs = [
                ParagraphPairModel(
                    id=block.id,
                    en=block.text,
                    ru=translations[block.id].targetText,
                )
                for block in page_blocks
            ]
            output.append(
                TranslatedPageModel(
                    pageNumber=page_number,
                    chapterTitle=page.get("chapterTitle"),
                    paragraphs=paragraphs,
                    footnotes=[],
                    readingTimeMinutes=self._reading_time(page, page_blocks),
                )
            )
        return output

    async def translate_batch(
        self,
        pages_data: List[Dict[str, Any]],
        book_title: str,
        author: str,
        target_lang: str = "kk",
        max_retries: int = 2,
        source_lang: Optional[str] = None,
    ) -> List[TranslatedPageModel]:
        """Translate one page batch; failures are propagated fail-closed.

        ``max_retries`` remains accepted for API compatibility but is
        intentionally ignored. A timeout is ``SubmissionUnknownError`` and
        must be reconciled by the job layer before any resubmission.
        """
        del max_retries
        if target_lang == "original":
            return self._generate_fallback(pages_data)

        envelope = self._build_envelope(pages_data, book_title, author, target_lang, source_lang=source_lang)
        response = await asyncio.to_thread(self.translation_adapter.translate_batch, envelope)
        return self._to_legacy_pages(pages_data, envelope, response)

    def _generate_fallback(self, pages_data: List[Dict[str, Any]]) -> List[TranslatedPageModel]:
        """Build pages for explicit ``original`` mode only.

        Kept under its historical name for callers that used this helper. It
        is never called for provider failures, so source text cannot be
        published as a successful translation.
        """
        results: List[TranslatedPageModel] = []
        for page in pages_data:
            page_number = int(page["pageNumber"])
            blocks = self._page_blocks(page)
            paragraphs = [ParagraphPairModel(id=block.id, en=block.text, ru=block.text) for block in blocks]
            results.append(
                TranslatedPageModel(
                    pageNumber=page_number,
                    chapterTitle=page.get("chapterTitle") or f"Страница {page_number}",
                    paragraphs=paragraphs,
                    footnotes=[],
                    readingTimeMinutes=self._reading_time(page, blocks),
                )
            )
        return results
