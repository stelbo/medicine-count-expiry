"""API handler utilities for Medicine Count & Expiry integration."""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)


def register_api_views(hass) -> None:
    """Register all API views with Home Assistant."""
    from .routes import (
        MedicineDetailView,
        MedicineLeafletView,
        MedicineListView,
        MedicineScanView,
        MedicineSummaryView,
    )

    hass.http.register_view(MedicineListView())
    hass.http.register_view(MedicineDetailView())
    hass.http.register_view(MedicineLeafletView())
    hass.http.register_view(MedicineScanView())
    hass.http.register_view(MedicineSummaryView())
    _LOGGER.info("Medicine Count & Expiry API views registered")
