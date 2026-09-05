import unicodedata
from typing import Any, Dict
from .models import BatchTranslationResponse, TranslationEnvelope


class TranslationValidationError(Exception):
    """Raised when translation output fails contract or schema validation."""
    pass


class BlockMismatchError(TranslationValidationError):
    """Raised when output block IDs do not match input block IDs 1:1."""
    pass


class FalseFallbackError(TranslationValidationError):
    """Raised when output is identical to source text during non-trivial translation."""
    pass


class TranslationValidator:
    @staticmethod
    def _normalized_for_fallback_check(text: str) -> str:
        """Normalize harmless formatting differences, not semantic content."""
        normalized = unicodedata.normalize("NFKC", text).casefold()
        return "".join(char for char in normalized if char.isalnum())

    def validate_response(
        self,
        envelope: TranslationEnvelope,
        response_data: Dict[str, Any],
    ) -> BatchTranslationResponse:
        try:
            response = BatchTranslationResponse.model_validate(response_data)
        except Exception as e:
            raise TranslationValidationError(f"Schema validation error: {e}")

        expected_ids = [b.id for b in envelope.blocks]
        received_ids = [r.id for r in response.results]

        if (
            len(expected_ids) != len(set(expected_ids))
            or set(expected_ids) != set(received_ids)
            or len(expected_ids) != len(received_ids)
        ):
            raise BlockMismatchError(
                f"Block ID mismatch. Expected: {expected_ids}, Received: {received_ids}"
            )

        source_lang = envelope.book.get("sourceLanguage", "")
        target_lang = envelope.book.get("targetLanguage", "")

        input_map = {b.id: b for b in envelope.blocks}
        for res in response.results:
            source_block = input_map[res.id]
            tgt_text = res.targetText.strip()

            if not tgt_text:
                raise TranslationValidationError(f"Empty target text for block {res.id}")

            if source_block.pageNumber is not None and res.pageNumber != source_block.pageNumber:
                raise BlockMismatchError(
                    f"Page mismatch for block {res.id}: expected {source_block.pageNumber}, "
                    f"received {res.pageNumber}"
                )

            if target_lang and target_lang != "original" and res.language != target_lang:
                raise TranslationValidationError(
                    f"Wrong target language for block {res.id}: expected {target_lang}, "
                    f"received {res.language}"
                )

            # Reject source echoes even when only whitespace, Unicode width,
            # case, or punctuation was changed.
            if source_lang and target_lang and source_lang != target_lang and target_lang != "original":
                src_norm = self._normalized_for_fallback_check(source_block.text)
                tgt_norm = self._normalized_for_fallback_check(tgt_text)
                if len(src_norm) > 10 and src_norm == tgt_norm:
                    raise FalseFallbackError(
                        f"Block {res.id} translation output is equivalent to source text. "
                        "False translation fallback rejected."
                    )

        return response
