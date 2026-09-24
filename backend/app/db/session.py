from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings, BACKEND_DIR

DB_FILE = BACKEND_DIR / "legal_metrology.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_FILE}"

# check_same_thread=False allows SQLite to handle multi-threaded requests in FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    FastAPI dependency yielding a database session per request,
    ensuring proper cleanup when request terminates.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Creates all SQLite tables defined in app.db.models if they do not exist,
    and ensures schema additions are safely migrated for existing tables.
    """
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Safely migrate new columns to existing SQLite tables if not present
    with engine.connect() as conn:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        if "inspections" in table_names:
            existing_cols = {col["name"] for col in inspector.get_columns("inspections")}
            new_inspection_cols = [
                ("compliance_status", "VARCHAR(50)"),
                ("compliance_report_json", "TEXT"),
                ("structured_data_json", "TEXT"),
                ("ocr_summary_json", "TEXT"),
                ("provenance_json", "TEXT"),
            ]
            for col_name, col_type in new_inspection_cols:
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE inspections ADD COLUMN {col_name} {col_type}"))
                    conn.commit()

        if "inspection_images" in table_names:
            existing_img_cols = {col["name"] for col in inspector.get_columns("inspection_images")}
            new_image_cols = [
                ("ocr_result_json", "TEXT"),
                ("processing_error", "TEXT"),
            ]
            for col_name, col_type in new_image_cols:
                if col_name not in existing_img_cols:
                    conn.execute(text(f"ALTER TABLE inspection_images ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
