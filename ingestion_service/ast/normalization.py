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
    Handles soft-hyphen markers (#\n, \x1e\n, -\n, inline \x1e and #) without corrupting
    compound words, bible citations, or verse ranges.
    """
    operations: List[Dict[str, Any]] = []

    current = raw_text

    # Sequence of normalization passes
    patterns = [
        # 1. Range separators: 2.6\x1e11, 2\x1e5, 7\x1e8, 10\x1e11, 69#70 -> en-dash '–'
        (
            re.compile(r"(\d+(?:\.\d+)?)(?:\x1e|#)(\d+)"),
            "range_separator_normalization",
            lambda m: (f"{m.group(1)}–{m.group(2)}", m.group(0)[len(m.group(1)):-len(m.group(2))]),
        ),
        # 2. Ordinal number suffixes: 60\x1eе, 3\x1eя, 1\x1eй -> hyphen '-'
        (
            re.compile(r"(\d+)(?:\x1e|#)([а-яА-ЯёЁ]+)"),
            "ordinal_suffix_hyphen",
            lambda m: (f"{m.group(1)}-{m.group(2)}", m.group(0)[len(m.group(1)):-len(m.group(2))]),
        ),
        # 3. Soft hyphen followed by space in chapter 13: за# являющие -> single word
        (
            re.compile(r"([а-яА-ЯёЁa-zA-Z]+)#[ \t]+([а-яА-ЯёЁa-zA-Z]+)"),
            "soft_hyphen_dehyphenation",
            lambda m: (f"{m.group(1)}{m.group(2)}", m.group(0)[len(m.group(1)):-len(m.group(2))]),
        ),
        # 4. Line-end dehyphenation across line breaks
        (
            re.compile(r"([а-яА-ЯёЁa-zA-Z]+)(#\n|\x1e\n|-\n)([а-яА-ЯёЁa-zA-Z]+)"),
            "line_end_dehyphenation",
            lambda m: (
                f"{m.group(1)}-{m.group(3)}"
                if m.group(1).lower() in {"во", "по", "кое", "две", "три"}
                and m.group(3).lower() in {"первых", "вторых", "третьих", "три", "то"}
                else f"{m.group(1)}{m.group(3)}",
                m.group(2),
            ),
        ),
        # 5. Inline control-char compound words: Во\x1eвторых, две\x1eтри -> hyphen '-'
        (
            re.compile(r"([а-яА-ЯёЁa-zA-Z]+)\x1e([а-яА-ЯёЁa-zA-Z]+)"),
            "control_char_hyphen",
            lambda m: (f"{m.group(1)}-{m.group(2)}", "\x1e"),
        ),
        # 6. Range separator at start of span: \x1e11 -> –11
        (
            re.compile(r"^(?:\x1e|#)(\d+)"),
            "range_separator_normalization",
            lambda m: (f"–{m.group(1)}", m.group(0)[:-len(m.group(1))]),
        ),
        # 7. Control-char compound suffix at start of span: \x1eвторых -> -вторых
        (
            re.compile(r"^(?:\x1e|#)([а-яА-ЯёЁa-zA-Z]+)"),
            "control_char_hyphen",
            lambda m: (f"-{m.group(1)}", m.group(0)[:-len(m.group(1))]),
        ),
        # 8. Fallback for any remaining unhandled \x1e or #
        (
            re.compile(r"[\x1e#]"),
            "control_char_hyphen",
            lambda m: ("-", m.group(0)),
        ),
    ]

    for pat, kind, rep_fn in patterns:
        new_parts = []
        last_idx = 0
        norm_offset = 0
        for match in pat.finditer(current):
            start, end = match.span()
            prefix = current[last_idx:start]
            new_parts.append(prefix)
            norm_offset += len(prefix)

            replacement, sep = rep_fn(match)
            norm_start = norm_offset
            norm_end = norm_start + len(replacement)

            operations.append({
                "kind": kind,
                "raw_range": [start, end],
                "normalized_range": [norm_start, norm_end],
                "original_separator": sep,
                "confidence": 0.99,
            })
            new_parts.append(replacement)
            norm_offset += len(replacement)
            last_idx = end
        new_parts.append(current[last_idx:])
        current = "".join(new_parts)

    return ReversibleNormalization(
        raw_text=raw_text,
        normalized_text=current,
        operations=operations,
    )
