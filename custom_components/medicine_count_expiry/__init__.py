"""Medicine Count & Expiry - Home Assistant custom integration."""
from __future__ import annotations

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .ai.claude_verifier import ClaudeVerifier
from .api.handlers import register_api_views
from .const import (
    CONF_CLAUDE_API_KEY,
    CONF_EXPIRY_WARNING_DAYS,
    CONF_NOTIFICATION_SERVICE,
    DB_FILE,
    DEFAULT_EXPIRY_WARNING_DAYS,
    DOMAIN,
    PLATFORMS,
)
from .frontend import async_register_frontend
from .notifications.alerts import MedicineAlerts
from .search.search_engine import MedicineSearchEngine
from .services import async_setup_services
from .storage.database import MedicineDatabase

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA: Final = {}  # No YAML configuration support


def _get_entry_value(entry: ConfigEntry, key: str, default):
    """Read a config value from options first, then data, then the given default."""
    return entry.options.get(key, entry.data.get(key, default))


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Medicine Count & Expiry component."""
    await async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Medicine Count & Expiry from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Initialise the SQLite database (blocking I/O – run in an executor thread).
    db_path = hass.config.path(DB_FILE)
    database: MedicineDatabase = await hass.async_add_executor_job(
        MedicineDatabase, db_path
    )

    # Read per-entry configuration values.
    warning_days: int = int(
        _get_entry_value(entry, CONF_EXPIRY_WARNING_DAYS, DEFAULT_EXPIRY_WARNING_DAYS)
    )
    notification_service: str = _get_entry_value(
        entry, CONF_NOTIFICATION_SERVICE, ""
    )

    search_engine = MedicineSearchEngine(database, warning_days=warning_days)
    alerts = MedicineAlerts(hass, database, notification_service, warning_days)

    hass.data[DOMAIN]["database"] = database
    hass.data[DOMAIN]["search_engine"] = search_engine
    hass.data[DOMAIN]["alerts"] = alerts
    hass.data[DOMAIN]["expiry_warning_days"] = warning_days

    # Initialise the Claude AI verifier only when an API key is provided.
    api_key: str = _get_entry_value(entry, CONF_CLAUDE_API_KEY, "")
    if api_key:
        hass.data[DOMAIN]["claude_verifier"] = ClaudeVerifier(api_key)

    # Register REST API views and HA services.
    register_api_views(hass)
    await async_setup_services(hass)

    # Forward setup to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Medicine Count & Expiry integration set up successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.pop(DOMAIN, None)
    return unloaded
