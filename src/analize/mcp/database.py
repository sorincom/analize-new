"""Database MCP - all database operations go through here."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from analize.models.schemas import Document, TestResult, TestType, User


class DatabaseMCP:
    """MCP interface for all database operations.

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
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sex TEXT NOT NULL,
                    age INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
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
                    lab_test_name TEXT NOT NULL,
                    value REAL,
                    value_text TEXT,
                    unit TEXT,
                    lower_limit REAL,
                    upper_limit REAL,
                    test_date DATE NOT NULL,
                    lab_name TEXT,
                    documentation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (test_type_id) REFERENCES test_types(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                );

                CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
                CREATE INDEX IF NOT EXISTS idx_test_results_user ON test_results(user_id);
                CREATE INDEX IF NOT EXISTS idx_test_results_type ON test_results(test_type_id);
            """)
            conn.commit()

    # User operations
    def create_user(self, name: str, sex: str, age: int) -> int:
        """Create a new user and return their ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (name, sex, age) VALUES (?, ?, ?)",
                (name, sex, age),
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

    # Document operations
    def create_document(self, user_id: int, file_path: str, content_hash: str) -> int:
        """Create a new document record and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO documents (user_id, file_path, content_hash) VALUES (?, ?, ?)",
                (user_id, file_path, content_hash),
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

    def mark_document_processed(self, document_id: int) -> None:
        """Mark a document as processed."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE documents SET processed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (document_id,),
            )
            conn.commit()

    def delete_results_for_document(self, document_id: int) -> int:
        """Delete all test results for a document (for reprocessing). Returns count deleted."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM test_results WHERE document_id = ?", (document_id,)
            )
            conn.commit()
            return cursor.rowcount

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

    def find_similar_test_type(self, name: str) -> TestType | None:
        """Find a test type with a similar name (basic matching).

        This is a placeholder for NLP-based matching.
        The LLM should handle the actual normalization logic.
        """
        # Basic exact match first
        test_type = self.get_test_type_by_name(name)
        if test_type:
            return test_type

        # TODO: Implement fuzzy matching or let LLM handle this
        return None

    # Test result operations
    def create_test_result(
        self,
        test_type_id: int,
        user_id: int,
        document_id: int,
        lab_test_name: str,
        test_date: str,
        value: float | None = None,
        value_text: str | None = None,
        unit: str | None = None,
        lower_limit: float | None = None,
        upper_limit: float | None = None,
        lab_name: str | None = None,
        documentation: str | None = None,
    ) -> int:
        """Create a new test result and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO test_results
                (test_type_id, user_id, document_id, lab_test_name, value, value_text,
                 unit, lower_limit, upper_limit, test_date, lab_name, documentation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    test_type_id,
                    user_id,
                    document_id,
                    lab_test_name,
                    value,
                    value_text,
                    unit,
                    lower_limit,
                    upper_limit,
                    test_date,
                    lab_name,
                    documentation,
                ),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

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
