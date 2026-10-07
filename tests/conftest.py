import os
from pathlib import Path
import shutil

TEST_DB = Path(__file__).parent / "test_certificate_jobs.db"
TEST_STORAGE = Path(__file__).parent / "generated_test"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["STORAGE_DIR"] = str(TEST_STORAGE)

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_state():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    shutil.rmtree(TEST_STORAGE, ignore_errors=True)
    TEST_STORAGE.mkdir(parents=True, exist_ok=True)
    yield
    Base.metadata.drop_all(bind=engine)
    shutil.rmtree(TEST_STORAGE, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_database(request):
    def cleanup():
        engine.dispose()
        if TEST_DB.exists():
            TEST_DB.unlink()
        shutil.rmtree(TEST_STORAGE, ignore_errors=True)

    request.addfinalizer(cleanup)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_payload():
    return {
        "certificate_title": "Certificate of Completion",
        "course_name": "Backend Engineering Workshop",
        "issuer_name": "Example Learning Academy",
        "issue_date": "2026-10-07",
        "recipients": [
            {"name": "Aarav Sharma", "email": "aarav@example.com", "certificate_id": "BE-001"},
            {"name": "Diya Verma", "email": "diya@example.com", "certificate_id": "BE-002"},
        ],
    }
