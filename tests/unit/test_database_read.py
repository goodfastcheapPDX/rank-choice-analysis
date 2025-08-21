import os
import tempfile

import pytest

from src.data.database import CVRDatabase


class TestDatabaseReadOperations:
    """Test database operations that only require read access."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        # Remove the empty file so DuckDB can create a proper database
        os.unlink(self.db_path)

    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_malformed_sql_query(self):
        """Test handling of malformed SQL queries."""
        db = CVRDatabase(":memory:", read_only=True)

        # Test various malformed queries
        malformed_queries = [
            "SELEC * FROM nonexistent_table",  # Typo
            "SELECT * FROM nonexistent_table",  # Table doesn't exist
            "SELECT incomplete",  # Incomplete SELECT
        ]

        for query in malformed_queries:
            with pytest.raises(Exception):
                db.query(query)

        db.close()

    def test_concurrent_database_access(self):
        """Test concurrent read access to the same database."""
        # First create a database with test data
        setup_db = CVRDatabase(self.db_path, read_only=False)
        setup_db.conn.execute(
            "CREATE TABLE concurrent_test (id INTEGER, timestamp TEXT)"
        )
        setup_db.conn.execute("INSERT INTO concurrent_test VALUES (1, 'test_time')")
        setup_db.close()

        # Open multiple read-only connections
        db_read1 = CVRDatabase(self.db_path, read_only=True)
        db_read2 = CVRDatabase(self.db_path, read_only=True)

        # Both should be able to read
        result1 = db_read1.query("SELECT COUNT(*) as count FROM concurrent_test")
        result2 = db_read2.query("SELECT COUNT(*) as count FROM concurrent_test")

        assert result1.iloc[0]["count"] == 1
        assert result2.iloc[0]["count"] == 1

        # Both should be able to read the actual data
        data1 = db_read1.query("SELECT * FROM concurrent_test")
        data2 = db_read2.query("SELECT * FROM concurrent_test")

        assert len(data1) == 1
        assert len(data2) == 1
        assert data1.iloc[0]["timestamp"] == "test_time"

        db_read1.close()
        db_read2.close()

    def test_database_corruption_detection(self):
        """Test detection of corrupted database files."""
        # Create a normal database first
        db = CVRDatabase(self.db_path, read_only=False)
        db.conn.execute("CREATE TABLE test_table (id INTEGER)")
        db.close()

        # Corrupt the database file by writing random data
        with open(self.db_path, "wb") as file:
            file.write(b"corrupted_data_not_sqlite")

        # Attempting to open should fail
        with pytest.raises(Exception):
            corrupted_db = CVRDatabase(self.db_path)
            corrupted_db.query("SELECT 1")

    def test_empty_database_file(self):
        """Test handling of empty database files."""
        # Create an empty file
        with open(self.db_path, "w") as f:
            f.write("")

        # Should handle empty file gracefully or raise appropriate error
        with pytest.raises(Exception):
            db = CVRDatabase(self.db_path)
            db.query("SELECT 1")

    def test_table_exists_error_handling(self):
        """Test table_exists method error handling."""
        db = CVRDatabase(":memory:", read_only=True)

        # Close connection to force error
        db.close()

        # Should handle closed connection gracefully and return False
        result = db.table_exists("any_table")
        assert result is False

    def test_execute_script_file_not_found(self):
        """Test execute_script with non-existent file."""
        db = CVRDatabase(":memory:", read_only=True)

        with pytest.raises(Exception):
            db.execute_script("nonexistent_script_file")

        db.close()

    def test_execute_script_malformed_sql(self):
        """Test execute_script with malformed SQL file."""
        # Create a temporary SQL file with malformed content
        sql_file = tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False)
        sql_file.write("SELEC * FROM malformed_query;")  # Typo in SELECT
        sql_file.close()

        db = CVRDatabase(":memory:", read_only=True)

        try:
            with pytest.raises(Exception):
                db.execute_script(sql_file.name)
        finally:
            os.unlink(sql_file.name)
            db.close()
