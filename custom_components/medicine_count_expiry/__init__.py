"""Medicine Count & Expiry - Home Assistant custom integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .ai.claude_verifier import ClaudeVerifier
from .api.handlers import register_api_views
from .const import (
    CLAUDE_MODEL,
    CONF_CLAUDE_API_KEY,
    CONF_DAILY_DIGEST,
    CONF_EXPIRY_WARNING_DAYS,
    CONF_NOTIFICATION_SERVICE,
    DB_FILE,
    DEFAULT_EXPIRY_WARNING_DAYS,
    DOMAIN,
    PLATFORMS,
)
from .notifications.alerts import MedicineAlerts
from .search.search_engine import MedicineSearchEngine
from .services import async_setup_services
from .storage.database import MedicineDatabase

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Medicine Count & Expiry from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    config = {**entry.data, **entry.options}

    db_path = hass.config.path(DB_FILE)
    database = MedicineDatabase(db_path)
    search_engine = MedicineSearchEngine(database)

    claude_verifier = None
    api_key = config.get(CONF_CLAUDE_API_KEY, "")
    if api_key:
        claude_verifier = ClaudeVerifier(api_key, CLAUDE_MODEL)
        _LOGGER.info("Claude AI verifier initialized")

    notification_service = config.get(CONF_NOTIFICATION_SERVICE, "")
    warning_days = config.get(CONF_EXPIRY_WARNING_DAYS, DEFAULT_EXPIRY_WARNING_DAYS)
    alerts = MedicineAlerts(hass, database, notification_service, warning_days)

    hass.data[DOMAIN] = {
        "database": database,
        "search_engine": search_engine,
        "claude_verifier": claude_verifier,
        "alerts": alerts,
        "config": config,
    }

    register_api_views(hass)
    await async_setup_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Schedule daily digest if configured
    if config.get(CONF_DAILY_DIGEST, False) and notification_service:
        async def _send_daily_digest(now=None):
            await alerts.send_daily_digest()

        async_track_time_interval(hass, _send_daily_digest, timedelta(hours=24))

    # Schedule periodic expiry checks every 6 hours
    async def _check_expiry(now=None):
        await alerts.check_and_notify()

    async_track_time_interval(hass, _check_expiry, timedelta(hours=6))

    _LOGGER.info("Medicine Count & Expiry integration set up successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.pop(DOMAIN, None)
    return unloaded
