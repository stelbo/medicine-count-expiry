"""Medicine Count & Expiry - Home Assistant custom integration."""
from __future__ import annotations

import logging
import shutil
from datetime import timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval

from .api.handlers import register_api_views
from .const import (
    CONF_AUTO_CLEANUP,
    CONF_CLAUDE_API_KEY,
    CONF_DAILY_DIGEST,
    CONF_DIGEST_TIME,
    CONF_EXPIRY_WARNING_DAYS,
    CONF_KEEP_DAYS,
    CONF_NOTIFICATION_SERVICE,
    DB_FILE,
    DEFAULT_AUTO_CLEANUP,
    DEFAULT_DAILY_DIGEST,
    DEFAULT_DIGEST_TIME,
    DEFAULT_EXPIRY_WARNING_DAYS,
    DEFAULT_KEEP_DAYS,
    DOMAIN,
    PLATFORMS,
)
from .frontend import register_frontend
from .notifications.alerts import MedicineAlerts
from .search.search_engine import MedicineSearchEngine
from .services import async_setup_services
from .storage.database import MedicineDatabase

_LOGGER = logging.getLogger(__name__)


def _copy_www_files(hass: HomeAssistant) -> None:
    """Copy bundled www files to /config/www/ so /local/ can serve them."""
    src = Path(__file__).parent / "www" / "medicine-count-expiry"
    dst = Path(hass.config.path("www")) / "medicine-count-expiry"
    try:
        dst.mkdir(parents=True, exist_ok=True)
        for src_file in src.iterdir():
            dst_file = dst / src_file.name
            shutil.copy2(src_file, dst_file)
            _LOGGER.debug("Copied %s → %s", src_file, dst_file)
        _LOGGER.info("Medicine Count & Expiry: www files copied to %s", dst)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Medicine Count & Expiry: could not copy www files (%s): %s",
            type(err).__name__,
            err,
        )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Medicine Count & Expiry component."""
    await hass.async_add_executor_job(_copy_www_files, hass)
    register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Medicine Count & Expiry from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # ── Database & search ────────────────────────────────────────────────────
    db_path = hass.config.path(DB_FILE)
    database = await hass.async_add_executor_job(MedicineDatabase, db_path)

    warning_days = int(
        entry.options.get(CONF_EXPIRY_WARNING_DAYS)
        or entry.data.get(CONF_EXPIRY_WARNING_DAYS, DEFAULT_EXPIRY_WARNING_DAYS)
    )
    search_engine = MedicineSearchEngine(database, warning_days=warning_days)

    hass.data[DOMAIN]["database"] = database
    hass.data[DOMAIN]["search_engine"] = search_engine

    # ── Claude AI ────────────────────────────────────────────────────────────
    api_key = entry.options.get(CONF_CLAUDE_API_KEY) or entry.data.get(CONF_CLAUDE_API_KEY)
    if api_key:
        from .ai.claude_verifier import ClaudeVerifier
        hass.data[DOMAIN]["claude_verifier"] = await hass.async_add_executor_job(
            ClaudeVerifier, api_key
        )

    # ── Notifications / alerts ────────────────────────────────────────────────
    notification_service = (
        entry.options.get(CONF_NOTIFICATION_SERVICE)
        or entry.data.get(CONF_NOTIFICATION_SERVICE, "")
    )
    alerts = MedicineAlerts(hass, database, notification_service, warning_days)
    hass.data[DOMAIN]["alerts"] = alerts

    # Hourly expiry check
    entry.async_on_unload(
        async_track_time_interval(hass, alerts.check_and_notify, timedelta(hours=1))
    )

    # Daily digest at configured time
    daily_digest = (
        entry.options.get(CONF_DAILY_DIGEST)
        if entry.options.get(CONF_DAILY_DIGEST) is not None
        else entry.data.get(CONF_DAILY_DIGEST, DEFAULT_DAILY_DIGEST)
    )
    if daily_digest:
        digest_time_str = (
            entry.options.get(CONF_DIGEST_TIME)
            or entry.data.get(CONF_DIGEST_TIME, DEFAULT_DIGEST_TIME)
        )
        try:
            hour, minute, second = (int(x) for x in digest_time_str.split(":"))
        except (ValueError, AttributeError):
            hour, minute, second = 8, 0, 0
            _LOGGER.warning("Invalid digest_time %r, defaulting to 08:00:00", digest_time_str)

        entry.async_on_unload(
            async_track_time_change(
                hass,
                alerts.send_daily_digest,
                hour=hour,
                minute=minute,
                second=second,
            )
        )
        _LOGGER.info("Daily digest scheduled at %02d:%02d:%02d", hour, minute, second)

    # ── Auto-cleanup ──────────────────────────────────────────────────────────
    auto_cleanup = (
        entry.options.get(CONF_AUTO_CLEANUP)
        if entry.options.get(CONF_AUTO_CLEANUP) is not None
        else entry.data.get(CONF_AUTO_CLEANUP, DEFAULT_AUTO_CLEANUP)
    )
    if auto_cleanup:
        keep_days = int(
            entry.options.get(CONF_KEEP_DAYS)
            or entry.data.get(CONF_KEEP_DAYS, DEFAULT_KEEP_DAYS)
        )

        async def _run_cleanup(now) -> None:
            count = await hass.async_add_executor_job(database.delete_older_than, keep_days)
            if count:
                _LOGGER.info("Auto-cleanup removed %d record(s)", count)

        entry.async_on_unload(
            async_track_time_change(hass, _run_cleanup, hour=0, minute=0, second=0)
        )
        _LOGGER.info("Auto-cleanup scheduled (keep_days=%d)", keep_days)

    # ── API, services, platforms ──────────────────────────────────────────────
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
