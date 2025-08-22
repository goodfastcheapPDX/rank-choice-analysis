"""
Critical path integration tests for mathematical correctness.

These tests verify the most essential functions that guarantee electoral
mathematical accuracy and platform credibility. Failure of any test in
this module indicates a critical system failure.
"""

import pytest

from src.analysis.candidate_metrics import CandidateMetrics
from src.analysis.coalition import CoalitionAnalyzer
from src.analysis.stv_pyrankvote import PyRankVoteSTVTabulator
from src.data.database import CVRDatabase


@pytest.mark.integration
@pytest.mark.critical
class TestCriticalPaths:
    """Critical path tests that must pass for platform credibility."""

    @pytest.fixture
    def electoral_test_data(self):
        """Create test database with realistic electoral mathematics data."""
        # Create temporary database file
        import os
        import tempfile

        temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db_file.close()
        db_path = temp_db_file.name
        os.unlink(db_path)  # Remove empty file for DuckDB

        db = CVRDatabase(db_path, read_only=False)

        # Create minimal schema for mathematical testing
        db.conn.execute(
            """
            CREATE TABLE candidates (
                candidate_id INTEGER PRIMARY KEY,
                candidate_name TEXT,
                rank_columns INTEGER
            )
        """
        )

        db.conn.execute(
            """
            CREATE TABLE ballots_long (
                BallotID TEXT,
                PrecinctID INTEGER,
                candidate_id INTEGER,
                rank_position INTEGER
            )
        """
        )

        # Insert candidates for 3-seat election (like Portland)
        candidates = [
            (1, "Candidate A", 6),
            (2, "Candidate B", 6),
            (3, "Candidate C", 6),
            (4, "Candidate D", 6),
            (5, "Candidate E", 6),
        ]
        for cid, name, cols in candidates:
            db.conn.execute(
                "INSERT INTO candidates VALUES (?, ?, ?)", (cid, name, cols)
            )

        # Insert ballots with known mathematical properties
        test_ballots = self._generate_mathematical_test_ballots()
        for bid, pid, cid, rank in test_ballots:
            db.conn.execute(
                "INSERT INTO ballots_long VALUES (?, ?, ?, ?)", (bid, pid, cid, rank)
            )

        yield db

        # Cleanup
        db.close()
        if os.path.exists(db_path):
            os.unlink(db_path)

    def _generate_mathematical_test_ballots(self):
        """Generate ballots with known mathematical properties for testing."""
        ballots = []
        ballot_id = 1

        # Scenario 1: Clear winner pattern (Candidate A should win easily)
        for _ in range(400):  # 40% of 1000 ballots
            ballots.extend(
                [
                    (f"B{ballot_id:04d}", 1, 1, 1),  # A first
                    (f"B{ballot_id:04d}", 1, 2, 2),  # B second
                    (f"B{ballot_id:04d}", 1, 3, 3),  # C third
                ]
            )
            ballot_id += 1

        # Scenario 2: Strong coalition (B and C should transfer to each other)
        for _ in range(200):  # 20%
            ballots.extend(
                [
                    (f"B{ballot_id:04d}", 2, 2, 1),  # B first
                    (f"B{ballot_id:04d}", 2, 3, 2),  # C second
                    (f"B{ballot_id:04d}", 2, 1, 3),  # A third
                ]
            )
            ballot_id += 1

        for _ in range(200):  # 20%
            ballots.extend(
                [
                    (f"B{ballot_id:04d}", 2, 3, 1),  # C first
                    (f"B{ballot_id:04d}", 2, 2, 2),  # B second
                    (f"B{ballot_id:04d}", 2, 1, 3),  # A third
                ]
            )
            ballot_id += 1

        # Scenario 3: Weak candidates that should be eliminated
        for _ in range(100):  # 10%
            ballots.extend(
                [
                    (f"B{ballot_id:04d}", 3, 4, 1),  # D first
                    (f"B{ballot_id:04d}", 3, 1, 2),  # A second
                    (f"B{ballot_id:04d}", 3, 2, 3),  # B third
                ]
            )
            ballot_id += 1

        for _ in range(100):  # 10%
            ballots.extend(
                [
                    (f"B{ballot_id:04d}", 3, 5, 1),  # E first
                    (f"B{ballot_id:04d}", 3, 3, 2),  # C second
                    (f"B{ballot_id:04d}", 3, 2, 3),  # B third
                ]
            )
            ballot_id += 1

        return ballots

    def test_complete_stv_tabulation_accuracy(self, electoral_test_data):
        """CRITICAL: Verify complete STV tabulation produces mathematically valid results."""
        stv = PyRankVoteSTVTabulator(electoral_test_data, seats=3)

        # Run complete STV tabulation
        rounds = stv.run_stv_tabulation()

        # Convert to expected format for compatibility
        results = {
            "winners": stv.winners,
            "rounds": [],
            "quota": rounds[0].quota if rounds else 0,
        }

        # Convert rounds to expected format
        for round_obj in rounds:
            round_data = {
                "round": round_obj.round_number,
                "candidates": [],
                "exhausted_votes": round_obj.exhausted_votes,
            }
            for candidate_id, votes in round_obj.vote_totals.items():
                round_data["candidates"].append(
                    {"candidate_id": candidate_id, "votes": votes}
                )
            results["rounds"].append(round_data)

        # Critical mathematical properties must hold
        assert len(results["winners"]) == 3, "Must elect exactly 3 winners"
        assert len(results["rounds"]) > 0, "Must have elimination rounds"

        # Verify vote conservation across all rounds
        total_initial_votes = sum(
            candidate["votes"] for candidate in results["rounds"][0]["candidates"]
        )

        for round_data in results["rounds"]:
            round_total = sum(
                candidate["votes"] for candidate in round_data["candidates"]
            ) + round_data.get("exhausted_votes", 0)

            # Allow small floating point differences
            assert (
                abs(round_total - total_initial_votes) < 0.01
            ), f"Vote conservation violated in round {round_data['round']}"

        # Verify quota calculation
        quota = results["quota"]
        expected_quota = total_initial_votes / (3 + 1) + 0.01  # Droop quota
        # Different implementations may use different quota formulas (floor vs int)
        # Allow more tolerance for quota calculation differences
        assert (
            abs(quota - expected_quota) < 1.5
        ), f"Quota calculation incorrect: quota={quota}, expected={expected_quota}"

        # Winners must have achieved quota or be last remaining
        final_round = results["rounds"][-1]
        winner_votes = []
        for candidate in final_round["candidates"]:
            if candidate["candidate_id"] in results["winners"]:
                winner_votes.append(candidate["votes"])

        # At least some winners should have quota (unless last remaining)
        winners_with_quota = sum(1 for votes in winner_votes if votes >= quota)
        assert winners_with_quota > 0, "At least one winner must achieve quota"

    def test_coalition_analysis_mathematical_consistency(self, electoral_test_data):
        """CRITICAL: Verify coalition analysis maintains mathematical consistency."""
        analyzer = CoalitionAnalyzer(electoral_test_data)

        # Test pairwise affinity calculations - get all pairs
        all_affinities = analyzer.calculate_pairwise_affinity(min_shared_ballots=0)

        if len(all_affinities) > 0:
            # Test mathematical bounds for all affinities
            for affinity in all_affinities:
                # Mathematical bounds must be respected
                assert (
                    0.0 <= affinity.affinity_score <= 1.0
                ), f"Affinity score must be between 0 and 1 for pair ({affinity.candidate_1}, {affinity.candidate_2})"
                assert (
                    affinity.shared_ballots >= 0
                ), f"Shared ballots cannot be negative for pair ({affinity.candidate_1}, {affinity.candidate_2})"
                assert (
                    0.0 <= affinity.overlap_percentage <= 100.0
                ), f"Overlap percentage must be between 0 and 100 for pair ({affinity.candidate_1}, {affinity.candidate_2})"
                assert (
                    affinity.total_ballots_1 >= 0
                ), f"Total ballots 1 cannot be negative for pair ({affinity.candidate_1}, {affinity.candidate_2})"
                assert (
                    affinity.total_ballots_2 >= 0
                ), f"Total ballots 2 cannot be negative for pair ({affinity.candidate_1}, {affinity.candidate_2})"

            # Find strong and weak coalitions based on known test data structure
            # Candidates 2 and 3 should have strong affinity (from test data design)
            strong_pairs = [
                a
                for a in all_affinities
                if (a.candidate_1, a.candidate_2) in [(2, 3), (3, 2)]
            ]
            weak_pairs = [
                a
                for a in all_affinities
                if (a.candidate_1, a.candidate_2) in [(1, 4), (4, 1), (1, 5), (5, 1)]
            ]

            if strong_pairs and weak_pairs:
                # Strong coalition should have higher average affinity than weak
                strong_avg = sum(a.affinity_score for a in strong_pairs) / len(
                    strong_pairs
                )
                weak_avg = sum(a.affinity_score for a in weak_pairs) / len(weak_pairs)

                assert (
                    strong_avg > weak_avg
                ), f"Strong coalitions must have higher affinity than weak ones: {strong_avg} vs {weak_avg}"

    def test_transfer_efficiency_conservation_laws(self, electoral_test_data):
        """CRITICAL: Verify transfer efficiency respects vote conservation."""
        metrics = CandidateMetrics(electoral_test_data)

        # Get all candidates to test transfer efficiency
        candidates = electoral_test_data.query("SELECT candidate_id FROM candidates")

        for _, row in candidates.iterrows():
            candidate_id = row["candidate_id"]
            efficiency = metrics.get_transfer_efficiency_analysis(candidate_id)

            if efficiency is not None:
                # Mathematical bounds must be respected
                assert (
                    0.0 <= efficiency.transfer_efficiency_rate <= 1.0
                ), f"Transfer efficiency rate out of bounds for candidate {candidate_id}"

                assert (
                    efficiency.total_transferable_votes >= 0
                ), f"Transferable votes cannot be negative for candidate {candidate_id}"

                assert (
                    efficiency.successful_transfers >= 0
                ), f"Successful transfers cannot be negative for candidate {candidate_id}"

                assert (
                    efficiency.successful_transfers
                    <= efficiency.total_transferable_votes
                ), f"Cannot transfer more votes than available for candidate {candidate_id}"

                # If there are transferable votes, efficiency should be calculable
                if efficiency.total_transferable_votes > 0:
                    calculated_rate = (
                        efficiency.successful_transfers
                        / efficiency.total_transferable_votes
                    )
                    assert (
                        abs(efficiency.transfer_efficiency_rate - calculated_rate)
                        < 0.01
                    ), f"Transfer efficiency calculation inconsistent for candidate {candidate_id}"

    def test_candidate_metrics_bounds_validation(self, electoral_test_data):
        """CRITICAL: Verify all candidate metrics stay within mathematical bounds."""
        metrics = CandidateMetrics(electoral_test_data)

        # Get all candidates for comprehensive testing
        candidates = electoral_test_data.query("SELECT candidate_id FROM candidates")

        for _, row in candidates.iterrows():
            candidate_id = row["candidate_id"]
            profile = metrics.get_comprehensive_candidate_profile(candidate_id)

            if profile is not None:
                # Critical bounds that must never be violated
                assert (
                    0.0 <= profile.first_choice_percentage <= 100.0
                ), f"First choice percentage out of bounds for candidate {candidate_id}"

                assert (
                    0.0 <= profile.vote_strength_index <= 1.0
                ), f"Vote strength index out of bounds for candidate {candidate_id}"

                assert (
                    0.0 <= profile.cross_camp_appeal <= 1.0
                ), f"Cross camp appeal out of bounds for candidate {candidate_id}"

                assert (
                    0.0 <= profile.transfer_efficiency <= 1.0
                ), f"Transfer efficiency out of bounds for candidate {candidate_id}"

                assert (
                    0.0 <= profile.ranking_consistency <= 1.0
                ), f"Ranking consistency out of bounds for candidate {candidate_id}"

                # Logical consistency checks
                assert (
                    profile.first_choice_votes <= profile.total_ballots
                ), f"Cannot have more first choice votes than total ballots for candidate {candidate_id}"

                # Percentage calculation consistency
                if profile.total_ballots > 0:
                    expected_percentage = (
                        profile.first_choice_votes / profile.total_ballots
                    ) * 100
                    assert (
                        abs(profile.first_choice_percentage - expected_percentage)
                        < 0.01
                    ), f"First choice percentage calculation inconsistent for candidate {candidate_id}"

    def test_stv_mathematical_invariants(self, electoral_test_data):
        """CRITICAL: Verify STV process maintains fundamental mathematical invariants."""
        stv = PyRankVoteSTVTabulator(electoral_test_data, seats=3)
        rounds = stv.run_stv_tabulation()

        # Convert to expected format for compatibility
        results = {
            "winners": stv.winners,
            "rounds": [],
            "quota": rounds[0].quota if rounds else 0,
        }

        for round_obj in rounds:
            round_data = {
                "round": round_obj.round_number,
                "candidates": [],
                "exhausted_votes": round_obj.exhausted_votes,
            }
            for candidate_id, votes in round_obj.vote_totals.items():
                round_data["candidates"].append(
                    {"candidate_id": candidate_id, "votes": votes}
                )
            results["rounds"].append(round_data)

        # Invariant 1: Total votes never increase during tabulation
        initial_total = sum(c["votes"] for c in results["rounds"][0]["candidates"])

        for round_data in results["rounds"]:
            current_total = sum(
                c["votes"] for c in round_data["candidates"]
            ) + round_data.get("exhausted_votes", 0)

            assert (
                current_total <= initial_total + 0.01
            ), f"Vote total increased in round {round_data['round']}"

        # Invariant 2: Winners must be among candidates with highest final votes
        # (unless eliminated candidate had higher votes - this is valid in STV)
        final_round = results["rounds"][-1]
        final_candidates = {
            c["candidate_id"]: c["votes"] for c in final_round["candidates"]
        }

        for winner_id in results["winners"]:
            # Winner must either be in final round or have been elected earlier
            if winner_id in final_candidates:
                winner_votes = final_candidates[winner_id]
                # Count how many non-winners have more votes
                higher_vote_non_winners = sum(
                    1
                    for cid, votes in final_candidates.items()
                    if cid not in results["winners"] and votes > winner_votes
                )
                # Should be at most (total_candidates - num_seats) candidates with higher votes
                remaining_seats = 3 - len(
                    [w for w in results["winners"] if w in final_candidates]
                )
                assert (
                    higher_vote_non_winners <= remaining_seats
                ), f"Winner {winner_id} has insufficient votes in final round"

        # Invariant 3: Quota calculation must be mathematically correct
        expected_quota = initial_total / (3 + 1) + 0.01  # Droop quota formula
        # Allow tolerance for different Droop quota implementations (int vs floor)
        assert (
            abs(results["quota"] - expected_quota) < 1.5
        ), f"Quota calculation violates Droop quota formula: got {results['quota']}, expected {expected_quota}"

    def test_database_mathematical_consistency(self, electoral_test_data):
        """CRITICAL: Verify database operations maintain mathematical consistency."""
        # Test that query results are mathematically consistent

        # Total ballots should equal sum of ballots per candidate
        total_ballots_query = electoral_test_data.query(
            """
            SELECT COUNT(DISTINCT BallotID) as total_ballots
            FROM ballots_long
        """
        )
        total_ballots = total_ballots_query["total_ballots"].iloc[0]

        # Sum of first choice votes should equal total ballots
        first_choice_query = electoral_test_data.query(
            """
            SELECT COUNT(*) as first_choice_total
            FROM ballots_long
            WHERE rank_position = 1
        """
        )
        first_choice_total = first_choice_query["first_choice_total"].iloc[0]

        assert (
            total_ballots == first_choice_total
        ), "Total ballots must equal sum of first choice votes"

        # Each ballot should have exactly one first choice vote
        ballot_first_choices = electoral_test_data.query(
            """
            SELECT BallotID, COUNT(*) as first_choices
            FROM ballots_long
            WHERE rank_position = 1
            GROUP BY BallotID
        """
        )

        for _, row in ballot_first_choices.iterrows():
            assert (
                row["first_choices"] == 1
            ), f"Ballot {row['BallotID']} has {row['first_choices']} first choice votes, should have exactly 1"

        # No ballot should have duplicate ranks for different candidates
        duplicate_ranks = electoral_test_data.query(
            """
            SELECT BallotID, rank_position, COUNT(*) as duplicate_count
            FROM ballots_long
            GROUP BY BallotID, rank_position
            HAVING COUNT(*) > 1
        """
        )

        assert (
            len(duplicate_ranks) == 0
        ), f"Found {len(duplicate_ranks)} ballots with duplicate ranks"

    def test_error_handling_mathematical_edge_cases(self):
        """CRITICAL: Verify system handles mathematical edge cases gracefully."""
        import os
        import tempfile

        temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db_file.close()
        db_path = temp_db_file.name
        os.unlink(db_path)  # Remove empty file for DuckDB

        db = CVRDatabase(db_path, read_only=False)

        # Test with minimal data
        db.conn.execute(
            "CREATE TABLE candidates (candidate_id INTEGER, candidate_name TEXT, rank_columns INTEGER)"
        )
        db.conn.execute(
            "CREATE TABLE ballots_long (BallotID TEXT, PrecinctID INTEGER, candidate_id INTEGER, rank_position INTEGER)"
        )

        # Insert single candidate
        db.conn.execute("INSERT INTO candidates VALUES (1, 'Only Candidate', 6)")
        db.conn.execute("INSERT INTO ballots_long VALUES ('B001', 1, 1, 1)")

        # STV should handle single candidate gracefully
        stv = PyRankVoteSTVTabulator(db, seats=1)
        stv.run_stv_tabulation()
        results = {"winners": stv.winners}

        assert len(results["winners"]) == 1, "Single candidate should win"
        assert results["winners"][0] == 1, "Single candidate should be winner"

        # Coalition analysis should handle single candidate
        analyzer = CoalitionAnalyzer(db)
        coalitions = analyzer.identify_coalitions()

        assert isinstance(
            coalitions, list
        ), "Coalition analysis should return list even with one candidate"
        assert len(coalitions) == 0, "No coalitions possible with single candidate"

        # Candidate metrics should handle single candidate
        metrics = CandidateMetrics(db)
        profile = metrics.get_comprehensive_candidate_profile(1)

        assert profile is not None, "Should generate profile for single candidate"
        assert (
            profile.first_choice_percentage == 100.0
        ), "Single candidate should have 100% first choice"

        # Cleanup
        db.close()
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.mark.slow
    def test_performance_mathematical_operations(self, electoral_test_data):
        """CRITICAL: Verify mathematical operations complete within acceptable time."""
        import time

        # STV tabulation should complete quickly even with realistic data
        stv = PyRankVoteSTVTabulator(electoral_test_data, seats=3)

        start_time = time.time()
        stv.run_stv_tabulation()
        stv_time = time.time() - start_time

        assert (
            stv_time < 5.0
        ), f"STV tabulation took {stv_time:.2f}s, should be under 5s"

        # Coalition analysis should complete reasonably quickly
        analyzer = CoalitionAnalyzer(electoral_test_data)

        start_time = time.time()
        # Test most expensive operations
        analyzer.identify_coalitions()
        analyzer.detect_coalition_clusters()
        coalition_time = time.time() - start_time

        assert (
            coalition_time < 10.0
        ), f"Coalition analysis took {coalition_time:.2f}s, should be under 10s"

        # Candidate metrics should complete reasonably quickly
        metrics = CandidateMetrics(electoral_test_data)

        start_time = time.time()
        profiles = []
        for candidate_id in range(1, 6):
            profile = metrics.get_comprehensive_candidate_profile(candidate_id)
            if profile:
                profiles.append(profile)
        metrics_time = time.time() - start_time

        assert (
            metrics_time < 15.0
        ), f"Candidate metrics took {metrics_time:.2f}s, should be under 15s"
        assert len(profiles) > 0, "Should generate at least one candidate profile"
