"""
STV Interface Testing.

This module tests the run_stv_tabulation interface and result structures
to ensure compatibility during PyRankVote migration.
"""

import sys
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analysis.stv import STVRound, STVTabulator
from data.database import CVRDatabase


class TestSTVInterface(unittest.TestCase):
    """Test STV tabulation interface and result structures."""

    def setUp(self):
        """Set up test fixtures."""
        self.db = CVRDatabase(":memory:")
        self._setup_test_data()

    def tearDown(self):
        """Clean up test fixtures."""
        self.db.close()

    def _setup_test_data(self):
        """Set up test data for interface testing."""
        # Create tables
        self.db.conn.execute(
            """
            CREATE TABLE candidates (
                candidate_id INTEGER,
                candidate_name TEXT,
                rank_columns INTEGER
            )
        """
        )

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
        candidates = [(1, "Alice", 6), (2, "Bob", 6), (3, "Charlie", 6)]
        self.db.conn.executemany("INSERT INTO candidates VALUES (?, ?, ?)", candidates)

        # Insert ballot data - simple 3-candidate election
        ballot_data = []

        # 50 ballots: Alice first, Bob second
        for i in range(50):
            ballot_data.extend(
                [
                    (f"ballot_{i}", 1, 1, 1, "Alice", 1, 1),
                    (f"ballot_{i}", 1, 1, 2, "Bob", 2, 1),
                ]
            )

        # 40 ballots: Bob first, Charlie second
        for i in range(40):
            ballot_data.extend(
                [
                    (f"ballot_{i+50}", 1, 1, 2, "Bob", 1, 1),
                    (f"ballot_{i+50}", 1, 1, 3, "Charlie", 2, 1),
                ]
            )

        # 30 ballots: Charlie first, Alice second
        for i in range(30):
            ballot_data.extend(
                [
                    (f"ballot_{i+90}", 1, 1, 3, "Charlie", 1, 1),
                    (f"ballot_{i+90}", 1, 1, 1, "Alice", 2, 1),
                ]
            )

        self.db.conn.executemany(
            "INSERT INTO ballots_long VALUES (?, ?, ?, ?, ?, ?, ?)", ballot_data
        )

    def test_run_stv_tabulation_return_type(self):
        """Test that run_stv_tabulation returns correct type."""
        tabulator = STVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()

        # Should return a list
        self.assertIsInstance(rounds, list)

        # Should have at least one round
        self.assertGreater(len(rounds), 0)

        # Each round should be an STVRound object
        for round_obj in rounds:
            self.assertIsInstance(round_obj, STVRound)

    def test_stv_round_structure(self):
        """Test STVRound objects have correct structure."""
        tabulator = STVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()

        first_round = rounds[0]

        # Check required attributes exist
        self.assertTrue(hasattr(first_round, "round_number"))
        self.assertTrue(hasattr(first_round, "continuing_candidates"))
        self.assertTrue(hasattr(first_round, "vote_totals"))
        self.assertTrue(hasattr(first_round, "quota"))
        self.assertTrue(hasattr(first_round, "winners_this_round"))
        self.assertTrue(hasattr(first_round, "eliminated_this_round"))
        self.assertTrue(hasattr(first_round, "transfers"))
        self.assertTrue(hasattr(first_round, "exhausted_votes"))
        self.assertTrue(hasattr(first_round, "total_continuing_votes"))

        # Check types
        self.assertIsInstance(first_round.round_number, int)
        self.assertIsInstance(first_round.continuing_candidates, list)
        self.assertIsInstance(first_round.vote_totals, dict)
        self.assertIsInstance(first_round.quota, (int, float))
        self.assertIsInstance(first_round.winners_this_round, list)
        self.assertIsInstance(first_round.eliminated_this_round, list)
        self.assertIsInstance(first_round.transfers, dict)
        self.assertIsInstance(first_round.exhausted_votes, (int, float))
        self.assertIsInstance(first_round.total_continuing_votes, (int, float))

    def test_winners_identification(self):
        """Test that winners are correctly identified."""
        tabulator = STVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()

        # Should have exactly 2 winners
        self.assertEqual(len(tabulator.winners), 2)

        # Winners should be candidate IDs
        for winner in tabulator.winners:
            self.assertIsInstance(winner, int)
            self.assertIn(winner, [1, 2, 3])  # Valid candidate IDs

    def test_quota_consistency(self):
        """Test quota calculation consistency across rounds."""
        tabulator = STVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()

        # All rounds should have the same quota (no vote exhaustion in this test)
        first_quota = rounds[0].quota
        for round_obj in rounds:
            self.assertEqual(round_obj.quota, first_quota)

        # Quota should match manual calculation
        expected_quota = int(120 / 3) + 1  # 120 total votes, 2+1 seats
        self.assertEqual(first_quota, expected_quota)

    def test_round_progression(self):
        """Test that round numbers progress correctly."""
        tabulator = STVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()

        # Round numbers should start at 1 and increment
        for i, round_obj in enumerate(rounds):
            self.assertEqual(round_obj.round_number, i + 1)

    def test_vote_totals_consistency(self):
        """Test vote totals are consistent."""
        tabulator = STVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()

        first_round = rounds[0]

        # Vote totals should include all continuing candidates
        for candidate_id in first_round.continuing_candidates:
            self.assertIn(candidate_id, first_round.vote_totals)
            self.assertGreater(first_round.vote_totals[candidate_id], 0)

        # Total votes should equal continuing votes
        total_votes = sum(first_round.vote_totals.values())
        self.assertEqual(total_votes, first_round.total_continuing_votes)

    def test_transfer_structure(self):
        """Test transfer data structure."""
        tabulator = STVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()

        for round_obj in rounds:
            # Transfers should be a dict
            self.assertIsInstance(round_obj.transfers, dict)

            # If transfers exist, they should have correct structure
            for from_candidate, transfers in round_obj.transfers.items():
                self.assertIsInstance(from_candidate, int)
                self.assertIsInstance(transfers, dict)

                for to_candidate, amount in transfers.items():
                    self.assertIsInstance(to_candidate, int)
                    self.assertIsInstance(amount, (int, float))
                    self.assertGreaterEqual(amount, 0)

    def test_different_seat_counts(self):
        """Test interface works with different seat counts."""
        for seats in [1, 2, 3]:
            tabulator = STVTabulator(self.db, seats=seats)
            rounds = tabulator.run_stv_tabulation()

            # Should complete successfully
            self.assertGreater(len(rounds), 0)

            # Should elect correct number of winners (or fewer if not enough candidates)
            expected_winners = min(seats, 3)  # We have 3 candidates
            self.assertEqual(len(tabulator.winners), expected_winners)

    def test_reproducibility(self):
        """Test that results are reproducible."""
        tabulator1 = STVTabulator(self.db, seats=2)
        rounds1 = tabulator1.run_stv_tabulation()

        tabulator2 = STVTabulator(self.db, seats=2)
        rounds2 = tabulator2.run_stv_tabulation()

        # Results should be identical
        self.assertEqual(len(rounds1), len(rounds2))
        self.assertEqual(tabulator1.winners, tabulator2.winners)

        # Round data should be identical
        for r1, r2 in zip(rounds1, rounds2):
            self.assertEqual(r1.round_number, r2.round_number)
            self.assertEqual(r1.quota, r2.quota)
            self.assertEqual(r1.winners_this_round, r2.winners_this_round)
            self.assertEqual(r1.eliminated_this_round, r2.eliminated_this_round)


if __name__ == "__main__":
    unittest.main()
