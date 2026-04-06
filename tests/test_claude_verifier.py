"""Tests for ClaudeVerifier (with mocked Anthropic client)."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.medicine_count_expiry.ai.claude_verifier import (
    ClaudeVerifier,
    _parse_claude_response,
    _retry_with_backoff,
)


@pytest.fixture
def verifier():
    """Return a ClaudeVerifier with a fake API key."""
    return ClaudeVerifier(api_key="test-key-123", model="claude-sonnet-4-6")


def _mock_anthropic_response(text: str):
    """Create a mock Anthropic messages.create return value."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


@pytest.mark.asyncio
async def test_verify_medicine_success(verifier):
    """verify_medicine should parse Claude JSON response correctly."""
    mock_response_data = {
        "verified": True,
        "medicine_name_valid": True,
        "expiry_date_valid": True,
        "description_valid": True,
        "confidence_score": 0.95,
        "notes": "All data looks valid.",
        "normalized_expiry": "2025-12-31",
    }
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(json.dumps(mock_response_data))
        )
        mock_get_client.return_value = mock_client

        result = await verifier.verify_medicine(
            medicine_name="Paracetamol 500mg",
            expiry_date="2025-12-31",
            description="Pain relief",
        )

    assert result["verified"] is True
    assert result["confidence_score"] == pytest.approx(0.95)
    assert result["normalized_expiry"] == "2025-12-31"


@pytest.mark.asyncio
async def test_verify_medicine_invalid_json(verifier):
    """verify_medicine should return failure dict on malformed JSON."""
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("not valid json {{")
        )
        mock_get_client.return_value = mock_client

        result = await verifier.verify_medicine("Drug", "2025-01-01")

    assert result["verified"] is False
    assert result["confidence_score"] == 0.0
    assert "notes" in result


@pytest.mark.asyncio
async def test_verify_medicine_api_error(verifier):
    """verify_medicine should handle API exceptions gracefully."""
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))
        mock_get_client.return_value = mock_client

        result = await verifier.verify_medicine("Drug", "2025-01-01")

    assert result["verified"] is False
    assert "error" in result["notes"].lower() or "Verification error" in result["notes"]


@pytest.mark.asyncio
async def test_extract_from_image_success(verifier):
    """extract_from_image should parse Claude JSON response correctly."""
    mock_response_data = {
        "medicine_name": "Aspirin 100mg",
        "expiry_date": "2026-03-31",
        "description": "100mg tablets",
        "barcode": "1234567890",
        "confidence": {"medicine_name": 0.9, "expiry_date": 0.85, "description": 0.8},
        "raw_expiry_text": "EXP 03/2026",
    }
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(json.dumps(mock_response_data))
        )
        mock_get_client.return_value = mock_client

        result = await verifier.extract_from_image(b"fake_image_bytes", "image/jpeg")

    assert result["medicine_name"] == "Aspirin 100mg"
    assert result["expiry_date"] == "2026-03-31"
    assert result["confidence"]["medicine_name"] == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_extract_from_image_invalid_json(verifier):
    """extract_from_image should return None fields on malformed JSON."""
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("oops not json")
        )
        mock_get_client.return_value = mock_client

        result = await verifier.extract_from_image(b"fake_bytes")

    assert result["medicine_name"] is None
    assert result["expiry_date"] is None
    assert result["confidence"]["medicine_name"] == 0.0


@pytest.mark.asyncio
async def test_extract_from_image_api_error(verifier):
    """extract_from_image should handle API exceptions gracefully."""
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("Network failure"))
        mock_get_client.return_value = mock_client

        result = await verifier.extract_from_image(b"fake_bytes")

    assert result["medicine_name"] is None
    assert result["expiry_date"] is None


def test_get_client_missing_anthropic():
    """ClaudeVerifier should raise ImportError at construction when anthropic is not installed."""
    with patch(
        "custom_components.medicine_count_expiry.ai.claude_verifier._get_anthropic",
        side_effect=ImportError("anthropic package is required"),
    ):
        with pytest.raises(ImportError, match="anthropic package is required"):
            ClaudeVerifier(api_key="test-key-123")


def test_client_is_cached(verifier):
    """_get_client should reuse the same client instance across calls."""
    with patch.object(verifier, "_get_client") as mock_get_client:
        fake_client = MagicMock()
        mock_get_client.return_value = fake_client
        c1 = verifier._get_client()
        c2 = verifier._get_client()
        assert c1 is c2


@pytest.mark.asyncio
async def test_generate_leaflet_success(verifier):
    """generate_leaflet should parse Claude JSON response and return Slovak leaflet sections."""
    mock_response_data = {
        "pouzitie": "Úľava od miernej až stredne ťažkej bolesti a horúčky.",
        "davkovanie": "500-1000 mg každých 4-6 hodín podľa potreby.",
        "vedlajsie_ucinky": "Vzácne: nausea, vyrážka.",
        "varovania": "Neprekonať maximálnu dennú dávku 4000 mg.",
        "skladovanie": "Chladné, suché miesto. Mimo dosahu detí.",
        "interakcie": "Warfarin – možné liekové interakcie.",
    }
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(json.dumps(mock_response_data))
        )
        mock_get_client.return_value = mock_client

        result = await verifier.generate_leaflet("Paracetamol 500mg")

    assert result["pouzitie"] is not None
    assert result["davkovanie"] is not None
    assert result["skladovanie"] is not None
    assert "error" not in result


@pytest.mark.asyncio
async def test_generate_leaflet_invalid_json(verifier):
    """generate_leaflet should return error dict on malformed JSON."""
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("not valid json")
        )
        mock_get_client.return_value = mock_client

        result = await verifier.generate_leaflet("Ibuprofen 200mg")

    assert "error" in result
    assert result["pouzitie"] is None


@pytest.mark.asyncio
async def test_generate_leaflet_api_error(verifier):
    """generate_leaflet should handle API exceptions gracefully."""
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("Network failure"))
        mock_get_client.return_value = mock_client

        result = await verifier.generate_leaflet("Aspirin 100mg")

    assert "error" in result
    assert result["pouzitie"] is None


@pytest.mark.asyncio
async def test_extract_label_info_success(verifier):
    """extract_label_info should parse Claude JSON response and return name + description only."""
    mock_response_data = {
        "medicine_name": "Aspirin Plus",
        "description": "500mg tablets",
        "confidence": {"medicine_name": 0.95, "description": 0.90},
    }
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(json.dumps(mock_response_data))
        )
        mock_get_client.return_value = mock_client

        result = await verifier.extract_label_info(b"fake_image_bytes", "image/jpeg")

    assert result["medicine_name"] == "Aspirin Plus"
    assert result["description"] == "500mg tablets"
    assert result["confidence"]["medicine_name"] == pytest.approx(0.95)
    assert result["confidence"]["description"] == pytest.approx(0.90)
    assert "expiry_date" not in result


@pytest.mark.asyncio
async def test_extract_label_info_invalid_json(verifier):
    """extract_label_info should return None fields on malformed JSON."""
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("not valid json")
        )
        mock_get_client.return_value = mock_client

        result = await verifier.extract_label_info(b"fake_bytes")

    assert result["medicine_name"] is None
    assert result["description"] is None
    assert result["confidence"]["medicine_name"] == 0.0
    assert result["confidence"]["description"] == 0.0


@pytest.mark.asyncio
async def test_extract_label_info_api_error(verifier):
    """extract_label_info should handle API exceptions gracefully."""
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("Network failure"))
        mock_get_client.return_value = mock_client

        result = await verifier.extract_label_info(b"fake_bytes")

    assert result["medicine_name"] is None
    assert result["description"] is None
    assert result["confidence"]["medicine_name"] == 0.0


@pytest.mark.asyncio
async def test_extract_label_info_default_media_type(verifier):
    """extract_label_info should use image/jpeg as default media type."""
    mock_response_data = {
        "medicine_name": "Ibuprofen 200mg",
        "description": "200mg film-coated tablets",
        "confidence": {"medicine_name": 0.88, "description": 0.80},
    }
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(json.dumps(mock_response_data))
        )
        mock_get_client.return_value = mock_client

        result = await verifier.extract_label_info(b"fake_bytes")

    assert result["medicine_name"] == "Ibuprofen 200mg"


@pytest.mark.asyncio
async def test_extract_and_verify_success(verifier):
    """extract_and_verify should return extraction merged with verification data."""
    extraction_data = {
        "medicine_name": "Aspirin 100mg",
        "expiry_date": "2026-03-31",
        "description": "100mg tablets",
        "barcode": None,
        "confidence": {"medicine_name": 0.9, "expiry_date": 0.85, "description": 0.8},
        "raw_expiry_text": "EXP 03/2026",
    }
    verification_data = {
        "verified": True,
        "medicine_name_valid": True,
        "expiry_date_valid": True,
        "description_valid": True,
        "confidence_score": 0.92,
        "notes": "All looks valid.",
        "normalized_expiry": "2026-03-31",
    }

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        # First call is extraction (image content), second is verification (text only)
        if call_count == 1:
            return _mock_anthropic_response(json.dumps(extraction_data))
        return _mock_anthropic_response(json.dumps(verification_data))

    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        result = await verifier.extract_and_verify(b"fake_image_bytes", "image/jpeg")

    assert result["medicine_name"] == "Aspirin 100mg"
    assert result["expiry_date"] == "2026-03-31"
    assert result["description"] == "100mg tablets"
    assert result["confidence"]["medicine_name"] == pytest.approx(0.9)
    assert result["confidence"]["expiry_date"] == pytest.approx(0.85)
    assert result["verified"] is True
    assert result["overall_confidence"] == pytest.approx(0.92)
    assert result["verification"]["confidence_score"] == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_extract_and_verify_no_medicine_name(verifier):
    """extract_and_verify should skip verification when no medicine name is extracted."""
    extraction_data = {
        "medicine_name": None,
        "expiry_date": None,
        "description": None,
        "confidence": {"medicine_name": 0.0, "expiry_date": 0.0, "description": 0.0},
    }

    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(json.dumps(extraction_data))
        )
        mock_get_client.return_value = mock_client

        result = await verifier.extract_and_verify(b"fake_image_bytes", "image/jpeg")

    assert result["medicine_name"] is None
    assert "verification" not in result
    assert "overall_confidence" not in result
    # Only one API call made (no verification step)
    assert mock_client.messages.create.call_count == 1


@pytest.mark.asyncio
async def test_extract_and_verify_verification_fails_gracefully(verifier):
    """extract_and_verify should still return extraction when verification errors."""
    extraction_data = {
        "medicine_name": "Ibuprofen 200mg",
        "expiry_date": "2027-01-31",
        "description": "Anti-inflammatory",
        "confidence": {"medicine_name": 0.88, "expiry_date": 0.75, "description": 0.7},
    }

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_anthropic_response(json.dumps(extraction_data))
        raise RuntimeError("API quota exceeded")

    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        result = await verifier.extract_and_verify(b"fake_image_bytes", "image/jpeg")

    # Extraction data is still returned
    assert result["medicine_name"] == "Ibuprofen 200mg"
    assert result["expiry_date"] == "2027-01-31"
    # Verification failed gracefully – verified flag is False and confidence_score is 0
    assert result["verified"] is False
    assert result["overall_confidence"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_extract_label_info_empty_response_triggers_retry(verifier):
    """extract_label_info should retry once when Claude returns an empty response."""
    mock_response_data = {
        "medicine_name": "Aspirin Plus",
        "description": "500mg tablets",
        "confidence": {"medicine_name": 0.95, "description": 0.90},
    }

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_anthropic_response("")  # empty on first attempt
        return _mock_anthropic_response(json.dumps(mock_response_data))

    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        result = await verifier.extract_label_info(b"fake_bytes")

    assert call_count == 2
    assert result["medicine_name"] == "Aspirin Plus"


@pytest.mark.asyncio
async def test_extract_label_info_empty_medicine_name_triggers_retry(verifier):
    """extract_label_info should retry once when Claude returns a result with no medicine_name."""
    mock_response_data = {
        "medicine_name": "Paracetamol 500mg",
        "description": "500mg tablets",
        "confidence": {"medicine_name": 0.88, "description": 0.85},
    }

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_anthropic_response(json.dumps({"medicine_name": None, "description": None, "confidence": {}}))
        return _mock_anthropic_response(json.dumps(mock_response_data))

    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        result = await verifier.extract_label_info(b"fake_bytes")

    assert call_count == 2
    assert result["medicine_name"] == "Paracetamol 500mg"


@pytest.mark.asyncio
async def test_extract_label_info_no_retry_on_second_attempt(verifier):
    """extract_label_info should not retry more than once even if second attempt also fails."""
    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        return _mock_anthropic_response("")

    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        result = await verifier.extract_label_info(b"fake_bytes")

    assert call_count == 2
    assert result["medicine_name"] is None
    assert result["description"] is None


@pytest.mark.asyncio
async def test_extract_label_info_empty_string_medicine_name_triggers_retry(verifier):
    """extract_label_info should retry when Claude returns an empty string as medicine_name."""
    mock_response_data = {
        "medicine_name": "Ibuprofen 400mg",
        "description": "400mg tablets",
        "confidence": {"medicine_name": 0.92, "description": 0.88},
    }

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_anthropic_response(json.dumps({"medicine_name": "", "description": None, "confidence": {}}))
        return _mock_anthropic_response(json.dumps(mock_response_data))

    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        result = await verifier.extract_label_info(b"fake_bytes")

    assert call_count == 2
    assert result["medicine_name"] == "Ibuprofen 400mg"


# ── _parse_claude_response tests ─────────────────────────────────────────────


def test_parse_claude_response_plain_json():
    """_parse_claude_response should handle plain JSON without code fence."""
    data = {"medicine_name": "Aspirin", "confidence": 0.99}
    result = _parse_claude_response(json.dumps(data))
    assert result == data


def test_parse_claude_response_json_code_fence():
    """_parse_claude_response should strip ```json ... ``` code fences."""
    data = {"medicine_name": "PARALEN 500", "description": "500 mg tablets"}
    wrapped = f"```json\n{json.dumps(data)}\n```"
    result = _parse_claude_response(wrapped)
    assert result == data


def test_parse_claude_response_bare_code_fence():
    """_parse_claude_response should strip ``` ... ``` code fences without language tag."""
    data = {"verified": True, "confidence_score": 0.95}
    wrapped = f"```\n{json.dumps(data)}\n```"
    result = _parse_claude_response(wrapped)
    assert result == data


def test_parse_claude_response_uppercase_json_tag():
    """_parse_claude_response should handle uppercase JSON language tag."""
    data = {"medicine_name": "Aspirin"}
    wrapped = f"```JSON\n{json.dumps(data)}\n```"
    result = _parse_claude_response(wrapped)
    assert result == data


def test_parse_claude_response_strips_whitespace():
    """_parse_claude_response should handle leading/trailing whitespace."""
    data = {"key": "value"}
    result = _parse_claude_response(f"  \n{json.dumps(data)}\n  ")
    assert result == data


def test_parse_claude_response_invalid_json_raises():
    """_parse_claude_response should raise JSONDecodeError on invalid JSON."""
    import json as _json
    with pytest.raises(_json.JSONDecodeError):
        _parse_claude_response("not valid json {{")


@pytest.mark.asyncio
async def test_verify_medicine_markdown_wrapped_response(verifier):
    """verify_medicine should parse Claude JSON wrapped in markdown code fence."""
    mock_response_data = {
        "verified": True,
        "confidence_score": 0.99,
        "notes": "Looks good.",
        "normalized_expiry": "2026-04-26",
    }
    wrapped = f"```json\n{json.dumps(mock_response_data)}\n```"
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(wrapped)
        )
        mock_get_client.return_value = mock_client

        result = await verifier.verify_medicine("PARALEN 500", "2026-04-26")

    assert result["verified"] is True
    assert result["confidence_score"] == pytest.approx(0.99)


@pytest.mark.asyncio
async def test_extract_label_info_markdown_wrapped_response(verifier):
    """extract_label_info should parse Claude JSON wrapped in markdown code fence."""
    mock_response_data = {
        "medicine_name": "PARALEN 500",
        "description": "500 mg tablets / paracetamol",
        "confidence": {"medicine_name": 0.99, "description": 0.99},
    }
    wrapped = f"```json\n{json.dumps(mock_response_data)}\n```"
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(wrapped)
        )
        mock_get_client.return_value = mock_client

        result = await verifier.extract_label_info(b"fake_bytes")

    assert result["medicine_name"] == "PARALEN 500"
    assert result["confidence"]["medicine_name"] == pytest.approx(0.99)


@pytest.mark.asyncio
async def test_extract_from_image_markdown_wrapped_response(verifier):
    """extract_from_image should parse Claude JSON wrapped in markdown code fence."""
    mock_response_data = {
        "medicine_name": None,
        "expiry_date": "2028-04-30",
        "description": None,
        "barcode": None,
        "confidence": {"medicine_name": 0.0, "expiry_date": 0.95, "description": 0.0},
        "raw_expiry_text": "04 2028",
    }
    wrapped = f"```json\n{json.dumps(mock_response_data)}\n```"
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(wrapped)
        )
        mock_get_client.return_value = mock_client

        result = await verifier.extract_from_image(b"fake_bytes")

    assert result["expiry_date"] == "2028-04-30"
    assert result["confidence"]["expiry_date"] == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_generate_leaflet_markdown_wrapped_response(verifier):
    """generate_leaflet should parse Claude JSON wrapped in markdown code fence."""
    mock_response_data = {
        "pouzitie": "Úľava od bolesti a horúčky.",
        "davkovanie": "500-1000 mg každých 4-6 hodín.",
        "vedlajsie_ucinky": "Vzácne: nausea.",
        "varovania": "Neprekonať 4000 mg denne.",
        "skladovanie": "Chladné, suché miesto.",
        "interakcie": None,
    }
    wrapped = f"```json\n{json.dumps(mock_response_data)}\n```"
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(wrapped)
        )
        mock_get_client.return_value = mock_client

        result = await verifier.generate_leaflet("PARALEN 500")

    assert result["pouzitie"] == "Úľava od bolesti a horúčky."
    assert "error" not in result


# ── _retry_with_backoff tests ─────────────────────────────────────────────────


def _make_overload_error(status_code: int):
    """Create an exception that mimics an Anthropic API overload/rate-limit error."""
    err = Exception(f"Error code: {status_code}")
    err.status_code = status_code
    return err


@pytest.mark.asyncio
async def test_retry_with_backoff_succeeds_on_first_attempt():
    """_retry_with_backoff should return immediately when the first call succeeds."""
    async def _coro():
        return "ok"

    result = await _retry_with_backoff(_coro)
    assert result == "ok"


@pytest.mark.asyncio
async def test_retry_with_backoff_retries_on_529(monkeypatch):
    """_retry_with_backoff should retry when status_code 529 is raised."""
    call_count = 0

    async def _coro():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise _make_overload_error(529)
        return "success"

    monkeypatch.setattr(
        "custom_components.medicine_count_expiry.ai.claude_verifier.asyncio.sleep",
        AsyncMock(),
    )

    result = await _retry_with_backoff(_coro, max_retries=3, base_delay=0.0)
    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_with_backoff_retries_on_429(monkeypatch):
    """_retry_with_backoff should retry when status_code 429 is raised."""
    call_count = 0

    async def _coro():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_overload_error(429)
        return "success"

    monkeypatch.setattr(
        "custom_components.medicine_count_expiry.ai.claude_verifier.asyncio.sleep",
        AsyncMock(),
    )

    result = await _retry_with_backoff(_coro, max_retries=3, base_delay=0.0)
    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_with_backoff_raises_immediately_on_other_errors():
    """_retry_with_backoff should not retry on errors other than 429/529."""
    call_count = 0

    async def _coro():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("unexpected error")

    with pytest.raises(RuntimeError, match="unexpected error"):
        await _retry_with_backoff(_coro, max_retries=3)

    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_with_backoff_exhausts_retries_and_raises(monkeypatch):
    """_retry_with_backoff should raise the last exception after all retries fail."""
    call_count = 0

    async def _coro():
        nonlocal call_count
        call_count += 1
        raise _make_overload_error(529)

    monkeypatch.setattr(
        "custom_components.medicine_count_expiry.ai.claude_verifier.asyncio.sleep",
        AsyncMock(),
    )

    with pytest.raises(Exception) as exc_info:
        await _retry_with_backoff(_coro, max_retries=3, base_delay=0.0)

    assert call_count == 3
    assert exc_info.value.status_code == 529


@pytest.mark.asyncio
async def test_extract_label_info_retries_on_529(verifier, monkeypatch):
    """extract_label_info should retry automatically on a 529 overloaded error."""
    mock_response_data = {
        "medicine_name": "Aspirin 100mg",
        "description": "100mg tablets",
        "confidence": {"medicine_name": 0.9, "description": 0.8},
    }
    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_overload_error(529)
        return _mock_anthropic_response(json.dumps(mock_response_data))

    monkeypatch.setattr(
        "custom_components.medicine_count_expiry.ai.claude_verifier.asyncio.sleep",
        AsyncMock(),
    )

    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        result = await verifier.extract_label_info(b"fake_bytes")

    assert call_count == 2
    assert result["medicine_name"] == "Aspirin 100mg"


@pytest.mark.asyncio
async def test_extract_from_image_retries_on_529(verifier, monkeypatch):
    """extract_from_image should retry automatically on a 529 overloaded error."""
    mock_response_data = {
        "medicine_name": "Ibuprofen 200mg",
        "expiry_date": "2027-06-30",
        "description": "200mg tablets",
        "confidence": {"medicine_name": 0.9, "expiry_date": 0.85, "description": 0.8},
    }
    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_overload_error(529)
        return _mock_anthropic_response(json.dumps(mock_response_data))

    monkeypatch.setattr(
        "custom_components.medicine_count_expiry.ai.claude_verifier.asyncio.sleep",
        AsyncMock(),
    )

    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        result = await verifier.extract_from_image(b"fake_bytes")

    assert call_count == 2
    assert result["medicine_name"] == "Ibuprofen 200mg"


@pytest.mark.asyncio
async def test_generate_leaflet_retries_on_529(verifier, monkeypatch):
    """generate_leaflet should retry automatically on a 529 overloaded error."""
    mock_response_data = {
        "pouzitie": "Úľava od bolesti.",
        "davkovanie": "500 mg každých 6 hodín.",
        "vedlajsie_ucinky": "Nausea.",
        "varovania": "Neprekonať dennú dávku.",
        "skladovanie": "Chladné miesto.",
        "interakcie": None,
    }
    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_overload_error(529)
        return _mock_anthropic_response(json.dumps(mock_response_data))

    monkeypatch.setattr(
        "custom_components.medicine_count_expiry.ai.claude_verifier.asyncio.sleep",
        AsyncMock(),
    )

    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        result = await verifier.generate_leaflet("Paracetamol 500mg")

    assert call_count == 2
    assert result["pouzitie"] == "Úľava od bolesti."
    assert "error" not in result


@pytest.mark.asyncio
async def test_generate_leaflet_with_dosing_table(verifier):
    """generate_leaflet should support structured table format for davkovanie."""
    mock_response_data = {
        "pouzitie": "Liek na zníženie horúčky a bolesť.",
        "davkovanie": {
            "type": "table",
            "headers": ["Vek", "Dávka", "Max. denná dávka"],
            "rows": [
                ["3-6 mes", "72 mg", "360 mg"],
                ["6-12 mes", "120 mg", "540 mg"],
                ["1-2 roky", "144 mg", "660 mg"],
            ],
        },
        "vedlajsie_ucinky": "Vzácne: nausea.",
        "varovania": "Neprekonať maximálnu dennú dávku.",
        "skladovanie": "Chladné, suché miesto.",
        "interakcie": None,
    }
    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(json.dumps(mock_response_data))
        )
        mock_get_client.return_value = mock_client

        result = await verifier.generate_leaflet("Paralen 200 sirup")

    assert result["pouzitie"] is not None
    assert isinstance(result["davkovanie"], dict)
    assert result["davkovanie"]["type"] == "table"
    assert result["davkovanie"]["headers"] == ["Vek", "Dávka", "Max. denná dávka"]
    assert len(result["davkovanie"]["rows"]) == 3
    assert result["davkovanie"]["rows"][0] == ["3-6 mes", "72 mg", "360 mg"]
    assert "error" not in result


@pytest.mark.asyncio
async def test_verify_medicine_retries_on_529(verifier, monkeypatch):
    """verify_medicine should retry automatically on a 529 overloaded error."""
    mock_response_data = {
        "verified": True,
        "confidence_score": 0.95,
        "notes": "All valid.",
        "normalized_expiry": "2026-12-31",
    }
    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_overload_error(529)
        return _mock_anthropic_response(json.dumps(mock_response_data))

    monkeypatch.setattr(
        "custom_components.medicine_count_expiry.ai.claude_verifier.asyncio.sleep",
        AsyncMock(),
    )

    with patch.object(verifier, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create = mock_create
        mock_get_client.return_value = mock_client

        result = await verifier.verify_medicine("Aspirin 100mg", "2026-12-31")

    assert call_count == 2
    assert result["verified"] is True
