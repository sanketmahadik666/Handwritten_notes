"""Queue and worker implementation for OCR processing."""

from __future__ import annotations

import datetime
from typing import Optional

from .db import Database
from .models import PageJob, PageStatus
from .service import _now_iso, JobService


class QueueWorker:
    def __init__(self, db: Database, max_retries: int = 3):
        self.db = db
        self.max_retries = max_retries
        self.job_service = JobService(db)

    def recover_interrupted(self) -> int:
        """Move OCR_RUNNING pages back to QUEUED."""
        now = _now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE page_jobs
                SET status = ?, updated_at = ?
                WHERE status = ?
                """,
                (PageStatus.QUEUED.value, now, PageStatus.OCR_RUNNING.value)
            )
            return cursor.rowcount

    def claim_next(self) -> Optional[PageJob]:
        """Atomically claim the next queued page."""
        now = _now_iso()
        with self.db.transaction() as conn:
            row = conn.execute(
                """
                SELECT page_job_id, job_id, attempt_count 
                FROM page_jobs 
                WHERE status = ? 
                ORDER BY created_at ASC, page_number ASC 
                LIMIT 1
                """,
                (PageStatus.QUEUED.value,)
            ).fetchone()

            if not row:
                return None

            page_job_id = row["page_job_id"]
            job_id = row["job_id"]
            new_attempt = row["attempt_count"] + 1
            
            if new_attempt > self.max_retries:
                conn.execute(
                    """
                    UPDATE page_jobs
                    SET status = ?, updated_at = ?, attempt_count = ?, error = ?
                    WHERE page_job_id = ?
                    """,
                    (PageStatus.OCR_FAILED.value, now, new_attempt, "Max retries exceeded", page_job_id)
                )
                self.job_service._update_job_status(conn, job_id)
                # We exceeded max retries, return None so worker tries another
                return None
            
            conn.execute(
                """
                UPDATE page_jobs
                SET status = ?, updated_at = ?, started_at = coalesce(started_at, ?), attempt_count = ?
                WHERE page_job_id = ?
                """,
                (PageStatus.OCR_RUNNING.value, now, now, new_attempt, page_job_id)
            )
            
            # Update parent job status to running
            conn.execute(
                """
                UPDATE jobs
                SET status = 'running', updated_at = ?, started_at = coalesce(started_at, ?)
                WHERE job_id = ?
                """,
                (now, now, job_id)
            )
            
            # Fetch updated row within the same transaction
            updated_row = conn.execute("SELECT * FROM page_jobs WHERE page_job_id = ?", (page_job_id,)).fetchone()
            return self.job_service._row_to_page_job(updated_row)

    def mark_complete(self, page_job_id: str, raw_text_path: str, raw_text_sha256: str, document_json_path: str) -> None:
        now = _now_iso()
        with self.db.transaction() as conn:
            row = conn.execute("SELECT job_id FROM page_jobs WHERE page_job_id = ?", (page_job_id,)).fetchone()
            if not row:
                return
            job_id = row["job_id"]

            conn.execute(
                """
                UPDATE page_jobs
                SET status = ?, updated_at = ?, completed_at = ?, raw_text_path = ?, raw_text_sha256 = ?, document_json_path = ?
                WHERE page_job_id = ?
                """,
                (PageStatus.OCR_COMPLETE.value, now, now, raw_text_path, raw_text_sha256, document_json_path, page_job_id)
            )
            self.job_service._update_job_status(conn, job_id)

    def mark_failed(self, page_job_id: str, error: str) -> None:
        now = _now_iso()
        with self.db.transaction() as conn:
            row = conn.execute("SELECT job_id FROM page_jobs WHERE page_job_id = ?", (page_job_id,)).fetchone()
            if not row:
                return
            job_id = row["job_id"]

            conn.execute(
                """
                UPDATE page_jobs
                SET status = ?, updated_at = ?, error = ?, completed_at = ?
                WHERE page_job_id = ?
                """,
                (PageStatus.OCR_FAILED.value, now, error, now, page_job_id)
            )
            self.job_service._update_job_status(conn, job_id)
