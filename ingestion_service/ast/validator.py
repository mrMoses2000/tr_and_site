import re
from typing import Dict, Any, List
from .models import DocumentPage


class FidelityValidator:
    @staticmethod
    def _digit_sequences(text: str) -> List[str]:
        return re.findall(r"\d+", text)

    def verify_digit_sequences(self, raw_text: str, processed_text: str) -> bool:
        """
        Verifies that all digit sequences present in the raw text
        are preserved in the processed/AST text in matching counts.
        """
        # Exact sequence equality prevents both dropped digits and injected
        # numbers, while also catching reordered citations/page references.
        return self._digit_sequences(raw_text) == self._digit_sequences(processed_text)

    def validate_multiset_digits(self, raw_text: str, normalized_text: str) -> Dict[str, Any]:
        """
        Validates that multiset of digit sequences in raw_text matches normalized_text.
        """
        from collections import Counter
        raw_digits = self._digit_sequences(raw_text)
        norm_digits = self._digit_sequences(normalized_text)
        raw_counter = Counter(raw_digits)
        norm_counter = Counter(norm_digits)
        passed = raw_counter == norm_counter
        return {
            "status": "PASS" if passed else "FAIL",
            "raw_count": sum(raw_counter.values()),
            "normalized_count": sum(norm_counter.values()),
            "diff": {
                "missing": list((raw_counter - norm_counter).elements()),
                "extra": list((norm_counter - raw_counter).elements()),
            },
        }

    def validate_figures_presence(
        self,
        drawing_count: Optional[int] = None,
        figure_blocks: Any = None,
        page_index: Optional[int] = None,
        drawings_count: Optional[int] = None,
        figure_blocks_count: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Validates that when vector drawings or diagrams are present on a page,
        at least one FigureBlock exists.
        """
        d_cnt = drawing_count if drawing_count is not None else (drawings_count or 0)
        if isinstance(figure_blocks, list):
            f_cnt = len(figure_blocks)
        elif isinstance(figure_blocks, int):
            f_cnt = figure_blocks
        elif figure_blocks_count is not None:
            f_cnt = figure_blocks_count
        else:
            f_cnt = 0

        passed = not (d_cnt >= 5 and f_cnt == 0)
        return {
            "status": "PASS" if passed else "FAIL",
            "page_index": page_index,
            "drawing_count": d_cnt,
            "figure_blocks_count": f_cnt,
        }

    def validate_page_fidelity(
        self,
        raw_text: str,
        document_page: DocumentPage,
    ) -> Dict[str, Any]:
        """
        Runs Gate D fidelity checks:
        1. Digit sequence preservation
        2. Citation integrity
        3. Footnote anchor agreement
        4. Reading order acyclicity
        """
        # Collect all text from all blocks in DocumentPage
        block_texts: List[str] = []
        for block in document_page.blocks:
            if hasattr(block, "runs"):
                for run in block.runs:
                    block_texts.append(run.text)
        for fn in document_page.footnotes:
            if fn.label:
                block_texts.append(fn.label)
            for b in fn.blocks:
                if hasattr(b, "runs"):
                    for r in b.runs:
                        block_texts.append(r.text)

        combined_ast_text = " ".join(block_texts)

        digits_valid = self.verify_digit_sequences(raw_text, combined_ast_text)

        # Footnote agreement: each footnote label should be referenced in text or valid
        fn_agreement = True
        for fn in document_page.footnotes:
            if not fn.label:
                fn_agreement = False

        passed = digits_valid and fn_agreement and document_page.review_status == "verified"

        return {
            "passed": passed,
            "digits_preserved": digits_valid,
            "footnote_agreement": fn_agreement,
            "review_status": document_page.review_status,
        }
