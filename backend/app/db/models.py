import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, func
from app.db.session import Base

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
