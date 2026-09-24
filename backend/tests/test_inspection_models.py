import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base, init_db, engine
from app.db.models import Inspection, InspectionImage, VALID_IMAGE_ROLES

@pytest.fixture
def db_session():
    """
    Provides an isolated in-memory SQLite database session for model testing,
    ensuring each test starts with a clean slate without persisting garbage.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


def test_init_db_creates_inspection_tables():
    """Verify that init_db() successfully creates inspections and inspection_images tables."""
    init_db()
    table_names = Base.metadata.tables.keys()
    assert "inspections" in table_names
    assert "inspection_images" in table_names
    assert "scan_records" in table_names


def test_inspection_creation(db_session):
    """
    1. Inspection creation:
    Verify that an Inspection record can be instantiated and persisted with custom attributes.
    """
    inspection = Inspection(
        product_name="Haldiram's Bhujia",
        country_of_manufacture="India",
        country_of_sale="India",
        is_imported=False,
        commodity_type="Snacks & Confectionery",
        inspection_notes="Standard retail packaging inspection",
        status="IN_PROGRESS"
    )
    db_session.add(inspection)
    db_session.commit()
    db_session.refresh(inspection)

    assert inspection.id is not None
    assert inspection.id > 0
    assert len(inspection.inspection_id) > 0
    assert inspection.product_name == "Haldiram's Bhujia"
    assert inspection.country_of_manufacture == "India"
    assert inspection.country_of_sale == "India"
    assert inspection.is_imported is False
    assert inspection.commodity_type == "Snacks & Confectionery"
    assert inspection.inspection_notes == "Standard retail packaging inspection"
    assert inspection.status == "IN_PROGRESS"


def test_inspection_image_creation(db_session):
    """
    2. InspectionImage creation:
    Verify that an InspectionImage record can be created and persisted linked to an inspection.
    """
    inspection = Inspection(product_name="Dettol Handwash")
    db_session.add(inspection)
    db_session.commit()
    db_session.refresh(inspection)

    image = InspectionImage(
        inspection_id=inspection.inspection_id,
        file_id="scan-uuid-dettol-01",
        original_filename="dettol_front.jpg",
        image_path="uploads/original/scan-uuid-dettol-01_front.jpg",
        image_role="front",
        sequence=1,
        processing_status="COMPLETED"
    )
    db_session.add(image)
    db_session.commit()
    db_session.refresh(image)

    assert image.id is not None
    assert image.inspection_id == inspection.inspection_id
    assert image.file_id == "scan-uuid-dettol-01"
    assert image.original_filename == "dettol_front.jpg"
    assert image.image_path == "uploads/original/scan-uuid-dettol-01_front.jpg"
    assert image.image_role == "front"
    assert image.sequence == 1
    assert image.processing_status == "COMPLETED"


def test_relationship_between_inspection_and_inspection_image(db_session):
    """
    3. Relationship between Inspection and InspectionImage:
    Verify parent-child bidirectional relationship, sequence ordering, and cascade delete.
    """
    inspection = Inspection(product_name="Cadbury Dairy Milk Silk")
    db_session.add(inspection)
    db_session.commit()
    db_session.refresh(inspection)

    img_front = InspectionImage(
        inspection_id=inspection.inspection_id,
        image_role="front",
        sequence=1,
        original_filename="front.jpg"
    )
    img_back = InspectionImage(
        inspection_id=inspection.inspection_id,
        image_role="back",
        sequence=2,
        original_filename="back.jpg"
    )
    img_label = InspectionImage(
        inspection_id=inspection.inspection_id,
        image_role="label",
        sequence=3,
        original_filename="nutritional_label.jpg"
    )
    db_session.add_all([img_back, img_front, img_label])
    db_session.commit()
    db_session.refresh(inspection)

    # 1. Parent contains children ordered by sequence
    assert len(inspection.images) == 3
    assert inspection.images[0].image_role == "front"
    assert inspection.images[0].sequence == 1
    assert inspection.images[1].image_role == "back"
    assert inspection.images[1].sequence == 2
    assert inspection.images[2].image_role == "label"
    assert inspection.images[2].sequence == 3

    # 2. Child refers back to parent
    assert img_front.inspection is inspection
    assert img_back.inspection.product_name == "Cadbury Dairy Milk Silk"

    # 3. Cascade deletion: deleting inspection deletes all linked images
    db_session.delete(inspection)
    db_session.commit()

    remaining_images = db_session.query(InspectionImage).filter(
        InspectionImage.inspection_id == inspection.inspection_id
    ).all()
    assert len(remaining_images) == 0


def test_inspection_and_image_default_values(db_session):
    """
    4. Default values:
    Verify default values for both Inspection and InspectionImage models.
    """
    # Inspection defaults
    inspection = Inspection()
    db_session.add(inspection)
    db_session.commit()
    db_session.refresh(inspection)

    assert isinstance(inspection.inspection_id, str)
    assert len(inspection.inspection_id) >= 32
    assert inspection.is_imported is False
    assert inspection.status == "PENDING"
    assert inspection.created_at is not None
    assert isinstance(inspection.created_at, datetime.datetime)
    assert inspection.updated_at is not None
    assert isinstance(inspection.updated_at, datetime.datetime)

    # InspectionImage defaults
    image = InspectionImage(inspection_id=inspection.inspection_id)
    db_session.add(image)
    db_session.commit()
    db_session.refresh(image)

    assert image.image_role == "label"
    assert image.sequence == 1
    assert image.processing_status == "PENDING"
    assert image.uploaded_at is not None
    assert isinstance(image.uploaded_at, datetime.datetime)


def test_nullable_fields(db_session):
    """
    5. Nullable fields:
    Verify that all optional attributes on Inspection and InspectionImage accept None cleanly.
    """
    inspection = Inspection(
        product_name=None,
        country_of_manufacture=None,
        country_of_sale=None,
        commodity_type=None,
        inspection_notes=None
    )
    db_session.add(inspection)
    db_session.commit()
    db_session.refresh(inspection)

    assert inspection.product_name is None
    assert inspection.country_of_manufacture is None
    assert inspection.country_of_sale is None
    assert inspection.commodity_type is None
    assert inspection.inspection_notes is None

    image = InspectionImage(
        inspection_id=inspection.inspection_id,
        file_id=None,
        original_filename=None,
        image_path=None
    )
    db_session.add(image)
    db_session.commit()
    db_session.refresh(image)

    assert image.file_id is None
    assert image.original_filename is None
    assert image.image_path is None


@pytest.mark.parametrize("valid_role", [
    "front",
    "back",
    "left",
    "right",
    "top",
    "bottom",
    "label",
    "other"
])
def test_valid_image_roles(db_session, valid_role):
    """
    6. Valid image_role values:
    Verify that all 8 supported roles are accepted without error.
    """
    assert valid_role in VALID_IMAGE_ROLES
    inspection = Inspection(product_name="Role Test Product")
    db_session.add(inspection)
    db_session.commit()

    image = InspectionImage(
        inspection_id=inspection.inspection_id,
        image_role=valid_role
    )
    db_session.add(image)
    db_session.commit()
    db_session.refresh(image)

    assert image.image_role == valid_role


@pytest.mark.parametrize("invalid_role", [
    "diagonal",
    "side",
    "angled_view",
    "perspective",
    "barcode_only",
    "",
    "FRONT",  # Case-sensitive check
    "unknown"
])
def test_invalid_image_role_rejection(db_session, invalid_role):
    """
    7. Invalid image_role rejection:
    Verify that setting an unsupported image_role raises a ValueError immediately.
    """
    with pytest.raises(ValueError) as exc_info:
        InspectionImage(
            inspection_id="any-inspection-id",
            image_role=invalid_role
        )
    assert f"Invalid image_role '{invalid_role}'" in str(exc_info.value)


def test_invalid_image_role_rejection_on_attribute_update(db_session):
    """
    7b. Invalid image_role rejection on mutation:
    Verify that mutating an existing InspectionImage to an invalid role also raises ValueError.
    """
    inspection = Inspection(product_name="Mutation Test")
    db_session.add(inspection)
    db_session.commit()

    image = InspectionImage(
        inspection_id=inspection.inspection_id,
        image_role="front"
    )
    db_session.add(image)
    db_session.commit()

    with pytest.raises(ValueError) as exc_info:
        image.image_role = "unsupported_view"
    assert "Invalid image_role 'unsupported_view'" in str(exc_info.value)
