from fastapi.testclient import TestClient
import pytest

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)
