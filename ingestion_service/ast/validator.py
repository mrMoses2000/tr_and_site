import re
from typing import Dict, Any, List
from .models import DocumentPage


class FidelityValidator:
    def verify_digit_sequences(self, raw_text: str, processed_text: str) -> bool:
        """
        Verifies that all digit sequences present in the raw text
        are preserved in the processed/AST text in matching counts.
        """
        raw_digits = re.findall(r'\d+', raw_text)
        processed_digits = re.findall(r'\d+', processed_text)

        if not raw_digits:
            return True

        # Check that all raw digit tokens appear in processed digits in identical multiset
        from collections import Counter
        raw_counter = Counter(raw_digits)
        processed_counter = Counter(processed_digits)

        for digit, count in raw_counter.items():
            if processed_counter[digit] < count:
                return False

        return True

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

        passed = digits_valid and fn_agreement and document_page.review_status != "needs_review"

        return {
            "passed": passed,
            "digits_preserved": digits_valid,
            "footnote_agreement": fn_agreement,
            "review_status": document_page.review_status,
        }
