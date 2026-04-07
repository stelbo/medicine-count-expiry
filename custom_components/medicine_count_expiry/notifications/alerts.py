"""Notification alerts for medicine expiry."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, List, Optional

from ..const import DEFAULT_EXPIRY_WARNING_DAYS, DOMAIN
from ..storage.database import MedicineDatabase
from ..storage.models import Medicine

_LOGGER = logging.getLogger(__name__)


class MedicineAlerts:
    """Manages expiry alerts and notifications."""

    def __init__(
        self,
        hass,
        database: MedicineDatabase,
        notification_service: str,
        warning_days: int = DEFAULT_EXPIRY_WARNING_DAYS,
    ) -> None:
        """Initialize the alerts manager."""
        self._hass = hass
        self._db = database
        self._notification_service = notification_service
        self._warning_days = warning_days

    async def check_and_notify(self, now: Any = None) -> None:
        """Check for expiring/expired medicines and send notifications.

        Uses computed :meth:`~Medicine.get_status` results so that medicines
        past their post-opening validity period (status ``opened_too_long``) are
        included in the expired alert alongside manufacturing-expired medicines.
        """
        all_medicines = await self._hass.async_add_executor_job(self._db.get_all_medicines)
        expired = [
            m for m in all_medicines
            if m.get_status(self._warning_days) in ("expired", "opened_too_long")
        ]
        expiring_soon = [
            m for m in all_medicines
            if m.get_status(self._warning_days) == "expiring_soon"
        ]

        if expired:
            await self._send_expired_alert(expired)

        if expiring_soon:
            await self._send_expiring_soon_alert(expiring_soon)

    async def _send_expired_alert(self, medicines: List[Medicine]) -> None:
        """Send alert for expired medicines."""
        names = ", ".join(m.medicine_name for m in medicines[:5])
        suffix = f" and {len(medicines) - 5} more" if len(medicines) > 5 else ""
        message = f"🚨 EXPIRED medicines: {names}{suffix}. Please remove them immediately!"
        await self._notify(
            title="Medicine Count: Expired Medicines",
            message=message,
        )

    async def _send_expiring_soon_alert(self, medicines: List[Medicine]) -> None:
        """Send alert for medicines expiring soon."""
        lines = []
        for m in medicines[:5]:
            try:
                mfg_days = (date.fromisoformat(m.expiry_date) - date.today()).days
            except (ValueError, TypeError):
                mfg_days = 0
            open_expiry = m.open_expiry_date
            if open_expiry:
                try:
                    open_days = (date.fromisoformat(open_expiry) - date.today()).days
                    days_left = min(mfg_days, open_days)
                except (ValueError, TypeError):
                    days_left = mfg_days
            else:
                days_left = mfg_days
            lines.append(f"{m.medicine_name} (expires in {days_left} days)")
        suffix = f"\n...and {len(medicines) - 5} more" if len(medicines) > 5 else ""
        message = "⚠️ Medicines expiring soon:\n" + "\n".join(lines) + suffix
        await self._notify(
            title="Medicine Count: Expiring Soon",
            message=message,
        )

    async def send_daily_digest(self, now: Any = None) -> None:
        """Send a daily digest of medicine status."""
        all_medicines = await self._hass.async_add_executor_job(self._db.get_all_medicines)
        expired = [
            m for m in all_medicines
            if m.get_status(self._warning_days) in ("expired", "opened_too_long")
        ]
        expiring_soon = [
            m for m in all_medicines
            if m.get_status(self._warning_days) == "expiring_soon"
        ]

        lines = [
            "📋 Medicine Inventory Digest",
            f"Total medicines: {len(all_medicines)}",
            f"Expired: {len(expired)}",
            f"Expiring within {self._warning_days} days: {len(expiring_soon)}",
        ]

        if expired:
            lines.append("\n🚨 Expired:")
            for m in expired[:3]:
                lines.append(f"  - {m.medicine_name} (expired {m.expiry_date})")

        if expiring_soon:
            lines.append(f"\n⚠️ Expiring soon:")
            for m in expiring_soon[:3]:
                try:
                    mfg_days = (date.fromisoformat(m.expiry_date) - date.today()).days
                except (ValueError, TypeError):
                    mfg_days = 0
                open_expiry = m.open_expiry_date
                if open_expiry:
                    try:
                        open_days = (date.fromisoformat(open_expiry) - date.today()).days
                        days_left = min(mfg_days, open_days)
                    except (ValueError, TypeError):
                        days_left = mfg_days
                else:
                    days_left = mfg_days
                lines.append(f"  - {m.medicine_name} ({days_left} days)")

        await self._notify(
            title="Medicine Count: Daily Digest",
            message="\n".join(lines),
        )

    async def _notify(self, title: str, message: str) -> None:
        """Send a notification via Home Assistant."""
        if not self._notification_service:
            _LOGGER.warning("No notification service configured")
            return
        if self._notification_service == f"{DOMAIN}_notification":
            _LOGGER.warning(
                "Notification service '%s' only fires HA bus events and will not "
                "deliver push notifications. Configure a real HA notify service "
                "(e.g. 'persistent_notification' or 'mobile_app_<device_name>').",
                self._notification_service,
            )
        try:
            await self._hass.services.async_call(
                "notify",
                self._notification_service,
                {"title": title, "message": message},
            )
            _LOGGER.info("Notification sent: %s", title)
        except Exception as e:
            _LOGGER.error("Failed to send notification: %s", e)
