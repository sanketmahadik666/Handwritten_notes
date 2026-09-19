"""Deterministic, provenance-preserving raster image input handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import unicodedata

import cv2
import numpy as np

from .hashing import sha256_file


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
UNSUPPORTED_IMAGE_EXTENSIONS = {
    ".pdf",
    ".gif",
    ".svg",
    ".ico",
    ".heic",
    ".heif",
    ".jxl",
    ".jp2",
    ".exr",
    ".hdr",
}


class ImageInputError(ValueError):
    """Raised for unsupported, unreadable, or unsafe input images."""


@dataclass
class LoadedImage:
    source_path: Path
    relative_path: str
    source_image_sha256: str
    bgr_image: np.ndarray
    width: int
    height: int
    original_channels: int
    input_handling: dict[str, Any]


def _normalized_relative(path: Path, root: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = Path(path.name)
    return unicodedata.normalize("NFC", relative.as_posix())


def discover_images(input_path: str | Path) -> tuple[Path, list[Path]]:
    root_or_file = Path(input_path)
    if not root_or_file.exists():
        raise ImageInputError(f"Input path does not exist: {root_or_file}")
    if root_or_file.is_file():
        if root_or_file.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ImageInputError(f"Unsupported image extension: {root_or_file.suffix or '<none>'}")
        return root_or_file.parent, [root_or_file]
    if not root_or_file.is_dir():
        raise ImageInputError(f"Input path is neither a file nor directory: {root_or_file}")
    files = [path for path in root_or_file.rglob("*") if path.is_file()]
    unsupported = sorted(
        (path for path in files if path.suffix.lower() in UNSUPPORTED_IMAGE_EXTENSIONS),
        key=lambda path: _normalized_relative(path, root_or_file).casefold(),
    )
    if unsupported:
        listed = ", ".join(_normalized_relative(path, root_or_file) for path in unsupported)
        raise ImageInputError(f"Unsupported image files must not be skipped: {listed}")
    images = [path for path in files if path.suffix.lower() in SUPPORTED_EXTENSIONS]
    images.sort(key=lambda path: _normalized_relative(path, root_or_file).casefold())
    if not images:
        raise ImageInputError(f"No supported raster images found under: {root_or_file}")
    return root_or_file, images


def load_image(path: str | Path, input_root: str | Path) -> LoadedImage:
    source_path = Path(path)
    if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ImageInputError(f"Unsupported image extension: {source_path.suffix or '<none>'}")
    image = cv2.imread(str(source_path), cv2.IMREAD_UNCHANGED)
    if image is None or image.size == 0:
        raise ImageInputError(f"Unreadable image: {source_path}")
    if image.dtype != np.uint8:
        raise ImageInputError(f"Unsupported image dtype {image.dtype}; only uint8 raster images are supported")

    handling: dict[str, Any] = {"decoder": "opencv_imread_unchanged", "operations": []}
    if image.ndim == 2:
        height, width = image.shape
        original_channels = 1
        bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        handling["operations"].append("grayscale_to_bgr")
    elif image.ndim == 3 and image.shape[2] == 3:
        height, width, original_channels = image.shape
        bgr = image
        handling["operations"].append("preserved_bgr")
    elif image.ndim == 3 and image.shape[2] == 4:
        height, width, original_channels = image.shape
        alpha = image[:, :, 3:4].astype(np.float32) / 255.0
        bgr = np.round(image[:, :, :3].astype(np.float32) * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
        handling["operations"].append("bgra_alpha_composited_on_white_to_bgr")
    else:
        raise ImageInputError(f"Unsupported image layout {image.shape} for: {source_path}")

    handling["decoded_dtype"] = str(image.dtype)
    handling["model_input_channels"] = 3
    return LoadedImage(
        source_path=source_path,
        relative_path=_normalized_relative(source_path, Path(input_root)),
        source_image_sha256=sha256_file(source_path),
        bgr_image=bgr,
        width=int(width),
        height=int(height),
        original_channels=int(original_channels),
        input_handling=handling,
    )
