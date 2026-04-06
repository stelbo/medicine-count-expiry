"""Database layer for Medicine Count & Expiry integration."""
from __future__ import annotations

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
    unit TEXT DEFAULT ''
)
"""

CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_medicine_name ON medicines(medicine_name)",
    "CREATE INDEX IF NOT EXISTS idx_expiry_date ON medicines(expiry_date)",
    "CREATE INDEX IF NOT EXISTS idx_location ON medicines(location)",
]


class MedicineDatabase:
    """SQLite database for medicine storage."""

    def __init__(self, db_path: str) -> None:
        """Initialize the database."""
        self._db_path = db_path
        self._init_db()
        self._migrate_db()

    def _connect(self) -> sqlite3.Connection:
        """Return a new connection with row_factory set to sqlite3.Row."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize the database tables."""
        with self._connect() as conn:
            conn.execute(CREATE_TABLE_SQL)
            for idx_sql in CREATE_INDEX_SQL:
                conn.execute(idx_sql)
            conn.commit()
        _LOGGER.debug("Database initialized at %s", self._db_path)

    def _migrate_db(self) -> None:
        """Apply incremental schema migrations for existing databases."""
        with self._connect() as conn:
            cursor = conn.execute("PRAGMA table_info(medicines)")
            existing_columns = {row["name"] for row in cursor.fetchall()}
            if "unit" not in existing_columns:
                conn.execute("ALTER TABLE medicines ADD COLUMN unit TEXT DEFAULT ''")
                conn.commit()
                _LOGGER.debug("Migrated database: added 'unit' column")

    def _row_to_medicine(self, row: sqlite3.Row) -> Medicine:
        """Convert a database row to a Medicine object."""
        return Medicine(
            medicine_id=row["medicine_id"],
            medicine_name=row["medicine_name"],
            expiry_date=row["expiry_date"],
            description=row["description"],
            quantity=row["quantity"],
            location=row["location"],
            image_url=row["image_url"],
            ai_verified=bool(row["ai_verified"]),
            confidence_score=row["confidence_score"],
            added_date=row["added_date"],
            updated_date=row["updated_date"],
            unit=row["unit"],
        )

    def add_medicine(self, medicine: Medicine) -> Medicine:
        """Add a new medicine to the database."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO medicines
                   (medicine_id, medicine_name, expiry_date, description, quantity,
                    location, image_url, ai_verified, confidence_score, added_date,
                    updated_date, unit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    medicine.unit,
                ),
            )
            conn.commit()
        _LOGGER.info("Added medicine: %s", medicine.medicine_name)
        return medicine

    def update_medicine(self, medicine: Medicine) -> Optional[Medicine]:
        """Update an existing medicine."""
        medicine.updated_date = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """UPDATE medicines SET
                   medicine_name=?, expiry_date=?, description=?, quantity=?,
                   location=?, image_url=?, ai_verified=?, confidence_score=?,
                   updated_date=?, unit=?
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
                    medicine.unit,
                    medicine.medicine_id,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        _LOGGER.info("Updated medicine: %s", medicine.medicine_name)
        return medicine

    def delete_medicine(self, medicine_id: str) -> bool:
        """Delete a medicine by ID."""
        with self._connect() as conn:
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
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM medicines WHERE medicine_id=?", (medicine_id,)
            )
            row = cursor.fetchone()
        if row:
            return self._row_to_medicine(row)
        return None

    def get_all_medicines(self) -> List[Medicine]:
        """Get all medicines."""
        with self._connect() as conn:
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

        with self._connect() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        return [self._row_to_medicine(row) for row in rows]

    def get_expiring_medicines(self, days: int) -> List[Medicine]:
        """Get medicines expiring within the given number of days."""
        from datetime import date, timedelta
        today = date.today()
        future = today + timedelta(days=days)
        return self.search_medicines(
            expiry_before=future.isoformat(),
            expiry_after=today.isoformat(),
        )

    def get_expired_medicines(self) -> List[Medicine]:
        """Get all expired medicines."""
        from datetime import date
        today = date.today().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM medicines WHERE expiry_date < ? ORDER BY expiry_date ASC",
                (today,),
            )
            rows = cursor.fetchall()
        return [self._row_to_medicine(row) for row in rows]
