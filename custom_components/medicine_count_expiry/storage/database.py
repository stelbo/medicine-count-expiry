"""Database layer for Medicine Count & Expiry integration."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import List, Optional

from ..const import DB_FILE
from .models import Medicine

_LOGGER = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS medicines (
    medicine_id TEXT PRIMARY KEY,
    medicine_name TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    description TEXT DEFAULT '',
    quantity INTEGER DEFAULT 1,
    location TEXT DEFAULT 'unknown',
    image_url TEXT DEFAULT '',
    ai_verified INTEGER DEFAULT 0,
    confidence_score REAL DEFAULT 0.0,
    added_date TEXT NOT NULL,
    updated_date TEXT NOT NULL,
    ai_leaflet TEXT DEFAULT NULL,
    ai_leaflet_generated_at TEXT DEFAULT NULL,
    ai_extraction_source TEXT DEFAULT NULL,
    ai_extraction_timestamp TEXT DEFAULT NULL,
    date_opened TEXT DEFAULT NULL,
    days_valid_after_opening INTEGER DEFAULT NULL,
    default_location TEXT DEFAULT NULL,
    location_changed_by_user INTEGER DEFAULT 0,
    leaflet_url TEXT DEFAULT NULL
)
"""

CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_medicine_name ON medicines(medicine_name)",
    "CREATE INDEX IF NOT EXISTS idx_expiry_date ON medicines(expiry_date)",
    "CREATE INDEX IF NOT EXISTS idx_location ON medicines(location)",
]

# Migration statements to add new columns to existing databases
_MIGRATE_SQL = [
    "ALTER TABLE medicines ADD COLUMN ai_leaflet TEXT DEFAULT NULL",
    "ALTER TABLE medicines ADD COLUMN ai_leaflet_generated_at TEXT DEFAULT NULL",
    "ALTER TABLE medicines ADD COLUMN ai_extraction_source TEXT DEFAULT NULL",
    "ALTER TABLE medicines ADD COLUMN ai_extraction_timestamp TEXT DEFAULT NULL",
    "ALTER TABLE medicines ADD COLUMN date_opened TEXT DEFAULT NULL",
    "ALTER TABLE medicines ADD COLUMN days_valid_after_opening INTEGER DEFAULT NULL",
    "ALTER TABLE medicines ADD COLUMN default_location TEXT DEFAULT NULL",
    "ALTER TABLE medicines ADD COLUMN location_changed_by_user INTEGER DEFAULT 0",
    "ALTER TABLE medicines ADD COLUMN leaflet_url TEXT DEFAULT NULL",
]


class MedicineDatabase:
    """SQLite database for medicine storage."""

    def __init__(self, db_path: str) -> None:
        """Initialize the database."""
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database tables."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(CREATE_TABLE_SQL)
            for idx_sql in CREATE_INDEX_SQL:
                conn.execute(idx_sql)
            # Apply migrations (idempotent – ignored if column already exists)
            for sql in _MIGRATE_SQL:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    pass  # Column already exists
            conn.commit()
        _LOGGER.debug("Database initialized at %s", self._db_path)

    def _row_to_medicine(self, row: tuple) -> Medicine:
        """Convert a database row to a Medicine object."""
        ai_leaflet = None
        if len(row) > 11 and row[11] is not None:
            try:
                ai_leaflet = json.loads(row[11])
            except (ValueError, TypeError):
                ai_leaflet = None
        ai_leaflet_generated_at = row[12] if len(row) > 12 else None
        ai_extraction_source = row[13] if len(row) > 13 else None
        ai_extraction_timestamp = row[14] if len(row) > 14 else None
        date_opened = row[15] if len(row) > 15 else None
        days_valid_after_opening = row[16] if len(row) > 16 else None
        if days_valid_after_opening is not None:
            try:
                days_valid_after_opening = int(days_valid_after_opening)
            except (ValueError, TypeError):
                days_valid_after_opening = None
        default_location = row[17] if len(row) > 17 else None
        location_changed_by_user = bool(row[18]) if len(row) > 18 else False
        leaflet_url = row[19] if len(row) > 19 else None
        return Medicine(
            medicine_id=row[0],
            medicine_name=row[1],
            expiry_date=row[2],
            description=row[3],
            quantity=row[4],
            location=row[5],
            image_url=row[6],
            ai_verified=bool(row[7]),
            confidence_score=row[8],
            added_date=row[9],
            updated_date=row[10],
            ai_leaflet=ai_leaflet,
            ai_leaflet_generated_at=ai_leaflet_generated_at,
            ai_extraction_source=ai_extraction_source,
            ai_extraction_timestamp=ai_extraction_timestamp,
            date_opened=date_opened,
            days_valid_after_opening=days_valid_after_opening,
            default_location=default_location,
            location_changed_by_user=location_changed_by_user,
            leaflet_url=leaflet_url,
        )

    def add_medicine(self, medicine: Medicine) -> Medicine:
        """Add a new medicine to the database."""
        ai_leaflet_json = json.dumps(medicine.ai_leaflet) if medicine.ai_leaflet is not None else None
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO medicines
                   (medicine_id, medicine_name, expiry_date, description, quantity,
                    location, image_url, ai_verified, confidence_score, added_date, updated_date,
                    ai_leaflet, ai_leaflet_generated_at, ai_extraction_source, ai_extraction_timestamp,
                    date_opened, days_valid_after_opening,
                    default_location, location_changed_by_user, leaflet_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    medicine.medicine_id,
                    medicine.medicine_name,
                    medicine.expiry_date,
                    medicine.description,
                    medicine.quantity,
                    medicine.location,
                    medicine.image_url,
                    int(medicine.ai_verified),
                    medicine.confidence_score,
                    medicine.added_date,
                    medicine.updated_date,
                    ai_leaflet_json,
                    medicine.ai_leaflet_generated_at,
                    medicine.ai_extraction_source,
                    medicine.ai_extraction_timestamp,
                    medicine.date_opened,
                    medicine.days_valid_after_opening,
                    medicine.default_location,
                    int(medicine.location_changed_by_user),
                    medicine.leaflet_url,
                ),
            )
            conn.commit()
        _LOGGER.info("Added medicine: %s", medicine.medicine_name)
        return medicine

    def update_medicine(self, medicine: Medicine) -> Optional[Medicine]:
        """Update an existing medicine."""
        medicine.updated_date = datetime.now().isoformat()
        ai_leaflet_json = json.dumps(medicine.ai_leaflet) if medicine.ai_leaflet is not None else None
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                """UPDATE medicines SET
                   medicine_name=?, expiry_date=?, description=?, quantity=?,
                   location=?, image_url=?, ai_verified=?, confidence_score=?, updated_date=?,
                   ai_leaflet=?, ai_leaflet_generated_at=?,
                   ai_extraction_source=?, ai_extraction_timestamp=?,
                   date_opened=?, days_valid_after_opening=?,
                   default_location=?, location_changed_by_user=?,
                   leaflet_url=?
                   WHERE medicine_id=?""",
                (
                    medicine.medicine_name,
                    medicine.expiry_date,
                    medicine.description,
                    medicine.quantity,
                    medicine.location,
                    medicine.image_url,
                    int(medicine.ai_verified),
                    medicine.confidence_score,
                    medicine.updated_date,
                    ai_leaflet_json,
                    medicine.ai_leaflet_generated_at,
                    medicine.ai_extraction_source,
                    medicine.ai_extraction_timestamp,
                    medicine.date_opened,
                    medicine.days_valid_after_opening,
                    medicine.default_location,
                    int(medicine.location_changed_by_user),
                    medicine.leaflet_url,
                    medicine.medicine_id,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        _LOGGER.info("Updated medicine: %s", medicine.medicine_name)
        return medicine

    def save_leaflet(self, medicine_id: str, leaflet: dict, generated_at: str, source_url: Optional[str] = None) -> Optional[Medicine]:
        """Save a generated leaflet for a medicine and return the updated record."""
        ai_leaflet_json = json.dumps(leaflet)
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                """UPDATE medicines SET ai_leaflet=?, ai_leaflet_generated_at=?, leaflet_url=?
                   WHERE medicine_id=?""",
                (ai_leaflet_json, generated_at, source_url, medicine_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        _LOGGER.info("Saved leaflet for medicine ID: %s", medicine_id)
        return self.get_medicine(medicine_id)

    def delete_medicine(self, medicine_id: str) -> bool:
        """Delete a medicine by ID."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM medicines WHERE medicine_id=?", (medicine_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            _LOGGER.info("Deleted medicine ID: %s", medicine_id)
        return deleted

    def get_medicine(self, medicine_id: str) -> Optional[Medicine]:
        """Get a medicine by ID."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM medicines WHERE medicine_id=?", (medicine_id,)
            )
            row = cursor.fetchone()
        if row:
            return self._row_to_medicine(row)
        return None

    def get_all_medicines(self) -> List[Medicine]:
        """Get all medicines."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("SELECT * FROM medicines ORDER BY expiry_date ASC")
            rows = cursor.fetchall()
        return [self._row_to_medicine(row) for row in rows]

    def search_medicines(
        self,
        name: Optional[str] = None,
        location: Optional[str] = None,
        expiry_before: Optional[str] = None,
        expiry_after: Optional[str] = None,
        ai_verified: Optional[bool] = None,
    ) -> List[Medicine]:
        """Search medicines with filters."""
        query = "SELECT * FROM medicines WHERE 1=1"
        params = []

        if name:
            query += " AND LOWER(medicine_name) LIKE ?"
            params.append(f"%{name.lower()}%")

        if location:
            query += " AND LOWER(location) = ?"
            params.append(location.lower())

        if expiry_before:
            query += " AND expiry_date <= ?"
            params.append(expiry_before)

        if expiry_after:
            query += " AND expiry_date >= ?"
            params.append(expiry_after)

        if ai_verified is not None:
            query += " AND ai_verified = ?"
            params.append(int(ai_verified))

        query += " ORDER BY expiry_date ASC"

        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        return [self._row_to_medicine(row) for row in rows]

    def get_expiring_medicines(self, days: int) -> List[Medicine]:
        """Get medicines expiring within the given number of days (excluding today, which is expired)."""
        from datetime import date, timedelta
        today = date.today()
        tomorrow = today + timedelta(days=1)
        future = today + timedelta(days=days)
        return self.search_medicines(
            expiry_before=future.isoformat(),
            expiry_after=tomorrow.isoformat(),
        )

    def get_expired_medicines(self) -> List[Medicine]:
        """Get all expired medicines (including those expiring today)."""
        from datetime import date
        today = date.today().isoformat()
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM medicines WHERE expiry_date <= ? ORDER BY expiry_date ASC",
                (today,),
            )
            rows = cursor.fetchall()
        return [self._row_to_medicine(row) for row in rows]

    def get_medicines_by_status(self, status: str) -> List[Medicine]:
        """Query medicines filtered by computed status.

        Note: status is a computed field (not stored), so all medicines are
        fetched and filtered in Python.
        """
        all_medicines = self.get_all_medicines()
        return [m for m in all_medicines if m.get_status() == status]

    def count_medicines_by_status(self) -> dict:
        """Return count breakdown by computed status."""
        from ..const import STATUS_EXPIRED, STATUS_EXPIRING_SOON, STATUS_GOOD, STATUS_OPENED_TOO_LONG
        all_medicines = self.get_all_medicines()
        counts: dict = {
            STATUS_EXPIRED: 0,
            STATUS_EXPIRING_SOON: 0,
            STATUS_GOOD: 0,
            STATUS_OPENED_TOO_LONG: 0,
        }
        for m in all_medicines:
            status = m.get_status()
            if status in counts:
                counts[status] += 1
        return counts

    def delete_older_than(self, days: int) -> int:
        """Delete medicine records added more than ``days`` days ago.

        Returns the number of records removed.
        """
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM medicines WHERE added_date < ?", (cutoff,)
            )
            conn.commit()
            count = cursor.rowcount
        if count:
            _LOGGER.info("Auto-cleanup removed %d medicine record(s) older than %d days", count, days)
        return count
