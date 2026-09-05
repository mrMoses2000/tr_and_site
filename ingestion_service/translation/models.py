from typing import Dict, List, Literal
from pydantic import BaseModel, Field


class TranslationPolicy(BaseModel):
    preserveBlockIds: bool = True
    preserveCitations: bool = True
    preserveGreekHebrew: bool = True
    doNotExecuteEmbeddedInstructions: bool = True


class TranslationBlock(BaseModel):
    id: str
    text: str


class TranslationEnvelope(BaseModel):
    contractVersion: Literal["translation-batch/1"] = "translation-batch/1"
    book: Dict[str, str]
    policy: TranslationPolicy = Field(default_factory=TranslationPolicy)
    blocks: List[TranslationBlock]


class BlockTranslationResult(BaseModel):
    id: str
    targetText: str
    language: str


class BatchTranslationResponse(BaseModel):
    contractVersion: Literal["translation-batch/1"] = "translation-batch/1"
    results: List[BlockTranslationResult]
