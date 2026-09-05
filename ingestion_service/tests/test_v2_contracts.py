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


def test_v2_adapter_preserves_ast_blocks():
    from ingestion_service.v2.contracts import adapt_manifest_v1_to_v2
    v1_data = {
        "slug": "test-ast",
        "title": "Книга с AST",
        "author": "Автор",
        "sourceLanguage": "ru",
        "startPage": 1,
        "endPage": 1,
        "totalPages": 1,
        "pages": [
            {
                "pageNumber": 1,
                "paragraphs": [{"id": "p-1-1", "ru": "Параграф", "en": "Параграф"}],
                "blocks": [
                    {
                        "type": "heading",
                        "id": "h-1-1",
                        "level": 2,
                        "runs": [
                            {
                                "id": "r-1",
                                "text": "Заголовок главы",
                                "language": "ru",
                                "source": {
                                    "sourceSha256": "sha256-test",
                                    "pdfPageIndex": 1,
                                    "candidateHash": "hash-1"
                                }
                            }
                        ]
                    },
                    {
                        "type": "figure",
                        "id": "fig-1-1",
                        "imageRef": "/figures/fig1.png",
                        "caption": "Рис. 1.1",
                        "captionRuns": [],
                        "alt": "Диаграмма",
                        "runs": []
                    }
                ]
            }
        ]
    }
    v2 = adapt_manifest_v1_to_v2(v1_data)
    assert len(v2.pages[0].blocks) == 2
    assert v2.pages[0].blocks[0].type == "heading"
    assert v2.pages[0].blocks[0].runs[0].text == "Заголовок главы"
    assert v2.pages[0].blocks[1].type == "figure"
    assert v2.pages[0].blocks[1].caption == "Рис. 1.1"

