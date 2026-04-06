"""REST API routes for Medicine Count & Expiry integration."""
from __future__ import annotations

import logging
from functools import partial

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from ..const import DOMAIN
from ..storage.models import Medicine

_LOGGER = logging.getLogger(__name__)

_NOT_READY = web.json_response({"error": "Integration not ready"}, status=503)


def _domain_data(hass, *required_keys: str):
    """Return the domain data dict, or None if any required key is absent."""
    data = hass.data.get(DOMAIN)
    if not data:
        return None
    if any(k not in data for k in required_keys):
        return None
    return data


class MedicineListView(HomeAssistantView):
    """View to list all medicines or add a new one."""

    url = "/api/medicine_count_expiry/medicines"
    name = "api:medicine_count_expiry:medicines"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request - list/search medicines."""
        hass = request.app["hass"]
        data = _domain_data(hass, "search_engine")
        if data is None:
            return web.json_response({"error": "Integration not ready"}, status=503)
        search_engine = data["search_engine"]

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
        data = _domain_data(hass, "database")
        if data is None:
            return web.json_response({"error": "Integration not ready"}, status=503)
        database = data["database"]

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        if not body.get("medicine_name") or not body.get("expiry_date"):
            return web.json_response(
                {"error": "medicine_name and expiry_date are required"}, status=400
            )

        medicine = Medicine.from_dict(body)
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
        data = _domain_data(hass, "database")
        if data is None:
            return web.json_response({"error": "Integration not ready"}, status=503)
        database = data["database"]
        medicine = await hass.async_add_executor_job(database.get_medicine, medicine_id)
        if not medicine:
            return web.json_response({"error": "Medicine not found"}, status=404)
        return web.json_response(medicine.to_dict())

    async def put(self, request: web.Request, medicine_id: str) -> web.Response:
        """Handle PUT request - update a medicine."""
        hass = request.app["hass"]
        data = _domain_data(hass, "database")
        if data is None:
            return web.json_response({"error": "Integration not ready"}, status=503)
        database = data["database"]

        existing = await hass.async_add_executor_job(database.get_medicine, medicine_id)
        if not existing:
            return web.json_response({"error": "Medicine not found"}, status=404)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        merged = {**existing.to_dict(), **body, "medicine_id": medicine_id}
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
        data = _domain_data(hass, "database")
        if data is None:
            return web.json_response({"error": "Integration not ready"}, status=503)
        database = data["database"]

        deleted = await hass.async_add_executor_job(database.delete_medicine, medicine_id)
        if not deleted:
            return web.json_response({"error": "Medicine not found"}, status=404)

        hass.bus.async_fire(
            f"{DOMAIN}_medicine_deleted", {"medicine_id": medicine_id}
        )
        return web.json_response({"success": True})


class MedicineScanView(HomeAssistantView):
    """View to scan a medicine image with Claude AI."""

    url = "/api/medicine_count_expiry/scan"
    name = "api:medicine_count_expiry:scan"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request - scan a medicine image."""
        hass = request.app["hass"]
        domain_data = hass.data.get(DOMAIN) or {}
        claude_verifier = domain_data.get("claude_verifier")

        if not claude_verifier:
            return web.json_response(
                {"error": "Claude AI is not configured"}, status=503
            )

        try:
            body = await request.read()
            content_type = request.content_type or "image/jpeg"
            result = await claude_verifier.extract_from_image(body, content_type)
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
        data = _domain_data(hass, "search_engine")
        if data is None:
            return web.json_response({"error": "Integration not ready"}, status=503)
        search_engine = data["search_engine"]
        summary = await hass.async_add_executor_job(search_engine.get_summary)
        return web.json_response(summary)
