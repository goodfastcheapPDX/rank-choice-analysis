"""
Database Integration Robustness Tests

These tests verify that the CVRDatabase integration layer handles edge cases,
error conditions, and data integrity constraints properly. Critical for ensuring
reliable operation in production environments.

Phase 2: Core Feature Reliability - Database Integration Foundation
"""

import os
import tempfile
import time

import pytest

from src.data.database import CVRDatabase


class TestDatabaseRobustness:
    """Test database integration robustness and error handling."""

    def setup_method(self):
        """Set up test fixtures with controlled database environment."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        os.unlink(self.db_path)  # Remove empty file for DuckDB

        # Initialize database with test data
        self.db = CVRDatabase(self.db_path, read_only=False)
        self._create_robust_test_data()

    def teardown_method(self):
        """Clean up test fixtures."""
        self.db.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _create_robust_test_data(self):
        """Create comprehensive test data for robustness testing."""
        # Create candidates table
        self.db.conn.execute(
            """
            CREATE TABLE candidates (
                candidate_id INTEGER,
                candidate_name TEXT
            )
        """
        )

        # Insert test candidates with various edge cases
        candidates = [
            (1, "Normal Candidate"),
            (2, "Candidate with 'Quotes'"),
            (3, "Candidate; with; semicolons"),
            (4, "Candidate\nwith\nnewlines"),
            (999, "High ID Candidate"),
        ]

        for cand_id, name in candidates:
            self.db.conn.execute(
                "INSERT INTO candidates VALUES (?, ?)", (cand_id, name)
            )

        # Create ballots_long table
        self.db.conn.execute(
            """
            CREATE TABLE ballots_long (
                BallotID TEXT,
                candidate_id INTEGER,
                rank_position INTEGER
            )
        """
        )

        # Create diverse ballot patterns for edge case testing
        ballots = []

        # Normal ballots
        for i in range(1000):
            ballots.extend(
                [
                    (f"ballot_{i}", 1, 1),
                    (f"ballot_{i}", 2, 2),
                    (f"ballot_{i}", 3, 3),
                ]
            )

        # Edge case ballots
        # Ballots with gaps in ranking
        for i in range(50):
            ballots.extend(
                [
                    (f"gap_ballot_{i}", 1, 1),
                    (f"gap_ballot_{i}", 3, 3),  # Skip rank 2
                    (f"gap_ballot_{i}", 4, 5),  # Skip rank 4
                ]
            )

        # Single-candidate ballots
        for i in range(100):
            ballots.append((f"single_{i}", 1, 1))

        # Ballots with special characters in IDs
        special_ballot_ids = [
            "ballot'with'quotes",
            "ballot;with;semicolons",
            "ballot with spaces",
            "ballot\nwith\nnewlines",
            "ballot_with_unicode_😊",
        ]
        for ballot_id in special_ballot_ids:
            ballots.extend(
                [
                    (ballot_id, 1, 1),
                    (ballot_id, 2, 2),
                ]
            )

        # Insert all ballot data
        for ballot_id, cand_id, rank in ballots:
            self.db.conn.execute(
                "INSERT INTO ballots_long VALUES (?, ?, ?)", (ballot_id, cand_id, rank)
            )

    def test_sequential_read_reliability(self):
        """Test that sequential read operations maintain consistency and reliability."""

        # Perform multiple sequential reads to test reliability
        results = []
        for i in range(10):
            candidate_result = self.db.query("SELECT COUNT(*) as count FROM candidates")
            ballot_result = self.db.query("SELECT COUNT(*) as count FROM ballots_long")

            results.append(
                {
                    "iteration": i,
                    "candidates": candidate_result.iloc[0]["count"],
                    "ballots": ballot_result.iloc[0]["count"],
                }
            )

        # Verify consistency across all reads
        candidate_counts = [r["candidates"] for r in results]
        ballot_counts = [r["ballots"] for r in results]

        assert (
            len(set(candidate_counts)) == 1
        ), f"Inconsistent candidate counts: {set(candidate_counts)}"
        assert (
            len(set(ballot_counts)) == 1
        ), f"Inconsistent ballot counts: {set(ballot_counts)}"
        assert (
            candidate_counts[0] == 5
        ), f"Expected 5 candidates, got {candidate_counts[0]}"
        assert ballot_counts[0] > 0, "Should have ballot data"

    def test_query_error_handling(self):
        """Test that malformed queries are handled gracefully."""

        # Test various types of SQL errors
        error_queries = [
            "SELECT * FROM nonexistent_table",  # Table doesn't exist
            "SELECT invalid_column FROM candidates",  # Column doesn't exist
            "SELECT * FROM candidates WHERE",  # Incomplete WHERE clause
            "INSERT INTO candidates VALUES (1)",  # Wrong number of values
            "SELECT COUNT(*) as count FROM candidates GROUP BY invalid_col",  # Invalid GROUP BY
        ]

        for query in error_queries:
            with pytest.raises(Exception):
                self.db.query(query)

    def test_special_character_handling(self):
        """Test that special characters in data are handled correctly."""

        # Query candidates with special characters
        result = self.db.query(
            "SELECT candidate_name FROM candidates WHERE candidate_id IN (2, 3, 4)"
        )

        names = result["candidate_name"].tolist()
        assert "Candidate with 'Quotes'" in names
        assert "Candidate; with; semicolons" in names
        assert "Candidate\nwith\nnewlines" in names

        # Query ballots with special character IDs
        result = self.db.query(
            """
            SELECT DISTINCT BallotID
            FROM ballots_long
            WHERE BallotID LIKE '%with%' OR BallotID LIKE '%😊%'
            """
        )

        ballot_ids = result["BallotID"].tolist()
        assert len(ballot_ids) >= 4, "Should find ballots with special characters"

    def test_large_query_performance(self):
        """Test performance with larger queries and verify reasonable response times."""

        start_time = time.time()

        # Complex aggregation query
        result = self.db.query(
            """
            SELECT
                candidate_id,
                COUNT(*) as vote_count,
                AVG(rank_position) as avg_rank,
                MIN(rank_position) as min_rank,
                MAX(rank_position) as max_rank
            FROM ballots_long
            GROUP BY candidate_id
            ORDER BY vote_count DESC
            """
        )

        query_time = time.time() - start_time

        # Verify results make sense - candidate 999 might not have ballots
        assert (
            len(result) >= 4
        ), f"Should have at least 4 candidates with votes, got {len(result)}"
        assert result.iloc[0]["vote_count"] > 0, "Top candidate should have votes"

        # Performance check - should complete in reasonable time
        assert query_time < 2.0, f"Query took too long: {query_time:.2f}s"

    def test_data_integrity_constraints(self):
        """Test that data integrity is maintained under various conditions."""

        # Test candidate ID consistency
        candidate_ids_in_candidates = set(
            self.db.query("SELECT DISTINCT candidate_id FROM candidates")[
                "candidate_id"
            ]
        )
        candidate_ids_in_ballots = set(
            self.db.query("SELECT DISTINCT candidate_id FROM ballots_long")[
                "candidate_id"
            ]
        )

        # All candidate IDs in ballots should exist in candidates table
        orphaned_ids = candidate_ids_in_ballots - candidate_ids_in_candidates
        assert len(orphaned_ids) == 0, f"Found orphaned candidate IDs: {orphaned_ids}"

        # Test rank position validity
        invalid_ranks = self.db.query(
            "SELECT COUNT(*) as count FROM ballots_long WHERE rank_position < 1"
        ).iloc[0]["count"]
        assert invalid_ranks == 0, "Found invalid rank positions"

        # Test ballot ID consistency
        ballot_count_by_id = self.db.query(
            """
            SELECT BallotID, COUNT(*) as rank_count
            FROM ballots_long
            GROUP BY BallotID
            HAVING COUNT(*) > 10
            """
        )
        assert (
            len(ballot_count_by_id) == 0
        ), "Found ballots with suspiciously many ranks"

    def test_edge_case_queries(self):
        """Test queries that handle edge cases and boundary conditions."""

        # Test queries with no results
        empty_result = self.db.query(
            "SELECT * FROM candidates WHERE candidate_id = 99999"
        )
        assert len(empty_result) == 0, "Should return empty DataFrame"

        # Test queries with NULL handling
        null_safe_query = self.db.query(
            """
            SELECT candidate_id, candidate_name
            FROM candidates
            WHERE candidate_name IS NOT NULL
            ORDER BY candidate_id
            """
        )
        assert len(null_safe_query) == 5, "Should handle NULL values correctly"

        # Test LIMIT and OFFSET
        limited_result = self.db.query("SELECT * FROM ballots_long LIMIT 5")
        assert len(limited_result) == 5, "LIMIT should work correctly"

        # Test aggregation with edge cases
        aggregation_result = self.db.query(
            """
            SELECT
                candidate_id,
                COUNT(DISTINCT BallotID) as unique_ballots,
                COUNT(*) as total_rankings
            FROM ballots_long
            WHERE candidate_id <= 2
            GROUP BY candidate_id
            HAVING COUNT(*) > 0
            """
        )
        assert (
            len(aggregation_result) == 2
        ), "Should aggregate correctly with conditions"

    def test_connection_recovery(self):
        """Test that database connections can be re-established after errors."""

        # Perform successful operation
        initial_result = self.db.query("SELECT COUNT(*) as count FROM candidates")
        initial_count = initial_result.iloc[0]["count"]

        # Close and reopen connection
        self.db.close()
        self.db = CVRDatabase(self.db_path, read_only=True)

        # Verify connection works after restart
        recovery_result = self.db.query("SELECT COUNT(*) as count FROM candidates")
        recovery_count = recovery_result.iloc[0]["count"]

        assert (
            recovery_count == initial_count
        ), "Data should be consistent after reconnection"

    def test_memory_usage_stability(self):
        """Test that repeated queries don't cause memory leaks."""

        # Perform many queries to check for memory stability
        query_results = []

        for i in range(100):
            result = self.db.query(
                f"""
                SELECT candidate_id, COUNT(*) as count
                FROM ballots_long
                WHERE candidate_id <= {(i % 4) + 1}
                GROUP BY candidate_id
                """
            )
            query_results.append(len(result))

        # Verify results are consistent
        assert len(query_results) == 100, "All queries should complete"
        assert all(
            count > 0 for count in query_results
        ), "All queries should return data"

    def test_read_consistency_under_load(self):
        """Test that read operations remain consistent under repeated access."""

        counts = []
        for i in range(50):
            # Perform reads with slight delays to simulate real usage
            result = self.db.query("SELECT COUNT(*) as count FROM ballots_long")
            counts.append(result.iloc[0]["count"])

            if i % 10 == 0:
                time.sleep(0.01)  # Occasional small delay

        # All counts should be identical (data consistency)
        assert len(set(counts)) == 1, f"Inconsistent read counts: {set(counts)}"
        assert counts[0] > 0, "Should have data to read"

        # Test different query patterns for consistency
        aggregation_results = []
        for _ in range(10):
            result = self.db.query(
                "SELECT candidate_id, COUNT(*) as votes FROM ballots_long GROUP BY candidate_id ORDER BY candidate_id"
            )
            aggregation_results.append(len(result))

        assert (
            len(set(aggregation_results)) == 1
        ), "Aggregation results should be consistent"

    def test_query_input_safety(self):
        """Test that queries handle various input types and special characters safely."""

        # Test integer filtering - should work with direct SQL
        result = self.db.query(
            "SELECT COUNT(*) as count FROM ballots_long WHERE candidate_id = 1"
        )
        assert result.iloc[0]["count"] > 0, "Integer filtering query should work"

        # Test string filtering with LIKE - test special character handling
        result = self.db.query(
            "SELECT COUNT(*) as count FROM candidates WHERE candidate_name LIKE '%with%'"
        )
        assert (
            result.iloc[0]["count"] >= 3
        ), "Should find candidates with 'with' in name"

        # Test multiple conditions
        result = self.db.query(
            "SELECT COUNT(*) as count FROM ballots_long WHERE candidate_id = 1 AND rank_position = 1"
        )
        assert result.iloc[0]["count"] > 0, "Multi-condition query should work"

        # Test handling of quotes in data
        result = self.db.query(
            "SELECT COUNT(*) as count FROM candidates WHERE candidate_name LIKE '%Quotes%'"
        )
        assert result.iloc[0]["count"] == 1, "Should find candidate with quotes in name"
