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


def test_summary_expiring_soon_matches_individual_status(db):
    """Summary expiring_soon count must agree with individual get_status() using the same threshold.

    Regression test: with DEFAULT_EXPIRY_WARNING_DAYS=30, a medicine expiring in 20 days
    should appear in both individual status and summary as 'expiring_soon', not 'good'.
    """
    from datetime import date, timedelta
    from custom_components.medicine_count_expiry.search.search_engine import MedicineSearchEngine

    soon = (date.today() + timedelta(days=20)).isoformat()
    m = Medicine(medicine_name="Paralen 500", expiry_date=soon)
    db.add_medicine(m)

    engine = MedicineSearchEngine(db, warning_days=30)
    summary = engine.get_summary()

    # Individual status must match the summary bucket
    assert m.get_status(30) == "expiring_soon"
    assert summary["expiring_soon"] == 1
    assert summary["good"] == 0


def test_summary_uses_configured_warning_days(db):
    """get_summary() must use the search engine's configured warning_days, not a hardcoded value."""
    from datetime import date, timedelta
    from custom_components.medicine_count_expiry.search.search_engine import MedicineSearchEngine

    # Medicine expiring in 20 days
    soon = (date.today() + timedelta(days=20)).isoformat()
    m = Medicine(medicine_name="Ibuprofen 400mg", expiry_date=soon)
    db.add_medicine(m)

    # With 30-day threshold: should be expiring_soon
    engine_30 = MedicineSearchEngine(db, warning_days=30)
    summary_30 = engine_30.get_summary()
    assert summary_30["expiring_soon"] == 1
    assert summary_30["good"] == 0

    # With 10-day threshold: should be good (20 days > 10)
    engine_10 = MedicineSearchEngine(db, warning_days=10)
    summary_10 = engine_10.get_summary()
    assert summary_10["expiring_soon"] == 0
    assert summary_10["good"] == 1


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


def test_get_summary_opened_too_long_counted_in_expired(db, search_engine, sample_medicine):
    """opened_too_long medicines should be counted in expired, not in good."""
    from datetime import date, timedelta
    past_open = (date.today() - timedelta(days=20)).isoformat()
    opened_too_long = Medicine(
        medicine_name="Paralen 200ml",
        expiry_date="2099-01-01",
        date_opened=past_open,
        days_valid_after_opening=7,
    )
    db.add_medicine(sample_medicine)
    db.add_medicine(opened_too_long)
    summary = search_engine.get_summary()
    assert summary["total"] == 2
    assert summary["expired"] == 1
    assert summary["expired_opened_too_long"] == 1
    assert summary["expired_manufacturing"] == 0
    assert summary["good"] == 1


def test_get_summary_expired_breakdown(db, search_engine):
    """get_summary() should include expired_manufacturing and expired_opened_too_long fields."""
    from datetime import date, timedelta
    past_open = (date.today() - timedelta(days=20)).isoformat()

    mfg_expired = Medicine(medicine_name="OldDrug", expiry_date="2000-01-01")
    opened_expired = Medicine(
        medicine_name="Paralen",
        expiry_date="2099-01-01",
        date_opened=past_open,
        days_valid_after_opening=7,
    )
    db.add_medicine(mfg_expired)
    db.add_medicine(opened_expired)

    summary = search_engine.get_summary()
    assert summary["expired"] == 2
    assert summary["expired_manufacturing"] == 1
    assert summary["expired_opened_too_long"] == 1


def test_get_summary_has_breakdown_fields(search_engine):
    """get_summary() must always return expired_manufacturing and expired_opened_too_long keys."""
    summary = search_engine.get_summary()
    assert "expired_manufacturing" in summary
    assert "expired_opened_too_long" in summary


def test_get_all_expired_includes_opened_too_long(db, search_engine):
    """get_all_expired() should include both manufacturing-expired and opened_too_long medicines."""
    from datetime import date, timedelta
    past_open = (date.today() - timedelta(days=20)).isoformat()
    mfg_expired = Medicine(medicine_name="OldDrug", expiry_date="2000-01-01")
    opened_too_long = Medicine(
        medicine_name="OpenedTooLong",
        expiry_date="2099-01-01",
        date_opened=past_open,
        days_valid_after_opening=7,
    )
    good = Medicine(medicine_name="GoodDrug", expiry_date="2099-01-01")
    db.add_medicine(mfg_expired)
    db.add_medicine(opened_too_long)
    db.add_medicine(good)
    results = search_engine.get_all_expired()
    assert len(results) == 2
    ids = {m.medicine_id for m in results}
    assert mfg_expired.medicine_id in ids
    assert opened_too_long.medicine_id in ids
    assert good.medicine_id not in ids


def test_get_all_expiring_soon_includes_open_expiry(db):
    """get_all_expiring_soon() should include medicines expiring via their open countdown."""
    from datetime import date, timedelta
    from custom_components.medicine_count_expiry.search.search_engine import MedicineSearchEngine

    # Opened 15 days ago, valid for 30 days → open_delta = 15, within warning_days=30
    open_date = (date.today() - timedelta(days=15)).isoformat()
    open_expiring = Medicine(
        medicine_name="AlmostDone",
        expiry_date="2099-01-01",
        date_opened=open_date,
        days_valid_after_opening=30,
    )
    mfg_expiring = Medicine(
        medicine_name="MfgExpiring",
        expiry_date=(date.today() + timedelta(days=10)).isoformat(),
    )
    good = Medicine(medicine_name="GoodDrug", expiry_date="2099-01-01")
    db.add_medicine(open_expiring)
    db.add_medicine(mfg_expiring)
    db.add_medicine(good)

    engine = MedicineSearchEngine(db, warning_days=30)
    results = engine.get_all_expiring_soon()
    assert len(results) == 2
    ids = {m.medicine_id for m in results}
    assert open_expiring.medicine_id in ids
    assert mfg_expiring.medicine_id in ids
    assert good.medicine_id not in ids
