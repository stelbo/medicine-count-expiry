"""Services for Medicine Count & Expiry integration."""
from __future__ import annotations

import logging
from functools import partial

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_DESCRIPTION,
    ATTR_EXPIRY_DATE,
    ATTR_IMAGE_URL,
    ATTR_LOCATION,
    ATTR_MEDICINE_ID,
    ATTR_MEDICINE_NAME,
    ATTR_QUANTITY,
    DOMAIN,
    EVENT_NOTIFICATION,
    SERVICE_ADD_MEDICINE,
    SERVICE_DELETE_MEDICINE,
    SERVICE_SCAN_IMAGE,
    SERVICE_SEARCH_MEDICINES,
    SERVICE_SEND_DIGEST,
    SERVICE_UPDATE_MEDICINE,
)
from .storage.models import Medicine

_LOGGER = logging.getLogger(__name__)


async def trigger_notification(hass: HomeAssistant, notification_type: str, medicine) -> None:
    """Fire a notification event on the HA event bus for automation triggers.

    Fires ``medicine_count_expiry_notification`` with event data containing:
    - ``type``: one of "medicine_expired", "medicine_expiring_soon",
      "medicine_opened_too_long"
    - ``medicine_name``: display name of the medicine
    - ``medicine_id``: unique identifier
    - ``expiry_date``: manufacturing expiry date (YYYY-MM-DD)
    - ``open_expiry_date``: calculated open expiry date or None
    """
    hass.bus.async_fire(
        EVENT_NOTIFICATION,
        {
            "type": notification_type,
            "medicine_name": medicine.medicine_name,
            "medicine_id": medicine.medicine_id,
            "expiry_date": medicine.expiry_date,
            "open_expiry_date": medicine.open_expiry_date,
        },
    )
    _LOGGER.debug(
        "Notification event fired: type=%s medicine=%s",
        notification_type,
        medicine.medicine_name,
    )

ADD_MEDICINE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MEDICINE_NAME): cv.string,
        vol.Required(ATTR_EXPIRY_DATE): cv.string,
        vol.Optional(ATTR_DESCRIPTION, default=""): cv.string,
        vol.Optional(ATTR_QUANTITY, default=1): vol.All(int, vol.Range(min=1)),
        vol.Optional(ATTR_LOCATION, default="unknown"): cv.string,
        vol.Optional(ATTR_IMAGE_URL, default=""): cv.string,
    }
)

UPDATE_MEDICINE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MEDICINE_ID): cv.string,
        vol.Optional(ATTR_MEDICINE_NAME): cv.string,
        vol.Optional(ATTR_EXPIRY_DATE): cv.string,
        vol.Optional(ATTR_DESCRIPTION): cv.string,
        vol.Optional(ATTR_QUANTITY): vol.All(int, vol.Range(min=1)),
        vol.Optional(ATTR_LOCATION): cv.string,
        vol.Optional(ATTR_IMAGE_URL): cv.string,
    }
)

DELETE_MEDICINE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MEDICINE_ID): cv.string,
    }
)

SEARCH_MEDICINES_SCHEMA = vol.Schema(
    {
        vol.Optional("name"): cv.string,
        vol.Optional("location"): cv.string,
        vol.Optional("expiry_before"): cv.string,
        vol.Optional("expiry_after"): cv.string,
        vol.Optional("status"): vol.In(["expired", "expiring_soon", "good"]),
    }
)

SCAN_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_IMAGE_URL): cv.url,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Medicine Count & Expiry integration."""

    async def handle_add_medicine(call: ServiceCall) -> None:
        """Handle add_medicine service call."""
        database = hass.data[DOMAIN]["database"]
        claude_verifier = hass.data[DOMAIN].get("claude_verifier")

        medicine = Medicine(
            medicine_name=call.data[ATTR_MEDICINE_NAME],
            expiry_date=call.data[ATTR_EXPIRY_DATE],
            description=call.data.get(ATTR_DESCRIPTION, ""),
            quantity=call.data.get(ATTR_QUANTITY, 1),
            location=call.data.get(ATTR_LOCATION, "unknown"),
            image_url=call.data.get(ATTR_IMAGE_URL, ""),
        )

        if claude_verifier:
            try:
                verification = await claude_verifier.verify_medicine(
                    medicine.medicine_name,
                    medicine.expiry_date,
                    medicine.description,
                )
                medicine.ai_verified = verification.get("verified", False)
                medicine.confidence_score = verification.get("confidence_score", 0.0)
                if verification.get("normalized_expiry"):
                    medicine.expiry_date = verification["normalized_expiry"]
            except Exception as e:
                _LOGGER.warning("AI verification failed: %s", e)

        await hass.async_add_executor_job(database.add_medicine, medicine)
        hass.bus.async_fire(
            f"{DOMAIN}_medicine_added",
            {"medicine_id": medicine.medicine_id, "medicine_name": medicine.medicine_name},
        )
        _LOGGER.info("Medicine added via service: %s", medicine.medicine_name)

    async def handle_update_medicine(call: ServiceCall) -> None:
        """Handle update_medicine service call."""
        database = hass.data[DOMAIN]["database"]
        medicine_id = call.data[ATTR_MEDICINE_ID]
        existing = await hass.async_add_executor_job(database.get_medicine, medicine_id)
        if not existing:
            _LOGGER.error("Medicine not found: %s", medicine_id)
            return

        updatable_attrs = [
            ATTR_MEDICINE_NAME,
            ATTR_EXPIRY_DATE,
            ATTR_DESCRIPTION,
            ATTR_QUANTITY,
            ATTR_LOCATION,
            ATTR_IMAGE_URL,
        ]
        for attr in updatable_attrs:
            if attr in call.data:
                setattr(existing, attr, call.data[attr])

        await hass.async_add_executor_job(database.update_medicine, existing)
        hass.bus.async_fire(
            f"{DOMAIN}_medicine_updated",
            {"medicine_id": medicine_id},
        )

    async def handle_delete_medicine(call: ServiceCall) -> None:
        """Handle delete_medicine service call."""
        database = hass.data[DOMAIN]["database"]
        medicine_id = call.data[ATTR_MEDICINE_ID]
        deleted = await hass.async_add_executor_job(database.delete_medicine, medicine_id)
        if deleted:
            hass.bus.async_fire(
                f"{DOMAIN}_medicine_deleted",
                {"medicine_id": medicine_id},
            )
        else:
            _LOGGER.error("Medicine not found for deletion: %s", medicine_id)

    async def handle_send_digest(call: ServiceCall) -> None:
        """Handle send_digest service call."""
        alerts = hass.data[DOMAIN].get("alerts")
        if alerts:
            await alerts.send_daily_digest()
        else:
            _LOGGER.warning("Alerts not configured; cannot send digest")

    async def handle_search_medicines(call: ServiceCall) -> None:
        """Handle search_medicines service call."""
        search_engine = hass.data[DOMAIN]["search_engine"]
        results = await hass.async_add_executor_job(
            partial(
                search_engine.search,
                name=call.data.get("name"),
                location=call.data.get("location"),
                expiry_before=call.data.get("expiry_before"),
                expiry_after=call.data.get("expiry_after"),
                status=call.data.get("status"),
            )
        )
        hass.bus.async_fire(
            f"{DOMAIN}_search_results",
            {"results": [m.to_dict() for m in results], "count": len(results)},
        )

    async def handle_scan_image(call: ServiceCall) -> None:
        """Handle scan_image service call — fetch an image URL and analyse with Claude."""
        claude_verifier = hass.data[DOMAIN].get("claude_verifier")
        if not claude_verifier:
            _LOGGER.error("Claude AI is not configured; cannot scan image")
            return

        image_url = call.data[ATTR_IMAGE_URL]
        session = async_get_clientsession(hass)
        try:
            async with session.get(image_url) as response:
                response.raise_for_status()
                image_data = await response.read()
                content_type = response.content_type or "image/jpeg"
        except Exception as e:
            _LOGGER.error("Failed to fetch image from %s: %s", image_url, e)
            return

        result = await claude_verifier.extract_from_image(image_data, content_type)
        hass.bus.async_fire(f"{DOMAIN}_scan_result", result)
        _LOGGER.info("Image scan completed, result fired as event")

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_MEDICINE, handle_add_medicine, schema=ADD_MEDICINE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_MEDICINE, handle_update_medicine, schema=UPDATE_MEDICINE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_MEDICINE, handle_delete_medicine, schema=DELETE_MEDICINE_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_SEND_DIGEST, handle_send_digest)
    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH_MEDICINES, handle_search_medicines, schema=SEARCH_MEDICINES_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SCAN_IMAGE, handle_scan_image, schema=SCAN_IMAGE_SCHEMA
    )

    # ── Notification service (visible in HA automations as a "Service called" trigger) ──

    NOTIFICATION_SCHEMA = vol.Schema(
        {
            vol.Required("message"): cv.string,
            vol.Optional("medicine_name"): cv.string,
            vol.Optional("event_type", default="notification"): cv.string,
        }
    )

    async def handle_send_notification(call: ServiceCall) -> None:
        """Handle medicine_count_expiry_notification service call.

        Fires ``medicine_count_expiry_notification`` on the HA event bus so
        automations can react to it via the "Event" trigger type.
        """
        hass.bus.async_fire(
            EVENT_NOTIFICATION,
            {
                "type": call.data.get("event_type", "notification"),
                "message": call.data["message"],
                "medicine_name": call.data.get("medicine_name"),
            },
        )
        _LOGGER.info(
            "Medicine notification service called: %s", call.data.get("message", "")
        )

    hass.services.async_register(
        "notify",
        f"{DOMAIN}_notification",
        handle_send_notification,
        schema=NOTIFICATION_SCHEMA,
    )

    _LOGGER.info("Medicine Count & Expiry services registered")
