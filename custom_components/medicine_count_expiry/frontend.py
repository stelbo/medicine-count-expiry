"""Frontend registration for Medicine Count & Expiry Lovelace card."""
from __future__ import annotations

import logging
import os

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Files are served from custom_components/medicine_count_expiry/www/medicine-count-expiry/
# via a static route so no manual copy into /config/www/ is needed.
_SERVE_PATH = "/medicine-count-expiry"
_RESOURCE_URL = f"{_SERVE_PATH}/medicine-count-card.js"
_EDITOR_URL = f"{_SERVE_PATH}/editor.js"
_WWW_DIR = os.path.join(os.path.dirname(__file__), "www", "medicine-count-expiry")


def register_frontend(hass: HomeAssistant) -> None:
    """Register Lovelace card files as frontend resources."""

    # Serve card files directly from the integration directory so they are
    # available on fresh HACS installs without any manual file copying.
    if hasattr(hass.http, "register_static_path"):
        hass.http.register_static_path(_SERVE_PATH, _WWW_DIR, cache_headers=True)
    else:
        _LOGGER.warning(
            "register_static_path not available; Lovelace card files may not be served automatically"
        )

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
