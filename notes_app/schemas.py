from pydantic import BaseModel
from typing import List, Optional


class ProviderModel(BaseModel):
    id: str
    label: str
    protocol: str
    enabled: bool
    base_url: str
    model: str
    has_api_key: bool


class ProviderListResponse(BaseModel):
    default_provider_id: str
    providers: List[ProviderModel]


class ProviderCreateRequest(BaseModel):
    id: str
    label: str
    protocol: str
    base_url: str
    model: str
    api_key: Optional[str] = None
    timeout_s: int = 60
    max_tokens: int = 1200


class JobCreateRequest(BaseModel):
    provider_id: Optional[str] = None
    file_paths: List[str]


class JobCreateResponse(BaseModel):
    job_id: str
    total_pages: int
    status: str
    created_at: str


class PageStatusModel(BaseModel):
    document_id: str
    index: int
    status: str
    raw_sha256: Optional[str] = None
    has_overlay: bool = False
    has_notes: bool = False


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    provider_id: Optional[str] = None
    pages: List[PageStatusModel]


class RetryNotesResponse(BaseModel):
    status: str
    document_id: str


class RetryOcrResponse(BaseModel):
    status: str
    document_id: str
