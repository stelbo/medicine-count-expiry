"""Tests for MedicineDatabase."""
import pytest
from datetime import date, timedelta

from custom_components.medicine_count_expiry.storage.database import MedicineDatabase
from custom_components.medicine_count_expiry.storage.models import Medicine


def test_add_and_retrieve(db, sample_medicine):
    """Adding a medicine should make it retrievable by ID."""
    db.add_medicine(sample_medicine)
    result = db.get_medicine(sample_medicine.medicine_id)
    assert result is not None
    assert result.medicine_name == sample_medicine.medicine_name
    assert result.expiry_date == sample_medicine.expiry_date
    assert result.quantity == sample_medicine.quantity
    assert result.location == sample_medicine.location


def test_add_returns_same_medicine(db, sample_medicine):
    """add_medicine should return the medicine object."""
    returned = db.add_medicine(sample_medicine)
    assert returned.medicine_id == sample_medicine.medicine_id


def test_get_nonexistent(db):
    """get_medicine with unknown ID should return None."""
    assert db.get_medicine("nonexistent-id") is None


def test_get_all_empty(db):
    """get_all_medicines on empty DB should return empty list."""
    assert db.get_all_medicines() == []


def test_get_all_returns_all(db, sample_medicine, expired_medicine):
    """get_all_medicines should return all added medicines."""
    db.add_medicine(sample_medicine)
    db.add_medicine(expired_medicine)
    results = db.get_all_medicines()
    assert len(results) == 2
    ids = {m.medicine_id for m in results}
    assert sample_medicine.medicine_id in ids
    assert expired_medicine.medicine_id in ids


def test_update_medicine(db, sample_medicine):
    """update_medicine should persist changed fields."""
    db.add_medicine(sample_medicine)
    sample_medicine.quantity = 99
    sample_medicine.location = "bedroom"
    db.update_medicine(sample_medicine)
    result = db.get_medicine(sample_medicine.medicine_id)
    assert result.quantity == 99
    assert result.location == "bedroom"


def test_update_nonexistent(db, sample_medicine):
    """update_medicine on a non-existent ID should return None."""
    result = db.update_medicine(sample_medicine)
    assert result is None


def test_delete_medicine(db, sample_medicine):
    """delete_medicine should remove the medicine from the database."""
    db.add_medicine(sample_medicine)
    deleted = db.delete_medicine(sample_medicine.medicine_id)
    assert deleted is True
    assert db.get_medicine(sample_medicine.medicine_id) is None


def test_delete_nonexistent(db):
    """delete_medicine on a non-existent ID should return False."""
    assert db.delete_medicine("no-such-id") is False


def test_search_by_name(db, sample_medicine, expired_medicine):
    """search_medicines by name should return matching medicines."""
    db.add_medicine(sample_medicine)
    db.add_medicine(expired_medicine)
    results = db.search_medicines(name="paracetamol")
    assert len(results) == 1
    assert results[0].medicine_name == "Paracetamol 500mg"


def test_search_by_location(db, sample_medicine, expired_medicine):
    """search_medicines by location should filter correctly."""
    db.add_medicine(sample_medicine)
    db.add_medicine(expired_medicine)
    results = db.search_medicines(location="bathroom")
    assert all(m.location == "bathroom" for m in results)
    assert len(results) == 1


def test_search_by_ai_verified(db, sample_medicine):
    """search_medicines by ai_verified flag should work."""
    sample_medicine.ai_verified = True
    sample_medicine.confidence_score = 0.95
    db.add_medicine(sample_medicine)
    unverified = Medicine(medicine_name="TestDrug", expiry_date="2099-01-01")
    db.add_medicine(unverified)

    verified_results = db.search_medicines(ai_verified=True)
    assert len(verified_results) == 1
    assert verified_results[0].medicine_id == sample_medicine.medicine_id


def test_get_expired_medicines(db, expired_medicine, sample_medicine):
    """get_expired_medicines should only return expired entries."""
    db.add_medicine(expired_medicine)
    db.add_medicine(sample_medicine)
    expired = db.get_expired_medicines()
    assert len(expired) == 1
    assert expired[0].medicine_id == expired_medicine.medicine_id


def test_get_expiring_medicines(db, expiring_soon_medicine, sample_medicine):
    """get_expiring_medicines should return medicines expiring within given days."""
    db.add_medicine(expiring_soon_medicine)
    db.add_medicine(sample_medicine)
    expiring = db.get_expiring_medicines(days=30)
    assert len(expiring) == 1
    assert expiring[0].medicine_id == expiring_soon_medicine.medicine_id


def test_get_all_sorted_by_expiry(db):
    """get_all_medicines should be sorted by expiry_date ascending."""
    m1 = Medicine(medicine_name="Late", expiry_date="2099-12-31")
    m2 = Medicine(medicine_name="Soon", expiry_date="2025-01-01")
    m3 = Medicine(medicine_name="Middle", expiry_date="2050-06-15")
    db.add_medicine(m1)
    db.add_medicine(m2)
    db.add_medicine(m3)
    results = db.get_all_medicines()
    dates = [m.expiry_date for m in results]
    assert dates == sorted(dates)


def test_medicine_ai_verified_roundtrip(db):
    """ai_verified boolean should survive a database round-trip."""
    m = Medicine(medicine_name="Verified Drug", expiry_date="2099-01-01", ai_verified=True, confidence_score=0.88)
    db.add_medicine(m)
    retrieved = db.get_medicine(m.medicine_id)
    assert retrieved.ai_verified is True
    assert abs(retrieved.confidence_score - 0.88) < 1e-6


def test_save_leaflet_and_retrieve(db):
    """save_leaflet should persist the leaflet JSON and return the updated medicine."""
    m = Medicine(medicine_name="Paracetamol 500mg", expiry_date="2099-01-01")
    db.add_medicine(m)

    leaflet = {
        "pouzitie": "Úľava od bolesti",
        "davkovanie": "500mg každé 4 hodiny",
        "vedlajsie_ucinky": "Vzácne nausea",
        "varovania": "Neprekonať 4g denne",
        "skladovanie": "Chladné miesto",
        "interakcie": None,
    }
    generated_at = "2025-01-15T10:00:00"

    updated = db.save_leaflet(m.medicine_id, leaflet, generated_at)
    assert updated is not None
    assert updated.ai_leaflet == leaflet
    assert updated.ai_leaflet_generated_at == generated_at

    # Verify it persists after a fresh read
    retrieved = db.get_medicine(m.medicine_id)
    assert retrieved.ai_leaflet == leaflet
    assert retrieved.ai_leaflet_generated_at == generated_at


def test_save_leaflet_nonexistent(db):
    """save_leaflet on a non-existent ID should return None."""
    result = db.save_leaflet("no-such-id", {"pouzitie": "test"}, "2025-01-01T00:00:00")
    assert result is None


def test_ai_leaflet_none_by_default(db):
    """A newly added medicine should have ai_leaflet as None."""
    m = Medicine(medicine_name="Test Drug", expiry_date="2099-01-01")
    db.add_medicine(m)
    retrieved = db.get_medicine(m.medicine_id)
    assert retrieved.ai_leaflet is None
    assert retrieved.ai_leaflet_generated_at is None


def test_medicine_to_dict_includes_leaflet_fields(db):
    """to_dict should include ai_leaflet and ai_leaflet_generated_at fields."""
    leaflet = {"pouzitie": "Test", "davkovanie": "1 tab"}
    m = Medicine(
        medicine_name="Drug",
        expiry_date="2099-01-01",
        ai_leaflet=leaflet,
        ai_leaflet_generated_at="2025-06-01T12:00:00",
    )
    d = m.to_dict()
    assert "ai_leaflet" in d
    assert d["ai_leaflet"] == leaflet
    assert d["ai_leaflet_generated_at"] == "2025-06-01T12:00:00"


# ── Opening date / open expiry tests ─────────────────────────────────────────

def test_open_fields_none_by_default(db):
    """A new medicine should have date_opened and days_valid_after_opening as None."""
    m = Medicine(medicine_name="Test Drug", expiry_date="2099-01-01")
    db.add_medicine(m)
    retrieved = db.get_medicine(m.medicine_id)
    assert retrieved.date_opened is None
    assert retrieved.days_valid_after_opening is None


def test_open_fields_roundtrip(db):
    """date_opened and days_valid_after_opening should survive a database round-trip."""
    m = Medicine(
        medicine_name="Paralen 200ml",
        expiry_date="2027-12-31",
        date_opened="2026-04-01",
        days_valid_after_opening=14,
    )
    db.add_medicine(m)
    retrieved = db.get_medicine(m.medicine_id)
    assert retrieved.date_opened == "2026-04-01"
    assert retrieved.days_valid_after_opening == 14


def test_open_expiry_date_computed(db):
    """open_expiry_date in to_dict should be computed as date_opened + days_valid_after_opening."""
    m = Medicine(
        medicine_name="Paralen 200ml",
        expiry_date="2027-12-31",
        date_opened="2026-04-01",
        days_valid_after_opening=14,
    )
    d = m.to_dict()
    assert d["open_expiry_date"] == "2026-04-15"


def test_open_expiry_date_none_when_no_fields():
    """open_expiry_date should be None when date_opened is not set."""
    m = Medicine(medicine_name="TestDrug", expiry_date="2099-01-01")
    d = m.to_dict()
    assert d["open_expiry_date"] is None


def test_status_opened_too_long():
    """Medicine opened too long ago should have status 'opened_too_long'."""
    from datetime import date, timedelta
    past_date = (date.today() - timedelta(days=30)).isoformat()
    m = Medicine(
        medicine_name="Paralen 200ml",
        expiry_date="2099-01-01",
        date_opened=past_date,
        days_valid_after_opening=14,
    )
    assert m.get_status() == "opened_too_long"


def test_status_good_when_opened_within_validity():
    """Medicine opened but within validity period should still check manufacturing expiry."""
    from datetime import date, timedelta
    recent = (date.today() - timedelta(days=3)).isoformat()
    m = Medicine(
        medicine_name="Paralen 200ml",
        expiry_date="2099-01-01",
        date_opened=recent,
        days_valid_after_opening=30,
    )
    assert m.get_status() == "good"


def test_status_priority_opened_too_long_over_good_manufacturing():
    """opened_too_long takes priority over a good manufacturing expiry."""
    from datetime import date, timedelta
    old_open = (date.today() - timedelta(days=20)).isoformat()
    m = Medicine(
        medicine_name="Paralen 200ml",
        expiry_date="2099-12-31",  # Manufacturing expiry far in future
        date_opened=old_open,
        days_valid_after_opening=7,
    )
    assert m.get_status() == "opened_too_long"


def test_status_manufacturing_expiry_when_no_open_date():
    """Without date_opened, status falls back to manufacturing expiry check."""
    m = Medicine(
        medicine_name="TestDrug",
        expiry_date="2000-01-01",  # expired
        date_opened=None,
        days_valid_after_opening=None,
    )
    assert m.get_status() == "expired"


def test_update_medicine_open_fields(db):
    """update_medicine should persist date_opened and days_valid_after_opening changes."""
    m = Medicine(medicine_name="TestDrug", expiry_date="2099-01-01")
    db.add_medicine(m)

    from datetime import date
    m.date_opened = date.today().isoformat()
    m.days_valid_after_opening = 28
    db.update_medicine(m)

    retrieved = db.get_medicine(m.medicine_id)
    assert retrieved.date_opened == date.today().isoformat()
    assert retrieved.days_valid_after_opening == 28


def test_to_dict_includes_open_fields():
    """to_dict should include date_opened, days_valid_after_opening, and open_expiry_date."""
    m = Medicine(
        medicine_name="Drug",
        expiry_date="2099-01-01",
        date_opened="2026-06-01",
        days_valid_after_opening=14,
    )
    d = m.to_dict()
    assert "date_opened" in d
    assert d["date_opened"] == "2026-06-01"
    assert "days_valid_after_opening" in d
    assert d["days_valid_after_opening"] == 14
    assert "open_expiry_date" in d
    assert d["open_expiry_date"] == "2026-06-15"


def test_from_dict_loads_open_fields():
    """from_dict should correctly load date_opened and days_valid_after_opening."""
    data = {
        "medicine_name": "Drug",
        "expiry_date": "2099-01-01",
        "date_opened": "2026-06-01",
        "days_valid_after_opening": 14,
    }
    m = Medicine.from_dict(data)
    assert m.date_opened == "2026-06-01"
    assert m.days_valid_after_opening == 14


# ── Database query helper tests ───────────────────────────────────────────────

def test_get_medicines_by_status_expired(db, expired_medicine, sample_medicine):
    """get_medicines_by_status('expired') should return only manufacturing-expired medicines."""
    db.add_medicine(expired_medicine)
    db.add_medicine(sample_medicine)
    results = db.get_medicines_by_status("expired")
    assert len(results) == 1
    assert results[0].medicine_id == expired_medicine.medicine_id


def test_get_medicines_by_status_good(db, expired_medicine, sample_medicine):
    """get_medicines_by_status('good') should return only good medicines."""
    db.add_medicine(expired_medicine)
    db.add_medicine(sample_medicine)
    results = db.get_medicines_by_status("good")
    assert len(results) == 1
    assert results[0].medicine_id == sample_medicine.medicine_id


def test_get_medicines_by_status_opened_too_long(db):
    """get_medicines_by_status('opened_too_long') should return opened-too-long medicines."""
    from datetime import date, timedelta
    past_open = (date.today() - timedelta(days=20)).isoformat()
    opened = Medicine(
        medicine_name="Paralen",
        expiry_date="2099-01-01",
        date_opened=past_open,
        days_valid_after_opening=7,
    )
    good = Medicine(medicine_name="GoodDrug", expiry_date="2099-01-01")
    db.add_medicine(opened)
    db.add_medicine(good)
    results = db.get_medicines_by_status("opened_too_long")
    assert len(results) == 1
    assert results[0].medicine_id == opened.medicine_id


def test_count_medicines_by_status(db, expired_medicine, sample_medicine):
    """count_medicines_by_status should return correct counts per status."""
    db.add_medicine(expired_medicine)
    db.add_medicine(sample_medicine)
    counts = db.count_medicines_by_status()
    assert counts["expired"] == 1
    assert counts["good"] == 1
    assert counts["expiring_soon"] == 0
    assert counts["opened_too_long"] == 0


def test_count_medicines_by_status_empty(db):
    """count_medicines_by_status on empty DB should return all zeros."""
    counts = db.count_medicines_by_status()
    assert counts["expired"] == 0
    assert counts["good"] == 0
    assert counts["expiring_soon"] == 0
    assert counts["opened_too_long"] == 0


# ── Location tracking ──────────────────────────────────────────────────────

def test_default_location_set_on_add(db):
    """default_location should be initialised from location when medicine is added."""
    m = Medicine(medicine_name="Aspirin", expiry_date="2099-12-31", location="bathroom")
    db.add_medicine(m)
    result = db.get_medicine(m.medicine_id)
    assert result.default_location == "bathroom"
    assert result.location_changed_by_user is False


def test_location_changed_by_user_persisted(db, sample_medicine):
    """location_changed_by_user flag should round-trip through the database."""
    db.add_medicine(sample_medicine)
    sample_medicine.location = "bedroom"
    sample_medicine.location_changed_by_user = True
    db.update_medicine(sample_medicine)
    result = db.get_medicine(sample_medicine.medicine_id)
    assert result.location == "bedroom"
    assert result.location_changed_by_user is True
    # default_location should still hold the original value
    assert result.default_location == "bathroom"


def test_default_location_not_overwritten_on_update(db, sample_medicine):
    """Updating location should not change default_location."""
    db.add_medicine(sample_medicine)
    sample_medicine.location = "kitchen"
    sample_medicine.location_changed_by_user = True
    db.update_medicine(sample_medicine)
    result = db.get_medicine(sample_medicine.medicine_id)
    assert result.default_location == "bathroom"  # original
    assert result.location == "kitchen"            # updated
