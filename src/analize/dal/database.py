"""Database DAL - all database operations go through here."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from analize.models.schemas import Document, Lab, TestResult, TestType, User


class Database:
    """Data Access Layer for all database operations.

    The Flask app must NOT access the database directly.
    All CRUD operations go through this class.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            # Check schema version
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            )
            schema_table_exists = cursor.fetchone() is not None

            if not schema_table_exists:
                # New database - check if old schema exists
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                )
                users_table_exists = cursor.fetchone() is not None

                if users_table_exists:
                    # Old schema exists - check if it has the old 'age' column
                    cursor = conn.execute("PRAGMA table_info(users)")
                    columns = {row[1] for row in cursor.fetchall()}
                    if "age" in columns:
                        raise RuntimeError(
                            "Database schema is outdated (stores 'age' instead of 'date_of_birth'). "
                            "Delete the database file and restart to create a new schema."
                        )

            conn.executescript("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sex TEXT NOT NULL,
                    date_of_birth DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS labs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    address TEXT,
                    phone TEXT,
                    email TEXT,
                    accreditation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    lab_id INTEGER,
                    file_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    tokens TEXT,
                    cost REAL,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (lab_id) REFERENCES labs(id)
                );

                CREATE TABLE IF NOT EXISTS test_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    standard_name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    category TEXT
                );

                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_type_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    document_id INTEGER NOT NULL,
                    lab_id INTEGER NOT NULL,
                    lab_test_name TEXT NOT NULL,
                    value REAL,
                    value_text TEXT,
                    value_normalized TEXT,
                    unit TEXT,
                    lower_limit REAL,
                    upper_limit REAL,
                    test_date DATE NOT NULL,
                    interpretation TEXT,
                    documentation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (test_type_id) REFERENCES test_types(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (document_id) REFERENCES documents(id),
                    FOREIGN KEY (lab_id) REFERENCES labs(id),
                    UNIQUE (user_id, test_type_id, test_date, lab_id)
                );

                CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
                CREATE INDEX IF NOT EXISTS idx_test_results_user ON test_results(user_id);
                CREATE INDEX IF NOT EXISTS idx_test_results_type ON test_results(test_type_id);
                CREATE INDEX IF NOT EXISTS idx_test_results_lab ON test_results(lab_id);
                CREATE INDEX IF NOT EXISTS idx_test_results_natural_key
                    ON test_results(user_id, test_type_id, test_date, lab_id);
            """)

            # Set schema version for new databases
            if not schema_table_exists:
                conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (2)")
            else:
                # Check current version
                cursor = conn.execute("SELECT MAX(version) FROM schema_version")
                current_version = cursor.fetchone()[0]
                if current_version < 2:
                    # Check if documents table has tokens column
                    cursor = conn.execute("PRAGMA table_info(documents)")
                    columns = {row[1] for row in cursor.fetchall()}
                    if "tokens" not in columns:
                        raise RuntimeError(
                            "Database schema is outdated (missing tokens/cost columns). "
                            "Delete the database file and restart to create a new schema."
                        )

            conn.commit()

    # User operations
    def create_user(self, name: str, sex: str, date_of_birth: str) -> int:
        """Create a new user and return their ID.

        Args:
            name: User's name
            sex: M, F, or O
            date_of_birth: Date of birth in YYYY-MM-DD format

        Returns:
            User ID
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (name, sex, date_of_birth) VALUES (?, ?, ?)",
                (name, sex, date_of_birth),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def get_user(self, user_id: int) -> User | None:
        """Get a user by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if row:
                return User(**dict(row))
            return None

    def list_users(self) -> list[User]:
        """List all users."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
            return [User(**dict(row)) for row in rows]

    # Lab operations
    def create_lab(
        self,
        name: str,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        accreditation: str | None = None,
    ) -> int:
        """Create a new lab and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO labs (name, address, phone, email, accreditation)
                VALUES (?, ?, ?, ?, ?)""",
                (name, address, phone, email, accreditation),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def get_lab(self, lab_id: int) -> Lab | None:
        """Get a lab by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM labs WHERE id = ?", (lab_id,)).fetchone()
            if row:
                return Lab(**dict(row))
            return None

    def get_lab_by_name(self, name: str) -> Lab | None:
        """Get a lab by exact name match."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM labs WHERE name = ?", (name,)).fetchone()
            if row:
                return Lab(**dict(row))
            return None

    def list_labs(self) -> list[Lab]:
        """List all labs."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM labs ORDER BY name").fetchall()
            return [Lab(**dict(row)) for row in rows]

    # Document operations
    def create_document(
        self, user_id: int, file_path: str, content_hash: str, lab_id: int | None = None
    ) -> int:
        """Create a new document record and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO documents (user_id, lab_id, file_path, content_hash) VALUES (?, ?, ?, ?)",
                (user_id, lab_id, file_path, content_hash),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def get_document_by_hash(self, content_hash: str) -> Document | None:
        """Find a document by its content hash."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            if row:
                return Document(**dict(row))
            return None

    def get_document(self, document_id: int) -> Document | None:
        """Get a document by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            if row:
                return Document(**dict(row))
            return None

    def update_document_lab(self, document_id: int, lab_id: int) -> None:
        """Update the lab associated with a document."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE documents SET lab_id = ? WHERE id = ?",
                (lab_id, document_id),
            )
            conn.commit()

    def mark_document_processed(self, document_id: int) -> None:
        """Mark a document as processed."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE documents SET processed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (document_id,),
            )
            conn.commit()

    def list_documents_for_user(self, user_id: int) -> list[Document]:
        """List all documents for a user."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE user_id = ? ORDER BY uploaded_at DESC",
                (user_id,),
            ).fetchall()
            return [Document(**dict(row)) for row in rows]

    def update_document_tokens(self, document_id: int, tokens_json: str) -> None:
        """Update token usage for a document.

        Args:
            document_id: Document ID
            tokens_json: JSON string with token counts per model
                Example: '{"gemini-2.5-flash": {"input": 1000, "output": 500}}'
        """
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE documents SET tokens = ? WHERE id = ?",
                (tokens_json, document_id),
            )
            conn.commit()

    # Test type operations
    def create_test_type(
        self, standard_name: str, description: str | None = None, category: str | None = None
    ) -> int:
        """Create a new test type and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO test_types (standard_name, description, category) VALUES (?, ?, ?)",
                (standard_name, description, category),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def get_test_type_by_name(self, standard_name: str) -> TestType | None:
        """Get a test type by its standard name."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM test_types WHERE standard_name = ?", (standard_name,)
            ).fetchone()
            if row:
                return TestType(**dict(row))
            return None

    def list_test_types(self) -> list[TestType]:
        """List all test types."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM test_types ORDER BY standard_name"
            ).fetchall()
            return [TestType(**dict(row)) for row in rows]

    # Test result operations
    def get_test_result(
        self,
        user_id: int,
        test_type_id: int,
        test_date: str,
        lab_id: int,
    ) -> TestResult | None:
        """Get a test result by natural key.

        Args:
            user_id: User ID
            test_type_id: Test type ID
            test_date: Test date (YYYY-MM-DD)
            lab_id: Lab ID

        Returns:
            TestResult if found, None otherwise
        """
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM test_results
                WHERE user_id = ? AND test_type_id = ? AND test_date = ? AND lab_id = ?""",
                (user_id, test_type_id, test_date, lab_id),
            ).fetchone()

            if row:
                return TestResult(**dict(row))
            return None

    def upsert_test_result(
        self,
        test_type_id: int,
        user_id: int,
        document_id: int,
        lab_id: int,
        lab_test_name: str,
        test_date: str,
        value: float | None = None,
        value_text: str | None = None,
        value_normalized: str | None = None,
        unit: str | None = None,
        lower_limit: float | None = None,
        upper_limit: float | None = None,
        interpretation: str | None = None,
        documentation: str | None = None,
    ) -> tuple[int, bool]:
        """Upsert a test result based on natural key.

        If result exists for (user_id, test_type_id, test_date, lab_id), updates it.
        Otherwise, creates new result.

        Args:
            test_type_id: Test type ID
            user_id: User ID
            document_id: Document ID (updated to latest document referencing this result)
            lab_id: Lab ID
            lab_test_name: Lab's name for the test
            test_date: Test date (YYYY-MM-DD)
            value: Numeric value
            value_text: Text value for non-numeric results
            value_normalized: Normalized qualitative value (POSITIVE, NEGATIVE, etc.)
            unit: Unit of measurement
            lower_limit: Lower reference range
            upper_limit: Upper reference range
            interpretation: Clinical interpretation of result
            documentation: Notes about the test

        Returns:
            Tuple of (result_id, created) where created=True if new, False if updated
        """
        with self._get_connection() as conn:
            # Check if exists
            existing = conn.execute(
                """SELECT id FROM test_results
                WHERE user_id = ? AND test_type_id = ? AND test_date = ? AND lab_id = ?""",
                (user_id, test_type_id, test_date, lab_id),
            ).fetchone()

            if existing:
                # Update existing
                result_id = existing["id"]
                conn.execute(
                    """UPDATE test_results SET
                    document_id = ?,
                    lab_test_name = ?,
                    value = ?,
                    value_text = ?,
                    value_normalized = ?,
                    unit = ?,
                    lower_limit = ?,
                    upper_limit = ?,
                    interpretation = ?,
                    documentation = ?,
                    updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?""",
                    (
                        document_id,
                        lab_test_name,
                        value,
                        value_text,
                        value_normalized,
                        unit,
                        lower_limit,
                        upper_limit,
                        interpretation,
                        documentation,
                        result_id,
                    ),
                )
                conn.commit()
                return (result_id, False)
            else:
                # Insert new
                cursor = conn.execute(
                    """INSERT INTO test_results
                    (test_type_id, user_id, document_id, lab_id, lab_test_name, value, value_text,
                     value_normalized, unit, lower_limit, upper_limit, test_date, interpretation, documentation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        test_type_id,
                        user_id,
                        document_id,
                        lab_id,
                        lab_test_name,
                        value,
                        value_text,
                        value_normalized,
                        unit,
                        lower_limit,
                        upper_limit,
                        test_date,
                        interpretation,
                        documentation,
                    ),
                )
                conn.commit()
                return (cursor.lastrowid, True)  # type: ignore[return-value]

    def get_results_for_user(self, user_id: int) -> list[dict[str, Any]]:
        """Get all test results for a user with test type info."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT tr.*, tt.standard_name, tt.category
                FROM test_results tr
                JOIN test_types tt ON tr.test_type_id = tt.id
                WHERE tr.user_id = ?
                ORDER BY tr.test_date DESC, tt.standard_name""",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_results_for_test_type(
        self, user_id: int, test_type_id: int
    ) -> list[TestResult]:
        """Get all results for a specific test type and user (for timeline)."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM test_results
                WHERE user_id = ? AND test_type_id = ?
                ORDER BY test_date ASC""",
                (user_id, test_type_id),
            ).fetchall()
            return [TestResult(**dict(row)) for row in rows]
