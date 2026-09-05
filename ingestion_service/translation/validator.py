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

        if set(expected_ids) != set(received_ids) or len(expected_ids) != len(received_ids):
            raise BlockMismatchError(
                f"Block ID mismatch. Expected: {expected_ids}, Received: {received_ids}"
            )

        source_lang = envelope.book.get("sourceLanguage", "")
        target_lang = envelope.book.get("targetLanguage", "")

        # Check for false fallback if translating between different languages
        if source_lang and target_lang and source_lang != target_lang and target_lang != "original":
            input_map = {b.id: b.text.strip() for b in envelope.blocks}
            for res in response.results:
                src_text = input_map.get(res.id, "")
                tgt_text = res.targetText.strip()

                if not tgt_text:
                    raise TranslationValidationError(f"Empty target text for block {res.id}")

                if src_text and tgt_text == src_text and len(src_text) > 10:
                    raise FalseFallbackError(
                        f"Block {res.id} translation output is identical to source Russian text. "
                        f"False translation fallback rejected."
                    )

        return response
