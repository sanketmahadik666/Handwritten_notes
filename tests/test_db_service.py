"""Tests for DB and Service layers."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from handwritten_ocr.db import Database
from handwritten_ocr.service import JobService, JobNotFoundError, PageNotFoundError, InvalidTransitionError
from handwritten_ocr.models import JobStatus, PageStatus


class TestDatabaseAndService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(self.db_path)
        self.service = JobService(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_schema_init(self):
        with self.db.connection() as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = {t["name"] for t in tables}
            self.assertIn("jobs", table_names)
            self.assertIn("page_jobs", table_names)

    def test_job_creation(self):
        job = self.service.create_job("doc1", 3, "fingerprint_123")
        self.assertEqual(job.total_pages, 3)
        self.assertEqual(job.status, JobStatus.QUEUED)
        
        pages = self.service.get_job_pages(job.job_id)
        self.assertEqual(len(pages), 3)
        self.assertEqual(pages[0].page_number, 1)
        self.assertEqual(pages[1].page_number, 2)
        self.assertEqual(pages[2].page_number, 3)
        for page in pages:
            self.assertEqual(page.status, PageStatus.QUEUED)

    def test_job_not_found(self):
        with self.assertRaises(JobNotFoundError):
            self.service.get_job("invalid")

    def test_invalid_page_count(self):
        with self.assertRaises(ValueError):
            self.service.create_job("doc1", 0)

    def test_reopen_persists(self):
        job = self.service.create_job("doc1", 2)
        # Reopen db
        new_db = Database(self.db_path)
        new_service = JobService(new_db)
        
        reloaded_job = new_service.get_job(job.job_id)
        self.assertEqual(reloaded_job.job_id, job.job_id)
        
        pages = new_service.get_job_pages(job.job_id)
        self.assertEqual(len(pages), 2)
        
    def test_retry_page(self):
        job = self.service.create_job("doc1", 1)
        pages = self.service.get_job_pages(job.job_id)
        page = pages[0]
        
        # Should raise InvalidTransitionError because it's QUEUED
        with self.assertRaises(InvalidTransitionError):
            self.service.retry_page(page.page_job_id)
            
        # Manually fail it
        with self.db.transaction() as conn:
            conn.execute("UPDATE page_jobs SET status = ? WHERE page_job_id = ?", (PageStatus.OCR_FAILED.value, page.page_job_id))
            
        # Retry should succeed now
        retried_page = self.service.retry_page(page.page_job_id)
        self.assertEqual(retried_page.status, PageStatus.QUEUED)

if __name__ == '__main__':
    unittest.main()
