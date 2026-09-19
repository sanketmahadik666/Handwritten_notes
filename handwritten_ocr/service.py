"""Service layer for creating and querying jobs and pages."""

from __future__ import annotations

import datetime
import uuid
from typing import List, Optional

from .db import Database
from .models import Job, PageJob, JobStatus, PageStatus


class JobNotFoundError(Exception):
    pass


class PageNotFoundError(Exception):
    pass


class InvalidTransitionError(Exception):
    pass


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class JobService:
    def __init__(self, db: Database):
        self.db = db

    def create_job(self, document_id: str, page_count: int, config_fingerprint: Optional[str] = None) -> Job:
        """Create a new job and enqueue all its pages atomically."""
        if page_count <= 0:
            raise ValueError("page_count must be positive")

        job_id = str(uuid.uuid4())
        now = _now_iso()

        job = Job(
            job_id=job_id,
            document_id=document_id,
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
            started_at=None,
            completed_at=None,
            total_pages=page_count,
            completed_pages=0,
            failed_pages=0,
            error=None,
            config_fingerprint=config_fingerprint,
        )

        pages = []
        for p in range(1, page_count + 1):
            page = PageJob(
                page_job_id=str(uuid.uuid4()),
                job_id=job_id,
                document_id=document_id,
                page_number=p,
                status=PageStatus.QUEUED,
                created_at=now,
                updated_at=now,
                started_at=None,
                completed_at=None,
                attempt_count=0,
                error=None,
                raw_text_path=None,
                raw_text_sha256=None,
                document_json_path=None,
                overlay_path=None,
            )
            pages.append(page)

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, document_id, status, created_at, updated_at,
                    started_at, completed_at, total_pages, completed_pages,
                    failed_pages, error, config_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id, job.document_id, job.status.value, job.created_at, job.updated_at,
                    job.started_at, job.completed_at, job.total_pages, job.completed_pages,
                    job.failed_pages, job.error, job.config_fingerprint
                )
            )

            for p in pages:
                conn.execute(
                    """
                    INSERT INTO page_jobs (
                        page_job_id, job_id, document_id, page_number, status,
                        created_at, updated_at, started_at, completed_at, attempt_count,
                        error, raw_text_path, raw_text_sha256, document_json_path, overlay_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p.page_job_id, p.job_id, p.document_id, p.page_number, p.status.value,
                        p.created_at, p.updated_at, p.started_at, p.completed_at, p.attempt_count,
                        p.error, p.raw_text_path, p.raw_text_sha256, p.document_json_path, p.overlay_path
                    )
                )

        return job

    def get_job(self, job_id: str) -> Job:
        with self.db.connection() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row:
                raise JobNotFoundError(f"Job {job_id} not found")
            return self._row_to_job(row)

    def get_job_pages(self, job_id: str) -> List[PageJob]:
        with self.db.connection() as conn:
            rows = conn.execute("SELECT * FROM page_jobs WHERE job_id = ? ORDER BY page_number ASC", (job_id,)).fetchall()
            return [self._row_to_page_job(r) for r in rows]

    def get_page_job(self, page_job_id: str) -> PageJob:
        with self.db.connection() as conn:
            row = conn.execute("SELECT * FROM page_jobs WHERE page_job_id = ?", (page_job_id,)).fetchone()
            if not row:
                raise PageNotFoundError(f"PageJob {page_job_id} not found")
            return self._row_to_page_job(row)

    def retry_page(self, page_job_id: str) -> PageJob:
        now = _now_iso()
        with self.db.transaction() as conn:
            row = conn.execute("SELECT status, job_id FROM page_jobs WHERE page_job_id = ?", (page_job_id,)).fetchone()
            if not row:
                raise PageNotFoundError(f"PageJob {page_job_id} not found")

            if row["status"] != PageStatus.OCR_FAILED.value:
                raise InvalidTransitionError(f"Cannot retry page in status {row['status']}")

            conn.execute(
                """
                UPDATE page_jobs
                SET status = ?, updated_at = ?, error = NULL
                WHERE page_job_id = ?
                """,
                (PageStatus.QUEUED.value, now, page_job_id)
            )

            # Re-evaluating job status logic (e.g. from failed -> running/queued)
            self._update_job_status(conn, row["job_id"])

        return self.get_page_job(page_job_id)

    def _row_to_job(self, row: dict) -> Job:
        return Job(
            job_id=row["job_id"],
            document_id=row["document_id"],
            status=JobStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            total_pages=row["total_pages"],
            completed_pages=row["completed_pages"],
            failed_pages=row["failed_pages"],
            error=row["error"],
            config_fingerprint=row["config_fingerprint"],
        )

    def _row_to_page_job(self, row: dict) -> PageJob:
        return PageJob(
            page_job_id=row["page_job_id"],
            job_id=row["job_id"],
            document_id=row["document_id"],
            page_number=row["page_number"],
            status=PageStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            attempt_count=row["attempt_count"],
            error=row["error"],
            raw_text_path=row["raw_text_path"],
            raw_text_sha256=row["raw_text_sha256"],
            document_json_path=row["document_json_path"],
            overlay_path=row["overlay_path"],
        )

    def _update_job_status(self, conn, job_id: str):
        """Recompute job status based on pages and update."""
        rows = conn.execute("SELECT status FROM page_jobs WHERE job_id = ?", (job_id,)).fetchall()
        total = len(rows)
        completed = sum(1 for r in rows if r["status"] == PageStatus.OCR_COMPLETE.value)
        failed = sum(1 for r in rows if r["status"] == PageStatus.OCR_FAILED.value)
        queued = sum(1 for r in rows if r["status"] == PageStatus.QUEUED.value)
        running = sum(1 for r in rows if r["status"] == PageStatus.OCR_RUNNING.value)
        
        now = _now_iso()

        new_status = JobStatus.QUEUED
        if total > 0:
            if completed == total:
                new_status = JobStatus.COMPLETED
            elif completed + failed == total:
                if completed == 0:
                    new_status = JobStatus.FAILED
                else:
                    new_status = JobStatus.COMPLETED_WITH_ERRORS
            elif running > 0 or (completed > 0 and queued > 0):
                new_status = JobStatus.RUNNING
            elif queued == total:
                new_status = JobStatus.QUEUED
            else:
                new_status = JobStatus.RUNNING
        
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, completed_pages = ?, failed_pages = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (new_status.value, completed, failed, now, job_id)
        )
