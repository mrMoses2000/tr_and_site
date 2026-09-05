from typing import List
from pydantic import BaseModel, Field


class ChecksumEntry(BaseModel):
    path: str
    sha256: str
    byte_size: int


class ReleaseManifest(BaseModel):
    release_id: str
    job_id: str
    slug: str
    created_at: str
    files: List[ChecksumEntry] = Field(default_factory=list)
    is_promoted: bool = False
