"""Sensor platform for Medicine Count & Expiry integration."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_EXPIRY_WARNING_DAYS,
    DEFAULT_EXPIRY_WARNING_DAYS,
    DOMAIN,
    NOTIFICATION_EXPIRY_SOON_DAYS,
    NOTIFICATION_TYPE_EXPIRED,
    NOTIFICATION_TYPE_EXPIRING_SOON,
    NOTIFICATION_TYPE_OPENED_TOO_LONG,
    STATUS_EXPIRED,
    STATUS_OPENED_TOO_LONG,
)
from .services import trigger_notification

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Medicine Count & Expiry sensors from a config entry."""
    if DOMAIN not in hass.data or "search_engine" not in hass.data[DOMAIN]:
        _LOGGER.warning("Search engine not initialized, skipping sensor setup")
        return

    search_engine = hass.data[DOMAIN]["search_engine"]
    warning_days = (
        entry.options.get(CONF_EXPIRY_WARNING_DAYS)
        or entry.data.get(CONF_EXPIRY_WARNING_DAYS, DEFAULT_EXPIRY_WARNING_DAYS)
    )

    entities = [
        MedicineTotalCountSensor(hass, search_engine),
        MedicineExpiredCountSensor(hass, search_engine),
        MedicineExpiringSoonCountSensor(hass, search_engine, warning_days),
    ]
    async_add_entities(entities, update_before_add=True)


class MedicineBaseSensor(SensorEntity):
    """Base class for Medicine Count & Expiry sensors."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant, search_engine) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._search_engine = search_engine
        self._attr_native_value = 0
        self._extra_attrs: dict[str, Any] = {}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return self._extra_attrs

    async def async_added_to_hass(self) -> None:
        """Register event listeners when added to HA."""
        for event_suffix in ("medicine_added", "medicine_updated", "medicine_deleted"):
            self.hass.bus.async_listen(
                f"{DOMAIN}_{event_suffix}",
                self._handle_medicine_change,
            )

    @callback
    def _handle_medicine_change(self, event) -> None:
        """Handle medicine data change events."""
        self.async_schedule_update_ha_state(force_refresh=True)


class MedicineTotalCountSensor(MedicineBaseSensor):
    """Sensor reporting total medicine count."""

    _attr_name = "Medicine Total Count"
    _attr_unique_id = f"{DOMAIN}_total_count"
    _attr_icon = "mdi:pill"
    _attr_native_unit_of_measurement = "medicines"

    def __init__(self, hass: HomeAssistant, search_engine) -> None:
        """Initialize the total-count sensor."""
        super().__init__(hass, search_engine)
        # Tracks the last-notified status per medicine_id so events only fire on
        # status transitions (not on every sensor poll).
        # Note: this state is in-memory only and resets on HA restart, which means
        # notification events for already-alerting medicines will re-fire once after
        # a restart.  This is intentional – it ensures automations are not silently
        # skipped after a reboot.
        self._last_notified_status: dict[str, str] = {}

    async def async_update(self) -> None:
        """Update sensor state."""
        if self._search_engine:
            summary = await self.hass.async_add_executor_job(self._search_engine.get_summary)
            self._attr_native_value = summary["total"]
            self._extra_attrs = {
                "expired": summary["expired"],
                "expiring_soon": summary["expiring_soon"],
                "good": summary["good"],
                "locations": summary["locations"],
            }
            await self._fire_notification_events()
        else:
            self._attr_native_value = 0
            self._extra_attrs = {}

    async def _fire_notification_events(self) -> None:
        """Fire HA bus notification events for medicines requiring attention.

        Events are only fired when a medicine's notification-worthy status
        changes (transition into the condition), preventing repeated events on
        every sensor poll.
        """
        all_medicines = await self.hass.async_add_executor_job(
            self._search_engine.get_all
        )
        today = date.today()
        # Build a set of currently active medicine IDs so we can clean up stale entries
        active_ids = {m.medicine_id for m in all_medicines}
        # Remove medicines that no longer exist
        for gone_id in set(self._last_notified_status) - active_ids:
            del self._last_notified_status[gone_id]

        for medicine in all_medicines:
            status = medicine.get_status()
            notification_type: str | None = None

            if status == STATUS_EXPIRED:
                notification_type = NOTIFICATION_TYPE_EXPIRED
            elif status == STATUS_OPENED_TOO_LONG:
                notification_type = NOTIFICATION_TYPE_OPENED_TOO_LONG
            else:
                # Check manufacturing expiry within the short notification window
                try:
                    expiry = date.fromisoformat(medicine.expiry_date)
                    days_until = (expiry - today).days
                    if 0 <= days_until <= NOTIFICATION_EXPIRY_SOON_DAYS:
                        notification_type = NOTIFICATION_TYPE_EXPIRING_SOON
                except (ValueError, TypeError):
                    pass

            prev = self._last_notified_status.get(medicine.medicine_id)
            if notification_type is not None and prev != notification_type:
                await trigger_notification(self.hass, notification_type, medicine)
                self._last_notified_status[medicine.medicine_id] = notification_type
            elif notification_type is None and prev is not None:
                # Medicine returned to a non-alerting state; reset so it can
                # fire again if it re-enters an alert condition.
                del self._last_notified_status[medicine.medicine_id]


class MedicineExpiredCountSensor(MedicineBaseSensor):
    """Sensor reporting count of expired medicines."""

    _attr_name = "Medicine Expired Count"
    _attr_unique_id = f"{DOMAIN}_expired_count"
    _attr_icon = "mdi:pill-off"
    _attr_native_unit_of_measurement = "medicines"

    async def async_update(self) -> None:
        """Update sensor state."""
        if self._search_engine:
            summary = await self.hass.async_add_executor_job(self._search_engine.get_summary)
            self._attr_native_value = summary["expired"]
            self._extra_attrs = {
                "expired_manufacturing": summary.get("expired_manufacturing", 0),
                "expired_opened_too_long": summary.get("expired_opened_too_long", 0),
                "medicines": [
                    {
                        "name": m.medicine_name,
                        "expiry_date": m.expiry_date,
                        "location": m.location,
                    }
                    for m in (await self.hass.async_add_executor_job(
                        self._search_engine.get_expired
                    ))[:10]
                ],
            }
        else:
            self._attr_native_value = 0
            self._extra_attrs = {"medicines": []}


class MedicineExpiringSoonCountSensor(MedicineBaseSensor):
    """Sensor reporting count of medicines expiring soon."""

    _attr_name = "Medicine Expiring Soon Count"
    _attr_unique_id = f"{DOMAIN}_expiring_soon_count"
    _attr_icon = "mdi:pill-multiple"
    _attr_native_unit_of_measurement = "medicines"

    def __init__(self, hass: HomeAssistant, search_engine, warning_days: int = DEFAULT_EXPIRY_WARNING_DAYS) -> None:
        """Initialize the expiring-soon sensor."""
        super().__init__(hass, search_engine)
        self._warning_days = warning_days

    async def async_update(self) -> None:
        """Update sensor state."""
        if self._search_engine:
            summary = await self.hass.async_add_executor_job(self._search_engine.get_summary)
            self._attr_native_value = summary["expiring_soon"]
            expiring_soon = await self.hass.async_add_executor_job(
                self._search_engine.get_expiring_soon
            )
            self._extra_attrs = {
                "medicines": [
                    {
                        "name": m.medicine_name,
                        "expiry_date": m.expiry_date,
                        "location": m.location,
                        "days_until_expiry": (
                            date.fromisoformat(m.expiry_date) - date.today()
                        ).days,
                    }
                    for m in expiring_soon[:10]
                ]
            }
        else:
            self._attr_native_value = 0
            self._extra_attrs = {"medicines": []}
