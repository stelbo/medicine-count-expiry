"""Options flow for Medicine Count & Expiry integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
    TimeSelectorConfig,
)

from .const import (
    CONF_AUTO_CLEANUP,
    CONF_CLAUDE_API_KEY,
    CONF_CONFIDENCE_THRESHOLD,
    CONF_DAILY_DIGEST,
    CONF_DEFAULT_LOCATION,
    CONF_DEFAULT_UNIT,
    CONF_DIGEST_TIME,
    CONF_ENABLE_CAMERA,
    CONF_EXPIRY_WARNING_DAYS,
    CONF_KEEP_DAYS,
    CONF_LOCATIONS,
    CONF_NOTIFICATION_SERVICE,
    DEFAULT_AUTO_CLEANUP,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_DAILY_DIGEST,
    DEFAULT_DEFAULT_LOCATION,
    DEFAULT_DEFAULT_UNIT,
    DEFAULT_DIGEST_TIME,
    DEFAULT_ENABLE_CAMERA,
    DEFAULT_EXPIRY_WARNING_DAYS,
    DEFAULT_KEEP_DAYS,
    DEFAULT_LOCATIONS,
    LOCATION_PRESETS,
    UNIT_PRESETS,
)

_LOGGER = logging.getLogger(__name__)


def _get(entry: config_entries.ConfigEntry, key: str, default: Any) -> Any:
    """Get a value from options first, then data, then fall back to default."""
    return entry.options.get(key, entry.data.get(key, default))


class MedicineCountExpiryOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Medicine Count & Expiry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: API Configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input.get(CONF_CLAUDE_API_KEY, "")
            if api_key and not await self._validate_claude_key(api_key):
                errors[CONF_CLAUDE_API_KEY] = "invalid_api_key"
            else:
                self._data.update(user_input)
                return await self.async_step_notifications()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CLAUDE_API_KEY,
                        default=_get(self.config_entry, CONF_CLAUDE_API_KEY, ""),
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Notification Settings."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_storage()

        return self.async_show_form(
            step_id="notifications",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_EXPIRY_WARNING_DAYS,
                        default=_get(
                            self.config_entry,
                            CONF_EXPIRY_WARNING_DAYS,
                            DEFAULT_EXPIRY_WARNING_DAYS,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=30, step=1, mode=NumberSelectorMode.SLIDER
                        )
                    ),
                    vol.Optional(
                        CONF_DAILY_DIGEST,
                        default=_get(
                            self.config_entry, CONF_DAILY_DIGEST, DEFAULT_DAILY_DIGEST
                        ),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_DIGEST_TIME,
                        default=_get(
                            self.config_entry, CONF_DIGEST_TIME, DEFAULT_DIGEST_TIME
                        ),
                    ): TimeSelector(TimeSelectorConfig()),
                    vol.Optional(
                        CONF_NOTIFICATION_SERVICE,
                        default=_get(self.config_entry, CONF_NOTIFICATION_SERVICE, ""),
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                }
            ),
        )

    async def async_step_storage(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Storage Settings."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_defaults()

        return self.async_show_form(
            step_id="storage",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LOCATIONS,
                        default=_get(
                            self.config_entry, CONF_LOCATIONS, DEFAULT_LOCATIONS
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=LOCATION_PRESETS,
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Optional(
                        CONF_AUTO_CLEANUP,
                        default=_get(
                            self.config_entry, CONF_AUTO_CLEANUP, DEFAULT_AUTO_CLEANUP
                        ),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_KEEP_DAYS,
                        default=_get(
                            self.config_entry, CONF_KEEP_DAYS, DEFAULT_KEEP_DAYS
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=30, max=365, step=1, mode=NumberSelectorMode.SLIDER
                        )
                    ),
                }
            ),
        )

    async def async_step_defaults(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Medicine Defaults."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)

        return self.async_show_form(
            step_id="defaults",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DEFAULT_LOCATION,
                        default=_get(
                            self.config_entry,
                            CONF_DEFAULT_LOCATION,
                            DEFAULT_DEFAULT_LOCATION,
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=LOCATION_PRESETS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_DEFAULT_UNIT,
                        default=_get(
                            self.config_entry, CONF_DEFAULT_UNIT, DEFAULT_DEFAULT_UNIT
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=UNIT_PRESETS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_ENABLE_CAMERA,
                        default=_get(
                            self.config_entry,
                            CONF_ENABLE_CAMERA,
                            DEFAULT_ENABLE_CAMERA,
                        ),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_CONFIDENCE_THRESHOLD,
                        default=_get(
                            self.config_entry,
                            CONF_CONFIDENCE_THRESHOLD,
                            DEFAULT_CONFIDENCE_THRESHOLD,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=100, step=1, mode=NumberSelectorMode.SLIDER
                        )
                    ),
                }
            ),
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
