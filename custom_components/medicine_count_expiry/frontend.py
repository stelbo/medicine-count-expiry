"""Frontend registration for Medicine Count & Expiry Lovelace card."""
from __future__ import annotations

import logging
import pathlib

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# ✅ FIXED: Point to www/medicine-count-card at root level
_CARD_DIR = pathlib.Path(__file__).parent.parent.parent / "www" / "medicine-count-card"
_STATIC_PATH = "/medicine_count_expiry/medicine-count-card"
_RESOURCE_URL = f"{_STATIC_PATH}/medicine-count-card.js"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register static path and Lovelace card as a frontend resource."""
    if not _CARD_DIR.is_dir():
        _LOGGER.warning(
            "Medicine Count & Expiry card directory not found at %s", _CARD_DIR
        )
        return

    try:
        hass.http.register_static_path(
            _STATIC_PATH, str(_CARD_DIR), cache_headers=False
        )
        _LOGGER.debug(
            "Registered static path %s -> %s", _STATIC_PATH, _CARD_DIR
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Could not register static path for medicine-count-card (%s): %s",
            type(err).__name__,
            err,
        )
        return

    add_extra_js_url(hass, _RESOURCE_URL)
    _LOGGER.info(
        "Medicine Count & Expiry card registered as frontend resource at %s",
        _RESOURCE_URL,
    )
