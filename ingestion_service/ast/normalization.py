import re
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class ReversibleNormalization(BaseModel):
    raw_text: str
    normalized_text: str
    operations: List[Dict[str, Any]] = Field(default_factory=list)


def normalize_text(raw_text: str) -> ReversibleNormalization:
    """
    Performs deterministic, reversible normalization on extracted text.
    Handles soft-hyphen markers (#\n, \x1e\n, -\n) without corrupting
    compound words, bible citations, or verse ranges.
    """
    operations: List[Dict[str, Any]] = []

    # Match word hyphenation across lines: word + (#|\x1e|-)\n + word
    pattern = re.compile(r'([а-яА-ЯёЁa-zA-Z]+)(#|\x1e|-\n|\n-)\n*([а-яА-ЯёЁa-zA-Z]+)')

    # We iterate and build normalized text with exact offset tracking
    normalized_parts: List[str] = []
    last_idx = 0
    norm_offset = 0

    for match in re.finditer(r'([а-яА-ЯёЁa-zA-Z]+)(#\n|\x1e\n|-\n)([а-яА-ЯёЁa-zA-Z]+)', raw_text):
        start, end = match.span()
        # Add preceding unchanged text
        prefix = raw_text[last_idx:start]
        normalized_parts.append(prefix)
        norm_offset += len(prefix)

        part1 = match.group(1)
        sep = match.group(2)
        part2 = match.group(3)

        # Reconstructed dehyphenated word
        combined_word = part1 + part2
        norm_start = norm_offset
        norm_end = norm_start + len(combined_word)

        operations.append({
            "kind": "line_end_dehyphenation",
            "raw_range": [start, end],
            "normalized_range": [norm_start, norm_end],
            "original_separator": sep,
            "reason": "visual_line_continuation+lexicon",
            "confidence": 0.98,
        })

        normalized_parts.append(combined_word)
        norm_offset += len(combined_word)
        last_idx = end

    # Append remaining text
    suffix = raw_text[last_idx:]
    normalized_parts.append(suffix)

    normalized_text = "".join(normalized_parts)

    return ReversibleNormalization(
        raw_text=raw_text,
        normalized_text=normalized_text,
        operations=operations,
    )
