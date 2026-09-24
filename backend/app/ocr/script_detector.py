"""
Deterministic Unicode Script Detector for PackSure.

Classifies text into:
- LATIN
- DEVANAGARI
- MIXED
- UNKNOWN

Uses Python standard-library Unicode functionality (unicodedata and character code points).
Zero external dependencies, zero machine learning models, zero external network calls.
"""

import unicodedata
from enum import Enum
from typing import Tuple, NamedTuple


class ScriptType(str, Enum):
    LATIN = "LATIN"
    DEVANAGARI = "DEVANAGARI"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class ScriptDetectionResult(NamedTuple):
    script: str
    confidence: float
    latin_count: int
    devanagari_count: int
    other_count: int


class ScriptDetector:
    """
    Deterministic Unicode script detector based on character-level Unicode code points.

    Excludes whitespace, ASCII/Unicode decimal digits, punctuation, and currency symbols
    so that numbers and symbols (e.g. '120.00', ':-()', '₹') do not falsely trigger Latin classification.
    """

    @staticmethod
    def is_devanagari_char(c: str) -> bool:
        """
        Determines whether a character belongs to the Devanagari script.
        Includes:
        - Devanagari block (U+0900..U+097F)
        - Devanagari Extended block (U+A8E0..U+A8FF)
        Excludes Devanagari digits (U+0966..U+096F) and dandas/punctuation (U+0964, U+0965).
        """
        cp = ord(c)
        if 0x0900 <= cp <= 0x097F or 0xA8E0 <= cp <= 0xA8FF:
            cat = unicodedata.category(c)
            # Letters (Lo), vowel signs / matras (Mc, Mn), signs (Mn, Mc), modifier letters (Lm)
            return cat in {"Lo", "Mc", "Mn", "Lm"}
        return False

    @staticmethod
    def is_latin_char(c: str) -> bool:
        """
        Determines whether a character belongs to the Latin script.
        Includes:
        - Basic Latin letters (A-Z, a-z)
        - Latin-1 Supplement, Latin Extended-A & B, Latin Extended Additional
        Excludes digits (0-9), ASCII punctuation, and math/currency symbols.
        """
        cat = unicodedata.category(c)
        if not cat.startswith("L"):
            return False
        cp = ord(c)
        # Fast path for standard ASCII letters
        if (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A):
            return True
        # Extended Latin ranges
        if (0x00C0 <= cp <= 0x024F) or (0x1E00 <= cp <= 0x1EFF):
            return "LATIN" in unicodedata.name(c, "")
        return False

    @classmethod
    def analyze(cls, text: str) -> ScriptDetectionResult:
        """
        Performs detailed script character counting and classification.
        """
        if not text or not str(text).strip():
            return ScriptDetectionResult(
                script=ScriptType.UNKNOWN.value,
                confidence=0.0,
                latin_count=0,
                devanagari_count=0,
                other_count=0
            )

        latin_count = 0
        devanagari_count = 0
        other_count = 0

        for c in text:
            if cls.is_latin_char(c):
                latin_count += 1
            elif cls.is_devanagari_char(c):
                devanagari_count += 1
            elif unicodedata.category(c).startswith("L"):
                # Alphabetic character belonging to another script (e.g. Cyrillic, Arabic, Han)
                other_count += 1

        total_script = latin_count + devanagari_count + other_count
        if total_script == 0:
            return ScriptDetectionResult(
                script=ScriptType.UNKNOWN.value,
                confidence=0.0,
                latin_count=0,
                devanagari_count=0,
                other_count=0
            )

        if latin_count > 0 and devanagari_count > 0:
            # Deterministic confidence: proportion of recognized script characters
            confidence = round((latin_count + devanagari_count) / total_script, 4)
            return ScriptDetectionResult(
                script=ScriptType.MIXED.value,
                confidence=confidence,
                latin_count=latin_count,
                devanagari_count=devanagari_count,
                other_count=other_count
            )
        elif latin_count > 0:
            confidence = round(latin_count / total_script, 4)
            return ScriptDetectionResult(
                script=ScriptType.LATIN.value,
                confidence=confidence,
                latin_count=latin_count,
                devanagari_count=0,
                other_count=other_count
            )
        elif devanagari_count > 0:
            confidence = round(devanagari_count / total_script, 4)
            return ScriptDetectionResult(
                script=ScriptType.DEVANAGARI.value,
                confidence=confidence,
                latin_count=0,
                devanagari_count=devanagari_count,
                other_count=other_count
            )
        else:
            return ScriptDetectionResult(
                script=ScriptType.UNKNOWN.value,
                confidence=0.0,
                latin_count=0,
                devanagari_count=0,
                other_count=other_count
            )

    @classmethod
    def detect_script(cls, text: str) -> Tuple[str, float]:
        """
        Convenience method returning (detected_script, script_confidence).
        """
        res = cls.analyze(text)
        return res.script, res.confidence
