"""REST API routes for Medicine Count & Expiry integration."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from functools import partial

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..const import DOMAIN
from ..storage.models import Medicine

_LOGGER = logging.getLogger(__name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_date(value: str) -> bool:
    """Return True if *value* is a YYYY-MM-DD formatted date string."""
    if not _DATE_RE.match(value):
        return False
    try:
        from datetime import date
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


class MedicineListView(HomeAssistantView):
    """View to list all medicines or add a new one."""

    url = "/api/medicine_count_expiry/medicines"
    name = "api:medicine_count_expiry:medicines"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request - list/search medicines."""
        hass = request.app["hass"]
        search_engine = hass.data[DOMAIN]["search_engine"]

        ai_verified_raw = request.query.get("ai_verified")
        ai_verified = None
        if ai_verified_raw is not None:
            ai_verified = ai_verified_raw.lower() == "true"

        medicines = await hass.async_add_executor_job(
            partial(
                search_engine.search,
                name=request.query.get("name"),
                location=request.query.get("location"),
                expiry_before=request.query.get("expiry_before"),
                expiry_after=request.query.get("expiry_after"),
                ai_verified=ai_verified,
                status=request.query.get("status"),
            )
        )
        return web.json_response([m.to_dict() for m in medicines])

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request - add a new medicine."""
        hass = request.app["hass"]
        database = hass.data[DOMAIN]["database"]

        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        if not data.get("medicine_name") or not data.get("expiry_date"):
            return web.json_response(
                {"error": "medicine_name and expiry_date are required"}, status=400
            )

        if not _valid_date(data["expiry_date"]):
            return web.json_response(
                {"error": "expiry_date must be in YYYY-MM-DD format"}, status=400
            )

        medicine = Medicine.from_dict(data)
        medicine = await hass.async_add_executor_job(database.add_medicine, medicine)
        hass.bus.async_fire(
            f"{DOMAIN}_medicine_added", {"medicine_id": medicine.medicine_id}
        )
        return web.json_response(medicine.to_dict(), status=201)


class MedicineDetailView(HomeAssistantView):
    """View to get, update, or delete a specific medicine."""

    url = "/api/medicine_count_expiry/medicines/{medicine_id}"
    name = "api:medicine_count_expiry:medicine"
    requires_auth = True

    async def get(self, request: web.Request, medicine_id: str) -> web.Response:
        """Handle GET request - get a specific medicine."""
        hass = request.app["hass"]
        database = hass.data[DOMAIN]["database"]
        medicine = await hass.async_add_executor_job(database.get_medicine, medicine_id)
        if not medicine:
            return web.json_response({"error": "Medicine not found"}, status=404)
        return web.json_response(medicine.to_dict())

    async def put(self, request: web.Request, medicine_id: str) -> web.Response:
        """Handle PUT request - update a medicine."""
        hass = request.app["hass"]
        database = hass.data[DOMAIN]["database"]

        existing = await hass.async_add_executor_job(database.get_medicine, medicine_id)
        if not existing:
            return web.json_response({"error": "Medicine not found"}, status=404)

        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        if "expiry_date" in data and not _valid_date(data["expiry_date"]):
            return web.json_response(
                {"error": "expiry_date must be in YYYY-MM-DD format"}, status=400
            )

        merged = {**existing.to_dict(), **data, "medicine_id": medicine_id}
        updated_medicine = Medicine.from_dict(merged)
        result = await hass.async_add_executor_job(database.update_medicine, updated_medicine)
        if not result:
            return web.json_response({"error": "Update failed"}, status=500)

        hass.bus.async_fire(
            f"{DOMAIN}_medicine_updated", {"medicine_id": medicine_id}
        )
        return web.json_response(result.to_dict())

    async def delete(self, request: web.Request, medicine_id: str) -> web.Response:
        """Handle DELETE request - delete a medicine."""
        hass = request.app["hass"]
        database = hass.data[DOMAIN]["database"]

        deleted = await hass.async_add_executor_job(database.delete_medicine, medicine_id)
        if not deleted:
            return web.json_response({"error": "Medicine not found"}, status=404)

        hass.bus.async_fire(
            f"{DOMAIN}_medicine_deleted", {"medicine_id": medicine_id}
        )
        return web.json_response({"success": True})


class MedicineLeafletView(HomeAssistantView):
    """View to generate or retrieve a Slovak package leaflet for a medicine."""

    url = "/api/medicine_count_expiry/medicines/{medicine_id}/leaflet"
    name = "api:medicine_count_expiry:medicine_leaflet"
    requires_auth = True

    async def post(self, request: web.Request, medicine_id: str) -> web.Response:
        """Handle POST request - generate or return cached leaflet."""
        hass = request.app["hass"]
        database = hass.data[DOMAIN]["database"]
        claude_verifier = hass.data[DOMAIN].get("claude_verifier")

        medicine = await hass.async_add_executor_job(database.get_medicine, medicine_id)
        if not medicine:
            return web.json_response({"error": "Medicine not found"}, status=404)

        # Return cached leaflet if already generated
        if medicine.ai_leaflet:
            return web.json_response(
                {
                    "leaflet": medicine.ai_leaflet,
                    "generated_at": medicine.ai_leaflet_generated_at,
                    "cached": True,
                }
            )

        if not claude_verifier:
            return web.json_response(
                {"error": "Claude AI is not configured"}, status=503
            )

        try:
            leaflet = await claude_verifier.generate_leaflet(medicine.medicine_name)
            generated_at = datetime.now().isoformat()
            updated = await hass.async_add_executor_job(
                database.save_leaflet, medicine_id, leaflet, generated_at
            )
            if not updated:
                return web.json_response({"error": "Failed to save leaflet"}, status=500)
            return web.json_response(
                {
                    "leaflet": leaflet,
                    "generated_at": generated_at,
                    "cached": False,
                }
            )
        except Exception as e:
            _LOGGER.error("Leaflet generation error: %s", e)
            return web.json_response({"error": str(e)}, status=500)


class MedicineScanView(HomeAssistantView):
    """View to scan a medicine image with Claude AI."""

    url = "/api/medicine_count_expiry/scan"
    name = "api:medicine_count_expiry:scan"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request - scan a medicine image."""
        hass = request.app["hass"]
        claude_verifier = hass.data[DOMAIN].get("claude_verifier")

        if not claude_verifier:
            return web.json_response(
                {"error": "Claude AI is not configured"}, status=503
            )

        try:
            data = await request.read()
            content_type = request.content_type or "image/jpeg"
            result = await claude_verifier.extract_and_verify(data, content_type)
            return web.json_response(result)
        except Exception as e:
            _LOGGER.error("Scan error: %s", e)
            return web.json_response({"error": str(e)}, status=500)


class MedicineSummaryView(HomeAssistantView):
    """View to get medicine inventory summary."""

    url = "/api/medicine_count_expiry/summary"
    name = "api:medicine_count_expiry:summary"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request - get inventory summary."""
        hass = request.app["hass"]
        search_engine = hass.data[DOMAIN]["search_engine"]
        summary = await hass.async_add_executor_job(search_engine.get_summary)
        return web.json_response(summary)
