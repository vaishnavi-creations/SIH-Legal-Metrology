import time
import logging
from pathlib import Path
from typing import Union, Optional, List
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from app.schemas.ocr import OCRTextBlock, OCRResult

logger = logging.getLogger(__name__)

class OCRService:
    """
    Lightweight, high-performance OCR service powered by RapidOCR (PaddleOCR models running on ONNX Runtime).
    Extracts text, confidence scores, and bounding box coordinates from product packaging labels.
    """

    _instance: Optional["OCRService"] = None
    _engine: Optional[RapidOCR] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OCRService, cls).__new__(cls)
            try:
                cls._engine = RapidOCR()
                logger.info("RapidOCR ONNX engine initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize RapidOCR engine: {e}")
                raise
        return cls._instance

    @classmethod
    def extract_from_image(cls, image_input: Union[np.ndarray, str, Path]) -> OCRResult:
        """
        Executes OCR extraction on an image (provided as an OpenCV numpy array or a file path).
        Returns a structured OCRResult containing full text, confidence, and bounding box coordinates.
        """
        start_time = time.time()

        # Load image if file path is provided
        if isinstance(image_input, (str, Path)):
            img_path = str(image_input)
            img = cv2.imread(img_path)
            if img is None:
                raise ValueError(f"Could not read image from path: {img_path}")
        elif isinstance(image_input, np.ndarray):
            img = image_input
        else:
            raise TypeError("Expected image_input to be a numpy array or file path.")

        # Ensure engine is instantiated
        service = cls()
        engine = service._engine

        # Run OCR inference
        # RapidOCR returns: (results, elapse_list)
        # results format: [[polygon_points, text, confidence], ...]
        raw_results, elapse = engine(img)
        elapsed_total = round(time.time() - start_time, 4)

        if not raw_results:
            return OCRResult(
                full_text="",
                blocks=[],
                block_count=0,
                average_confidence=0.0,
                execution_time_seconds=elapsed_total
            )

        blocks: List[OCRTextBlock] = []
        confidences: List[float] = []
        text_lines: List[str] = []

        for item in raw_results:
            polygon, text, conf = item
            conf_float = round(float(conf), 4)
            confidences.append(conf_float)

            # Calculate 2D bounding box [x_min, y_min, x_max, y_max]
            x_coords = [p[0] for p in polygon]
            y_coords = [p[1] for p in polygon]
            box_2d = [
                int(min(x_coords)),
                int(min(y_coords)),
                int(max(x_coords)),
                int(max(y_coords))
            ]

            clean_text = text.strip()
            if clean_text:
                text_lines.append(clean_text)

            blocks.append(
                OCRTextBlock(
                    text=clean_text,
                    confidence=conf_float,
                    polygon=[[float(p[0]), float(p[1])] for p in polygon],
                    box_2d=box_2d
                )
            )

        avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        full_text = "\n".join(text_lines)

        return OCRResult(
            full_text=full_text,
            blocks=blocks,
            block_count=len(blocks),
            average_confidence=avg_conf,
            execution_time_seconds=elapsed_total
        )
