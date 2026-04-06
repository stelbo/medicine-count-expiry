"""Frontend registration for Medicine Count & Expiry Lovelace card."""
from __future__ import annotations

import logging

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_RESOURCE_URL = "/local/medicine-count-expiry/medicine-count-card.js"


def register_frontend(hass: HomeAssistant) -> None:
    """Register Lovelace card as a frontend resource."""

    try:
        # Register the card JS file as a frontend resource
        add_extra_js_url(hass, _RESOURCE_URL)
        _LOGGER.info(
            "Medicine Count & Expiry card registered as frontend resource at %s",
            _RESOURCE_URL,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Could not register medicine-count-card frontend resource (%s): %s",
            type(err).__name__,
            err,
        )
