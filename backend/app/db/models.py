import datetime
import uuid
from typing import Set
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    func
)
from sqlalchemy.orm import relationship, validates
from app.db.session import Base

VALID_IMAGE_ROLES: Set[str] = {
    "front",
    "back",
    "left",
    "right",
    "top",
    "bottom",
    "label",
    "other",
}

class ScanRecord(Base):
    """
    SQLAlchemy model storing inspection scan sessions, image references,
    OCR extractions, structured product declarations, and compliance reports.
    """
    __tablename__ = "scan_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_id = Column(String(64), unique=True, index=True, nullable=False)
    original_filename = Column(String(255), nullable=True)
    image_path = Column(String(500), nullable=True)
    processed_image_path = Column(String(500), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), server_default=func.now())

    # Key product summary fields for quick search & filtering
    product_name = Column(String(255), nullable=True, index=True)
    common_name = Column(String(255), nullable=True)
    brand = Column(String(255), nullable=True)
    mrp = Column(Float, nullable=True)
    net_quantity = Column(String(100), nullable=True)

    # Compliance summary
    compliance_status = Column(String(50), nullable=False, index=True, default="INSUFFICIENT_DATA")
    violations_count = Column(Integer, default=0)
    warnings_count = Column(Integer, default=0)
    summary = Column(Text, nullable=True)

    # Detailed payloads stored as JSON strings
    ocr_text = Column(Text, nullable=True)
    ocr_blocks_json = Column(Text, nullable=True)
    structured_data_json = Column(Text, nullable=True)
    compliance_report_json = Column(Text, nullable=True)


class Inspection(Base):
    """
    Product-level Inspection domain model supporting multi-image sessions,
    commodity metadata, and compliance verification status.
    """
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    inspection_id = Column(String(64), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    product_name = Column(String(255), nullable=True, index=True)
    country_of_manufacture = Column(String(100), nullable=True)
    country_of_sale = Column(String(100), nullable=True)
    is_imported = Column(Boolean, nullable=False, default=False)
    commodity_type = Column(String(100), nullable=True)
    inspection_notes = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="PENDING", index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), server_default=func.now(), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    # Bidirectional relationship to associated package images
    images = relationship("InspectionImage", back_populates="inspection", cascade="all, delete-orphan", order_by="InspectionImage.sequence")


class InspectionImage(Base):
    """
    Domain model storing individual image assets belonging to an Inspection session,
    including image role (front, back, label, etc.) and link to scan records.
    """
    __tablename__ = "inspection_images"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    inspection_id = Column(String(64), ForeignKey("inspections.inspection_id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(String(64), nullable=True, index=True)
    original_filename = Column(String(255), nullable=True)
    image_path = Column(String(500), nullable=True)
    image_role = Column(String(50), nullable=False, default="label")
    sequence = Column(Integer, nullable=False, default=1)
    processing_status = Column(String(50), nullable=False, default="PENDING")
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), server_default=func.now())

    # Bidirectional relationship back to parent inspection
    inspection = relationship("Inspection", back_populates="images")

    @validates("image_role")
    def validate_image_role(self, key, value):
        if value not in VALID_IMAGE_ROLES:
            raise ValueError(f"Invalid image_role '{value}'. Must be one of: {sorted(VALID_IMAGE_ROLES)}")
        return value
