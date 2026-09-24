import re
import json
import logging
import httpx
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.schemas.product import (
    StructuredProductData,
    MRPDetails,
    NetQuantityDetails,
    DateDetails,
    ManufacturerDetails,
    ConsumerCareDetails,
    UnitSalePriceDetails
)

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

DEV_DIGITS_TABLE = str.maketrans("०१२३४५६७८९", "0123456789")

DEV_UNIT_MAP = {
    "ग्राम": "g",
    "ग्रा": "g",
    "किग्रा": "kg",
    "किलोग्राम": "kg",
    "मिलीलीटर": "ml",
    "मिली": "ml",
    "लीटर": "l",
    "ली": "l",
    "मिलीग्राम": "mg",
    "मिग्रा": "mg",
}

def _devanagari_to_ascii_digits(text: str) -> str:
    """Converts Devanagari numerals (०-९) to ASCII digits (0-9)."""
    return text.translate(DEV_DIGITS_TABLE)

class StructuredDataExtractor:
    """
    Parses unstructured OCR text into typed, structured packaged commodity declarations.
    Uses Google Gemini Flash API when GEMINI_API_KEY is configured,
    and seamlessly falls back to a deterministic regex/heuristic parser when offline or without an API key.
    """

    @classmethod
    async def extract(cls, ocr_text: str) -> StructuredProductData:
        """
        Main extraction entry point. Attempts Gemini AI extraction first if key is present,
        falling back to local heuristic extraction if needed.
        """
        if not ocr_text or not ocr_text.strip():
            return StructuredProductData(
                extraction_method="empty_input",
                extraction_confidence=0.0
            )

        api_key = settings.GEMINI_API_KEY.strip() if settings.GEMINI_API_KEY else ""

        if api_key:
            try:
                ai_result = await cls._extract_with_gemini(ocr_text, api_key)
                if ai_result:
                    return ai_result
            except Exception as e:
                logger.warning(f"Gemini AI extraction failed ({e}). Falling back to local heuristic parser.")

        # Fallback to local heuristic extractor
        return cls._extract_with_heuristics(ocr_text)

    @classmethod
    async def _extract_with_gemini(cls, ocr_text: str, api_key: str) -> Optional[StructuredProductData]:
        """
        Calls Gemini 1.5 Flash via REST API requesting structured JSON output.
        """
        prompt = f"""You are a Legal Metrology packaging compliance assistant in India.
Analyze the following OCR text extracted from a packaged commodity product label.
Extract the relevant packaged-commodity declarations into a clean JSON object.

Do not invent or assume data that is not in the text. If a field is missing, set it to null.

OCR TEXT:
\"\"\"
{ocr_text}
\"\"\"

Return ONLY a valid JSON object matching this exact structure:
{{
  "product_name": "Full trade or brand name",
  "common_or_generic_name": "Generic or common name (e.g. Baked Oat Cookies, Shampoo)",
  "brand": "Brand name if identifiable",
  "mrp": {{
    "raw_text": "Exact text snippet showing price",
    "value": 55.0,
    "currency": "INR",
    "includes_taxes": true,
    "unit_sale_price": "Rs. 0.275/g"
  }},
  "net_quantity": {{
    "raw_text": "Exact text snippet showing weight/volume",
    "value": 200.0,
    "unit": "g",
    "piece_count": null
  }},
  "dates": {{
    "raw_text": "Exact text snippet showing dates",
    "manufacturing_date": "MM/YYYY or DD/MM/YYYY",
    "packaging_date": null,
    "expiry_date": null,
    "best_before": "e.g. 6 Months from packaging"
  }},
  "manufacturer": {{
    "raw_text": "Exact text snippet for manufacturer/packer",
    "name": "Company name",
    "address": "Postal address",
    "pincode": "6-digit PIN code",
    "entity_type": "manufacturer or packer or importer"
  }},
  "consumer_care": {{
    "raw_text": "Exact text snippet for consumer care",
    "phone": "Toll-free or phone number",
    "email": "Email address",
    "address": null
  }},
  "country_of_origin": "India or other country",
  "batch_number": "Batch or lot code",
  "other_declarations": []
}}
"""
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1
            }
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(f"{GEMINI_API_URL}?key={api_key}", json=payload, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text}")
                return None

            resp_data = resp.json()
            candidates = resp_data.get("candidates", [])
            if not candidates:
                return None

            content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            parsed_json = json.loads(content_text)

            # Construct StructuredProductData from Gemini JSON
            parsed_json["extraction_method"] = "gemini_ai"
            parsed_json["extraction_confidence"] = 0.95
            return StructuredProductData(**parsed_json)

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalizes fullwidth East Asian punctuation produced by OCR engines,
        Devanagari danda separators, and non-breaking spaces into standard ASCII characters.
        """
        charmap = {
            '：': ':',
            '，': ',',
            '．': '.',
            '－': '-',
            '（': '(',
            '）': ')',
            '【': '[',
            '】': ']',
            '／': '/',
            '।': '|',      # Devanagari danda
            '\u00a0': ' ',  # non-breaking space
            '\u2000': ' ',
            '\u2001': ' ',
            '\u2002': ' ',
            '\u2003': ' ',
            '\u200b': '',   # zero-width space
            '\u200e': '',   # LTR mark
            '\u200f': '',   # RTL mark
            '\ufeff': '',   # BOM
        }
        for src, dst in charmap.items():
            text = text.replace(src, dst)
        return text

    @staticmethod
    def _is_section_marker(line: str) -> bool:
        """
        Detects provenance / multi-image section markers such as '--- FRONT ---' or 'FRONT'.
        Prevents these markers from being incorrectly treated as product or brand names.
        """
        clean = line.strip()
        return bool(
            re.match(r'^-+\s*[A-Za-z\s]+\s*-+$', clean)
            or clean.upper() in {'FRONT', 'BACK', 'SIDE', 'TOP', 'BOTTOM', 'LEFT', 'RIGHT', 'LABEL', 'OTHER'}
        )

    @staticmethod
    def _is_declaration_header(line: str) -> bool:
        """
        Detects whether a line begins with known statutory packaging declaration keywords.
        Used to prevent declaration headers from becoming product names or being absorbed into addresses.
        Supports English and Devanagari (Hindi/Marathi).
        """
        return bool(re.search(
            r'^(?:MRP|M\.R\.P|Maximum\s*Retail|Retail\s*Price|'
            r'Net\s*(?:Quantity|Qty|Weight|Wt|Q)|'
            r'Pkg|Mfg|Manufactur|Packed|Packer|Producer|Importer|Imported|Import|'
            r'Factory\s*Address|Regd\s*Office|Address|Mfg\s*at|'
            r'Consumer|Customer|Grievance|Help\s*Line|Toll\s*Free|'
            r'Best\s*Before|Use\s*By|Expiry|Exp\.?\s*Date|'
            r'Batch|Lot|'
            r'Country|Made\s*in|'
            r'Commodity|Generic|Common|'
            r'Unit\s*Sale\s*Price|USP|Phone|Tel|Email|Contact|Call|'
            r'अधिकतम\s*(?:खुदरा\s*)?मूल्य|अधिकतमखुदरामूल्य|खुदरा\s*मूल्य|मूल्य|'
            r'शुद्ध\s*मात्रा|शुद्धमात्रा|मात्रा|कुल\s*मात्रा|'
            r'निर्माता|उत्पादक|पैककर्ता|पैकर|आयातकर्ता|आयातक|'
            r'कारखाना\s*(?:का\s*)?पता|पंजीकृत\s*कार्यालय|पता|'
            r'उपभोक्ता\s*देखभाल|उपभोक्तादेखभाल|उपभोक्ता\s*सेवा|ग्राहक\s*सेवा|ग्राहकसेवा|हेल्पलाइन|'
            r'निर्माण\s*(?:की\s*)?(?:तिथि|तारीख|माह)?|निर्माणतिथि|पैकिंग\s*(?:की\s*)?(?:तिथि|तारीख)?|पैकिंगतिथि|'
            r'उपयोग\s*की\s*अवधि|समाप्ति\s*(?:की\s*)?(?:तिथि|तारीख)?|समाप्तितिथि|अवसान\s*तिथि|'
            r'इकाई\s*(?:बिक्री\s*)?मूल्य|प्रति\s*इकाई|मूल\s*देश|उत्पत्ति\s*का\s*देश)',
            line.strip(),
            re.IGNORECASE
        ))

    @classmethod
    def _extract_with_heuristics(cls, ocr_text: str) -> StructuredProductData:
        """
        Deterministic regex and pattern matching extractor for packaged commodity declarations.
        Extracts MRP, Net Quantity, Dates, Manufacturer, Consumer Care, Origin, and Generic Name.
        """
        normalized_text = cls._normalize_text(ocr_text)
        lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
        full_text = "\n".join(lines)

        # 1. Product Name & Generic Name
        product_name = None
        generic_name = None
        brand = None

        # Check for Common/Generic Name line (supports Commodity, Common Name, Generic Name both inline and next-line, English and Devanagari)
        for i, line in enumerate(lines):
            gen_kw = re.search(
                r'^(?:Common\s*(?:or|/)?\s*Generic\s*Name|Common\s*Name|Generic\s*Name|Commodity|Generic|Common|'
                r'सामान्य\s*(?:या\s*)?जेनेरिक\s*नाम|सामान्य\s*नाम|वस्तु)\s*[:.-]?\s*(.*)$',
                line,
                re.IGNORECASE
            )
            if gen_kw:
                inline_val = gen_kw.group(1).strip()
                inline_val = re.sub(r'^[:.-]+\s*', '', inline_val).strip()
                if inline_val and len(inline_val) > 1:
                    generic_name = inline_val
                    break
                elif i + 1 < len(lines):
                    next_l = lines[i + 1].strip()
                    clean_next = re.sub(r'^[:.-]+\s*', '', next_l).strip()
                    if clean_next and not cls._is_declaration_header(clean_next):
                        generic_name = clean_next
                        break

        # Fallback regex search on full text if not found via line iteration
        if not generic_name:
            gen_match = re.search(
                r'(?:Common|Generic|Commodity|सामान्य\s*नाम|वस्तु)\s*(?:Name)?\s*[:.-]?\s*([A-Za-z0-9\u0900-\u097F\s]+?)(?=\n|$)',
                full_text,
                re.IGNORECASE
            )
            if gen_match:
                candidate_gen = re.sub(r'^[:.-]+\s*', '', gen_match.group(1)).strip()
                if candidate_gen and not cls._is_declaration_header(candidate_gen):
                    generic_name = candidate_gen

        # Scan for candidate product name (ignoring section markers, declaration headers, and noise)
        for line in lines:
            if not cls._is_section_marker(line) and not cls._is_declaration_header(line):
                clean_l = re.sub(r'^[/\\Vv\W_]+', '', line).strip()
                if len(clean_l) > 3 and not product_name:
                    product_name = clean_l
                    break

        # If still not found, fallback to first non-marker and non-header line
        if not product_name and lines:
            for line in lines:
                if not cls._is_section_marker(line) and not cls._is_declaration_header(line):
                    clean_l = re.sub(r'^[/\\Vv\W_]+', '', line).strip()
                    if len(clean_l) > 1:
                        product_name = clean_l
                        break

        # 2. Maximum Retail Price (MRP)
        mrp_data = MRPDetails()
        mrp_regex = re.search(
            r'(?:Maximum\s*Retail\s*Price|Retail\s*Price|M\.R\.P\.?|MRP|'
            r'अधिकतम\s*(?:खुदरा\s*)?मूल्य|अधिकतमखुदरामूल्य|खुदरा\s*मूल्य|मूल्य)'
            r'(?:[\s:.-]|incl\.?\s*of\s*all\s*taxes|सभी\s*करों\s*सहित)*'
            r'(?:Rs\.?|INR|₹)?'
            r'[\s:.-]*'
            r'([0-9]+(?:\.[0-9]{1,2})?|[०-९]+(?:\.[०-९]{1,2})?)'
            r'(?=\s*(?:/|[\s,.\b]|$))',
            full_text,
            re.IGNORECASE
        )
        if not mrp_regex:
            # Reverse pattern: e.g. "₹ 120 / अधिकतम खुदरा मूल्य" or "120 / MRP"
            mrp_regex = re.search(
                r'(?:(?:Rs\.?|INR|₹)\s*)?([0-9]+(?:\.[0-9]{1,2})?|[०-९]+(?:\.[०-९]{1,2})?)\s*(?:[\s:./\-])+\s*'
                r'(?:Maximum\s*Retail\s*Price|Retail\s*Price|M\.R\.P\.?|MRP|'
                r'अधिकतम\s*(?:खुदरा\s*)?मूल्य|अधिकतमखुदरामूल्य|खुदरा\s*मूल्य|मूल्य)',
                full_text,
                re.IGNORECASE
            )

        if mrp_regex:
            try:
                mrp_val_str = _devanagari_to_ascii_digits(mrp_regex.group(1))
                mrp_data.value = float(mrp_val_str)
            except (ValueError, TypeError):
                pass

        # Check if taxes are included (tolerant of OCR artifacts like 'lnclusiveofalltaxes' and Hindi 'सभी करों सहित')
        if re.search(r'plus\s*taxes|taxes\s*extra|excl(?:usive)?\.?\s*(?:of)?\s*taxes|कर\s*अतिरिक्त', full_text, re.IGNORECASE):
            mrp_data.includes_taxes = False
        elif re.search(r'[iIl1|]ncl(?:usive)?\.?\s*(?:of)?\s*(?:all)?\s*taxes|सभी\s*करों\s*सहित|कर\s*सहित', full_text, re.IGNORECASE):
            mrp_data.includes_taxes = True

        # Grab raw MRP line/snippet
        for i, line in enumerate(lines):
            if re.search(r'\b(?:MRP|M\.R\.P|Retail\s*Price)\b|अधिकतम\s*(?:खुदरा\s*)?मूल्य|अधिकतमखुदरामूल्य|खुदरा\s*मूल्य|मूल्य', line, re.IGNORECASE):
                snippet = line
                # If isolated header like 'MRP', join next line for price/tax context
                if len(line.split()) <= 2 and i + 1 < len(lines):
                    next_l = lines[i + 1].strip()
                    if not cls._is_declaration_header(next_l) and not cls._is_section_marker(next_l):
                        snippet = f"{line} {next_l}"
                mrp_data.raw_text = snippet
                break

        # Unit Sale Price
        usp_data = None
        usp_match = re.search(
            r'(?:Unit\s*Sale\s*Price|USP|इकाई\s*(?:बिक्री\s*)?मूल्य|इकाई\s*मूल्य|प्रति\s*इकाई\s*मूल्य)'
            r'[\s:.-]*'
            r'(?:Rs\.?|INR|₹|天)?'
            r'[\s:.-]*'
            r'([0-9]+(?:\.[0-9]+)?|[०-९]+(?:\.[०-९]+)?)'
            r'\s*(?:\/|\s*per\s*|\s*प्रति\s*)'
            r'\s*([0-9]*\s*[a-zA-Z]+|[0-9]*\s*(?:ग्राम|किग्रा|किलोग्राम|मिलीलीटर|मिली|लीटर|ली|मिग्रा|मिलीग्राम|ग्रा))',
            full_text,
            re.IGNORECASE
        )
        if usp_match:
            try:
                usp_val_str = _devanagari_to_ascii_digits(usp_match.group(1))
                usp_val = float(usp_val_str)
                usp_u_raw = usp_match.group(2).strip()
                # Map Devanagari unit if present
                for dev_u, eng_u in DEV_UNIT_MAP.items():
                    if dev_u in usp_u_raw:
                        usp_u_raw = usp_u_raw.replace(dev_u, eng_u)
                        break
                usp_raw = usp_match.group(0).strip()
                usp_data = UnitSalePriceDetails(
                    raw_text=usp_raw,
                    value=usp_val,
                    unit=usp_u_raw,
                    currency="INR"
                )
                mrp_data.unit_sale_price = f"Rs. {usp_val} / {usp_u_raw}"
            except (ValueError, IndexError):
                pass

        # 3. Net Quantity
        net_qty = NetQuantityDetails()
        net_match = re.search(
            r'(?:Net\s*(?:Quantity|Qty|Weight|Wt\.?)|Net|शुद्ध\s*मात्रा|शुद्धमात्रा|मात्रा|कुल\s*मात्रा)'
            r'\s*[:.-]?\s*'
            r'([0-9]+(?:\.[0-9]+)?|[०-९]+(?:\.[०-९]+)?)'
            r'\s*'
            r'([a-zA-Z]+|ग्राम|किग्रा|किलोग्राम|मिलीलीटर|मिली|लीटर|ली|मिग्रा|मिलीग्राम|ग्रा)'
            r'(?:\s*[\b\s/)]|$)',
            full_text,
            re.IGNORECASE
        )
        if not net_match:
            # Reverse search: e.g. "150 g / शुद्ध मात्रा"
            net_match = re.search(
                r'([0-9]+(?:\.[0-9]+)?|[०-९]+(?:\.[०-९]+)?)\s*'
                r'([a-zA-Z]+|ग्राम|किग्रा|किलोग्राम|मिलीलीटर|मिली|लीटर|ली|मिग्रा|मिलीग्राम|ग्रा)'
                r'\s*(?:/|\s*-\s*|\s+)\s*'
                r'(?:Net\s*(?:Quantity|Qty|Weight|Wt\.?)|Net|शुद्ध\s*मात्रा|शुद्धमात्रा|मात्रा|कुल\s*मात्रा)',
                full_text,
                re.IGNORECASE
            )

        if net_match:
            try:
                val_str = _devanagari_to_ascii_digits(net_match.group(1))
                net_qty.value = float(val_str)
                unit_raw = net_match.group(2).strip()
                net_qty.unit = DEV_UNIT_MAP.get(unit_raw, unit_raw.lower())
            except ValueError:
                pass

        # Check piece count
        piece_match = re.search(
            r'([0-9]+|[०-९]+)\s*(?:pcs|pieces|units|tablets|cookies|capsules|N|नग|पीस|गोलियां|इकाइयां)\b',
            full_text,
            re.IGNORECASE
        )
        if piece_match:
            try:
                pc_str = _devanagari_to_ascii_digits(piece_match.group(1))
                net_qty.piece_count = int(pc_str)
            except ValueError:
                pass

        for line in lines:
            if re.search(r'Net\s*(?:Quantity|Qty|Weight|Wt)|शुद्ध\s*मात्रा|शुद्धमात्रा|मात्रा|कुल\s*मात्रा', line, re.IGNORECASE):
                net_qty.raw_text = line
                break

        # 4. Dates (Mfg, Packaging, Best Before, Expiry, Imported)
        dates_data = DateDetails()
        mfg_match = re.search(
            r'(?:Mfg|Manufacture|Manufactured|Pkd|Packed|Packing|Imported|Import|'
            r'निर्माण\s*(?:तिथि|तारीख|माह)?|निर्माणतिथि|पैकिंग\s*(?:तिथि|तारीख)?|पैकिंगतिथि)'
            r'\s*(?:Date|Dt\.?|Month|Year|की\s*तारीख)?\s*[:.-]*\s*'
            r'([0-9]{1,2}[/-][0-9]{2,4}|[A-Za-z]{3,9}\s*[0-9]{2,4}|[०-९]{1,2}[/-][०-९]{2,4})',
            full_text,
            re.IGNORECASE
        )
        if mfg_match:
            raw_date = mfg_match.group(1).strip()
            dates_data.manufacturing_date = _devanagari_to_ascii_digits(raw_date)

        best_before_match = re.search(
            r'(?:Best\s*Before|Use\s*By|उपयोग\s*की\s*अवधि|समाप्ति\s*(?:तिथि|तारीख)?|समाप्तितिथि|अवसान\s*तिथि)\s*[:.-]?\s*(.+?)(?=\n|$|\.)',
            full_text,
            re.IGNORECASE
        )
        if best_before_match:
            dates_data.best_before = best_before_match.group(0).strip()

        for i, line in enumerate(lines):
            if re.search(r'\b(?:Mfg|Manufacture|Best\s*Before|Expiry|Exp\.?\s*Date|Pkd|Imported|Import)\b|'
                         r'निर्माण\s*(?:तिथि|तारीख)?|निर्माणतिथि|पैकिंग\s*(?:तिथि|तारीख)?|पैकिंगतिथि|'
                         r'उपयोग\s*की\s*अवधि|समाप्ति|अवसान', line, re.IGNORECASE):
                snippet = line
                if i + 1 < len(lines) and re.match(r'^[:.-]*\s*[0-9०-९]', lines[i + 1].strip()):
                    snippet = f"{line} {lines[i + 1].strip()}"
                dates_data.raw_text = snippet
                break

        # 5. Manufacturer / Packer / Importer Details
        mfg_entity = ManufacturerDetails()
        pincode_match = re.search(r'\b([1-9][0-9]{5}|[१-९][०-९]{5})\b', full_text)
        if pincode_match:
            mfg_entity.pincode = _devanagari_to_ascii_digits(pincode_match.group(1))

        # Look for manufacturer/importer declaration line (supports inline and next-line company names)
        name_line_idx = None
        for i, line in enumerate(lines):
            mfg_kw = re.search(
                r'^(?:Manufactured\s*(?:&|and)?\s*Packed\s*by|Manufacturer\s*(?:&|and)?\s*Packer|'
                r'Manufacturer|Manufactured\s*by|Packed\s*by|Marketed\s*by|Mfd\s*by|Mfg\s*by|Pkd\s*by|'
                r'Packer|Producer|Importer|Imported\s*by|'
                r'निर्माता\s*(?:एवं|और)?\s*पैककर्ता|निर्माता\s*(?:द्वारा)?|उत्पादक|पैककर्ता|पैकर|'
                r'द्वारा\s*निर्मित|निर्मित|आयातकर्ता|आयातक)\s*[:.-]?\s*(.*)$',
                line,
                re.IGNORECASE
            )
            if mfg_kw:
                if re.search(r'Importer|Imported\s*by|आयातकर्ता|आयातक', line, re.IGNORECASE):
                    mfg_entity.entity_type = "importer"
                elif re.search(r'Packer|Packed\s*by|Pkd\s*by|पैककर्ता|पैकर', line, re.IGNORECASE):
                    mfg_entity.entity_type = "packer"
                else:
                    mfg_entity.entity_type = "manufacturer"

                inline_name = re.sub(r'^[:.-]+\s*', '', mfg_kw.group(1)).strip()
                if inline_name and len(inline_name) > 2:
                    mfg_entity.name = inline_name
                    name_line_idx = i
                elif i + 1 < len(lines):
                    next_l = re.sub(r'^[:.-]+\s*', '', lines[i + 1]).strip()
                    if next_l and not re.search(r'^(?:Plot|Flat|Factory|Address|Consumer|Net|MRP|Pkg|Mfg\s*Date|Country|उपभोक्ता|शुद्ध|मूल्य)', next_l, re.IGNORECASE):
                        mfg_entity.name = next_l
                        name_line_idx = i + 1
                mfg_entity.raw_text = line if not mfg_entity.name or mfg_entity.name in line else f"{line} {lines[i+1]}"
                break

        addr_match = re.search(
            r'(?:Factory\s*Address|Regd\s*Office|Address|Mfg\s*at|कारखाना\s*का\s*पता|पंजीकृत\s*कार्यालय|पता)\s*[:.-]?\s*(.+)',
            full_text,
            re.IGNORECASE
        )
        if addr_match:
            mfg_entity.address = addr_match.group(1).strip()
        elif name_line_idx is not None and name_line_idx + 1 < len(lines):
            # Collect subsequent address lines until the next declaration header or section marker begins
            collected_addr_lines = []
            for j in range(name_line_idx + 1, len(lines)):
                l_cand = lines[j].strip()
                if cls._is_declaration_header(l_cand) or cls._is_section_marker(l_cand):
                    break
                collected_addr_lines.append(l_cand)
            if collected_addr_lines:
                mfg_entity.address = " ".join(collected_addr_lines)
        elif mfg_entity.pincode:
            # Look for line containing the pincode as address
            for line in lines:
                if mfg_entity.pincode in line and not re.search(r'Consumer|Email|Phone|MRP|उपभोक्ता|मूल्य', line, re.IGNORECASE):
                    mfg_entity.address = line
                    break

        if not mfg_entity.raw_text:
            for line in lines:
                if re.search(r'Manufactured|Manufacturer|Packed\s*by|Marketed\s*by|Mfd\s*by|Mfg\s*by|Importer|Imported|'
                             r'निर्माता|उत्पादक|पैककर्ता|पैकर|आयातकर्ता|आयातक', line, re.IGNORECASE):
                    mfg_entity.raw_text = line
                    break

        # 6. Consumer Care Details
        care_data = ConsumerCareDetails()
        # Accommodate OCR artifacts like "care @nutricrunch.com"
        email_match = re.search(r'([a-zA-Z0-9_.+-]+)\s*@\s*([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', full_text)
        if email_match:
            care_data.email = f"{email_match.group(1)}@{email_match.group(2)}".strip()

        phone_match = re.search(
            r'(?:Toll\s*Free|Tel|Phone|Contact|Help\s*Line|Call|हेल्पलाइन|फोन|संपर्क)?\s*[:.-]?\s*'
            r'(1800[-\s]?[0-9]{3}[-\s]?[0-9]{3,4}|[0-9]{3,5}[-\s]?[0-9]{6,8}|\+91[-\s]?[0-9]{10})',
            full_text,
            re.IGNORECASE
        )
        if phone_match:
            care_data.phone = phone_match.group(1).strip()

        for line in lines:
            if re.search(r'Consumer\s*Care|Customer\s*Care|Grievance|Toll\s*Free|'
                         r'उपभोक्ता\s*देखभाल|उपभोक्तादेखभाल|उपभोक्ता\s*सेवा|ग्राहक\s*सेवा|ग्राहकसेवा', line, re.IGNORECASE):
                care_data.raw_text = line
                break

        # 7. Country of Origin
        country = None
        country_match = re.search(
            r'(?:Country\s*(?:of\s*)?Origin|Countryof\s*Origin|Made\s*in|मूल\s*देश|उत्पत्ति\s*का\s*देश)\s*[:.-]?\s*([A-Za-z\u0900-\u097F\s]+?)(?=\n|$|\.)',
            full_text,
            re.IGNORECASE
        )
        if country_match:
            country = country_match.group(1).strip()

        # 8. Batch Number
        batch_no = None
        # Word boundary \b prevents matching "Plot 42" as "Lot 42"
        batch_match = re.search(r'\b(?:Batch|Lot)\s*(?:No\.?|Number)?\s*[:.-]?\s*([A-Za-z0-9-]+)', full_text, re.IGNORECASE)
        if batch_match:
            batch_no = batch_match.group(1).strip()


        return StructuredProductData(
            product_name=product_name,
            common_or_generic_name=generic_name,
            brand=brand,
            mrp=mrp_data,
            net_quantity=net_qty,
            dates=dates_data,
            manufacturer=mfg_entity,
            consumer_care=care_data,
            unit_sale_price=usp_data,
            country_of_origin=country,
            batch_number=batch_no,
            extraction_method="regex_heuristic",
            extraction_confidence=0.88
        )
