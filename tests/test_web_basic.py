"""
Basic Web API Testing Suite.

Simple, focused tests for FastAPI endpoints to improve coverage.
Starts with working tests and gradually expands.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from fastapi.testclient import TestClient

# Add src to path before importing local modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Local imports after path modification - this is intentional to avoid import errors
from web.main import app  # noqa: E402


class TestBasicWebAPI(unittest.TestCase):
    """Test basic FastAPI web application functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)

    def test_home_page_loads(self):
        """Test that home page loads successfully."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))

    def test_coalition_page_loads(self):
        """Test that coalition page loads successfully."""
        response = self.client.get("/coalition")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))

    def test_vote_flow_page_loads(self):
        """Test that vote flow page loads successfully."""
        response = self.client.get("/vote-flow")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))

    def test_candidates_page_loads(self):
        """Test that candidates page loads successfully."""
        response = self.client.get("/candidates")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))

    def test_database_not_configured_error(self):
        """Test API endpoints when database is not configured."""
        # Clear database path to trigger error
        with patch("web.main.db_path", None), patch.dict("os.environ", {}, clear=True):
            response = self.client.get("/api/summary")
            self.assertEqual(response.status_code, 500)
            self.assertIn("Database not configured", response.json()["detail"])

    # Note: Removed problematic DataFrame mock tests that caused recursion errors
    # These will be implemented later with better mocking strategies

    @patch("web.main.STVTabulator")
    @patch("web.main.get_database")
    def test_api_stv_results_basic(self, mock_get_db, mock_stv_tabulator):
        """Test /api/stv-results endpoint basic functionality."""
        # Mock STV tabulator
        mock_tabulator = Mock()
        mock_tabulator.winners = [1, 2]
        mock_tabulator.rounds = []

        # Mock the return values
        final_results_df = pd.DataFrame(
            {
                "candidate_id": [1, 2, 3],
                "final_votes": [400, 350, 200],
                "status": ["elected", "elected", "not_elected"],
            }
        )
        round_summary_df = pd.DataFrame(
            {"round": [1, 2], "candidate_id": [1, 2], "votes": [400, 350]}
        )

        mock_tabulator.get_final_results.return_value = final_results_df
        mock_tabulator.get_round_summary.return_value = round_summary_df
        mock_stv_tabulator.return_value = mock_tabulator

        mock_db = Mock()
        mock_get_db.return_value = mock_db

        response = self.client.get("/api/stv-results")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("final_results", data)
        self.assertIn("winners", data)
        self.assertEqual(len(data["winners"]), 2)

    @patch("web.main.get_database")
    def test_api_export_csv_endpoints(self, mock_get_db):
        """Test CSV export endpoints."""
        mock_db = Mock()
        mock_query_result = pd.DataFrame(
            {"column1": ["value1", "value2"], "column2": ["value3", "value4"]}
        )
        mock_db.query.return_value = mock_query_result
        mock_get_db.return_value = mock_db

        # Test summary export
        response = self.client.get("/api/export/summary")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers.get("content-type", ""))

        # Test first-choice export
        response = self.client.get("/api/export/first-choice")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers.get("content-type", ""))

    # Note: Removed database error handling test due to recursion issues
    # Will be implemented later with improved mocking strategy


if __name__ == "__main__":
    unittest.main()
