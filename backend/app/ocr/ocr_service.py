import time
import logging
from pathlib import Path
from typing import Union, Optional, List, Tuple
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from ch_ppocr_v3_rec.utils import CTCLabelDecode
from app.schemas.ocr import OCRTextBlock, OCRResult
from app.ocr.script_detector import ScriptDetector

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent / "models" / "devanagari"
DEVANAGARI_MODEL_PATH = MODELS_DIR / "rec.onnx"
DEVANAGARI_DICT_PATH = MODELS_DIR / "dict.txt"


class DevanagariRecognizer:
    """
    Specialized Devanagari text recognition engine based on PaddleOCR's
    devanagari_PP-OCRv3_mobile_rec ONNX model with complete Devanagari CTC vocabulary.
    """

    def __init__(self, model_path: Union[str, Path], dict_path: Union[str, Path]):
        model_str = str(model_path)
        dict_str = str(dict_path)
        if not Path(model_str).exists() or not Path(dict_str).exists():
            raise FileNotFoundError(
                f"Devanagari model files not found: {model_str}, {dict_str}"
            )

        # Initialize RapidOCR with use_angle_cls=False to avoid misclassifying Devanagari Shirorekha
        self._engine = RapidOCR(use_angle_cls=False)
        OrtInferSession = self._engine.init_module(
            "ch_ppocr_v3_rec.text_recognize", "OrtInferSession"
        )
        self._engine.text_recognizer.session = OrtInferSession(
            {"model_path": model_str, "use_cuda": False}
        )
        self._engine.text_recognizer.character_dict_path = dict_str
        self._engine.text_recognizer.postprocess_op = CTCLabelDecode(dict_str)

    def recognize_crops(self, crop_list: List[np.ndarray]) -> Tuple[list, float]:
        if not crop_list:
            return [], 0.0
        return self._engine.text_recognizer(crop_list)


class OCRService:
    """
    Lightweight, high-performance multilingual OCR service powered by RapidOCR
    (PaddleOCR models running on ONNX Runtime) with script-aware multi-model routing.
    Extracts text, confidence scores, bounding box coordinates, and script classifications
    from product packaging labels.
    """

    _instance: Optional["OCRService"] = None
    _engine: Optional[RapidOCR] = None
    _devanagari_engine: Optional[DevanagariRecognizer] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OCRService, cls).__new__(cls)
            try:
                cls._engine = RapidOCR()
                logger.info("RapidOCR baseline engine initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize RapidOCR engine: {e}")
                raise

            try:
                if DEVANAGARI_MODEL_PATH.exists() and DEVANAGARI_DICT_PATH.exists():
                    cls._devanagari_engine = DevanagariRecognizer(
                        DEVANAGARI_MODEL_PATH, DEVANAGARI_DICT_PATH
                    )
                    logger.info("Devanagari OCR recognition engine initialized successfully.")
                else:
                    logger.warning(
                        f"Devanagari OCR model not found at {DEVANAGARI_MODEL_PATH}. "
                        "Running in English/Latin only mode."
                    )
                    cls._devanagari_engine = None
            except Exception as e:
                logger.warning(
                    f"Could not initialize Devanagari OCR engine: {e}. Falling back to baseline."
                )
                cls._devanagari_engine = None

        return cls._instance

    @classmethod
    def _select_best_recognition(
        cls,
        text_en: str,
        score_en: float,
        text_hi: Optional[str],
        score_hi: Optional[float],
        min_confidence: float = 0.5,
    ) -> Optional[Tuple[str, float, str, float]]:
        """
        Selects the most accurate recognition result between English and Devanagari models for a crop.
        Returns (chosen_text, chosen_confidence, detected_script, script_confidence)
        or None if both results fall below min_confidence.
        """
        clean_en = (text_en or "").strip()
        clean_hi = (text_hi or "").strip() if text_hi is not None else ""
        s_en = float(score_en) if score_en is not None else 0.0
        s_hi = float(score_hi) if score_hi is not None else 0.0

        script_en, conf_en = ScriptDetector.detect_script(clean_en)
        script_hi, conf_hi = (
            ScriptDetector.detect_script(clean_hi) if clean_hi else ("UNKNOWN", 0.0)
        )

        # 1. If Devanagari model detected Devanagari or Mixed script with acceptable confidence:
        # The English model has 0 Devanagari characters in its vocabulary and cannot recognize it.
        if clean_hi and script_hi in ("DEVANAGARI", "MIXED") and s_hi >= min_confidence:
            return clean_hi, s_hi, script_hi, conf_hi

        # 2. If English model has acceptable confidence:
        # Prefer English baseline for Latin text, barcodes, and alphanumeric packaging codes
        if clean_en and s_en >= min_confidence:
            return clean_en, s_en, script_en, conf_en

        # 3. If English model failed (< 0.5) but Devanagari model produced valid text (>= 0.5):
        if clean_hi and s_hi >= min_confidence:
            return clean_hi, s_hi, script_hi, conf_hi

        # 4. Both models fell below confidence threshold
        return None

    @classmethod
    def extract_from_image(cls, image_input: Union[np.ndarray, str, Path]) -> OCRResult:
        """
        Executes multilingual OCR extraction on an image (OpenCV numpy array or file path).
        Returns a structured OCRResult containing full text, confidence, script metadata, and bounding boxes.
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

        # Ensure service is instantiated
        service = cls()
        default_engine = service._engine

        # 1. Detect text regions using the shared RapidOCR detector
        dt_boxes, det_elapse = default_engine.text_detector(img)

        if dt_boxes is None or len(dt_boxes) == 0:
            elapsed_total = round(time.time() - start_time, 4)
            return OCRResult(
                full_text="",
                blocks=[],
                block_count=0,
                average_confidence=0.0,
                execution_time_seconds=elapsed_total,
            )

        # 2. Sort bounding boxes (top-to-bottom, left-to-right) and extract cropped text images
        dt_boxes = default_engine.sorted_boxes(dt_boxes)
        img_crop_list = default_engine.get_crop_img_list(img, dt_boxes)

        # 3. Preserve unrotated crops for Devanagari model
        # (angle classifier in default_engine can misclassify Devanagari Shirorekha as 180-deg rotated text)
        unrotated_crops = [crop.copy() for crop in img_crop_list]

        # 4. Run angle classification on default crops (for Latin/Chinese)
        if default_engine.use_angle_cls:
            img_crop_list, _, _ = default_engine.text_cls(img_crop_list)

        # 5. Run baseline English/Latin recognizer
        rec_en_res, _ = default_engine.text_recognizer(img_crop_list)

        # 6. Run Devanagari recognizer on unrotated crops if available
        rec_hi_res = None
        if service._devanagari_engine is not None:
            try:
                rec_hi_res, _ = service._devanagari_engine.recognize_crops(unrotated_crops)
            except Exception as e:
                logger.warning(f"Devanagari recognition failed on crops: {e}")
                rec_hi_res = None

        elapsed_total = round(time.time() - start_time, 4)

        blocks: List[OCRTextBlock] = []
        confidences: List[float] = []
        text_lines: List[str] = []

        num_crops = len(dt_boxes)
        for i in range(num_crops):
            box = dt_boxes[i]
            t_en, s_en = (
                rec_en_res[i] if rec_en_res and i < len(rec_en_res) else ("", 0.0)
            )
            t_hi, s_hi = (
                rec_hi_res[i] if rec_hi_res and i < len(rec_hi_res) else (None, None)
            )

            # Choose winning recognition result
            chosen = cls._select_best_recognition(
                t_en, s_en, t_hi, s_hi, min_confidence=0.5
            )
            if chosen is None:
                continue

            chosen_text, chosen_conf, detected_script, script_conf = chosen
            conf_float = round(float(chosen_conf), 4)
            confidences.append(conf_float)
            text_lines.append(chosen_text)

            # 4-point polygon
            polygon = [[float(p[0]), float(p[1])] for p in box]

            # 2D rectangular bounding box [x_min, y_min, x_max, y_max]
            x_coords = [p[0] for p in box]
            y_coords = [p[1] for p in box]
            box_2d = [
                int(min(x_coords)),
                int(min(y_coords)),
                int(max(x_coords)),
                int(max(y_coords)),
            ]

            blocks.append(
                OCRTextBlock(
                    text=chosen_text,
                    confidence=conf_float,
                    polygon=polygon,
                    box_2d=box_2d,
                    detected_script=detected_script,
                    script_confidence=script_conf,
                )
            )

        avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        full_text = "\n".join(text_lines)

        return OCRResult(
            full_text=full_text,
            blocks=blocks,
            block_count=len(blocks),
            average_confidence=avg_conf,
            execution_time_seconds=elapsed_total,
        )
