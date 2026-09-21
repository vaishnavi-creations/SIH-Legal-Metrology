import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def create_dummy_image(format: str = "JPEG", size=(200, 100), color=(255, 128, 0)) -> io.BytesIO:
    """Helper to generate an in-memory test image."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return buf

def test_health_endpoint():
    """Verify that the health check endpoint returns 200 and expected status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data

def test_upload_valid_jpeg():
    """Verify that a valid JPEG image is accepted and preprocessed."""
    buf = create_dummy_image(format="JPEG", size=(300, 200))
    files = {"file": ("test_package.jpg", buf, "image/jpeg")}
    response = client.post("/api/scan/upload", files=files)
    
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["original_filename"] == "test_package.jpg"
    assert data["original_dimensions"]["width"] == 300
    assert data["original_dimensions"]["height"] == 200
    assert "processed_image" in data
    assert len(data["processed_image"]["preprocessing_steps_applied"]) > 0

def test_upload_valid_png():
    """Verify that a valid PNG image is accepted."""
    buf = create_dummy_image(format="PNG", size=(150, 150))
    files = {"file": ("label.png", buf, "image/png")}
    response = client.post("/api/scan/upload", files=files)
    
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["original_filename"] == "label.png"

def test_upload_unsupported_file_extension():
    """Verify that non-image file extensions are rejected with 400."""
    fake_file = io.BytesIO(b"Fake PDF data")
    files = {"file": ("document.pdf", fake_file, "application/pdf")}
    response = client.post("/api/scan/upload", files=files)
    
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]

def test_upload_empty_file():
    """Verify that a 0-byte file is rejected with 400."""
    empty_file = io.BytesIO(b"")
    files = {"file": ("empty.jpg", empty_file, "image/jpeg")}
    response = client.post("/api/scan/upload", files=files)
    
    assert response.status_code == 400
    assert "Uploaded file is empty" in response.json()["detail"]

def test_upload_corrupted_image_file():
    """Verify that non-image bytes with a .jpg extension fail OpenCV decoding."""
    corrupted_data = io.BytesIO(b"This is just plain text, not a valid image stream.")
    files = {"file": ("corrupted.jpg", corrupted_data, "image/jpeg")}
    response = client.post("/api/scan/upload", files=files)
    
    assert response.status_code == 400
    assert "OpenCV failed to decode" in response.json()["detail"]
