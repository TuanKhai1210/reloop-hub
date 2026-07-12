import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_reloop.db"
os.environ["JWT_SECRET"] = "test-secret-at-least-thirty-two-bytes-long"
os.environ["DEVICE_API_KEY"] = "test-device-key"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.seed import seed


@pytest.fixture(scope="session", autouse=True)
def test_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    Path("test_reloop.db").unlink(missing_ok=True)


@pytest.fixture()
def client():
    with TestClient(app) as value:
        yield value


@pytest.fixture()
def admin_headers(client: TestClient):
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "admin@reloop.vn", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
