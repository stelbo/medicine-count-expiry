"""Tests for MedicineAlerts notification logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, timedelta

from custom_components.medicine_count_expiry.notifications.alerts import MedicineAlerts
from custom_components.medicine_count_expiry.storage.models import Medicine


@pytest.fixture
def mock_hass():
    """Create a minimal mock Home Assistant instance."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    # async_add_executor_job must be awaitable and must actually call the function
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    return hass


@pytest.fixture
def alerts(mock_hass, db):
    """Return a MedicineAlerts instance wired to the test DB."""
    return MedicineAlerts(
        hass=mock_hass,
        database=db,
        notification_service="mobile_app_test",
        warning_days=30,
    )


@pytest.mark.asyncio
async def test_check_and_notify_no_medicines(alerts, mock_hass):
    """check_and_notify with empty DB should not call notify."""
    await alerts.check_and_notify()
    mock_hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_check_and_notify_expired(db, alerts, mock_hass, expired_medicine):
    """check_and_notify should notify when expired medicines exist."""
    db.add_medicine(expired_medicine)
    await alerts.check_and_notify()
    assert mock_hass.services.async_call.called
    call_args = mock_hass.services.async_call.call_args
    message = call_args[0][2]["message"]
    assert "EXPIRED" in message
    assert "OldAspirin" in message


@pytest.mark.asyncio
async def test_check_and_notify_expiring_soon(db, alerts, mock_hass, expiring_soon_medicine):
    """check_and_notify should notify when medicines are expiring soon."""
    db.add_medicine(expiring_soon_medicine)
    await alerts.check_and_notify()
    assert mock_hass.services.async_call.called
    call_args = mock_hass.services.async_call.call_args
    message = call_args[0][2]["message"]
    assert "expiring soon" in message.lower()
    assert "Ibuprofen" in message


@pytest.mark.asyncio
async def test_check_and_notify_good_only(db, alerts, mock_hass, sample_medicine):
    """check_and_notify with only good medicines should not send alerts."""
    db.add_medicine(sample_medicine)
    await alerts.check_and_notify()
    mock_hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_send_daily_digest_empty(alerts, mock_hass):
    """send_daily_digest on empty inventory should still send a notification."""
    await alerts.send_daily_digest()
    assert mock_hass.services.async_call.called
    call_args = mock_hass.services.async_call.call_args
    assert call_args[0][0] == "notify"
    assert call_args[0][1] == "mobile_app_test"
    message = call_args[0][2]["message"]
    assert "Total medicines: 0" in message


@pytest.mark.asyncio
async def test_send_daily_digest_content(db, alerts, mock_hass, sample_medicine, expired_medicine, expiring_soon_medicine):
    """send_daily_digest should include counts for all status types."""
    db.add_medicine(sample_medicine)
    db.add_medicine(expired_medicine)
    db.add_medicine(expiring_soon_medicine)
    await alerts.send_daily_digest()
    call_args = mock_hass.services.async_call.call_args
    message = call_args[0][2]["message"]
    assert "Total medicines: 3" in message
    assert "Expired: 1" in message
    assert "OldAspirin" in message


@pytest.mark.asyncio
async def test_notify_no_service(db, mock_hass):
    """Alerts with no notification service should log a warning but not raise."""
    no_service_alerts = MedicineAlerts(
        hass=mock_hass,
        database=db,
        notification_service="",
        warning_days=30,
    )
    # Should complete without raising
    await no_service_alerts._notify("Test Title", "Test Message")
    mock_hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_expired_alert_truncates_long_list(db, alerts, mock_hass):
    """Expired alert message should truncate lists longer than 5."""
    for i in range(8):
        m = Medicine(
            medicine_name=f"OldDrug{i}",
            expiry_date="2000-01-01",
        )
        db.add_medicine(m)
    await alerts.check_and_notify()
    call_kwargs_list = mock_hass.services.async_call.call_args_list
    messages = [c[0][2]["message"] for c in call_kwargs_list]
    expired_message = next((m for m in messages if "EXPIRED" in m), None)
    assert expired_message is not None
    assert "more" in expired_message


@pytest.mark.asyncio
async def test_expiring_soon_alert_content(db, mock_hass):
    """Expiring soon alert should include days remaining."""
    soon = (date.today() + timedelta(days=5)).isoformat()
    m = Medicine(medicine_name="QuickExpire", expiry_date=soon)
    alerts_instance = MedicineAlerts(
        hass=mock_hass,
        database=db,
        notification_service="mobile_app",
        warning_days=30,
    )
    db.add_medicine(m)
    await alerts_instance.check_and_notify()
    call_args = mock_hass.services.async_call.call_args
    message = call_args[0][2]["message"]
    assert "QuickExpire" in message
    assert "days" in message
