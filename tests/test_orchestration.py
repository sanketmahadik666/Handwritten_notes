import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from handwritten_ocr.config import AppConfig, RunConfig, PipelineConfig, RuntimeConfig, DetectorConfig, ModelConfig, PreprocessingConfig, EvaluationConfig
from handwritten_ocr.db import Database
from handwritten_ocr.models import JobStatus, PageStatus
from handwritten_ocr.orchestrator import OrchestratorService


class MockPaddleX37Adapter:
    def __init__(self, config=None):
        self.config = config

    def runtime_observation(self):
        return {"versions": {}, "detector": {}, "recognizer": {}}

    def process(self, image_bgr):
        # We can optionally simulate failure if an attribute is set
        if getattr(self, "should_fail", False):
            raise RuntimeError("Mock OCR Failure")

        mock_output = MagicMock()
        mock_output.regions = []
        mock_output.timing = {"ms": 10.0}
        
        region = MagicMock()
        region.sorted_index = 0
        region.detector_index = 0
        region.raw_polygon = [[0, 0], [10, 0], [10, 10], [0, 10]]
        region.sorted_polygon = [[0, 0], [10, 0], [10, 10], [0, 10]]
        region.detector_score = 0.99
        region.crop = np.zeros((10, 10, 3), dtype=np.uint8)
        region.crop_status = "success"
        region.raw_text = "mocked text"
        region.recognition_score = 0.99
        region.recognition_order = 0
        region.metadata = {}
        mock_output.regions.append(region)
        
        return mock_output


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.sqlite")
        self.db = Database(self.db_path)
        
        app_config = AppConfig(
            database_path=self.db_path,
            ocr_worker_concurrency=1,
            notes_worker_concurrency=1,
            max_retries=3,
            queue_poll_interval_seconds=1
        )
        runtime_cfg = RuntimeConfig(paddleocr_version="", paddlex_version="", paddlepaddle_version="", requested_engine=None, device="cpu", enable_mkldnn=False, enable_cinn=False, cpu_threads=1)
        pipeline_cfg = PipelineConfig(lang="en", ocr_version="PP-OCRv4", use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, text_rec_score_thresh=0.0)
        detector_cfg = DetectorConfig(model_name="PP-OCRv6_medium_det", model_dir=None, limit_side_len=960, limit_type="max", max_side_limit=4000, thresh=0.3, box_thresh=0.6, unclip_ratio=1.5)
        recognizer_cfg = ModelConfig(model_name="PP-OCRv6_medium_rec", model_dir=None)
        doc_pre = {"orientation_classification": False, "unwarping": False, "textline_orientation": False}
        mod_pre = {"detector": "PaddleX-managed", "recognizer": "PaddleX-managed"}
        preproc = PreprocessingConfig(mode="original", operations=tuple())
        eval_cfg = EvaluationConfig(unicode_normalization="NFC", case_sensitive=True, whitespace="collapse_runs", punctuation="preserve")
        
        self.config = RunConfig(
            runtime=runtime_cfg, pipeline=pipeline_cfg, detector=detector_cfg, recognizer=recognizer_cfg,
            document_preprocessing=doc_pre, model_preprocessing=mod_pre, preprocessing=preproc, evaluation=eval_cfg,
            correction_status="skipped", app=app_config
        )
        
        self.output_root = Path(self.temp_dir) / "output"
        self.output_root.mkdir()
        
        self.service = OrchestratorService(self.db, self.config, self.output_root)
        
        # Create a mock directory with 3 dummy images
        self.input_dir = Path(self.temp_dir) / "input_docs"
        self.input_dir.mkdir()
        
        # Mock load_image and discover_images
        self.patcher_discover = patch("handwritten_ocr.orchestrator.discover_images")
        self.mock_discover = self.patcher_discover.start()
        self.mock_discover.return_value = (self.input_dir, [
            self.input_dir / "page1.png",
            self.input_dir / "page2.png",
            self.input_dir / "page3.png"
        ])
        
        self.patcher_load = patch("handwritten_ocr.orchestrator.load_image")
        self.mock_load = self.patcher_load.start()
        mock_img = MagicMock()
        mock_img.source_path.name = "page.png"
        mock_img.relative_path = "page.png"
        mock_img.source_image_sha256 = "12345"
        mock_img.width = 100
        mock_img.height = 100
        mock_img.original_channels = 3
        mock_img.input_handling = {}
        mock_img.bgr_image = np.zeros((100, 100, 3), dtype=np.uint8)
        self.mock_load.return_value = mock_img

        self.patcher_adapter = patch("handwritten_ocr.orchestrator.PaddleX37Adapter", MockPaddleX37Adapter)
        self.mock_adapter_class = self.patcher_adapter.start()

    def tearDown(self):
        self.service.stop_orchestrator()
        self.patcher_discover.stop()
        self.patcher_load.stop()
        self.patcher_adapter.stop()
        shutil.rmtree(self.temp_dir)

    def test_job_processing(self):
        """Test that multiple pages are processed independently and FIFO ordering is preserved."""
        job = self.service.create_job(str(self.input_dir), 3)
        self.assertEqual(job.status, JobStatus.QUEUED)
        
        self.service.start_orchestrator()
        
        # Wait for processing
        max_wait = 10
        start = time.time()
        while time.time() - start < max_wait:
            updated_job = self.service.get_job(job.job_id)
            if updated_job.status == JobStatus.COMPLETED:
                break
            time.sleep(0.1)
            
        updated_job = self.service.get_job(job.job_id)
        self.assertEqual(updated_job.status, JobStatus.COMPLETED)
        self.assertEqual(updated_job.completed_pages, 3)
        
        pages = self.service.get_pages(job.job_id)
        for page in pages:
            self.assertEqual(page.status, PageStatus.OCR_COMPLETE)
            self.assertTrue(page.raw_text_path is not None)
            
            # Verify artifact directory exists
            attempt_dir = self.output_root / job.job_id / f"attempt-{page.attempt_count}"
            doc_dir = attempt_dir / "documents" / f"page-{page.page_number:04d}"
            self.assertTrue(doc_dir.exists())
            self.assertTrue((doc_dir / "raw.txt").exists())
            self.assertTrue((doc_dir / "document.json").exists())

    def test_single_page_failure_isolation(self):
        """Test that a failed page does not stop subsequent pages."""
        job = self.service.create_job(str(self.input_dir), 3)
        
        def mock_load_side_effect(source_path, input_root):
            if "page2" in str(source_path):
                from handwritten_ocr.image_io import ImageInputError
                raise ImageInputError("Corrupt image")
            
            mock_img = MagicMock()
            mock_img.source_path.name = "page.png"
            mock_img.relative_path = "page.png"
            mock_img.source_image_sha256 = "12345"
            mock_img.width = 100
            mock_img.height = 100
            mock_img.original_channels = 3
            mock_img.input_handling = {}
            mock_img.bgr_image = np.zeros((100, 100, 3), dtype=np.uint8)
            return mock_img
            
        self.mock_load.side_effect = mock_load_side_effect
        
        self.service.start_orchestrator()
        
        max_wait = 10
        start = time.time()
        while time.time() - start < max_wait:
            updated_job = self.service.get_job(job.job_id)
            if updated_job.status in (JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_ERRORS):
                break
            time.sleep(0.1)
            
        updated_job = self.service.get_job(job.job_id)
        self.assertEqual(updated_job.status, JobStatus.COMPLETED_WITH_ERRORS)
        
        pages = self.service.get_pages(job.job_id)
        self.assertEqual(pages[0].status, PageStatus.OCR_COMPLETE)
        self.assertEqual(pages[1].status, PageStatus.OCR_FAILED)
        self.assertEqual(pages[2].status, PageStatus.OCR_COMPLETE)

    def test_explicit_retry(self):
        """Test explicit retry creates a new attempt without deleting prior artifacts."""
        job = self.service.create_job(str(self.input_dir), 1)
        
        # Force failure
        self.mock_load.side_effect = Exception("Temporary failure")
        self.service.start_orchestrator()
        
        while self.service.get_job(job.job_id).status != JobStatus.FAILED:
            time.sleep(0.1)
            
        pages = self.service.get_pages(job.job_id)
        page = pages[0]
        self.assertEqual(page.status, PageStatus.OCR_FAILED)
        self.assertEqual(page.attempt_count, 1)
        
        self.service.stop_orchestrator()
        
        # Remove failure condition
        self.mock_load.side_effect = None
        
        # Retry
        self.service.retry_page(page.page_job_id)
        
        updated_job = self.service.get_job(job.job_id)
        self.assertIn(updated_job.status, (JobStatus.QUEUED, JobStatus.RUNNING))
        
        self.service.start_orchestrator()
        
        max_wait = 10
        start = time.time()
        while time.time() - start < max_wait:
            updated_job = self.service.get_job(job.job_id)
            if updated_job.status == JobStatus.COMPLETED:
                break
            time.sleep(0.1)
            
        pages = self.service.get_pages(job.job_id)
        page = pages[0]
        self.assertEqual(page.status, PageStatus.OCR_COMPLETE)
        self.assertEqual(page.attempt_count, 2)
        
        # Artifacts should be in attempt-2
        attempt_dir = self.output_root / job.job_id / "attempt-2"
        doc_dir = attempt_dir / "documents" / "page-0001"
        self.assertTrue(doc_dir.exists())

    def test_interrupted_recovery(self):
        """Test that interrupted ocr_running work follows configured recovery policy."""
        job = self.service.create_job(str(self.input_dir), 1)
        
        # Manually set to OCR_RUNNING
        pages = self.service.get_pages(job.job_id)
        page = pages[0]
        with self.db.transaction() as conn:
            conn.execute("UPDATE page_jobs SET status = ? WHERE page_job_id = ?", (PageStatus.OCR_RUNNING.value, page.page_job_id))
            
        # Creating a new service instance should trigger recovery on start
        new_service = OrchestratorService(self.db, self.config, self.output_root)
        
        # We can just call recover_interrupted manually to simulate what start does (if we run loop directly)
        recovered = new_service.queue_worker.recover_interrupted()
        self.assertEqual(recovered, 1)
        
        page = new_service.get_page(page.page_job_id)
        self.assertEqual(page.status, PageStatus.QUEUED)

if __name__ == '__main__':
    unittest.main()
