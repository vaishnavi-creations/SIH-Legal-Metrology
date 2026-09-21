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
        Normalizes fullwidth East Asian punctuation produced by OCR engines
        and non-breaking spaces into standard ASCII characters.
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
            '\u00a0': ' ',  # non-breaking space
            '\u200b': '',   # zero-width space
        }
        for src, dst in charmap.items():
            text = text.replace(src, dst)
        return text

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

        # Check for Common/Generic Name line
        gen_match = re.search(r'(?:Common|Generic)\s*(?:Name)?\s*[:.-]?\s*(.+)', full_text, re.IGNORECASE)
        if gen_match:
            generic_name = gen_match.group(1).strip()

        # The first prominent non-header line is often the product/brand name
        for line in lines:
            if not re.search(r'(?:MRP|Net\s*Q|Pkg|Mfg|Consumer|Best\s*Before|Batch|Country)', line, re.IGNORECASE):
                if len(line) > 3 and not product_name:
                    product_name = line
                    break

        if not product_name and lines:
            product_name = lines[0]

        # 2. Maximum Retail Price (MRP)
        mrp_data = MRPDetails()
        mrp_regex = re.search(
            r'(?:Maximum\s*Retail\s*Price|Retail\s*Price|M\.R\.P\.?|MRP)'
            r'(?:[\s:.-]|incl\.?\s*of\s*all\s*taxes)*'
            r'(?:Rs\.?|INR|₹)?'
            r'[\s:.-]*'
            r'([0-9]+(?:\.[0-9]{1,2})?)',
            full_text,
            re.IGNORECASE
        )
        if mrp_regex:
            try:
                mrp_data.value = float(mrp_regex.group(1))
            except ValueError:
                pass

        # Check if taxes are included
        if re.search(r'(?:incl|inclusive)\.?\s*(?:of)?\s*all\s*taxes', full_text, re.IGNORECASE):
            mrp_data.includes_taxes = True
        elif re.search(r'plus\s*taxes|taxes\s*extra', full_text, re.IGNORECASE):
            mrp_data.includes_taxes = False

        # Grab raw MRP line/snippet
        for i, line in enumerate(lines):
            if re.search(r'\b(?:MRP|M\.R\.P|Retail\s*Price)\b', line, re.IGNORECASE):
                snippet = line
                # If isolated header like 'MRP', join next line for price/tax context
                if len(line.split()) <= 2 and i + 1 < len(lines):
                    snippet = f"{line} {lines[i+1]}"
                mrp_data.raw_text = snippet
                break

        # Unit Sale Price
        usp_data = None
        usp_match = re.search(
            r'(?:Unit\s*Sale\s*Price|USP)'
            r'[\s:.-]*'
            r'(?:Rs\.?|INR|₹|天)?'
            r'[\s:.-]*'
            r'([0-9]+(?:\.[0-9]+)?)'
            r'\s*(?:\/|\s*per\s*)'
            r'\s*([0-9]*\s*[a-zA-Z]+)',
            full_text,
            re.IGNORECASE
        )
        if usp_match:
            try:
                usp_val = float(usp_match.group(1))
                usp_u = usp_match.group(2).strip()
                usp_raw = usp_match.group(0).strip()
                usp_data = UnitSalePriceDetails(
                    raw_text=usp_raw,
                    value=usp_val,
                    unit=usp_u,
                    currency="INR"
                )
                mrp_data.unit_sale_price = f"Rs. {usp_val} / {usp_u}"
            except (ValueError, IndexError):
                pass

        # 3. Net Quantity
        net_qty = NetQuantityDetails()
        net_match = re.search(
            r'(?:Net\s*(?:Quantity|Qty|Weight|Wt\.?)|Net)\s*[:.-]?\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)\b',
            full_text,
            re.IGNORECASE
        )
        if net_match:
            try:
                net_qty.value = float(net_match.group(1))
                net_qty.unit = net_match.group(2).strip().lower()
            except ValueError:
                pass

        # Check piece count
        piece_match = re.search(r'([0-9]+)\s*(?:pcs|pieces|units|tablets|cookies|capsules|N)\b', full_text, re.IGNORECASE)
        if piece_match:
            try:
                net_qty.piece_count = int(piece_match.group(1))
            except ValueError:
                pass

        for line in lines:
            if re.search(r'Net\s*(?:Quantity|Qty|Weight|Wt)', line, re.IGNORECASE):
                net_qty.raw_text = line
                break

        # 4. Dates (Mfg, Packaging, Best Before, Expiry)
        dates_data = DateDetails()
        mfg_match = re.search(
            r'(?:Mfg|Manufacture|Manufactured|Pkd|Packed|Packing)\s*(?:Date|Dt\.?|Month)?\s*[:.-]?\s*([0-9]{1,2}[/-][0-9]{2,4}|[A-Za-z]{3,9}\s*[0-9]{2,4})',
            full_text,
            re.IGNORECASE
        )
        if mfg_match:
            dates_data.manufacturing_date = mfg_match.group(1).strip()

        best_before_match = re.search(
            r'(?:Best\s*Before|Use\s*By)\s*[:.-]?\s*(.+?)(?=\n|$|\.)',
            full_text,
            re.IGNORECASE
        )
        if best_before_match:
            dates_data.best_before = best_before_match.group(0).strip()

        for line in lines:
            if re.search(r'Mfg|Manufacture|Best\s*Before|Expiry|Exp\.?\s*Date|Pkd', line, re.IGNORECASE):
                dates_data.raw_text = line
                break

        # 5. Manufacturer / Packer Details
        mfg_entity = ManufacturerDetails()
        pincode_match = re.search(r'\b([1-9][0-9]{5})\b', full_text)
        if pincode_match:
            mfg_entity.pincode = pincode_match.group(1)

        # Look for manufacturer declaration line (supports inline and next-line company names)
        for i, line in enumerate(lines):
            mfg_kw = re.search(
                r'^(?:Manufactured\s*(?:&|and)?\s*Packed\s*by|Manufacturer\s*(?:&|and)?\s*Packer|Manufacturer|Manufactured\s*by|Packed\s*by|Marketed\s*by|Mfd\s*by|Mfg\s*by|Pkd\s*by|Packer|Producer)\s*[:.-]?\s*(.*)$',
                line,
                re.IGNORECASE
            )
            if mfg_kw:
                inline_name = mfg_kw.group(1).strip()
                if inline_name and len(inline_name) > 2:
                    mfg_entity.name = inline_name
                elif i + 1 < len(lines):
                    next_l = lines[i + 1].strip()
                    if not re.search(r'^(?:Plot|Flat|Factory|Address|Consumer|Net|MRP|Pkg|Mfg\s*Date|Country)', next_l, re.IGNORECASE):
                        mfg_entity.name = next_l
                mfg_entity.raw_text = line if not mfg_entity.name or mfg_entity.name in line else f"{line} {lines[i+1]}"
                break

        addr_match = re.search(
            r'(?:Factory\s*Address|Regd\s*Office|Address|Mfg\s*at)\s*[:.-]?\s*(.+)',
            full_text,
            re.IGNORECASE
        )
        if addr_match:
            mfg_entity.address = addr_match.group(1).strip()
        elif mfg_entity.pincode:
            # Look for line containing the pincode as address
            for line in lines:
                if mfg_entity.pincode in line and not re.search(r'Consumer|Email|Phone|MRP', line, re.IGNORECASE):
                    mfg_entity.address = line
                    break

        if not mfg_entity.raw_text:
            for line in lines:
                if re.search(r'Manufactured|Manufacturer|Packed\s*by|Marketed\s*by|Mfd\s*by|Mfg\s*by', line, re.IGNORECASE):
                    mfg_entity.raw_text = line
                    break

        # 6. Consumer Care Details
        care_data = ConsumerCareDetails()
        # Accommodate OCR artifacts like "care @nutricrunch.com"
        email_match = re.search(r'([a-zA-Z0-9_.+-]+)\s*@\s*([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', full_text)
        if email_match:
            care_data.email = f"{email_match.group(1)}@{email_match.group(2)}".strip()

        phone_match = re.search(
            r'(?:Toll\s*Free|Tel|Phone|Contact|Help\s*Line|Call)?\s*[:.-]?\s*(1800[-\s]?[0-9]{3}[-\s]?[0-9]{3,4}|[0-9]{3,5}[-\s]?[0-9]{6,8}|\+91[-\s]?[0-9]{10})',
            full_text,
            re.IGNORECASE
        )
        if phone_match:
            care_data.phone = phone_match.group(1).strip()

        for line in lines:
            if re.search(r'Consumer\s*Care|Customer\s*Care|Grievance|Toll\s*Free', line, re.IGNORECASE):
                care_data.raw_text = line
                break

        # 7. Country of Origin
        country = None
        country_match = re.search(
            r'(?:Country\s*of\s*Origin|Made\s*in)\s*[:.-]?\s*([A-Za-z\s]+?)(?=\n|$|\.)',
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
