"""Data models for Phase 2: Job and PageJob tracking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PageStatus(str, Enum):
    QUEUED = "queued"
    OCR_RUNNING = "ocr_running"
    OCR_FAILED = "ocr_failed"
    OCR_COMPLETE = "ocr_complete"
    NOTES_QUEUED = "notes_queued"
    NOTES_RUNNING = "notes_running"
    NOTES_FAILED = "notes_failed"
    NOTES_READY = "notes_ready"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    document_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    total_pages: int
    completed_pages: int
    failed_pages: int
    error: Optional[str]
    config_fingerprint: Optional[str]


@dataclass
class PageJob:
    page_job_id: str
    job_id: str
    document_id: str
    page_number: int
    status: PageStatus
    created_at: str
    updated_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    attempt_count: int
    error: Optional[str]
    raw_text_path: Optional[str]
    raw_text_sha256: Optional[str]
    document_json_path: Optional[str]
    overlay_path: Optional[str]
