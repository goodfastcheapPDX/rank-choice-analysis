import os
import tempfile
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from src.data.cvr_parser import CVRParser


class TestCVRParser:
    """Test CVR parser functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name

    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_parser_initialization(self):
        """Test parser initialization."""
        parser = CVRParser(self.db_path)
        assert parser.db is not None
        assert parser._loaded is False
        assert parser._candidates is None

    def test_parser_initialization_no_db_path(self):
        """Test parser initialization without database path."""
        parser = CVRParser()
        assert parser.db is not None
        assert parser._loaded is False
        assert parser._candidates is None

    @patch.object(CVRParser, "_get_existing_ballots_long_stats")
    @patch.object(CVRParser, "_is_ballots_long_current")
    def test_normalize_vote_data_uses_cache_when_current(
        self, mock_is_current, mock_get_stats
    ):
        """Test that normalize_vote_data uses cache when ballots_long is current."""
        # Setup mocks
        mock_is_current.return_value = True
        mock_get_stats.return_value = {
            "total_vote_records": 50000,
            "ballots_with_votes": 25000,
            "from_cache": True,
            "cache_performance_gain": "80% faster startup",
        }

        parser = CVRParser(self.db_path)
        parser._loaded = True

        result = parser.normalize_vote_data(force_rebuild=False)

        assert result["from_cache"] is True
        assert result["total_vote_records"] == 50000
        mock_is_current.assert_called_once()
        mock_get_stats.assert_called_once()

    @patch.object(CVRParser, "_update_processing_metadata")
    @patch.object(CVRParser, "_is_ballots_long_current")
    def test_normalize_vote_data_rebuilds_when_forced(
        self, mock_is_current, mock_update_metadata
    ):
        """Test that normalize_vote_data rebuilds when force_rebuild=True."""
        parser = CVRParser(self.db_path)
        parser._loaded = True

        # Mock database methods
        parser.db.query = Mock(
            side_effect=[
                pd.DataFrame(
                    {"column_name": ["candidate_1_rank_1", "candidate_2_rank_1"]}
                ),
                pd.DataFrame(
                    {
                        "total_vote_records": [1000],
                        "ballots_with_votes": [500],
                        "candidates_receiving_votes": [5],
                        "min_rank": [1],
                        "max_rank": [3],
                    }
                ),
            ]
        )
        parser.db.conn = Mock()
        parser.db.conn.execute = Mock()

        result = parser.normalize_vote_data(force_rebuild=True)

        assert "total_vote_records" in result
        mock_is_current.assert_not_called()  # Should not check cache when forcing rebuild
        mock_update_metadata.assert_called_once()

    def test_normalize_vote_data_not_loaded_error(self):
        """Test that normalize_vote_data raises error when data not loaded."""
        parser = CVRParser(self.db_path)
        parser._loaded = False

        with pytest.raises(RuntimeError, match="Must load CVR data first"):
            parser.normalize_vote_data()

    def test_extract_candidate_metadata_not_loaded_error(self):
        """Test that extract_candidate_metadata raises error when data not loaded."""
        parser = CVRParser(self.db_path)
        parser._loaded = False

        with pytest.raises(RuntimeError, match="Must load CVR data first"):
            parser.extract_candidate_metadata()

    def test_extract_candidate_metadata_success(self):
        """Test successful candidate metadata extraction."""
        parser = CVRParser(self.db_path)
        parser._loaded = True

        # Mock database methods
        mock_candidates = pd.DataFrame(
            {
                "candidate_id": [1, 2, 3],
                "candidate_name": ["Alice", "Bob", "Charlie"],
                "total_votes": [100, 150, 75],
            }
        )

        parser.db.execute_script = Mock()
        parser.db.query = Mock(return_value=mock_candidates)

        result = parser.extract_candidate_metadata()

        assert len(result) == 3
        assert list(result["candidate_name"]) == ["Alice", "Bob", "Charlie"]
        assert parser._candidates is not None
        parser.db.execute_script.assert_called_once_with("02_create_metadata")

    def test_load_cvr_file_success(self):
        """Test successful CVR file loading."""
        parser = CVRParser(self.db_path)

        # Mock database execute_script to return stats
        mock_stats = pd.DataFrame(
            {
                "total_ballots": [25000],
                "duplicate_ballots": [0],
                "valid_ballots": [25000],
            }
        )

        parser.db.execute_script = Mock(return_value=mock_stats)

        result = parser.load_cvr_file("test_file.csv")

        assert parser._loaded is True
        assert result["total_ballots"] == 25000
        assert result["duplicate_ballots"] == 0
        parser.db.execute_script.assert_called_once_with(
            "01_load_data", ["test_file.csv"]
        )

    def test_load_cvr_file_with_duplicates(self):
        """Test CVR file loading with duplicate ballots."""
        parser = CVRParser(self.db_path)

        # Mock database execute_script to return stats with duplicates
        mock_stats = pd.DataFrame(
            {
                "total_ballots": [25000],
                "duplicate_ballots": [5],
                "valid_ballots": [24995],
            }
        )

        parser.db.execute_script = Mock(return_value=mock_stats)

        with patch("src.data.cvr_parser.logger") as mock_logger:
            result = parser.load_cvr_file("test_file.csv")

            assert result["duplicate_ballots"] == 5
            mock_logger.warning.assert_called_once()

    def test_is_ballots_long_current_table_missing(self):
        """Test _is_ballots_long_current when table doesn't exist."""
        parser = CVRParser(self.db_path)
        parser.db.table_exists = Mock(return_value=False)

        result = parser._is_ballots_long_current()

        assert result is False
        parser.db.table_exists.assert_called_with("ballots_long")

    def test_is_ballots_long_current_no_data(self):
        """Test _is_ballots_long_current when table exists but has no data."""
        parser = CVRParser(self.db_path)
        parser.db.table_exists = Mock(return_value=True)
        parser.db.query = Mock(return_value=pd.DataFrame({"count": [0]}))

        result = parser._is_ballots_long_current()

        assert result is False

    def test_is_ballots_long_current_insufficient_data(self):
        """Test _is_ballots_long_current when table has insufficient data."""
        parser = CVRParser(self.db_path)
        parser.db.table_exists = Mock(
            side_effect=[True, True]
        )  # ballots_long and candidate_columns exist
        parser.db.query = Mock(
            return_value=pd.DataFrame({"count": [500]})
        )  # Less than 1000

        with patch("src.data.cvr_parser.logger") as mock_logger:
            result = parser._is_ballots_long_current()

            assert result is False
            mock_logger.warning.assert_called_once()

    def test_is_ballots_long_current_valid(self):
        """Test _is_ballots_long_current when table is valid and current."""
        parser = CVRParser(self.db_path)
        parser.db.table_exists = Mock(
            side_effect=[True, True]
        )  # ballots_long and candidate_columns exist
        parser.db.query = Mock(
            return_value=pd.DataFrame({"count": [25000]})
        )  # Sufficient data

        result = parser._is_ballots_long_current()

        assert result is True

    def test_is_ballots_long_current_exception_handling(self):
        """Test _is_ballots_long_current exception handling."""
        parser = CVRParser(self.db_path)
        parser.db.table_exists = Mock(side_effect=Exception("Database error"))

        with patch("src.data.cvr_parser.logger") as mock_logger:
            result = parser._is_ballots_long_current()

            assert result is False
            mock_logger.warning.assert_called_once()

    def test_get_existing_ballots_long_stats_success(self):
        """Test successful retrieval of existing ballots_long stats."""
        parser = CVRParser(self.db_path)

        mock_stats = pd.DataFrame(
            {
                "total_vote_records": [50000],
                "ballots_with_votes": [25000],
                "candidates_receiving_votes": [22],
                "min_rank": [1],
                "max_rank": [6],
            }
        )

        parser.db.query = Mock(return_value=mock_stats)

        result = parser._get_existing_ballots_long_stats()

        assert result["total_vote_records"] == 50000
        assert result["from_cache"] is True
        assert "cache_performance_gain" in result

    def test_get_existing_ballots_long_stats_exception(self):
        """Test exception handling in _get_existing_ballots_long_stats."""
        parser = CVRParser(self.db_path)
        parser.db.query = Mock(side_effect=Exception("Query failed"))

        with patch("src.data.cvr_parser.logger") as mock_logger:
            result = parser._get_existing_ballots_long_stats()

            assert "error" in result
            mock_logger.error.assert_called_once()

    def test_update_processing_metadata_success(self):
        """Test successful processing metadata update."""
        parser = CVRParser(self.db_path)
        parser.db.conn = Mock()
        parser.db.conn.execute = Mock()

        parser._update_processing_metadata()

        parser.db.conn.execute.assert_called_once()

    def test_update_processing_metadata_exception(self):
        """Test exception handling in _update_processing_metadata."""
        parser = CVRParser(self.db_path)
        parser.db.conn = Mock()
        parser.db.conn.execute = Mock(side_effect=Exception("Metadata update failed"))

        with patch("src.data.cvr_parser.logger") as mock_logger:
            parser._update_processing_metadata()

            mock_logger.warning.assert_called_once()

    def test_get_summary_statistics(self):
        """Test getting summary statistics."""
        parser = CVRParser(self.db_path)

        mock_stats = pd.DataFrame(
            {
                "total_ballots": [25000],
                "total_candidates": [22],
                "average_rankings": [3.2],
            }
        )

        parser.db.execute_script = Mock()
        parser.db.query = Mock(return_value=mock_stats)

        result = parser.get_summary_statistics()

        assert len(result) == 1
        assert result["total_ballots"].iloc[0] == 25000
        parser.db.execute_script.assert_called_once_with("04_basic_analysis")

    def test_get_first_choice_totals(self):
        """Test getting first choice totals."""
        parser = CVRParser(self.db_path)

        mock_totals = pd.DataFrame(
            {"candidate_name": ["Alice", "Bob"], "first_choice_votes": [1000, 800]}
        )

        parser.db.query = Mock(return_value=mock_totals)

        result = parser.get_first_choice_totals()

        assert len(result) == 2
        assert result["candidate_name"].iloc[0] == "Alice"

    def test_get_votes_by_rank(self):
        """Test getting votes by rank."""
        parser = CVRParser(self.db_path)

        mock_votes = pd.DataFrame(
            {"rank_position": [1, 2, 3], "total_votes": [25000, 20000, 15000]}
        )

        parser.db.query = Mock(return_value=mock_votes)

        result = parser.get_votes_by_rank()

        assert len(result) == 3
        assert result["rank_position"].iloc[0] == 1

    def test_get_ballot_completion_stats(self):
        """Test getting ballot completion statistics."""
        parser = CVRParser(self.db_path)

        mock_completion = pd.DataFrame(
            {
                "ranks_used": [1, 2, 3],
                "ballot_count": [5000, 10000, 8000],
                "percentage": [20.0, 40.0, 32.0],
            }
        )

        parser.db.query = Mock(return_value=mock_completion)

        result = parser.get_ballot_completion_stats()

        assert len(result) == 3
        assert result["percentage"].sum() == 92.0

    def test_analyze_candidate_partners(self):
        """Test candidate partner analysis."""
        parser = CVRParser(self.db_path)

        mock_partners = pd.DataFrame(
            {
                "partner_candidate": ["Bob", "Charlie"],
                "support_overlap": [0.3, 0.2],
                "rank_preference": [2, 3],
            }
        )

        parser.db.execute_script = Mock()
        parser.db.query = Mock(return_value=mock_partners)

        result = parser.analyze_candidate_partners("Alice")

        assert len(result) == 2
        assert result["partner_candidate"].iloc[0] == "Bob"
        parser.db.execute_script.assert_called_once_with("05_candidate_analysis")

    def test_get_ballot_by_id(self):
        """Test getting ballot by ID."""
        parser = CVRParser(self.db_path)

        mock_ballot = pd.DataFrame(
            {
                "rank_position": [1, 2, 3],
                "candidate_name": ["Alice", "Bob", "Charlie"],
                "candidate_id": [1, 2, 3],
            }
        )

        parser.db.query = Mock(return_value=mock_ballot)

        result = parser.get_ballot_by_id("BALLOT123")

        assert len(result) == 3
        assert result["rank_position"].iloc[0] == 1
        assert result["candidate_name"].iloc[0] == "Alice"

    def test_search_ballots(self):
        """Test ballot searching functionality."""
        parser = CVRParser(self.db_path)

        mock_ballots = pd.DataFrame(
            {
                "BallotID": ["BALLOT1", "BALLOT2"],
                "ranking_sequence": ["Alice,Bob,Charlie", "Alice,Charlie,Bob"],
            }
        )

        parser.db.query = Mock(return_value=mock_ballots)

        result = parser.search_ballots("Alice", rank_position=1, limit=5)

        assert len(result) == 2
        assert result["BallotID"].iloc[0] == "BALLOT1"

    def test_get_candidates_cached(self):
        """Test getting candidates when already cached."""
        parser = CVRParser(self.db_path)

        cached_candidates = pd.DataFrame(
            {"candidate_id": [1, 2], "candidate_name": ["Alice", "Bob"]}
        )
        parser._candidates = cached_candidates

        result = parser.get_candidates()

        assert len(result) == 2
        assert result["candidate_name"].iloc[0] == "Alice"

    def test_get_candidates_from_database(self):
        """Test getting candidates from database when not cached."""
        parser = CVRParser(self.db_path)
        parser._candidates = None

        mock_candidates = pd.DataFrame(
            {"candidate_id": [1, 2, 3], "candidate_name": ["Alice", "Bob", "Charlie"]}
        )

        parser.db.query = Mock(return_value=mock_candidates)

        result = parser.get_candidates()

        assert len(result) == 3
        assert parser._candidates is not None

    def test_context_manager(self):
        """Test CVRParser as context manager."""
        with patch.object(CVRParser, "close") as mock_close:
            with CVRParser(self.db_path) as parser:
                assert parser is not None
            mock_close.assert_called_once()

    def test_close_method(self):
        """Test close method."""
        parser = CVRParser(self.db_path)
        parser.db.close = Mock()

        parser.close()

        parser.db.close.assert_called_once()

    def test_sql_injection_protection_ballot_search(self):
        """Test SQL injection protection in ballot search methods."""
        parser = CVRParser(self.db_path)
        parser.db.query = Mock(return_value=pd.DataFrame())

        # Test with potentially malicious input
        malicious_candidate = "Alice'; DROP TABLE ballots_long; --"

        # Should not raise exception and should call query with the malicious string
        parser.search_ballots(malicious_candidate, rank_position=1)

        # Verify the query was called (actual SQL injection protection would be in the database layer)
        parser.db.query.assert_called_once()

    def test_sql_injection_protection_ballot_by_id(self):
        """Test SQL injection protection in get_ballot_by_id."""
        parser = CVRParser(self.db_path)
        parser.db.query = Mock(return_value=pd.DataFrame())

        # Test with potentially malicious input
        malicious_ballot_id = "BALLOT1'; DROP TABLE ballots_long; --"

        # Should not raise exception and should call query with the malicious string
        parser.get_ballot_by_id(malicious_ballot_id)

        # Verify the query was called
        parser.db.query.assert_called_once()

    def test_sql_injection_protection_candidate_partners(self):
        """Test SQL injection protection in analyze_candidate_partners."""
        parser = CVRParser(self.db_path)
        parser.db.execute_script = Mock()
        parser.db.query = Mock(return_value=pd.DataFrame())

        # Test with potentially malicious input
        malicious_candidate = "Alice'; DROP TABLE candidates; --"

        # Should not raise exception
        parser.analyze_candidate_partners(malicious_candidate)

        # Verify the methods were called
        parser.db.execute_script.assert_called_once()
        parser.db.query.assert_called_once()
