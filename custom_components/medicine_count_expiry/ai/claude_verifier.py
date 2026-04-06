"""Claude AI verification for medicine data."""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)

VERIFY_MEDICINE_PROMPT = """You are a pharmacy assistant helping verify medicine label data.

Analyze the following medicine information and provide verification:

Medicine Name: {medicine_name}
Expiry Date: {expiry_date}
Description: {description}

Please respond with a JSON object containing:
{{
    "verified": true/false,
    "medicine_name_valid": true/false,
    "expiry_date_valid": true/false,
    "description_valid": true/false,
    "confidence_score": 0.0-1.0,
    "notes": "any notes or warnings",
    "normalized_expiry": "YYYY-MM-DD format if valid, else null"
}}

Verify that:
1. The medicine name appears to be a real pharmaceutical product
2. The expiry date format is valid and the date is plausible
3. The description matches expected pharmaceutical terminology
4. Flag anything suspicious

Respond ONLY with the JSON object, no other text."""

GENERATE_LEAFLET_PROMPT = """Ty si pomocný asistent pre príbalové letáky liekov. Analyzuj názov tohto lieku a vytvor stručné zhrnutie príbalového letáka v slovenskom jazyku.

Názov lieku: {medicine_name}

Odpovedz VÝLUČNE vo formáte JSON s nasledujúcou štruktúrou (všetky hodnoty musia byť v slovenčine):
{{
    "pouzitie": "Krátky popis použitia lieku (1-2 vety)",
    "davkovanie": "Bežné dávkovanie pre dospelých (1-2 vety)",
    "vedlajsie_ucinky": "Najčastejšie vedľajšie účinky (1-2 vety)",
    "varovania": "Hlavné varovania a kontraindikácie (1-2 vety)",
    "skladovanie": "Podmienky skladovania (1 veta)",
    "interakcie": "Dôležité liekové interakcie alebo null ak nie sú relevantné"
}}

Odpovedz IBA s JSON objektom, bez ďalšieho textu."""

EXTRACT_FROM_IMAGE_PROMPT = """You are a pharmacy assistant. Analyze this medicine label image and extract information.

Please respond with a JSON object containing:
{
    "medicine_name": "extracted name or null",
    "expiry_date": "YYYY-MM-DD format or null",
    "description": "extracted description or null",
    "barcode": "barcode number if visible or null",
    "confidence": {
        "medicine_name": 0.0-1.0,
        "expiry_date": 0.0-1.0,
        "description": 0.0-1.0
    },
    "raw_expiry_text": "raw expiry text as found on label"
}

Extract as much information as possible. For expiry dates, common formats include:
- MM/YYYY, MM-YYYY
- MM/YY, MM-YY
- DD/MM/YYYY
- YYYY-MM-DD
Convert all dates to YYYY-MM-DD format.

Respond ONLY with the JSON object, no other text."""


class ClaudeVerifier:
    """Verifies medicine data using Claude AI."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022") -> None:
        """Initialize the Claude verifier."""
        self._api_key = api_key
        self._model = model
        self._client = None

    def _get_client(self):
        """Get or create the async Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
            except ImportError as err:
                raise ImportError(
                    "anthropic package is required. Install it with: pip install anthropic"
                ) from err
        return self._client

    async def verify_medicine(
        self,
        medicine_name: str,
        expiry_date: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Verify medicine data using Claude."""
        try:
            client = self._get_client()
            prompt = VERIFY_MEDICINE_PROMPT.format(
                medicine_name=medicine_name,
                expiry_date=expiry_date,
                description=description,
            )
            message = await client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = message.content[0].text.strip()
            result = json.loads(response_text)
            _LOGGER.debug("Claude verification result for %s: %s", medicine_name, result)
            return result
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse Claude response: %s", e)
            return {
                "verified": False,
                "confidence_score": 0.0,
                "notes": f"Failed to parse AI response: {e}",
            }
        except Exception as e:
            _LOGGER.error("Claude verification error: %s", e)
            return {
                "verified": False,
                "confidence_score": 0.0,
                "notes": f"Verification error: {e}",
            }

    async def generate_leaflet(self, medicine_name: str) -> dict[str, Any]:
        """Generate a Slovak package leaflet summary for a medicine using Claude."""
        try:
            client = self._get_client()
            prompt = GENERATE_LEAFLET_PROMPT.format(medicine_name=medicine_name)
            message = await client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = message.content[0].text.strip()
            result = json.loads(response_text)
            _LOGGER.debug("Claude leaflet result for %s: %s", medicine_name, result)
            return result
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse Claude leaflet response: %s", e)
            return {
                "pouzitie": None,
                "davkovanie": None,
                "vedlajsie_ucinky": None,
                "varovania": None,
                "skladovanie": None,
                "interakcie": None,
                "error": f"Failed to parse AI response: {e}",
            }
        except Exception as e:
            _LOGGER.error("Claude leaflet generation error: %s", e)
            return {
                "pouzitie": None,
                "davkovanie": None,
                "vedlajsie_ucinky": None,
                "varovania": None,
                "skladovanie": None,
                "interakcie": None,
                "error": f"Leaflet generation error: {e}",
            }

    async def extract_and_verify(self, image_data: bytes, media_type: str = "image/jpeg") -> dict[str, Any]:
        """Extract medicine info from an image AND verify the extracted data."""
        extraction = await self.extract_from_image(image_data, media_type)

        if extraction.get("medicine_name"):
            try:
                verification = await self.verify_medicine(
                    medicine_name=extraction["medicine_name"],
                    expiry_date=extraction.get("expiry_date") or "",
                    description=extraction.get("description") or "",
                )
            except Exception as e:
                _LOGGER.error("Verification step failed during extract_and_verify: %s", e)
                verification = {"verified": False, "confidence_score": 0.0, "notes": f"Verification error: {e}"}
            extraction["verification"] = verification
            extraction["verified"] = verification.get("verified", False)
            extraction["overall_confidence"] = verification.get("confidence_score", 0.0)

        return extraction

    async def extract_from_image(self, image_data: bytes, media_type: str = "image/jpeg") -> dict[str, Any]:
        """Extract medicine information from an image using Claude vision."""
        try:
            client = self._get_client()
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
            message = await client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": EXTRACT_FROM_IMAGE_PROMPT,
                            },
                        ],
                    }
                ],
            )
            response_text = message.content[0].text.strip()
            result = json.loads(response_text)
            _LOGGER.debug("Claude extraction result: %s", result)
            return result
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse Claude image response: %s", e)
            return {
                "medicine_name": None,
                "expiry_date": None,
                "description": None,
                "confidence": {"medicine_name": 0.0, "expiry_date": 0.0, "description": 0.0},
            }
        except Exception as e:
            _LOGGER.error("Claude image extraction error: %s", e)
            return {
                "medicine_name": None,
                "expiry_date": None,
                "description": None,
                "confidence": {"medicine_name": 0.0, "expiry_date": 0.0, "description": 0.0},
            }
