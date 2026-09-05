import pytest
from pathlib import Path

def test_v2_pydantic_contracts_import():
    from ingestion_service.v2.contracts import (
        SourceAnchor,
        InlineRun,
        DocumentBlock,
        BookManifestV2,
        adapt_manifest_v1_to_v2,
        validate_manifest_v2
    )

def test_v2_adapter_single_language_no_false_english():
    from ingestion_service.v2.contracts import adapt_manifest_v1_to_v2
    v1_data = {
        "slug": "test-ru",
        "title": "Русская книга",
        "author": "Автор",
        "sourceLanguage": "ru",
        "targetLanguage": "original",
        "startPage": 1,
        "endPage": 5,
        "totalPages": 5,
        "tableOfContents": [],
        "pages": [
            {
                "pageNumber": 1,
                "paragraphs": [{"id": "p-1-1", "ru": "Привет", "en": "Привет"}],
                "footnotes": [],
                "imageSrc": "/scans/test-ru/page_1.webp"
            }
        ]
    }
    v2 = adapt_manifest_v1_to_v2(v1_data)
    assert v2.schemaVersion == "2.0"
    assert v2.sourceLanguage == "ru"
    assert v2.availableLanguages == ["ru"]
    assert "en" not in v2.availableLanguages

def test_v2_schema_validation_rejection():
    from ingestion_service.v2.contracts import validate_manifest_v2
    with pytest.raises(ValueError):
        validate_manifest_v2({"schemaVersion": "1.0"})
    with pytest.raises(ValueError):
        validate_manifest_v2({"schemaVersion": "2.0", "pageRange": {"start": 10, "end": 2}})
