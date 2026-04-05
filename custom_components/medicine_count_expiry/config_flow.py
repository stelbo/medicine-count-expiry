"""Config flow for Medicine Count & Expiry integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_CLAUDE_API_KEY,
    CONF_DAILY_DIGEST,
    CONF_EXPIRY_WARNING_DAYS,
    CONF_NOTIFICATION_SERVICE,
    DEFAULT_DAILY_DIGEST,
    DEFAULT_EXPIRY_WARNING_DAYS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MedicineCountExpiryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Medicine Count & Expiry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input.get(CONF_CLAUDE_API_KEY, "")
            if api_key and not await self._validate_claude_key(api_key):
                errors[CONF_CLAUDE_API_KEY] = "invalid_api_key"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Medicine Count & Expiry",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_CLAUDE_API_KEY, default=""): str,
                vol.Optional(
                    CONF_EXPIRY_WARNING_DAYS, default=DEFAULT_EXPIRY_WARNING_DAYS
                ): vol.All(int, vol.Range(min=1, max=365)),
                vol.Optional(CONF_NOTIFICATION_SERVICE, default=""): str,
                vol.Optional(CONF_DAILY_DIGEST, default=DEFAULT_DAILY_DIGEST): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def _validate_claude_key(self, api_key: str) -> bool:
        """Validate the Claude API key by making a minimal test request."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}],
            )
            return True
        except Exception as e:
            _LOGGER.debug("API key validation failed: %s", e)
            return False

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return options flow."""
        return MedicineCountExpiryOptionsFlow(config_entry)


class MedicineCountExpiryOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Medicine Count & Expiry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_EXPIRY_WARNING_DAYS,
                    default=self.config_entry.options.get(
                        CONF_EXPIRY_WARNING_DAYS, DEFAULT_EXPIRY_WARNING_DAYS
                    ),
                ): vol.All(int, vol.Range(min=1, max=365)),
                vol.Optional(
                    CONF_NOTIFICATION_SERVICE,
                    default=self.config_entry.options.get(CONF_NOTIFICATION_SERVICE, ""),
                ): str,
                vol.Optional(
                    CONF_DAILY_DIGEST,
                    default=self.config_entry.options.get(CONF_DAILY_DIGEST, DEFAULT_DAILY_DIGEST),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
