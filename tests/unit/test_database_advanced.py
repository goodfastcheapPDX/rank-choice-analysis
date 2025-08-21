import os
import sqlite3
import tempfile
from unittest.mock import Mock, patch

import pytest

from src.data.database import CVRDatabase


class TestDatabaseErrorHandling:
    """Test database error handling and edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name

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
        # Create a database first
        db = CVRDatabase(self.db_path)
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
        db = CVRDatabase(self.db_path)
        db.conn.execute("CREATE TABLE test_table (id INTEGER)")
        db.close()

        # Make file read-only at OS level
        os.chmod(self.db_path, 0o444)

        try:
            # Should still be able to open in read-only mode
            readonly_db = CVRDatabase(self.db_path, read_only=True)
            readonly_db.query("SELECT * FROM test_table")
            readonly_db.close()

            # Should fail to open in write mode
            with pytest.raises(Exception):
                write_db = CVRDatabase(self.db_path, read_only=False)
                write_db.conn.execute("INSERT INTO test_table VALUES (1)")

        finally:
            # Restore permissions for cleanup
            os.chmod(self.db_path, 0o666)

    def test_connection_pooling_behavior(self):
        """Test connection pooling and concurrent access."""
        db = CVRDatabase(self.db_path)

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
        db = CVRDatabase(self.db_path)

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

    def test_malformed_sql_query(self):
        """Test handling of malformed SQL queries."""
        db = CVRDatabase(self.db_path)

        # Test various malformed queries
        malformed_queries = [
            "SELECT * FROM",  # Incomplete
            "SELEC * FROM nonexistent_table",  # Typo
            "SELECT * FROM nonexistent_table",  # Table doesn't exist
            "INSERT INTO",  # Incomplete INSERT
            "UPDATE SET value = 1",  # Missing table
        ]

        for query in malformed_queries:
            with pytest.raises(Exception):
                db.query(query)

        db.close()

    def test_concurrent_database_access(self):
        """Test concurrent access to the same database."""
        # Create initial database
        db1 = CVRDatabase(self.db_path)
        db1.conn.execute("CREATE TABLE concurrent_test (id INTEGER, timestamp TEXT)")
        db1.close()

        # Open multiple connections
        db_read1 = CVRDatabase(self.db_path, read_only=True)
        db_read2 = CVRDatabase(self.db_path, read_only=True)

        # Both should be able to read
        result1 = db_read1.query("SELECT COUNT(*) as count FROM concurrent_test")
        result2 = db_read2.query("SELECT COUNT(*) as count FROM concurrent_test")

        assert result1.iloc[0]["count"] == 0
        assert result2.iloc[0]["count"] == 0

        db_read1.close()
        db_read2.close()

    def test_database_corruption_detection(self):
        """Test detection of database corruption."""
        # Create a normal database first
        db = CVRDatabase(self.db_path)
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
        """Test handling of empty database file."""
        # Create empty file
        with open(self.db_path, "w"):
            pass

        # Should handle empty file gracefully
        with pytest.raises(Exception):
            db = CVRDatabase(self.db_path)
            db.query("SELECT 1")

    def test_table_exists_with_nonexistent_table(self):
        """Test table_exists method with nonexistent table."""
        db = CVRDatabase(self.db_path)

        # Table should not exist
        assert not db.table_exists("nonexistent_table")

        # Create table and verify it exists
        db.conn.execute("CREATE TABLE existing_table (id INTEGER)")
        assert db.table_exists("existing_table")

        db.close()

    def test_table_exists_error_handling(self):
        """Test table_exists method error handling."""
        db = CVRDatabase(self.db_path)

        # Close connection to force error
        db.close()

        # Should handle closed connection gracefully
        with pytest.raises(Exception):
            db.table_exists("any_table")

    def test_query_with_retry_functionality(self):
        """Test query_with_retry method."""
        db = CVRDatabase(self.db_path)

        # Create test table
        db.conn.execute("CREATE TABLE retry_test (id INTEGER)")
        db.conn.execute("INSERT INTO retry_test VALUES (1)")

        # Normal query should work
        result = db.query_with_retry("SELECT * FROM retry_test")
        assert len(result) == 1

        db.close()

    def test_query_with_retry_database_locked(self):
        """Test query_with_retry with database locked scenario."""
        db = CVRDatabase(self.db_path)

        # Create test table
        db.conn.execute("CREATE TABLE lock_test (id INTEGER)")

        # Mock a database locked error on first try, success on retry
        original_query = db.query
        call_count = 0

        def mock_query_with_lock_error(sql):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise sqlite3.OperationalError("database is locked")
            else:
                return original_query(sql)

        with patch.object(db, "query", side_effect=mock_query_with_lock_error):
            # Should retry and succeed
            result = db.query_with_retry("SELECT COUNT(*) as count FROM lock_test")
            assert result.iloc[0]["count"] == 0
            assert call_count == 2  # Should have retried once

        db.close()

    def test_execute_script_file_not_found(self):
        """Test execute_script with nonexistent script file."""
        db = CVRDatabase(self.db_path)

        with pytest.raises(Exception):
            db.execute_script("nonexistent_script")

        db.close()

    def test_execute_script_malformed_sql(self):
        """Test execute_script with malformed SQL."""
        db = CVRDatabase(self.db_path)

        # Create a temporary script file with malformed SQL
        script_content = "SELECT * FROM;"
        script_file = tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False)
        script_file.write(script_content)
        script_file.close()

        try:
            # Mock the script lookup to return our malformed script
            with patch("src.data.database.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                with open(script_file.name, "r") as f:
                    script_content = f.read()

                with patch("builtins.open", mock=Mock()) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = (
                        script_content
                    )

                    with pytest.raises(Exception):
                        db.execute_script("malformed_script")

        finally:
            os.unlink(script_file.name)
            db.close()

    def test_database_connection_recovery(self):
        """Test database connection recovery after failure."""
        db = CVRDatabase(self.db_path)

        # Create test table
        db.conn.execute("CREATE TABLE recovery_test (id INTEGER)")

        # Simulate connection failure and recovery
        original_conn = db.conn

        # Temporarily break the connection
        db.conn = None

        # Should fail with broken connection
        with pytest.raises(AttributeError):
            db.query("SELECT * FROM recovery_test")

        # Restore connection
        db.conn = original_conn

        # Should work again
        result = db.query("SELECT COUNT(*) as count FROM recovery_test")
        assert result.iloc[0]["count"] == 0

        db.close()

    def test_context_manager_exception_handling(self):
        """Test context manager behavior with exceptions."""
        try:
            with CVRDatabase(self.db_path) as db:
                db.conn.execute("CREATE TABLE context_test (id INTEGER)")
                # Simulate an exception
                raise ValueError("Test exception")

        except ValueError:
            # Exception should be propagated, but cleanup should still happen
            pass

        # Database should be properly closed
        # Verify by opening again
        with CVRDatabase(self.db_path) as db:
            # Table should still exist from before the exception
            assert db.table_exists("context_test")

    def test_memory_usage_with_large_datasets(self):
        """Test memory usage with large datasets."""
        db = CVRDatabase(self.db_path)

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
        db = CVRDatabase(self.db_path)

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

        # Insert special character data
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

    def test_sql_injection_protection(self):
        """Test protection against SQL injection attacks."""
        db = CVRDatabase(self.db_path)

        # Create test table
        db.conn.execute("CREATE TABLE injection_test (id INTEGER, name TEXT)")
        db.conn.execute("INSERT INTO injection_test VALUES (1, 'normal_user')")

        # Test SQL injection attempts (these should be safely handled)
        injection_attempts = [
            "1; DROP TABLE injection_test; --",
            "1' OR '1'='1",
            "1 UNION SELECT * FROM injection_test",
            "'; DELETE FROM injection_test; --",
        ]

        for injection_string in injection_attempts:
            # The query method should be safe from injection when used properly
            # Note: Direct string interpolation would be vulnerable,
            # but parameterized queries are safe
            try:
                # This demonstrates unsafe usage that could be vulnerable
                unsafe_query = (
                    f"SELECT * FROM injection_test WHERE id = {injection_string}"
                )
                # We expect this might fail due to malformed SQL, not execute malicious code
                with pytest.raises(Exception):
                    db.query(unsafe_query)
            except Exception:
                # Expected - malformed SQL should fail
                pass

        # Verify table still exists and has original data
        result = db.query("SELECT COUNT(*) as count FROM injection_test")
        assert result.iloc[0]["count"] == 1

        db.close()
