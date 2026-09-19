from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from handwritten_ocr.image_io import ImageInputError, discover_images, load_image


class ImageIoTests(unittest.TestCase):
    def test_discovery_is_deterministic_and_handles_common_channels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            gray = np.full((4, 5), 70, dtype=np.uint8)
            bgr = np.full((4, 5, 3), (10, 20, 30), dtype=np.uint8)
            bgra = np.zeros((4, 5, 4), dtype=np.uint8)
            bgra[:, :, :3] = (0, 0, 255)
            bgra[:, :, 3] = 0
            self.assertTrue(cv2.imwrite(str(root / "b.png"), bgr))
            self.assertTrue(cv2.imwrite(str(root / "a.png"), gray))
            self.assertTrue(cv2.imwrite(str(nested / "c.png"), bgra))

            input_root, images = discover_images(root)
            self.assertEqual([path.relative_to(root).as_posix() for path in images], ["a.png", "b.png", "nested/c.png"])
            loaded_gray = load_image(images[0], input_root)
            loaded_bgr = load_image(images[1], input_root)
            loaded_bgra = load_image(images[2], input_root)
            self.assertEqual(loaded_gray.original_channels, 1)
            self.assertEqual(loaded_gray.bgr_image.shape, (4, 5, 3))
            self.assertEqual(loaded_bgr.original_channels, 3)
            self.assertEqual(loaded_bgr.bgr_image[0, 0].tolist(), [10, 20, 30])
            self.assertEqual(loaded_bgra.original_channels, 4)
            self.assertEqual(loaded_bgra.bgr_image[0, 0].tolist(), [255, 255, 255])
            self.assertIn("bgra_alpha_composited_on_white_to_bgr", loaded_bgra.input_handling["operations"])

    def test_rejects_unsupported_and_unreadable_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsupported = root / "note.pdf"
            unsupported.write_bytes(b"not a PDF test image")
            corrupt = root / "broken.png"
            corrupt.write_bytes(b"not an image")
            with self.assertRaises(ImageInputError):
                discover_images(unsupported)
            with self.assertRaises(ImageInputError):
                load_image(corrupt, root)

    def test_directory_does_not_skip_unsupported_image_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bgr = np.full((4, 5, 3), (10, 20, 30), dtype=np.uint8)
            self.assertTrue(cv2.imwrite(str(root / "keep.png"), bgr))
            (root / "notes.pdf").write_bytes(b"%PDF-placeholder")
            with self.assertRaises(ImageInputError):
                discover_images(root)
