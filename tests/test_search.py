"""Tests for MedicineSearchEngine."""
import pytest
from datetime import date, timedelta

from custom_components.medicine_count_expiry.storage.models import Medicine


def test_search_all(db, search_engine, sample_medicine, expired_medicine):
    """search() with no filters should return all medicines."""
    db.add_medicine(sample_medicine)
    db.add_medicine(expired_medicine)
    results = search_engine.search()
    assert len(results) == 2


def test_search_by_name(db, search_engine, sample_medicine):
    """search() by name should return matching medicines."""
    db.add_medicine(sample_medicine)
    db.add_medicine(Medicine(medicine_name="Ibuprofen", expiry_date="2099-01-01"))
    results = search_engine.search(name="para")
    assert len(results) == 1
    assert results[0].medicine_name == "Paracetamol 500mg"


def test_search_by_status_expired(db, search_engine, expired_medicine, sample_medicine):
    """search() by status='expired' should filter correctly."""
    db.add_medicine(expired_medicine)
    db.add_medicine(sample_medicine)
    results = search_engine.search(status="expired")
    assert all(m.get_status() == "expired" for m in results)
    assert len(results) == 1


def test_search_by_status_good(db, search_engine, sample_medicine, expired_medicine):
    """search() by status='good' should exclude expired/expiring."""
    db.add_medicine(sample_medicine)
    db.add_medicine(expired_medicine)
    results = search_engine.search(status="good")
    assert all(m.get_status() == "good" for m in results)


def test_search_by_location(db, search_engine, sample_medicine):
    """search() by location should filter correctly."""
    db.add_medicine(sample_medicine)
    db.add_medicine(Medicine(medicine_name="Other", expiry_date="2099-01-01", location="kitchen"))
    results = search_engine.search(location="bathroom")
    assert len(results) == 1
    assert results[0].location == "bathroom"


def test_get_expired(db, search_engine, expired_medicine, sample_medicine):
    """get_expired() should only return expired medicines."""
    db.add_medicine(expired_medicine)
    db.add_medicine(sample_medicine)
    results = search_engine.get_expired()
    assert len(results) == 1
    assert results[0].medicine_id == expired_medicine.medicine_id


def test_get_expiring_soon(db, search_engine, expiring_soon_medicine, sample_medicine):
    """get_expiring_soon() should return medicines expiring within 30 days."""
    db.add_medicine(expiring_soon_medicine)
    db.add_medicine(sample_medicine)
    results = search_engine.get_expiring_soon(days=30)
    assert len(results) == 1
    assert results[0].medicine_id == expiring_soon_medicine.medicine_id


def test_get_by_location(db, search_engine, sample_medicine):
    """get_by_location() should return medicines at that location."""
    db.add_medicine(sample_medicine)
    db.add_medicine(Medicine(medicine_name="Other", expiry_date="2099-01-01", location="kitchen"))
    results = search_engine.get_by_location("bathroom")
    assert all(m.location == "bathroom" for m in results)


def test_get_all(db, search_engine, sample_medicine, expired_medicine):
    """get_all() should return all medicines."""
    db.add_medicine(sample_medicine)
    db.add_medicine(expired_medicine)
    assert len(search_engine.get_all()) == 2


def test_get_summary_empty(search_engine):
    """get_summary() on empty inventory returns zeros."""
    summary = search_engine.get_summary()
    assert summary["total"] == 0
    assert summary["expired"] == 0
    assert summary["expiring_soon"] == 0
    assert summary["good"] == 0
    assert summary["locations"] == []


def test_get_summary(db, search_engine, sample_medicine, expired_medicine, expiring_soon_medicine):
    """get_summary() should correctly tally each status bucket."""
    db.add_medicine(sample_medicine)
    db.add_medicine(expired_medicine)
    db.add_medicine(expiring_soon_medicine)
    summary = search_engine.get_summary()
    assert summary["total"] == 3
    assert summary["expired"] == 1
    assert summary["expiring_soon"] == 1
    assert summary["good"] == 1
    assert set(summary["locations"]) == {"bathroom", "first_aid_kit", "kitchen"}


def test_search_combined_filters(db, search_engine):
    """search() with multiple filters should apply all criteria."""
    m1 = Medicine(medicine_name="Aspirin", expiry_date="2099-01-01", location="bathroom")
    m2 = Medicine(medicine_name="Aspirin", expiry_date="2099-01-01", location="kitchen")
    m3 = Medicine(medicine_name="Ibuprofen", expiry_date="2099-01-01", location="bathroom")
    db.add_medicine(m1)
    db.add_medicine(m2)
    db.add_medicine(m3)
    results = search_engine.search(name="aspirin", location="bathroom")
    assert len(results) == 1
    assert results[0].medicine_id == m1.medicine_id
