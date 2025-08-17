"""
PyRankVote STV Implementation Interface Testing.

This module tests that the PyRankVote implementation maintains
compatibility with the original STV interface.
"""

import unittest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.database import CVRDatabase
from analysis.stv_pyrankvote import PyRankVoteSTVTabulator
from analysis.stv import STVRound


class TestPyRankVoteInterface(unittest.TestCase):
    """Test PyRankVote STV implementation interface compatibility."""
    
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
        self.db.conn.execute("""
            CREATE TABLE candidates (
                candidate_id INTEGER,
                candidate_name TEXT,
                rank_columns INTEGER
            )
        """)
        
        self.db.conn.execute("""
            CREATE TABLE ballots_long (
                BallotID TEXT,
                PrecinctID INTEGER,
                BallotStyleID INTEGER,
                candidate_id INTEGER,
                candidate_name TEXT,
                rank_position INTEGER,
                has_vote INTEGER
            )
        """)
        
        # Insert test candidates
        candidates = [
            (1, "Alice", 6),
            (2, "Bob", 6),
            (3, "Charlie", 6)
        ]
        self.db.conn.executemany("INSERT INTO candidates VALUES (?, ?, ?)", candidates)
        
        # Insert ballot data - simple 3-candidate election
        ballot_data = []
        
        # 50 ballots: Alice first, Bob second
        for i in range(50):
            ballot_data.extend([
                (f"ballot_{i}", 1, 1, 1, "Alice", 1, 1),
                (f"ballot_{i}", 1, 1, 2, "Bob", 2, 1)
            ])
            
        # 40 ballots: Bob first, Charlie second
        for i in range(40):
            ballot_data.extend([
                (f"ballot_{i+50}", 1, 1, 2, "Bob", 1, 1),
                (f"ballot_{i+50}", 1, 1, 3, "Charlie", 2, 1)
            ])
            
        # 30 ballots: Charlie first, Alice second
        for i in range(30):
            ballot_data.extend([
                (f"ballot_{i+90}", 1, 1, 3, "Charlie", 1, 1),
                (f"ballot_{i+90}", 1, 1, 1, "Alice", 2, 1)
            ])
            
        self.db.conn.executemany("INSERT INTO ballots_long VALUES (?, ?, ?, ?, ?, ?, ?)", ballot_data)
        
    def test_run_stv_tabulation_return_type(self):
        """Test that run_stv_tabulation returns correct type."""
        tabulator = PyRankVoteSTVTabulator(self.db, seats=2)
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
        tabulator = PyRankVoteSTVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()
        
        first_round = rounds[0]
        
        # Check required attributes exist
        self.assertTrue(hasattr(first_round, 'round_number'))
        self.assertTrue(hasattr(first_round, 'continuing_candidates'))
        self.assertTrue(hasattr(first_round, 'vote_totals'))
        self.assertTrue(hasattr(first_round, 'quota'))
        self.assertTrue(hasattr(first_round, 'winners_this_round'))
        self.assertTrue(hasattr(first_round, 'eliminated_this_round'))
        self.assertTrue(hasattr(first_round, 'transfers'))
        self.assertTrue(hasattr(first_round, 'exhausted_votes'))
        self.assertTrue(hasattr(first_round, 'total_continuing_votes'))
        
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
        tabulator = PyRankVoteSTVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()
        
        # Should have exactly 2 winners
        self.assertEqual(len(tabulator.winners), 2)
        
        # Winners should be candidate IDs
        for winner in tabulator.winners:
            self.assertIsInstance(winner, int)
            self.assertIn(winner, [1, 2, 3])  # Valid candidate IDs
            
    def test_quota_consistency(self):
        """Test quota calculation consistency."""
        tabulator = PyRankVoteSTVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()
        
        # All rounds should have the same quota
        first_quota = rounds[0].quota
        for round_obj in rounds:
            self.assertEqual(round_obj.quota, first_quota)
            
        # Quota should match manual calculation
        expected_quota = int(120 / 3) + 1  # 120 total votes, 2+1 seats
        self.assertEqual(first_quota, expected_quota)
        
    def test_round_progression(self):
        """Test that round numbers progress correctly."""
        tabulator = PyRankVoteSTVTabulator(self.db, seats=2)
        rounds = tabulator.run_stv_tabulation()
        
        # Round numbers should start at 1 and increment
        for i, round_obj in enumerate(rounds):
            self.assertEqual(round_obj.round_number, i + 1)
            
    def test_different_seat_counts(self):
        """Test interface works with different seat counts."""
        for seats in [1, 2, 3]:
            tabulator = PyRankVoteSTVTabulator(self.db, seats=seats)
            rounds = tabulator.run_stv_tabulation()
            
            # Should complete successfully
            self.assertGreater(len(rounds), 0)
            
            # Should elect correct number of winners (or fewer if not enough candidates)
            expected_winners = min(seats, 3)  # We have 3 candidates
            self.assertEqual(len(tabulator.winners), expected_winners)
            
    def test_reproducibility(self):
        """Test that results are reproducible."""
        tabulator1 = PyRankVoteSTVTabulator(self.db, seats=2)
        rounds1 = tabulator1.run_stv_tabulation()
        
        tabulator2 = PyRankVoteSTVTabulator(self.db, seats=2)
        rounds2 = tabulator2.run_stv_tabulation()
        
        # Results should be identical
        self.assertEqual(len(rounds1), len(rounds2))
        self.assertEqual(tabulator1.winners, tabulator2.winners)
        
        # Round data should be identical (basic check since PyRankVote has limited round data)
        for r1, r2 in zip(rounds1, rounds2):
            self.assertEqual(r1.round_number, r2.round_number)
            self.assertEqual(r1.quota, r2.quota)
            self.assertEqual(r1.winners_this_round, r2.winners_this_round)
            
    def test_api_methods_exist(self):
        """Test that all expected API methods exist and work."""
        tabulator = PyRankVoteSTVTabulator(self.db, seats=2)
        
        # Test methods exist
        self.assertTrue(hasattr(tabulator, 'run_stv_tabulation'))
        self.assertTrue(hasattr(tabulator, 'get_round_summary'))
        self.assertTrue(hasattr(tabulator, 'get_final_results'))
        self.assertTrue(hasattr(tabulator, 'get_initial_vote_counts'))
        self.assertTrue(hasattr(tabulator, 'calculate_droop_quota'))
        
        # Test methods return expected types
        rounds = tabulator.run_stv_tabulation()
        self.assertIsInstance(rounds, list)
        
        summary = tabulator.get_round_summary()
        self.assertIsNotNone(summary)
        
        results = tabulator.get_final_results()
        self.assertIsNotNone(results)
        
        initial = tabulator.get_initial_vote_counts()
        self.assertIsNotNone(initial)
        
        quota = tabulator.calculate_droop_quota(120)
        self.assertIsInstance(quota, (int, float))


if __name__ == '__main__':
    unittest.main()