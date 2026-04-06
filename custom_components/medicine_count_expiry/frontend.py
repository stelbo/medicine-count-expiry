"""Frontend registration for Medicine Count & Expiry Lovelace card."""
from __future__ import annotations

import logging

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Files are placed in /config/www/medicine-count-expiry/ and are served by
# Home Assistant at /local/medicine-count-expiry/.
_RESOURCE_URL = "/local/medicine-count-expiry/medicine-count-card.js"
_EDITOR_URL = "/local/medicine-count-expiry/editor.js"


def register_frontend(hass: HomeAssistant) -> None:
    """Register Lovelace card files as frontend resources."""

    for url in (_RESOURCE_URL, _EDITOR_URL):
        try:
            add_extra_js_url(hass, url)
            _LOGGER.info(
                "Medicine Count & Expiry registered frontend resource at %s",
                url,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Could not register medicine-count-card frontend resource (%s): %s",
                type(err).__name__,
                err,
            )
