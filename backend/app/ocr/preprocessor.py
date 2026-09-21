import os
import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Any, List

class ImagePreprocessor:
    """
    Handles image validation, decoding, resizing, and contrast enhancement
    to prepare packaged commodity photos for optimal OCR and text extraction.
    """

    MAX_DIMENSION = 2000
    MIN_DIMENSION = 600

    @classmethod
    def decode_image_bytes(cls, image_bytes: bytes) -> np.ndarray:
        """
        Decodes raw byte stream into an OpenCV BGR numpy array.
        Raises ValueError if bytes do not represent a valid image.
        """
        if not image_bytes:
            raise ValueError("Uploaded file is empty.")

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("OpenCV failed to decode image. File may be corrupted or in an unsupported format.")

        return img

    @classmethod
    def resize_for_ocr(cls, img: np.ndarray) -> Tuple[np.ndarray, List[str]]:
        """
        Resizes the image proportionally if it exceeds MAX_DIMENSION or is smaller than MIN_DIMENSION.
        """
        h, w = img.shape[:2]
        steps = []
        max_dim = max(h, w)

        if max_dim > cls.MAX_DIMENSION:
            scale = cls.MAX_DIMENSION / float(max_dim)
            new_w = int(w * scale)
            new_h = int(h * scale)
            # cv2.INTER_AREA is ideal for downsampling without aliasing
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            steps.append(f"Downscaled from {w}x{h} to {new_w}x{new_h} for memory and OCR efficiency")
        elif max_dim < cls.MIN_DIMENSION:
            scale = cls.MIN_DIMENSION / float(max_dim)
            new_w = int(w * scale)
            new_h = int(h * scale)
            # cv2.INTER_CUBIC is ideal for upscaling small text
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            steps.append(f"Upscaled from {w}x{h} to {new_w}x{new_h} to improve readability of small fonts")

        return img, steps

    @classmethod
    def enhance_contrast(cls, img: np.ndarray) -> Tuple[np.ndarray, List[str]]:
        """
        Enhances image contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
        in the LAB color space. This balances shadows, reflections, and glare on package plastic/cartons.
        """
        steps = []
        # Convert BGR to LAB color space
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Apply CLAHE to L (Luminance) channel
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        cl = clahe.apply(l)

        # Merge channels back and convert to BGR
        enhanced_lab = cv2.merge((cl, a, b))
        enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
        steps.append("Applied CLAHE (Contrast Limited Adaptive Histogram Equalization) to balance lighting/reflections")

        return enhanced_bgr, steps

    @classmethod
    def process_and_save(
        cls,
        image_bytes: bytes,
        file_id: str,
        original_filename: str,
        upload_base_dir: Path
    ) -> Dict[str, Any]:
        """
        Complete pipeline:
        1. Decode
        2. Validate dimensions
        3. Save original image
        4. Resize & enhance
        5. Save processed image
        6. Return complete metadata
        """
        # Step 1: Decode
        img = cls.decode_image_bytes(image_bytes)
        orig_h, orig_w, orig_c = img.shape

        # Ensure directory structure exists
        orig_dir = upload_base_dir / "original"
        proc_dir = upload_base_dir / "processed"
        orig_dir.mkdir(parents=True, exist_ok=True)
        proc_dir.mkdir(parents=True, exist_ok=True)

        # Step 2: Save original file
        clean_name = Path(original_filename).name.replace(" ", "_")
        orig_saved_name = f"{file_id}_{clean_name}"
        orig_path = orig_dir / orig_saved_name
        with open(orig_path, "wb") as f:
            f.write(image_bytes)

        # Step 3: Resize for OCR
        resized_img, resize_steps = cls.resize_for_ocr(img)

        # Step 4: Enhance contrast
        enhanced_img, enhance_steps = cls.enhance_contrast(resized_img)
        all_steps = resize_steps + enhance_steps

        # Step 5: Save processed image (PNG lossless)
        proc_saved_name = f"{file_id}_preprocessed.png"
        proc_path = proc_dir / proc_saved_name
        cv2.imwrite(str(proc_path), enhanced_img)

        proc_h, proc_w = enhanced_img.shape[:2]

        return {
            "original_dimensions": {
                "width": orig_w,
                "height": orig_h,
                "channels": orig_c
            },
            "processed_image": {
                "file_name": proc_saved_name,
                "relative_path": f"processed/{proc_saved_name}",
                "dimensions": {
                    "width": proc_w,
                    "height": proc_h,
                    "channels": enhanced_img.shape[2] if len(enhanced_img.shape) > 2 else 1
                },
                "preprocessing_steps_applied": all_steps
            },
            "original_saved_path": str(orig_path),
            "processed_saved_path": str(proc_path)
        }
