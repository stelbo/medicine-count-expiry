"""Tests for frontend registration module."""
from unittest.mock import MagicMock, call, patch

from custom_components.medicine_count_expiry.frontend import (
    _EDITOR_URL,
    _RESOURCE_URL,
    register_frontend,
)


def test_resource_url_uses_local_prefix():
    """`_RESOURCE_URL` must use the /local/ prefix so HA can serve it."""
    assert _RESOURCE_URL.startswith("/local/"), (
        f"_RESOURCE_URL should start with '/local/', got {_RESOURCE_URL!r}"
    )
    assert "medicine-count-card.js" in _RESOURCE_URL


def test_editor_url_uses_local_prefix():
    """`_EDITOR_URL` must use the /local/ prefix so HA can serve it."""
    assert _EDITOR_URL.startswith("/local/"), (
        f"_EDITOR_URL should start with '/local/', got {_EDITOR_URL!r}"
    )
    assert "editor.js" in _EDITOR_URL


def test_register_frontend_calls_add_extra_js_url_for_both_files():
    """register_frontend should register both card and editor JS URLs."""
    hass = MagicMock()

    with patch(
        "custom_components.medicine_count_expiry.frontend.add_extra_js_url"
    ) as mock_add:
        register_frontend(hass)

    assert mock_add.call_count == 2
    mock_add.assert_any_call(hass, _RESOURCE_URL)
    mock_add.assert_any_call(hass, _EDITOR_URL)


def test_register_frontend_logs_info_on_success(caplog):
    """register_frontend should log an info message for each registered URL."""
    import logging

    hass = MagicMock()

    with patch(
        "custom_components.medicine_count_expiry.frontend.add_extra_js_url"
    ):
        with caplog.at_level(logging.INFO, logger="custom_components.medicine_count_expiry.frontend"):
            register_frontend(hass)

    assert any(_RESOURCE_URL in record.message for record in caplog.records)
    assert any(_EDITOR_URL in record.message for record in caplog.records)


def test_register_frontend_handles_exception_gracefully(caplog):
    """register_frontend should catch exceptions and log a warning, not raise."""
    import logging

    hass = MagicMock()

    with patch(
        "custom_components.medicine_count_expiry.frontend.add_extra_js_url",
        side_effect=RuntimeError("test error"),
    ):
        with caplog.at_level(logging.WARNING, logger="custom_components.medicine_count_expiry.frontend"):
            # Should NOT raise even though add_extra_js_url raises
            register_frontend(hass)

    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_messages) == 2
    assert all("Could not register" in msg for msg in warning_messages)
