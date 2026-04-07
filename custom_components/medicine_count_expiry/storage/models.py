"""Database models for Medicine Count & Expiry integration."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())


@dataclass
class Medicine:
    """Represents a medicine entry."""

    medicine_name: str
    expiry_date: str  # ISO format: YYYY-MM-DD
    medicine_id: str = field(default_factory=generate_id)
    description: str = ""
    quantity: int = 1
    location: str = "unknown"
    image_url: str = ""
    ai_verified: bool = False
    confidence_score: float = 0.0
    added_date: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_date: str = field(default_factory=lambda: datetime.now().isoformat())
    ai_leaflet: Optional[dict] = None
    ai_leaflet_generated_at: Optional[str] = None
    ai_extraction_source: Optional[str] = None
    ai_extraction_timestamp: Optional[str] = None
    date_opened: Optional[str] = None  # ISO format: YYYY-MM-DD
    days_valid_after_opening: Optional[int] = None  # Number of days valid after opening
    default_location: Optional[str] = None  # Location stored when medicine was first added
    location_changed_by_user: bool = False  # True when user explicitly changed location

    def __post_init__(self) -> None:
        """Set default_location from location if not explicitly provided."""
        if self.default_location is None:
            self.default_location = self.location

    @property
    def open_expiry_date(self) -> Optional[str]:
        """Return the computed open expiry date (public accessor)."""
        return self._compute_open_expiry_date()

    def _compute_open_expiry_date(self) -> Optional[str]:
        """Compute open expiry date from date_opened + days_valid_after_opening."""
        if self.date_opened and self.days_valid_after_opening is not None:
            try:
                open_date = date.fromisoformat(self.date_opened)
                open_expiry = open_date + timedelta(days=int(self.days_valid_after_opening))
                return open_expiry.isoformat()
            except (ValueError, TypeError):
                pass
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine_name,
            "expiry_date": self.expiry_date,
            "description": self.description,
            "quantity": self.quantity,
            "location": self.location,
            "image_url": self.image_url,
            "ai_verified": self.ai_verified,
            "confidence_score": self.confidence_score,
            "added_date": self.added_date,
            "updated_date": self.updated_date,
            "status": self.get_status(),
            "ai_leaflet": self.ai_leaflet,
            "ai_leaflet_generated_at": self.ai_leaflet_generated_at,
            "ai_extraction_source": self.ai_extraction_source,
            "ai_extraction_timestamp": self.ai_extraction_timestamp,
            "date_opened": self.date_opened,
            "days_valid_after_opening": self.days_valid_after_opening,
            "open_expiry_date": self._compute_open_expiry_date(),
            "default_location": self.default_location,
            "location_changed_by_user": self.location_changed_by_user,
        }

    def get_status(self, warning_days: Optional[int] = None) -> str:
        """Get the expiry status of this medicine.

        Priority:
        1. Check open expiry (if date_opened and days_valid_after_opening are set)
        2. Check manufacturing expiry

        Args:
            warning_days: Number of days ahead of expiry to consider "expiring soon".
                          Defaults to DEFAULT_EXPIRY_WARNING_DAYS if not provided.
        """
        from ..const import DEFAULT_EXPIRY_WARNING_DAYS, STATUS_EXPIRED, STATUS_EXPIRING_SOON, STATUS_GOOD, STATUS_OPENED_TOO_LONG, STATUS_UNKNOWN
        if warning_days is None:
            warning_days = DEFAULT_EXPIRY_WARNING_DAYS
        today = date.today()

        # Priority 1: Check open expiry
        if self.date_opened and self.days_valid_after_opening is not None:
            try:
                open_date = date.fromisoformat(self.date_opened)
                open_expiry = open_date + timedelta(days=int(self.days_valid_after_opening))
                open_delta = (open_expiry - today).days
                if open_delta < 0:
                    return STATUS_OPENED_TOO_LONG
                if open_delta <= 3:
                    return STATUS_EXPIRING_SOON
            except (ValueError, TypeError):
                pass

        # Priority 2: Check manufacturing expiry
        try:
            expiry = date.fromisoformat(self.expiry_date)
            delta = (expiry - today).days
            if delta < 0:
                return STATUS_EXPIRED
            elif delta <= warning_days:
                return STATUS_EXPIRING_SOON
            else:
                return STATUS_GOOD
        except (ValueError, TypeError):
            return STATUS_UNKNOWN

    @classmethod
    def from_dict(cls, data: dict) -> "Medicine":
        """Create Medicine from dictionary."""
        ai_leaflet = data.get("ai_leaflet")
        # ai_leaflet may arrive as a JSON string when read from SQLite
        if isinstance(ai_leaflet, str):
            try:
                ai_leaflet = json.loads(ai_leaflet)
            except (ValueError, TypeError):
                ai_leaflet = None
        days_valid = data.get("days_valid_after_opening")
        if days_valid is not None:
            try:
                days_valid = int(days_valid)
            except (ValueError, TypeError):
                days_valid = None
        return cls(
            medicine_id=data.get("medicine_id", generate_id()),
            medicine_name=data["medicine_name"],
            expiry_date=data["expiry_date"],
            description=data.get("description", ""),
            quantity=data.get("quantity", 1),
            location=data.get("location", "unknown"),
            image_url=data.get("image_url", ""),
            ai_verified=data.get("ai_verified", False),
            confidence_score=data.get("confidence_score", 0.0),
            added_date=data.get("added_date", datetime.now().isoformat()),
            updated_date=data.get("updated_date", datetime.now().isoformat()),
            ai_leaflet=ai_leaflet,
            ai_leaflet_generated_at=data.get("ai_leaflet_generated_at"),
            ai_extraction_source=data.get("ai_extraction_source"),
            ai_extraction_timestamp=data.get("ai_extraction_timestamp"),
            date_opened=data.get("date_opened"),
            days_valid_after_opening=days_valid,
            default_location=data.get("default_location"),
            location_changed_by_user=bool(data.get("location_changed_by_user", False)),
        )
