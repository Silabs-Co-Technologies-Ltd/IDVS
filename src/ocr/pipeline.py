"""Offline OpenCV/EasyOCR pipeline for NAUB ID-card field extraction."""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

from src.config.settings import AppSettings
from src.models.entities import OCRField, OCRResult

try:
    import cv2
except ImportError:  # pragma: no cover - exercised only on minimal CI images
    cv2 = None

try:
    import easyocr
except ImportError:  # pragma: no cover
    easyocr = None


class OCRService:
    """Reusable service for image acquisition, card normalization, ROIs, and OCR."""

    def __init__(self, settings: AppSettings, reader: Any | None = None) -> None:
        self.settings = settings
        self.reader = reader

    def load_image(self, path: Path):
        if np is None or Image is None:
            raise RuntimeError("NumPy and Pillow are required for image loading")
        return np.array(Image.open(path).convert("RGB"))

    def capture_webcam(self, camera_index: int | None = None):
        if cv2 is None or np is None:
            raise RuntimeError("OpenCV is required for webcam capture")
        cap = cv2.VideoCapture(self.settings.camera_index if camera_index is None else camera_index)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError("Unable to capture an image from the configured camera")
        return frame

    def detect_card(self, image):
        """Detect the largest rectangular contour and perspective-correct it."""
        if cv2 is None:
            return image
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY if image.shape[-1] == 3 else cv2.COLOR_RGB2GRAY)
        edged = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image
        contour = max(contours, key=cv2.contourArea)
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) != 4:
            return image
        pts = self._order_points(approx.reshape(4, 2).astype("float32"))
        width = int(max(np.linalg.norm(pts[2] - pts[3]), np.linalg.norm(pts[1] - pts[0])))
        height = int(max(np.linalg.norm(pts[1] - pts[2]), np.linalg.norm(pts[0] - pts[3])))
        dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
        return cv2.warpPerspective(image, cv2.getPerspectiveTransform(pts, dst), (width, height))

    def preprocess(self, image):
        if cv2 is None:
            return image
        if image.ndim == 2:
            gray = image
        elif image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            raise ValueError("Expected a 2-D grayscale or 3-D RGB image")
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        denoised = cv2.fastNlMeansDenoising(clahe, h=10)
        sharp = cv2.addWeighted(denoised, 1.5, cv2.GaussianBlur(denoised, (0, 0), 3), -0.5, 0)
        return cv2.adaptiveThreshold(sharp, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9)

    def extract_rois(self, image) -> dict[str, object]:
        height, width = image.shape[:2]
        rois = {}
        for name, (x, y, w, h) in self.settings.roi_template.items():
            rois[name] = image[int(y * height): int((y + h) * height), int(x * width): int((x + w) * width)]
        return rois

    def run(self, image, image_path: Path | None = None) -> OCRResult:
        start = time.perf_counter()
        normalized = self.detect_card(image)
        processed = self.preprocess(normalized)
        fields = {name: self._ocr_field(name, roi) for name, roi in self.extract_rois(processed).items()}
        confidence = sum(field.confidence for field in fields.values()) / max(len(fields), 1)
        return OCRResult(fields, confidence, image_path, time.perf_counter() - start)

    def _ocr_field(self, name: str, roi) -> OCRField:
        reader = self._reader()
        results = reader.readtext(roi) if reader else []
        texts = [str(r[1]) for r in results]
        confidences = [float(r[2]) for r in results]
        text = self.clean_text(name, " ".join(texts))
        return OCRField(name, text, sum(confidences) / max(len(confidences), 1), [tuple(map(tuple, r[0])) for r in results] if results else [])

    def _reader(self) -> Any | None:
        if self.reader is None and easyocr is not None:
            self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return self.reader

    @staticmethod
    def clean_text(field_name: str, text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip().upper()
        if field_name == "matric_number":
            return re.sub(r"[^A-Z0-9/\-]", "", text)
        return re.sub(r"[^A-Z0-9 /\-&]", "", text)

    @staticmethod
    def _order_points(pts):
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0], rect[2] = pts[np.argmin(s)], pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1], rect[3] = pts[np.argmin(diff)], pts[np.argmax(diff)]
        return rect
