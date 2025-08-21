import os
import tempfile

import pytest

from src.data.database import CVRDatabase


class TestDatabaseWriteOperations:
    """Test database operations that require write access."""

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

    def test_database_connection_failure(self):
        """Test handling of database connection failures."""
        # Use an invalid path that should cause connection issues
        invalid_path = "/nonexistent/directory/database.db"

        with pytest.raises(Exception):
            db = CVRDatabase(invalid_path)
            # Attempt to use the connection
            db.query("SELECT 1")

    def test_database_readonly_mode(self):
        """Test read-only database mode."""
        # Create a database first (writable mode)
        db = CVRDatabase(self.db_path, read_only=False)
        db.conn.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")
        db.conn.execute("INSERT INTO test_table VALUES (1, 'test')")
        db.close()

        # Open in read-only mode
        readonly_db = CVRDatabase(self.db_path, read_only=True)

        # Reading should work
        result = readonly_db.query("SELECT * FROM test_table")
        assert len(result) == 1

        # Writing should fail
        with pytest.raises(Exception):
            readonly_db.conn.execute("INSERT INTO test_table VALUES (2, 'test2')")

        readonly_db.close()

    def test_database_file_permissions(self):
        """Test database access with restricted file permissions."""
        # Create a database file
        db = CVRDatabase(self.db_path, read_only=False)
        db.conn.execute("CREATE TABLE test_table (id INTEGER)")
        db.close()

        # Make file read-only at OS level
        os.chmod(self.db_path, 0o444)

        try:
            # Should still be able to open in read-only mode
            readonly_db = CVRDatabase(self.db_path, read_only=True)
            readonly_db.query("SELECT * FROM test_table")
            readonly_db.close()

            # Writing should fail
            with pytest.raises(Exception):
                write_db = CVRDatabase(self.db_path, read_only=False)
                write_db.conn.execute("INSERT INTO test_table VALUES (1)")

        finally:
            # Restore permissions for cleanup
            os.chmod(self.db_path, 0o666)

    def test_connection_pooling_behavior(self):
        """Test connection pooling and concurrent access."""
        db = CVRDatabase(self.db_path, read_only=False)

        # Create test table
        db.conn.execute("CREATE TABLE test_table (id INTEGER, value TEXT)")
        db.conn.execute("INSERT INTO test_table VALUES (1, 'first')")

        # Test multiple queries work
        result1 = db.query("SELECT * FROM test_table WHERE id = 1")
        result2 = db.query("SELECT COUNT(*) as count FROM test_table")

        assert len(result1) == 1
        assert result2.iloc[0]["count"] == 1

        db.close()

    def test_large_query_results(self):
        """Test handling of large query results."""
        db = CVRDatabase(self.db_path, read_only=False)

        # Create table with many rows
        db.conn.execute("CREATE TABLE large_table (id INTEGER, data TEXT)")

        # Insert a reasonable number of test rows
        for i in range(1000):
            db.conn.execute(f"INSERT INTO large_table VALUES ({i}, 'data_{i}')")

        # Query all rows
        result = db.query("SELECT * FROM large_table")
        assert len(result) == 1000

        # Query with LIMIT
        limited_result = db.query("SELECT * FROM large_table LIMIT 100")
        assert len(limited_result) == 100

        db.close()

    def test_table_exists_with_nonexistent_table(self):
        """Test table_exists method with nonexistent table."""
        # Use in-memory database to avoid connection conflicts
        db = CVRDatabase(":memory:", read_only=False)

        # Table should not exist
        assert not db.table_exists("nonexistent_table")

        # Create table and verify it exists
        db.conn.execute("CREATE TABLE existing_table (id INTEGER)")
        assert db.table_exists("existing_table", use_temporary_connection=False)

        db.close()

    def test_basic_database_operations(self):
        """Test basic database create, insert, query operations."""
        db = CVRDatabase(self.db_path, read_only=False)

        # Create test table
        db.conn.execute("CREATE TABLE basic_test (id INTEGER, name TEXT)")
        db.conn.execute("INSERT INTO basic_test VALUES (1, 'test_name')")

        # Query should work
        result = db.query("SELECT * FROM basic_test")
        assert len(result) == 1
        assert result.iloc[0]["name"] == "test_name"

        db.close()

    def test_context_manager_exception_handling(self):
        """Test context manager with exception handling."""
        # Test that database is properly closed even with exceptions
        try:
            with CVRDatabase(":memory:", read_only=False) as db:
                db.conn.execute("CREATE TABLE context_test (id INTEGER)")
                # Simulate an exception
                raise ValueError("Test exception")

        except ValueError:
            # Exception should be propagated, but cleanup should still happen
            pass

        # Database should be properly closed
        # Verify by opening again
        with CVRDatabase(":memory:", read_only=False) as db:
            # Should work without issues
            db.conn.execute("CREATE TABLE context_test2 (id INTEGER)")
            result = db.query("SELECT COUNT(*) as count FROM context_test2")
            assert len(result) == 1

    def test_memory_usage_with_large_datasets(self):
        """Test memory usage with moderately large datasets."""
        db = CVRDatabase(":memory:", read_only=False)

        # Create table with moderately large data
        db.conn.execute("CREATE TABLE memory_test (id INTEGER, data TEXT)")

        # Insert test data
        large_string = "x" * 1000  # 1KB string
        for i in range(100):  # 100KB total
            db.conn.execute(f"INSERT INTO memory_test VALUES ({i}, '{large_string}')")

        # Query should handle the data without memory issues
        result = db.query("SELECT COUNT(*) as count FROM memory_test")
        assert result.iloc[0]["count"] == 100

        # Query for all data
        all_data = db.query("SELECT * FROM memory_test")
        assert len(all_data) == 100

        db.close()

    def test_special_characters_in_data(self):
        """Test handling of special characters in data."""
        db = CVRDatabase(":memory:", read_only=False)

        # Create table
        db.conn.execute("CREATE TABLE special_chars (id INTEGER, text_data TEXT)")

        # Test various special characters
        special_strings = [
            "O'Malley",  # Apostrophe
            'Data with "quotes"',  # Double quotes
            "Data with 'single quotes'",  # Single quotes
            "Unicode: café, naïve, résumé",  # Unicode characters
            "Symbols: !@#$%^&*()",  # Special symbols
            "Line\nBreak",  # Newline
            "Tab\tCharacter",  # Tab
        ]

        for i, text in enumerate(special_strings):
            # Use parameterized query to safely insert
            db.conn.execute("INSERT INTO special_chars VALUES (?, ?)", (i, text))

        # Query back the data
        result = db.query("SELECT * FROM special_chars ORDER BY id")
        assert len(result) == len(special_strings)

        # Verify specific strings were preserved
        for i, original_text in enumerate(special_strings):
            retrieved_text = result.iloc[i]["text_data"]
            assert retrieved_text == original_text

        db.close()

    def test_parameterized_queries(self):
        """Test that parameterized queries work safely."""
        db = CVRDatabase(self.db_path, read_only=False)

        # Create test table
        db.conn.execute("CREATE TABLE param_test (id INTEGER, name TEXT)")

        # Use parameterized insert
        db.conn.execute("INSERT INTO param_test VALUES (?, ?)", (1, "safe_name"))
        db.conn.execute("INSERT INTO param_test VALUES (?, ?)", (2, "O'Malley"))

        # Query back the data
        result = db.query("SELECT * FROM param_test ORDER BY id")
        assert len(result) == 2
        assert result.iloc[1]["name"] == "O'Malley"

        db.close()
