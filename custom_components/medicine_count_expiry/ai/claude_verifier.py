"""Claude AI verification for medicine data."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import random
import re
import urllib.parse
from typing import Any, Optional

from ..const import CLAUDE_BASE_RETRY_DELAY, CLAUDE_MAX_RETRIES, CLAUDE_MAX_RETRY_DELAY

_LOGGER = logging.getLogger(__name__)


async def _retry_with_backoff(
    coro,
    max_retries: int = CLAUDE_MAX_RETRIES,
    base_delay: float = CLAUDE_BASE_RETRY_DELAY,
    max_delay: float = CLAUDE_MAX_RETRY_DELAY,
) -> Any:
    """Retry async operation with exponential backoff.

    Args:
        coro: Callable returning an async coroutine to retry
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Result of successful coroutine execution

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await coro()
        except Exception as e:
            last_exception = e

            error_code = getattr(e, "status_code", None)

            # Only retry on 429 (rate limit) and 529 (overloaded)
            if error_code not in (429, 529):
                raise

            if attempt < max_retries - 1:
                delay = min(
                    base_delay * (2 ** attempt) + random.uniform(0, 1),
                    max_delay,
                )
                _LOGGER.warning(
                    "Claude API overloaded (error %s). Retrying in %.1f seconds... (attempt %d/%d)",
                    error_code,
                    delay,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)
            else:
                _LOGGER.error(
                    "Claude API failed after %d attempts. Last error: %s",
                    max_retries,
                    last_exception,
                )

    # last_exception is always set here: the loop only exits without returning
    # when all attempts raised a retriable error.
    assert last_exception is not None
    raise last_exception


def _get_anthropic():
    """Lazily import the anthropic package to avoid blocking I/O at module load time."""
    try:
        import anthropic  # noqa: PLC0415
        return anthropic
    except ImportError:
        raise ImportError(
            "anthropic package is required. Install it with: pip install anthropic"
        )


def _parse_claude_response(response_text: str) -> dict:
    """Parse Claude response, handling markdown code fence wrapper."""
    response_text = response_text.strip()

    # Remove markdown code fence if present (e.g. ```json ... ```)
    if response_text.startswith("```"):
        parts = response_text.split("```")
        if len(parts) >= 2:
            response_text = parts[1]
            # Remove optional language tag (e.g. "json", "JSON") before the first newline
            newline_pos = response_text.find("\n")
            if newline_pos != -1:
                possible_tag = response_text[:newline_pos].strip()
                if possible_tag and possible_tag.isalpha():
                    response_text = response_text[newline_pos:].lstrip()
            elif response_text.lower().startswith("json"):
                response_text = response_text[4:].lstrip()

    return json.loads(response_text.strip())

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
    "davkovanie": <viď nižšie>,
    "vedlajsie_ucinky": "Najčastejšie vedľajšie účinky (1-2 vety)",
    "varovania": "Hlavné varovania a kontraindikácie (1-2 vety)",
    "skladovanie": "Podmienky skladovania (1 veta)",
    "interakcie": "Dôležité liekové interakcie alebo null ak nie sú relevantné"
}}

Pre pole "davkovanie":
- Ak liek má dávkovanie závislé od veku alebo hmotnosti (napr. sirupy, kvapky, pediatrické lieky), vráť štruktúrovanú tabuľku:
  {{"type": "table", "headers": ["Vek", "Dávka", "Max. denná dávka"], "rows": [["0-3 mes", "X mg", "Y mg"], ...]}}
  Hlavičky tabuľky prispôsob podľa relevantných stĺpcov (môžu byť napr. Vek, Hmotnosť, Dávka, Max. denná dávka atď.)
- Inak vráť bežný text (1-2 vety) ako reťazec.

Odpovedz IBA s JSON objektom, bez ďalšieho textu."""

EXTRACT_LABEL_PROMPT = """You are a pharmacy assistant. Analyze this medicine label image and extract the medicine name and description ONLY.

Do NOT extract the expiry date or any date information.

Please respond with a JSON object containing:
{
    "medicine_name": "extracted product name or null",
    "description": "dosage form and strength or null",
    "confidence": {
        "medicine_name": 0.0-1.0,
        "description": 0.0-1.0
    }
}

The medicine_name should be the product name as printed on the label (e.g. "Aspirin Plus", "Paracetamol 500mg").
The description should be the dosage form or strength (e.g. "500mg tablets", "200mg capsules", "10ml oral solution").

Respond ONLY with the JSON object, no other text."""

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

EXTRACT_OPEN_DAYS_PROMPT = """You are a pharmacy assistant. Your task is to determine how many days a medicine is valid after opening.

Medicine name: {medicine_name}

Based on your knowledge of this medicine's package leaflet and typical storage requirements, determine how many days it remains safe to use after being opened.

Common patterns:
- Eye drops: 28 days after opening
- Oral solutions/syrups: 14-30 days after opening
- Creams/ointments: 3-12 months after opening
- Nasal sprays: 28 days after opening

Please respond with a JSON object:
{{
    "days_valid_after_opening": <integer or null>,
    "notes": "brief explanation or source of this information"
}}

If you cannot determine this with reasonable confidence, return null for days_valid_after_opening.
Respond ONLY with the JSON object, no other text."""


_DRMAX_SEARCH_URL = "https://www.drmax.sk/search/?string={}"
_DRMAX_EXCLUDED_PATHS = r"(?!search|cart|account|login|register|category|blog|kontakt|o-nas)"
_DRMAX_PRODUCT_PATTERNS = [
    # Structured data / JSON-LD product URLs
    r'"url"\s*:\s*"(https://www\.drmax\.sk/[^"]+)"',
    # Anchor hrefs pointing to product detail pages (avoid search/category/utility pages)
    rf'href="(https://www\.drmax\.sk/{_DRMAX_EXCLUDED_PATHS}[^"]+\.html[^"]*)"',
    rf'href="(https://www\.drmax\.sk/{_DRMAX_EXCLUDED_PATHS}[a-z0-9][^"]{{10,}})"',
]


async def search_drmax_url(session: Any, medicine_name: str) -> Optional[str]:
    """Search DrMax.sk pharmacy for a medicine and return the best matching URL.

    Fetches the DrMax.sk search results page and tries to extract the first
    product URL.  Falls back to the search URL if no product page can be found
    or if the request fails.

    Args:
        session: An aiohttp ClientSession (e.g. from async_get_clientsession).
        medicine_name: The name of the medicine to search for.

    Returns:
        A direct product URL string, or the search URL as a fallback.
    """
    encoded = urllib.parse.quote(medicine_name)
    search_url = _DRMAX_SEARCH_URL.format(encoded)

    try:
        import aiohttp as _aiohttp  # noqa: PLC0415

        timeout = _aiohttp.ClientTimeout(total=10)
        async with session.get(
            search_url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HomeAssistant/1.0)"},
            allow_redirects=True,
        ) as resp:
            if resp.status != 200:
                _LOGGER.debug(
                    "DrMax search returned HTTP %s for %s, using search URL",
                    resp.status,
                    medicine_name,
                )
                return search_url

            html = await resp.text()

            for pattern in _DRMAX_PRODUCT_PATTERNS:
                matches = re.findall(pattern, html)
                if matches:
                    product_url = matches[0]
                    _LOGGER.debug(
                        "DrMax product URL for %s: %s", medicine_name, product_url
                    )
                    return product_url

            _LOGGER.debug(
                "No product URL found on DrMax for %s, using search URL", medicine_name
            )
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning(
            "Failed to search DrMax.sk for medicine '%s': %s", medicine_name, exc
        )

    return search_url


class ClaudeVerifier:
    """Verifies medicine data using Claude AI."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        """Initialize the Claude verifier."""
        self._api_key = api_key
        self._model = model
        anthropic = _get_anthropic()
        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    def _get_client(self):
        """Return the already-initialized async Anthropic client."""
        return self._client

    async def verify_medicine(
        self,
        medicine_name: str,
        expiry_date: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Verify medicine data using Claude."""
        response_text = ""
        try:
            client = self._get_client()
            prompt = VERIFY_MEDICINE_PROMPT.format(
                medicine_name=medicine_name,
                expiry_date=expiry_date,
                description=description,
            )

            async def _call():
                return await client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )

            message = await _retry_with_backoff(_call)
            response_text = message.content[0].text.strip()
            _LOGGER.debug("Claude verify raw response: %s", response_text[:200])
            result = _parse_claude_response(response_text)
            _LOGGER.debug("Claude verification result for %s: %s", medicine_name, result)
            return result
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse Claude response: %s. Raw: %s", e, response_text[:500])
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
        response_text = ""
        try:
            client = self._get_client()
            prompt = GENERATE_LEAFLET_PROMPT.format(medicine_name=medicine_name)

            async def _call():
                return await client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )

            message = await _retry_with_backoff(_call)
            response_text = message.content[0].text.strip()
            _LOGGER.debug("Claude leaflet raw response: %s", response_text[:200])
            result = _parse_claude_response(response_text)
            _LOGGER.debug("Claude leaflet result for %s: %s", medicine_name, result)
            return result
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse Claude leaflet response: %s. Raw: %s", e, response_text[:500])
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

    async def extract_days_valid_after_opening(self, medicine_name: str) -> dict[str, Any]:
        """Extract days valid after opening for a medicine using Claude.

        Args:
            medicine_name: The name of the medicine.

        Returns:
            dict with 'days_valid_after_opening' (int or None) and 'notes'.
        """
        response_text = ""
        try:
            client = self._get_client()
            prompt = EXTRACT_OPEN_DAYS_PROMPT.format(medicine_name=medicine_name)

            async def _call():
                return await client.messages.create(
                    model=self._model,
                    max_tokens=256,
                    messages=[{"role": "user", "content": prompt}],
                )

            message = await _retry_with_backoff(_call)
            response_text = message.content[0].text.strip()
            _LOGGER.debug("Claude open days raw response: %s", response_text[:200])
            result = _parse_claude_response(response_text)
            _LOGGER.debug("Claude open days result for %s: %s", medicine_name, result)
            days = result.get("days_valid_after_opening")
            if days is not None:
                try:
                    days = int(days)
                except (ValueError, TypeError):
                    days = None
            return {
                "days_valid_after_opening": days,
                "notes": result.get("notes", ""),
            }
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse Claude open days response: %s. Raw: %s", e, response_text[:500])
            return {"days_valid_after_opening": None, "notes": f"Failed to parse AI response: {e}"}
        except Exception as e:
            _LOGGER.error("Claude open days extraction error: %s", e)
            return {"days_valid_after_opening": None, "notes": f"Extraction error: {e}"}

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

    async def extract_label_info(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        _retry: bool = True,
    ) -> dict[str, Any]:
        """Extract only medicine name and description from a label image using Claude vision."""
        response_text = ""
        try:
            client = self._get_client()
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")

            async def _call():
                return await client.messages.create(
                    model=self._model,
                    max_tokens=512,
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
                                    "text": EXTRACT_LABEL_PROMPT,
                                },
                            ],
                        }
                    ],
                )

            message = await _retry_with_backoff(_call)
            response_text = message.content[0].text.strip()
            _LOGGER.debug("Claude label raw response: %s", response_text[:200])

            if not response_text:
                _LOGGER.error("Claude returned empty response for label extraction")
                if _retry:
                    _LOGGER.warning("Empty response from Claude, retrying label extraction...")
                    return await self.extract_label_info(image_data, media_type, _retry=False)
                return {
                    "medicine_name": None,
                    "description": None,
                    "confidence": {"medicine_name": 0.0, "description": 0.0},
                }

            result = _parse_claude_response(response_text)

            if not isinstance(result, dict) or not result.get("medicine_name"):
                if _retry:
                    _LOGGER.warning("Empty medicine_name from Claude, retrying label extraction...")
                    return await self.extract_label_info(image_data, media_type, _retry=False)

            _LOGGER.debug("Claude label extraction result: %s", result)
            return result
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse Claude label response: %s. Raw: %s", e, response_text[:500])
            return {
                "medicine_name": None,
                "description": None,
                "confidence": {"medicine_name": 0.0, "description": 0.0},
            }
        except Exception as e:
            _LOGGER.error("Claude label extraction error: %s", e)
            return {
                "medicine_name": None,
                "description": None,
                "confidence": {"medicine_name": 0.0, "description": 0.0},
            }

    async def extract_from_image(self, image_data: bytes, media_type: str = "image/jpeg") -> dict[str, Any]:
        """Extract medicine information from an image using Claude vision."""
        response_text = ""
        try:
            client = self._get_client()
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")

            async def _call():
                return await client.messages.create(
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

            message = await _retry_with_backoff(_call)
            response_text = message.content[0].text.strip()
            _LOGGER.debug("Claude image raw response: %s", response_text[:200])
            result = _parse_claude_response(response_text)
            _LOGGER.debug("Claude extraction result: %s", result)
            return result
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse Claude image response: %s. Raw: %s", e, response_text[:500])
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
