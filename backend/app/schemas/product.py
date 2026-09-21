from typing import Optional, List, Union, Any
from pydantic import BaseModel, Field, model_validator

class UnitSalePriceDetails(BaseModel):
    raw_text: Optional[str] = Field(None, description="Original raw text snippet for Unit Sale Price")
    value: Optional[float] = Field(None, description="Numeric unit sale price value")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g. 'g', 'kg', '100 g', '100 ml')")
    currency: str = Field("INR", description="Currency code")

class MRPDetails(BaseModel):
    raw_text: Optional[str] = Field(None, description="Original raw text snippet for MRP")
    value: Optional[float] = Field(None, description="Extracted numerical MRP value in Rupees")
    currency: str = Field("INR", description="Currency symbol/code, default INR")
    includes_taxes: Optional[bool] = Field(None, description="Whether the declaration explicitly includes '(incl. of all taxes)'")
    inclusive_of_taxes: Optional[bool] = Field(None, description="Alias for includes_taxes")
    unit_sale_price: Optional[Union[UnitSalePriceDetails, str]] = Field(None, description="Unit sale price declaration if present (e.g. 'Rs. 0.275/g')")

    @model_validator(mode="before")
    @classmethod
    def sync_tax_flags(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "inclusive_of_taxes" in data and "includes_taxes" not in data:
                data["includes_taxes"] = data["inclusive_of_taxes"]
            elif "includes_taxes" in data and "inclusive_of_taxes" not in data:
                data["inclusive_of_taxes"] = data["includes_taxes"]
        return data

class NetQuantityDetails(BaseModel):
    raw_text: Optional[str] = Field(None, description="Original raw text snippet for net quantity")
    value: Optional[float] = Field(None, description="Extracted numerical quantity")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g. g, kg, ml, l, pcs)")
    piece_count: Optional[int] = Field(None, description="Item/piece count if commodity is sold by number")

class DateDetails(BaseModel):
    raw_text: Optional[str] = Field(None, description="Original raw date declaration text")
    manufacturing_date: Optional[str] = Field(None, description="Month & year or date of manufacture (MM/YYYY or DD/MM/YYYY)")
    packaging_date: Optional[str] = Field(None, description="Month & year or date of packaging if distinct")
    packing_date: Optional[str] = Field(None, description="Alias for packaging_date")
    expiry_date: Optional[str] = Field(None, description="Expiry date if specified")
    best_before: Optional[str] = Field(None, description="Best before declaration (e.g. '6 Months from packaging')")

    @model_validator(mode="before")
    @classmethod
    def sync_packing_dates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "packing_date" in data and "packaging_date" not in data:
                data["packaging_date"] = data["packing_date"]
            elif "packaging_date" in data and "packing_date" not in data:
                data["packing_date"] = data["packaging_date"]
        return data

class ManufacturerDetails(BaseModel):
    raw_text: Optional[str] = Field(None, description="Original raw text snippet for manufacturer")
    name: Optional[str] = Field(None, description="Name of the manufacturing / packing entity")
    address: Optional[str] = Field(None, description="Physical postal address of the manufacturer/packer")
    pincode: Optional[str] = Field(None, description="6-digit postal PIN code if detected")
    entity_type: str = Field("manufacturer_or_packer", description="Type of entity: manufacturer, packer, or importer")

class ConsumerCareDetails(BaseModel):
    raw_text: Optional[str] = Field(None, description="Original raw consumer care snippet")
    phone: Optional[str] = Field(None, description="Toll-free or landline customer support telephone number")
    email: Optional[str] = Field(None, description="Customer grievance email address")
    address: Optional[str] = Field(None, description="Customer care physical address if distinct")

class StructuredProductData(BaseModel):
    product_name: Optional[str] = Field(None, description="Trade name or brand name of the commodity")
    common_or_generic_name: Optional[str] = Field(None, description="Generic or common name of the commodity as required by Rule 6(1)(b)")
    brand: Optional[str] = Field(None, description="Brand name if identifiable")
    mrp: MRPDetails = Field(default_factory=MRPDetails, description="Retail price declarations")
    net_quantity: NetQuantityDetails = Field(default_factory=NetQuantityDetails, description="Net weight, volume, or count")
    dates: DateDetails = Field(default_factory=DateDetails, description="Manufacturing, packing, and best before dates")
    manufacturer: ManufacturerDetails = Field(default_factory=ManufacturerDetails, description="Manufacturer / Packer / Importer details")
    consumer_care: ConsumerCareDetails = Field(default_factory=ConsumerCareDetails, description="Consumer grievance redressal details")
    unit_sale_price: Optional[Union[UnitSalePriceDetails, str]] = Field(None, description="Unit Sale Price declaration if declared at top-level")
    country_of_origin: Optional[str] = Field(None, description="Country of origin / manufacture (e.g. 'India')")
    batch_number: Optional[str] = Field(None, description="Batch, code, or lot identification number")
    other_declarations: List[str] = Field(default_factory=list, description="Other notable statements or declarations found")
    extraction_method: str = Field("heuristic", description="Method used for extraction: 'gemini_ai' or 'regex_heuristic'")
    extraction_confidence: float = Field(0.9, description="Confidence score of the structured field mapping")


class ExtractionRequest(BaseModel):
    text: str = Field(..., description="Raw text or OCR output to extract structured product data from")
    file_id: Optional[str] = Field(None, description="Optional associated file_id from previous upload")

class ExtractionResponse(BaseModel):
    success: bool = Field(True, description="Indicates if structured extraction succeeded")
    message: str = Field(..., description="Human-readable status summary")
    file_id: Optional[str] = Field(None, description="Associated file_id")
    data: StructuredProductData = Field(..., description="Extracted typed product fields")
