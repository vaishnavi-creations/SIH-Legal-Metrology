from pathlib import Path
from sqlalchemy import create_engine
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
    Creates all SQLite tables defined in app.db.models if they do not exist.
    """
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
