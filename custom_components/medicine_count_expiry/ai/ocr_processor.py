"""OCR processor for medicine label scanning."""
from __future__ import annotations

import calendar
import logging
import re
from datetime import datetime
from typing import Optional

_LOGGER = logging.getLogger(__name__)

# Common expiry date patterns: (regex, strptime_format)
EXPIRY_PATTERNS = [
    # EXP-prefixed patterns first (higher specificity)
    (r"(?:exp(?:iry)?\.?\s*:?\s*)(0[1-9]|1[0-2])[/\-](20\d{2})", "%m/%Y"),
    (r"(?:exp(?:iry)?\.?\s*:?\s*)(0[1-9]|1[0-2])[/\-](\d{2})", "%m/%y"),
    # YYYY-MM-DD
    (r"\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b", "%Y-%m-%d"),
    # DD/MM/YYYY
    (r"\b(0[1-9]|[12]\d|3[01])/(0[1-9]|1[0-2])/(20\d{2})\b", "%d/%m/%Y"),
    # MM/YYYY or MM-YYYY
    (r"\b(0[1-9]|1[0-2])[/\-](20\d{2})\b", "%m/%Y"),
    # MM/YY or MM-YY
    (r"\b(0[1-9]|1[0-2])[/\-](\d{2})\b", "%m/%y"),
]


class OCRProcessor:
    """Processes OCR text to extract medicine information."""

    def extract_expiry_date(self, text: str) -> Optional[str]:
        """Extract and normalize expiry date from OCR text."""
        for pattern, date_format in EXPIRY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_date = match.group(0)
                # Remove any prefix like "EXP:"
                raw_date = re.sub(
                    r"(?:exp(?:iry)?\.?\s*:?\s*)", "", raw_date, flags=re.IGNORECASE
                ).strip()
                # Normalize separator to '/'
                raw_date = raw_date.replace("-", "/")
                fmt = date_format.replace("-", "/")
                try:
                    parsed = datetime.strptime(raw_date, fmt)
                    # For MM/YY or MM/YYYY (no day), set day to last day of month
                    if "%d" not in fmt:
                        last_day = calendar.monthrange(parsed.year, parsed.month)[1]
                        parsed = parsed.replace(day=last_day)
                    return parsed.strftime("%Y-%m-%d")
                except ValueError:
                    continue
        return None

    def extract_medicine_name(self, text: str) -> Optional[str]:
        """Attempt to extract medicine name from OCR text."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return None
        # Usually the first prominent line is the medicine name.
        # Skip lines that look like pure numbers, barcodes, or very short tokens.
        for line in lines:
            if len(line) > 3 and not re.match(r"^[\d\s\W]+$", line):
                return line
        return lines[0] if lines else None

    def process_ocr_text(self, text: str) -> dict:
        """Process raw OCR text and extract medicine information."""
        return {
            "medicine_name": self.extract_medicine_name(text),
            "expiry_date": self.extract_expiry_date(text),
            "description": self._extract_description(text),
            "raw_text": text,
        }

    def _extract_description(self, text: str) -> str:
        """Extract description/dosage information from OCR text."""
        dosage_patterns = [
            r"\d+\s*(?:mg|ml|mcg|g|IU|units?)\b",
            r"(?:tablet|capsule|syrup|injection|cream|ointment|drops?|solution)\b",
        ]
        found = []
        for pattern in dosage_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            found.extend(matches)
        # Deduplicate while preserving order
        return ", ".join(dict.fromkeys(found)) if found else ""
