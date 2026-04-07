"""Search engine for medicine inventory."""
from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

from ..storage.database import MedicineDatabase
from ..storage.models import Medicine

_LOGGER = logging.getLogger(__name__)


class MedicineSearchEngine:
    """Provides search and filter functionality for medicines."""

    def __init__(self, database: MedicineDatabase, warning_days: int = 30) -> None:
        """Initialize the search engine.

        Args:
            database: The backing database instance.
            warning_days: Days ahead of expiry considered "expiring soon".
        """
        self._db = database
        self._warning_days = warning_days

    def search(
        self,
        name: Optional[str] = None,
        location: Optional[str] = None,
        expiry_before: Optional[str] = None,
        expiry_after: Optional[str] = None,
        ai_verified: Optional[bool] = None,
        status: Optional[str] = None,
    ) -> List[Medicine]:
        """Search medicines with multiple criteria."""
        results = self._db.search_medicines(
            name=name,
            location=location,
            expiry_before=expiry_before,
            expiry_after=expiry_after,
            ai_verified=ai_verified,
        )

        if status:
            results = [m for m in results if m.get_status(self._warning_days) == status]

        return results

    def get_expiring_soon(self, days: Optional[int] = None) -> List[Medicine]:
        """Get medicines expiring within the given number of days.

        Defaults to the configured ``warning_days`` if *days* is not specified.
        """
        return self._db.get_expiring_medicines(days if days is not None else self._warning_days)

    def get_expired(self) -> List[Medicine]:
        """Get all expired medicines."""
        return self._db.get_expired_medicines()

    def get_all_expired(self) -> List[Medicine]:
        """Get all medicines whose computed status is 'expired' or 'opened_too_long'.

        Unlike :meth:`get_expired`, this uses :meth:`~Medicine.get_status` so it
        correctly includes medicines that have been open past their post-opening
        validity period (status ``opened_too_long``), not just manufacturing-expired
        ones found by the SQL date query.
        """
        return [
            m for m in self._db.get_all_medicines()
            if m.get_status(self._warning_days) in ("expired", "opened_too_long")
        ]

    def get_all_expiring_soon(self) -> List[Medicine]:
        """Get all medicines whose computed status is 'expiring_soon'.

        Unlike :meth:`get_expiring_soon`, this uses :meth:`~Medicine.get_status` so it
        correctly includes medicines nearing the end of their post-opening validity
        period, not only those approaching their manufacturing expiry date.
        """
        return [
            m for m in self._db.get_all_medicines()
            if m.get_status(self._warning_days) == "expiring_soon"
        ]

    def get_by_location(self, location: str) -> List[Medicine]:
        """Get all medicines at a specific location."""
        return self._db.search_medicines(location=location)

    def get_all(self) -> List[Medicine]:
        """Get all medicines sorted by expiry date."""
        return self._db.get_all_medicines()

    def get_summary(self) -> dict:
        """Get a summary of the medicine inventory."""
        all_medicines = self._db.get_all_medicines()
        expired_manufacturing = 0
        expired_opened_too_long = 0
        expiring_soon_count = 0
        good_count = 0

        for m in all_medicines:
            status = m.get_status(self._warning_days)
            if status == "expired":
                expired_manufacturing += 1
            elif status == "opened_too_long":
                expired_opened_too_long += 1
            elif status == "expiring_soon":
                expiring_soon_count += 1
            else:
                good_count += 1

        expired_total = expired_manufacturing + expired_opened_too_long

        return {
            "total": len(all_medicines),
            "expired": expired_total,
            "expired_manufacturing": expired_manufacturing,
            "expired_opened_too_long": expired_opened_too_long,
            "expiring_soon": expiring_soon_count,
            "good": good_count,
            "locations": sorted({m.location for m in all_medicines}),
        }
