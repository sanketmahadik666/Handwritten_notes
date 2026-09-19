"""Tests for Queue logic."""

import tempfile
import unittest
from pathlib import Path

from handwritten_ocr.db import Database
from handwritten_ocr.queue import QueueWorker
from handwritten_ocr.service import JobService
from handwritten_ocr.models import JobStatus, PageStatus


class TestQueueWorker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(self.db_path)
        self.service = JobService(self.db)
        self.worker = QueueWorker(self.db, max_retries=2)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_claim_next(self):
        job = self.service.create_job("doc1", 2)
        
        # Claim first page
        page1 = self.worker.claim_next()
        self.assertIsNotNone(page1)
        self.assertEqual(page1.page_number, 1)
        self.assertEqual(page1.status, PageStatus.OCR_RUNNING)
        self.assertEqual(page1.attempt_count, 1)
        
        # Claim second page
        page2 = self.worker.claim_next()
        self.assertIsNotNone(page2)
        self.assertEqual(page2.page_number, 2)
        
        # No more pages
        page3 = self.worker.claim_next()
        self.assertIsNone(page3)
        
        # Job status should be RUNNING
        updated_job = self.service.get_job(job.job_id)
        self.assertEqual(updated_job.status, JobStatus.RUNNING)

    def test_mark_complete(self):
        job = self.service.create_job("doc1", 1)
        page1 = self.worker.claim_next()
        
        self.worker.mark_complete(page1.page_job_id, "/path/to/raw", "hash123", "/path/to/json")
        
        updated_page = self.service.get_page_job(page1.page_job_id)
        self.assertEqual(updated_page.status, PageStatus.OCR_COMPLETE)
        self.assertEqual(updated_page.raw_text_path, "/path/to/raw")
        self.assertEqual(updated_page.raw_text_sha256, "hash123")
        
        updated_job = self.service.get_job(job.job_id)
        self.assertEqual(updated_job.status, JobStatus.COMPLETED)
        self.assertEqual(updated_job.completed_pages, 1)

    def test_mark_failed(self):
        job = self.service.create_job("doc2", 2)
        page1 = self.worker.claim_next()
        
        self.worker.mark_failed(page1.page_job_id, "Bad image")
        
        updated_page = self.service.get_page_job(page1.page_job_id)
        self.assertEqual(updated_page.status, PageStatus.OCR_FAILED)
        self.assertEqual(updated_page.error, "Bad image")
        
        # Next page should still be available
        page2 = self.worker.claim_next()
        self.assertIsNotNone(page2)
        self.assertEqual(page2.page_number, 2)
        
        # Complete page 2
        self.worker.mark_complete(page2.page_job_id, "path", "hash", "json")
        
        updated_job = self.service.get_job(job.job_id)
        self.assertEqual(updated_job.status, JobStatus.COMPLETED_WITH_ERRORS)
        self.assertEqual(updated_job.failed_pages, 1)
        self.assertEqual(updated_job.completed_pages, 1)

    def test_recovery(self):
        job = self.service.create_job("doc3", 1)
        page1 = self.worker.claim_next()
        
        recovered_count = self.worker.recover_interrupted()
        self.assertEqual(recovered_count, 1)
        
        updated_page = self.service.get_page_job(page1.page_job_id)
        self.assertEqual(updated_page.status, PageStatus.QUEUED)
        
        # Claim again
        page1_again = self.worker.claim_next()
        self.assertEqual(page1_again.attempt_count, 2)
        
        # Claim again and hit max retries
        self.worker.recover_interrupted()
        page1_final = self.worker.claim_next()
        self.assertIsNone(page1_final) # Should fail due to max retries
        
        failed_page = self.service.get_page_job(page1.page_job_id)
        self.assertEqual(failed_page.status, PageStatus.OCR_FAILED)
        self.assertEqual(failed_page.error, "Max retries exceeded")


if __name__ == '__main__':
    unittest.main()
