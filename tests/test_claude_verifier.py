"""Tests for ClaudeVerifier (with mocked Anthropic client)."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.medicine_count_expiry.ai.claude_verifier import ClaudeVerifier


@pytest.fixture
def verifier():
    """Return a ClaudeVerifier with a fake API key."""
    return ClaudeVerifier(api_key="test-key-123", model="claude-3-5-sonnet-20241022")


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


def test_get_client_missing_anthropic(verifier):
    """_get_client should raise ImportError when anthropic is not installed."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("No module named 'anthropic'")
        return real_import(name, *args, **kwargs)

    verifier._client = None  # Reset cached client
    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(ImportError, match="anthropic package is required"):
            verifier._get_client()


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
