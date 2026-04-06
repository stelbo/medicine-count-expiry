"""Medicine Count & Expiry - Home Assistant custom integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api.handlers import register_api_views
from .const import CONF_CLAUDE_API_KEY, DB_FILE, DOMAIN, PLATFORMS
from .frontend import register_frontend
from .search.search_engine import MedicineSearchEngine
from .services import async_setup_services
from .storage.database import MedicineDatabase

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Medicine Count & Expiry component."""
    register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Medicine Count & Expiry from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    db_path = hass.config.path(DB_FILE)
    database = await hass.async_add_executor_job(MedicineDatabase, db_path)
    search_engine = MedicineSearchEngine(database)

    hass.data[DOMAIN]["database"] = database
    hass.data[DOMAIN]["search_engine"] = search_engine

    api_key = entry.options.get(CONF_CLAUDE_API_KEY) or entry.data.get(CONF_CLAUDE_API_KEY)
    if api_key:
        from .ai.claude_verifier import ClaudeVerifier
        hass.data[DOMAIN]["claude_verifier"] = ClaudeVerifier(api_key)

    register_api_views(hass)
    await async_setup_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Medicine Count & Expiry integration set up successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.pop(DOMAIN, None)
    return unloaded
