"""Sensor platform for Medicine Count & Expiry integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Medicine Count & Expiry sensors from a config entry."""
    search_engine = hass.data[DOMAIN]["search_engine"]

    entities = [
        MedicineTotalCountSensor(hass, search_engine),
        MedicineExpiredCountSensor(hass, search_engine),
        MedicineExpiringSoonCountSensor(hass, search_engine),
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

    def update(self) -> None:
        """Update sensor state."""
        summary = self._search_engine.get_summary()
        self._attr_native_value = summary["total"]
        self._extra_attrs = {
            "expired": summary["expired"],
            "expiring_soon": summary["expiring_soon"],
            "good": summary["good"],
            "locations": summary["locations"],
        }


class MedicineExpiredCountSensor(MedicineBaseSensor):
    """Sensor reporting count of expired medicines."""

    _attr_name = "Medicine Expired Count"
    _attr_unique_id = f"{DOMAIN}_expired_count"
    _attr_icon = "mdi:pill-off"
    _attr_native_unit_of_measurement = "medicines"

    def update(self) -> None:
        """Update sensor state."""
        expired = self._search_engine.get_expired()
        self._attr_native_value = len(expired)
        self._extra_attrs = {
            "medicines": [
                {
                    "name": m.medicine_name,
                    "expiry_date": m.expiry_date,
                    "location": m.location,
                }
                for m in expired[:10]
            ]
        }


class MedicineExpiringSoonCountSensor(MedicineBaseSensor):
    """Sensor reporting count of medicines expiring soon."""

    _attr_name = "Medicine Expiring Soon Count"
    _attr_unique_id = f"{DOMAIN}_expiring_soon_count"
    _attr_icon = "mdi:pill-multiple"
    _attr_native_unit_of_measurement = "medicines"

    def update(self) -> None:
        """Update sensor state."""
        expiring_soon = self._search_engine.get_expiring_soon()
        self._attr_native_value = len(expiring_soon)
        self._extra_attrs = {
            "medicines": [
                {
                    "name": m.medicine_name,
                    "expiry_date": m.expiry_date,
                    "location": m.location,
                    "days_until_expiry": (
                        __import__("datetime").date.fromisoformat(m.expiry_date)
                        - __import__("datetime").date.today()
                    ).days,
                }
                for m in expiring_soon[:10]
            ]
        }
