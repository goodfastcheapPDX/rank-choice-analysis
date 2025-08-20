import logging
import random
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


class DatabaseConnectionManager:
    """
    Manages DuckDB connections with pooling, retry logic, and proper cleanup.
    Handles read-only vs read-write connections to avoid locking issues.
    """

    def __init__(self):
        self.connections = {}
        self.lock = threading.Lock()

    def get_connection(
        self, db_path: str, read_only: bool = True, max_retries: int = 3
    ) -> duckdb.DuckDBPyConnection:
        """
        Get a database connection with retry logic and proper locking.

        Args:
            db_path: Path to DuckDB file
            read_only: Whether to open in read-only mode (avoids locks)
            max_retries: Maximum number of connection attempts

        Returns:
            DuckDB connection
        """
        # connection_key = f"{db_path}_{read_only}"  # Not currently used for pooling

        for attempt in range(max_retries):
            try:
                # Use read-only mode to avoid locks when possible
                if read_only and Path(db_path).exists():
                    conn = duckdb.connect(db_path, read_only=True)
                    logger.debug(f"Opened read-only connection to {db_path}")
                else:
                    conn = duckdb.connect(db_path)
                    logger.debug(f"Opened read-write connection to {db_path}")

                return conn

            except duckdb.IOException as e:
                if "Conflicting lock" in str(e) and attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    wait_time = (2**attempt) + random.uniform(0, 1)  # nosec B311
                    logger.warning(
                        f"Database locked, retrying in {wait_time:.2f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"Failed to connect to database after {max_retries} attempts: {e}"
                    )
                    raise

        raise Exception(
            f"Could not establish database connection after {max_retries} attempts"
        )

    @contextmanager
    def get_temporary_connection(self, db_path: str, read_only: bool = True):
        """
        Context manager for temporary database connections that auto-cleanup.

        Args:
            db_path: Path to DuckDB file
            read_only: Whether to open in read-only mode

        Yields:
            DuckDB connection
        """
        conn = None
        try:
            conn = self.get_connection(db_path, read_only)
            yield conn
        finally:
            if conn:
                try:
                    conn.close()
                    logger.debug(f"Closed temporary connection to {db_path}")
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")


# Global connection manager instance
_connection_manager = DatabaseConnectionManager()


class CVRDatabase:
    """
    Manages DuckDB connection and executes SQL scripts for CVR analysis.
    Now uses connection pooling and proper cleanup to avoid locking issues.
    """

    def __init__(self, db_path: Optional[str] = None, read_only: bool = True):
        """
        Initialize database connection manager.

        Args:
            db_path: Path to DuckDB file. If None, uses in-memory database.
            read_only: Whether to default to read-only connections (recommended for most use cases)
        """
        self.db_path = db_path
        self.read_only = read_only
        self.sql_dir = Path(__file__).parent.parent.parent / "sql"
        self._conn = None  # Will be created on-demand

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Get or create a database connection on-demand."""
        if self._conn is None:
            self._conn = _connection_manager.get_connection(
                self.db_path, self.read_only
            )
        return self._conn

    def execute_script(
        self, script_name: str, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Execute a SQL script file with optional parameters.

        Args:
            script_name: Name of SQL file (without .sql extension)
            params: Parameters to substitute in SQL script

        Returns:
            DataFrame with query results (if any)
        """
        script_path = self.sql_dir / f"{script_name}.sql"

        if not script_path.exists():
            raise FileNotFoundError(f"SQL script not found: {script_path}")

        with open(script_path, "r") as f:
            sql = f.read()

        # Simple parameter substitution for file paths
        if params:
            if isinstance(params, dict):
                for key, value in params.items():
                    # Properly quote file paths for SQL
                    quoted_value = (
                        f"'{str(value)}'"
                        if isinstance(value, (str, Path))
                        else str(value)
                    )
                    sql = sql.replace("?", quoted_value, 1)
            elif isinstance(params, (list, tuple)):
                for value in params:
                    # Properly quote file paths for SQL
                    quoted_value = (
                        f"'{str(value)}'"
                        if isinstance(value, (str, Path))
                        else str(value)
                    )
                    sql = sql.replace("?", quoted_value, 1)
            else:
                # Properly quote file paths for SQL
                quoted_value = (
                    f"'{str(params)}'"
                    if isinstance(params, (str, Path))
                    else str(params)
                )
                sql = sql.replace("?", quoted_value, 1)

        try:
            result = self.conn.execute(sql).fetchdf()
            logger.info(f"Executed script: {script_name}")
            return result
        except Exception as e:
            logger.error(f"Error executing script {script_name}: {e}")
            raise

    def query(self, sql: str, use_temporary_connection: bool = False) -> pd.DataFrame:
        """
        Execute a SQL query and return results as DataFrame.

        Args:
            sql: SQL query to execute
            use_temporary_connection: If True, uses a temporary connection that auto-cleans up
        """
        if use_temporary_connection:
            with _connection_manager.get_temporary_connection(
                self.db_path, read_only=True
            ) as temp_conn:
                return temp_conn.execute(sql).fetchdf()
        else:
            return self.conn.execute(sql).fetchdf()

    def query_with_retry(self, sql: str, max_retries: int = 3) -> pd.DataFrame:
        """
        Execute a SQL query with automatic retry and temporary connections.
        Recommended for web applications to avoid connection issues.
        """
        for attempt in range(max_retries):
            try:
                with _connection_manager.get_temporary_connection(
                    self.db_path, read_only=True
                ) as temp_conn:
                    return temp_conn.execute(sql).fetchdf()
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (2**attempt) + random.uniform(0, 0.5)  # nosec B311
                    logger.warning(f"Query failed, retrying in {wait_time:.2f}s: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Query failed after {max_retries} attempts: {e}")
                    raise

    def table_exists(
        self, table_name: str, use_temporary_connection: bool = True
    ) -> bool:
        """
        Check if a table exists in the database.

        Args:
            table_name: Name of table to check
            use_temporary_connection: Whether to use a temporary connection (recommended)
        """
        sql = "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?"

        if use_temporary_connection:
            with _connection_manager.get_temporary_connection(
                self.db_path, read_only=True
            ) as temp_conn:
                result = temp_conn.execute(sql, [table_name]).fetchone()
                return result[0] > 0
        else:
            result = self.conn.execute(sql, [table_name]).fetchone()
            return result[0] > 0

    def get_table_info(self, table_name: str) -> pd.DataFrame:
        """Get column information for a table."""
        with _connection_manager.get_temporary_connection(
            self.db_path, read_only=True
        ) as temp_conn:
            return temp_conn.execute(f"DESCRIBE {table_name}").fetchdf()

    def close(self):
        """Close database connection."""
        if self._conn:
            try:
                self._conn.close()
                logger.debug(f"Closed database connection to {self.db_path}")
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")
            finally:
                self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
