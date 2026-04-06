"""Database models for Medicine Count & Expiry integration."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
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
        }

    def get_status(self, warning_days: int = 30) -> str:
        """Get the expiry status of this medicine.

        Args:
            warning_days: Number of days ahead of expiry to consider "expiring soon".
        """
        from ..const import STATUS_EXPIRED, STATUS_EXPIRING_SOON, STATUS_GOOD, STATUS_UNKNOWN
        try:
            expiry = date.fromisoformat(self.expiry_date)
            today = date.today()
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
        )
