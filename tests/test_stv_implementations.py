"""
Test suite for STV implementations.

This module contains comprehensive tests for the current STVTabulator class
to ensure correctness before migrating to PyRankVote.
"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analysis.stv import STVTabulator
from data.database import CVRDatabase


class TestSTVTabulator(unittest.TestCase):
    """Test cases for the STVTabulator class."""

    def setUp(self):
        """Set up test fixtures with in-memory database."""
        # Use in-memory database for testing
        self.db = CVRDatabase(":memory:")  # In-memory database
        self._setup_test_data()

    def tearDown(self):
        """Clean up test fixtures."""
        self.db.close()

    def _setup_test_data(self):
        """Set up test data for STV testing."""
        # Create candidates table
        self.db.conn.execute(
            """
            CREATE TABLE candidates (
                candidate_id INTEGER,
                candidate_name TEXT,
                rank_columns INTEGER
            )
        """
        )

        # Create ballots_long table
        self.db.conn.execute(
            """
            CREATE TABLE ballots_long (
                BallotID TEXT,
                PrecinctID INTEGER,
                BallotStyleID INTEGER,
                candidate_id INTEGER,
                candidate_name TEXT,
                rank_position INTEGER,
                has_vote INTEGER
            )
        """
        )

        # Insert test candidates
        candidates_data = [
            (1, "Alice", 6),
            (2, "Bob", 6),
            (3, "Charlie", 6),
            (4, "Diana", 6),
        ]

        self.db.conn.executemany(
            "INSERT INTO candidates VALUES (?, ?, ?)", candidates_data
        )

    def _insert_ballot_data(self, ballot_data):
        """Insert ballot data for testing."""
        self.db.conn.executemany(
            "INSERT INTO ballots_long VALUES (?, ?, ?, ?, ?, ?, ?)", ballot_data
        )

    def test_droop_quota_calculation(self):
        """Test Droop quota calculation."""
        tabulator = STVTabulator(self.db, seats=2)

        # Test with 100 votes, 2 seats: quota = floor(100/3) + 1 = 34
        quota = tabulator.calculate_droop_quota(100)
        self.assertEqual(quota, 34)

        # Test with 1000 votes, 3 seats: quota = floor(1000/4) + 1 = 251
        tabulator_3 = STVTabulator(self.db, seats=3)
        quota_3 = tabulator_3.calculate_droop_quota(1000)
        self.assertEqual(quota_3, 251)

    def test_simple_election_two_seats(self):
        """Test simple election with clear winners."""
        # Ballot data: Alice=40, Bob=35, Charlie=25
        # For 2 seats with 100 votes: quota = 34
        # Alice and Bob should win
        ballot_data = []

        # 40 ballots for Alice (rank 1)
        for i in range(40):
            ballot_data.append((f"ballot_{i}", 1, 1, 1, "Alice", 1, 1))

        # 35 ballots for Bob (rank 1)
        for i in range(35):
            ballot_data.append((f"ballot_{i+40}", 1, 1, 2, "Bob", 1, 1))

        # 25 ballots for Charlie (rank 1)
        for i in range(25):
            ballot_data.append((f"ballot_{i+75}", 1, 1, 3, "Charlie", 1, 1))

        self._insert_ballot_data(ballot_data)

        tabulator = STVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()

        # Check that we have winners
        self.assertEqual(len(tabulator.winners), 2)
        self.assertIn(1, tabulator.winners)  # Alice
        self.assertIn(2, tabulator.winners)  # Bob

        # Check quota calculation
        self.assertEqual(rounds[0].quota, 34)

    def test_surplus_transfer(self):
        """Test surplus vote transfer mechanism."""
        # Alice gets 50 votes (surplus of 17 over quota=34)
        # Bob gets 30 votes
        # Charlie gets 20 votes
        # Alice's surplus should transfer to help determine second winner

        ballot_data = []

        # 30 ballots: Alice first, Bob second
        for i in range(30):
            ballot_data.extend(
                [
                    (f"ballot_{i}", 1, 1, 1, "Alice", 1, 1),
                    (f"ballot_{i}", 1, 1, 2, "Bob", 2, 1),
                ]
            )

        # 20 ballots: Alice first, Charlie second
        for i in range(20):
            ballot_data.extend(
                [
                    (f"ballot_{i+30}", 1, 1, 1, "Alice", 1, 1),
                    (f"ballot_{i+30}", 1, 1, 3, "Charlie", 2, 1),
                ]
            )

        # 30 ballots: Bob only
        for i in range(30):
            ballot_data.append((f"ballot_{i+50}", 1, 1, 2, "Bob", 1, 1))

        # 20 ballots: Charlie only
        for i in range(20):
            ballot_data.append((f"ballot_{i+80}", 1, 1, 3, "Charlie", 1, 1))

        self._insert_ballot_data(ballot_data)

        tabulator = STVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()

        # Alice should win immediately
        self.assertIn(1, tabulator.winners)

        # Check that there are multiple rounds due to transfers
        self.assertGreater(len(rounds), 1)

    def test_elimination_and_transfer(self):
        """Test candidate elimination and vote transfer."""
        # Set up election where weakest candidate is eliminated
        # and their votes transfer to determine winner

        ballot_data = []

        # 35 ballots: Alice first
        for i in range(35):
            ballot_data.append((f"ballot_{i}", 1, 1, 1, "Alice", 1, 1))

        # 34 ballots: Bob first
        for i in range(34):
            ballot_data.append((f"ballot_{i+35}", 1, 1, 2, "Bob", 1, 1))

        # 20 ballots: Charlie first, Alice second
        for i in range(20):
            ballot_data.extend(
                [
                    (f"ballot_{i+69}", 1, 1, 3, "Charlie", 1, 1),
                    (f"ballot_{i+69}", 1, 1, 1, "Alice", 2, 1),
                ]
            )

        # 11 ballots: Diana first, Bob second
        for i in range(11):
            ballot_data.extend(
                [
                    (f"ballot_{i+89}", 1, 1, 4, "Diana", 1, 1),
                    (f"ballot_{i+89}", 1, 1, 2, "Bob", 2, 1),
                ]
            )

        self._insert_ballot_data(ballot_data)

        tabulator = STVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()

        # Diana should be eliminated first (11 votes)
        # Then Charlie should be eliminated (20 votes)
        # Alice should win with transfers from Charlie
        # Bob should win with transfers from Diana

        self.assertEqual(len(tabulator.winners), 2)
        self.assertIn(1, tabulator.winners)  # Alice
        self.assertIn(2, tabulator.winners)  # Bob

    def test_edge_case_single_candidate(self):
        """Test edge case with only one candidate."""
        ballot_data = []

        # 100 ballots for Alice
        for i in range(100):
            ballot_data.append((f"ballot_{i}", 1, 1, 1, "Alice", 1, 1))

        self._insert_ballot_data(ballot_data)

        tabulator = STVTabulator(self.db, seats=1)
        rounds = tabulator.run_stv_tabulation()

        self.assertEqual(len(tabulator.winners), 1)
        self.assertIn(1, tabulator.winners)

    def test_exhausted_ballots(self):
        """Test handling of exhausted ballots (no more preferences)."""
        ballot_data = []

        # Some ballots with only first choice (will be exhausted)
        for i in range(30):
            ballot_data.append((f"ballot_{i}", 1, 1, 1, "Alice", 1, 1))

        # Some ballots with second choices
        for i in range(40):
            ballot_data.extend(
                [
                    (f"ballot_{i+30}", 1, 1, 2, "Bob", 1, 1),
                    (f"ballot_{i+30}", 1, 1, 3, "Charlie", 2, 1),
                ]
            )

        # Some ballots with only third choice candidate
        for i in range(30):
            ballot_data.append((f"ballot_{i+70}", 1, 1, 4, "Diana", 1, 1))

        self._insert_ballot_data(ballot_data)

        tabulator = STVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()

        # Should handle exhausted ballots gracefully
        self.assertEqual(len(tabulator.winners), 2)


class TestSTVRoundData(unittest.TestCase):
    """Test STVRound data structure and consistency."""

    def test_stv_round_creation(self):
        """Test STVRound data structure."""
        from analysis.stv import STVRound

        round_data = STVRound(
            round_number=1,
            continuing_candidates=[1, 2, 3],
            vote_totals={1: 100.0, 2: 80.0, 3: 70.0},
            quota=63.0,
            winners_this_round=[1],
            eliminated_this_round=[],
            transfers={},
            exhausted_votes=0.0,
            total_continuing_votes=250.0,
        )

        self.assertEqual(round_data.round_number, 1)
        self.assertEqual(len(round_data.continuing_candidates), 3)
        self.assertEqual(round_data.quota, 63.0)
        self.assertEqual(round_data.winners_this_round, [1])


if __name__ == "__main__":
    unittest.main()
