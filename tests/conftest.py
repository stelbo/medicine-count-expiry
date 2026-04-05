"""Shared pytest fixtures for Medicine Count & Expiry tests."""
import os
import sys
import pytest

# Ensure the repo root is on the path so tests can import custom_components
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.medicine_count_expiry.storage.database import MedicineDatabase
from custom_components.medicine_count_expiry.storage.models import Medicine
from custom_components.medicine_count_expiry.search.search_engine import MedicineSearchEngine


@pytest.fixture
def db(tmp_path):
    """Return a fresh in-memory-backed MedicineDatabase for each test."""
    db_file = str(tmp_path / "test_medicines.db")
    return MedicineDatabase(db_file)


@pytest.fixture
def search_engine(db):
    """Return a MedicineSearchEngine backed by the test database."""
    return MedicineSearchEngine(db)


@pytest.fixture
def sample_medicine():
    """Return a Medicine instance with known data."""
    return Medicine(
        medicine_name="Paracetamol 500mg",
        expiry_date="2099-12-31",
        description="Pain relief tablets",
        quantity=20,
        location="bathroom",
    )


@pytest.fixture
def expired_medicine():
    """Return an expired Medicine instance."""
    return Medicine(
        medicine_name="OldAspirin",
        expiry_date="2000-01-01",
        description="Expired aspirin",
        quantity=5,
        location="first_aid_kit",
    )


@pytest.fixture
def expiring_soon_medicine():
    """Return a Medicine expiring within 30 days."""
    from datetime import date, timedelta
    soon = (date.today() + timedelta(days=10)).isoformat()
    return Medicine(
        medicine_name="Ibuprofen 200mg",
        expiry_date=soon,
        description="Anti-inflammatory",
        quantity=12,
        location="kitchen",
    )
