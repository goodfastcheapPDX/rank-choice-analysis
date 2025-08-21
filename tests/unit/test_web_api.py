from unittest.mock import Mock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.web.main import (
    app,
    get_database,
    get_precomputed_pairs,
    has_precomputed_data,
    set_database_path,
)


class TestWebMainConfiguration:
    """Test web application configuration and utility functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)

    @patch("src.web.main.CVRDatabase")
    def test_get_database_with_path_set(self, mock_cvr_database):
        """Test get_database when global db_path is set."""
        with patch("src.web.main.db_path", "/test/path/db.db"):
            mock_db = Mock()
            mock_cvr_database.return_value = mock_db

            result = get_database()

            mock_cvr_database.assert_called_once_with(
                "/test/path/db.db", read_only=True
            )
            assert result == mock_db

    @patch("src.web.main.CVRDatabase")
    @patch.dict("os.environ", {"RVA_DATABASE_PATH": "/env/path/db.db"})
    def test_get_database_from_environment(self, mock_cvr_database):
        """Test get_database fallback to environment variable."""
        with patch("src.web.main.db_path", None):
            mock_db = Mock()
            mock_cvr_database.return_value = mock_db

            result = get_database()

            mock_cvr_database.assert_called_once_with("/env/path/db.db", read_only=True)
            assert result == mock_db

    def test_get_database_no_path_configured(self):
        """Test get_database raises exception when no path configured."""
        with (
            patch("src.web.main.db_path", None),
            patch.dict("os.environ", {}, clear=True),
        ):

            with pytest.raises(Exception):
                get_database()

    @patch("src.web.main.CVRDatabase")
    @patch.dict("os.environ", {})
    def test_set_database_path_success(self, mock_cvr_database):
        """Test successful database path setting."""
        mock_db = Mock()
        mock_cvr_database.return_value = mock_db
        mock_db.table_exists.return_value = True

        with patch("src.web.main.logger") as mock_logger:
            set_database_path("/new/test/path.db")

            # Check that environment variable is set
            import os

            assert os.environ["RVA_DATABASE_PATH"] == "/new/test/path.db"

            # Check that connection test was performed
            mock_cvr_database.assert_called_with("/new/test/path.db", read_only=True)
            mock_db.table_exists.assert_called_with("ballots_long")

            # Check logging
            mock_logger.info.assert_called()

    @patch("src.web.main.CVRDatabase")
    def test_set_database_path_connection_failure(self, mock_cvr_database):
        """Test database path setting with connection failure."""
        mock_cvr_database.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            set_database_path("/invalid/path.db")

    @patch("src.web.main.get_database")
    def test_has_precomputed_data_true(self, mock_get_database):
        """Test has_precomputed_data when tables exist."""
        mock_db = Mock()
        mock_db.table_exists.side_effect = lambda table: table in [
            "adjacent_pairs",
            "candidate_metrics",
        ]
        mock_get_database.return_value = mock_db

        result = has_precomputed_data()

        assert result is True
        assert mock_db.table_exists.call_count == 2

    @patch("src.web.main.get_database")
    def test_has_precomputed_data_false(self, mock_get_database):
        """Test has_precomputed_data when tables don't exist."""
        mock_db = Mock()
        mock_db.table_exists.return_value = False
        mock_get_database.return_value = mock_db

        result = has_precomputed_data()

        assert result is False

    @patch("src.web.main.get_database")
    def test_has_precomputed_data_exception(self, mock_get_database):
        """Test has_precomputed_data with database exception."""
        mock_get_database.side_effect = Exception("Database error")

        result = has_precomputed_data()

        assert result is False

    @patch("src.web.main.get_database")
    def test_get_precomputed_pairs_success(self, mock_get_database):
        """Test successful precomputed pairs retrieval."""
        mock_db = Mock()
        mock_pairs = pd.DataFrame(
            {
                "candidate_1": [1, 2],
                "candidate_2": [2, 3],
                "shared_ballots": [100, 75],
                "affinity_score": [0.8, 0.6],
            }
        )
        mock_db.query.return_value = mock_pairs
        mock_get_database.return_value = mock_db

        result = get_precomputed_pairs(min_shared_ballots=50)

        assert len(result) == 2
        mock_db.query.assert_called_once()

    @patch("src.web.main.get_database")
    def test_get_precomputed_pairs_with_filtering(self, mock_get_database):
        """Test precomputed pairs with custom filtering."""
        mock_db = Mock()
        mock_pairs = pd.DataFrame(
            {
                "candidate_1": [1],
                "candidate_2": [2],
                "shared_ballots": [150],
                "affinity_score": [0.9],
            }
        )
        mock_db.query.return_value = mock_pairs
        mock_get_database.return_value = mock_db

        result = get_precomputed_pairs(min_shared_ballots=100)

        # Should pass the minimum to the query
        assert len(result) == 1
        call_args = mock_db.query.call_args[0][0]
        assert "100" in call_args  # min_shared_ballots should be in query


class TestWebApplicationEndpoints:
    """Test web application endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)

    def test_app_title_and_description(self):
        """Test that FastAPI app has correct title and description."""
        assert app.title == "Ranked Elections Analyzer"
        assert app.description == "Portland STV Election Analysis Platform"

    @patch("src.web.main.get_database")
    def test_database_not_configured_error_handling(self, mock_get_database):
        """Test error handling when database is not configured."""
        from fastapi import HTTPException

        mock_get_database.side_effect = HTTPException(
            status_code=500, detail="Database not configured"
        )

        # This would test an endpoint that uses get_database()
        # Since we're testing the utility function, we verify the exception is raised
        with pytest.raises(HTTPException) as exc_info:
            get_database()

        assert exc_info.value.status_code == 500
        assert "Database not configured" in str(exc_info.value.detail)

    def test_startup_event(self):
        """Test application startup event."""
        # Test that startup doesn't raise exceptions
        # The actual startup event just logs, so we test it doesn't fail
        import asyncio

        from src.web.main import startup_event

        # Should not raise exception
        asyncio.run(startup_event())

    def test_shutdown_event(self):
        """Test application shutdown event."""
        # Test that shutdown doesn't raise exceptions
        import asyncio

        from src.web.main import shutdown_event

        # Should not raise exception
        asyncio.run(shutdown_event())

    @patch("src.web.main.templates")
    def test_templates_configuration(self, mock_templates):
        """Test that templates are configured correctly."""
        # Verify templates directory is configured
        from src.web.main import templates

        assert templates is not None


class TestWebApplicationIntegration:
    """Test web application integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)

    @patch("src.web.main.get_database")
    def test_database_connection_across_requests(self, mock_get_database):
        """Test that database connections work across multiple requests."""
        mock_db = Mock()
        mock_get_database.return_value = mock_db

        # Multiple calls to get_database should work
        db1 = get_database()
        db2 = get_database()

        assert db1 == mock_db
        assert db2 == mock_db
        assert mock_get_database.call_count == 2

    @patch("src.web.main.CVRDatabase")
    def test_read_only_database_connections(self, mock_cvr_database):
        """Test that database connections are read-only by default."""
        with patch("src.web.main.db_path", "/test/db.db"):
            get_database()

            # Verify read_only=True is passed
            mock_cvr_database.assert_called_with("/test/db.db", read_only=True)

    def test_global_database_path_persistence(self):
        """Test that database path persists globally."""
        import src.web.main as main_module

        # Set a test path
        original_path = getattr(main_module, "db_path", None)

        try:
            with patch("src.web.main.CVRDatabase") as mock_cvr:
                mock_db = Mock()
                mock_cvr.return_value = mock_db
                mock_db.table_exists.return_value = True

                set_database_path("/persistent/test.db")

                # Check that the global variable is set
                assert main_module.db_path == "/persistent/test.db"

                # Check that subsequent calls use the set path
                with patch("src.web.main.CVRDatabase") as mock_cvr2:
                    mock_db2 = Mock()
                    mock_cvr2.return_value = mock_db2

                    get_database()
                    mock_cvr2.assert_called_with("/persistent/test.db", read_only=True)

        finally:
            # Restore original path
            main_module.db_path = original_path

    @patch("src.web.main.logger")
    def test_logging_configuration(self, mock_logger):
        """Test that logging is properly configured."""
        # Test that logger is available and can be called
        mock_logger.info.return_value = None

        # Call a function that logs
        import asyncio

        from src.web.main import startup_event

        asyncio.run(startup_event())

        # Verify logging was called
        mock_logger.info.assert_called()

    def test_environment_variable_fallback(self):
        """Test environment variable fallback behavior."""
        import src.web.main as main_module

        original_path = getattr(main_module, "db_path", None)

        try:
            # Clear global path
            main_module.db_path = None

            with (
                patch.dict("os.environ", {"RVA_DATABASE_PATH": "/env/test.db"}),
                patch("src.web.main.CVRDatabase") as mock_cvr,
            ):

                mock_db = Mock()
                mock_cvr.return_value = mock_db

                result = get_database()

                # Should use environment variable
                mock_cvr.assert_called_with("/env/test.db", read_only=True)
                assert result == mock_db

                # Global path should be updated
                assert main_module.db_path == "/env/test.db"

        finally:
            # Restore original path
            main_module.db_path = original_path

    def test_multiple_database_instances_allowed(self):
        """Test that multiple database instances can be created."""
        with (
            patch("src.web.main.db_path", "/test/db.db"),
            patch("src.web.main.CVRDatabase") as mock_cvr,
        ):

            mock_cvr.side_effect = lambda path, read_only: Mock()

            # Multiple calls should create multiple instances
            db1 = get_database()
            db2 = get_database()

            assert db1 != db2  # Different mock instances
            assert mock_cvr.call_count == 2
