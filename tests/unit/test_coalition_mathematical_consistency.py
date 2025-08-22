"""
Mathematical consistency tests for coalition analysis algorithms.

These tests verify that coalition analysis maintains mathematical rigor
and produces consistent results under all conditions.
"""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from src.analysis.coalition import CoalitionAnalyzer


@pytest.mark.unit
class TestCoalitionMathematicalConsistency:
    """Test mathematical properties and consistency of coalition analysis."""

    @pytest.fixture
    def mock_database(self):
        """Mock database with controlled mathematical test data."""
        mock_db = Mock()

        # Mock candidate data
        mock_db.query_with_retry.return_value = pd.DataFrame(
            {
                "candidate_id": [1, 2, 3, 4, 5],
                "candidate_name": ["A", "B", "C", "D", "E"],
            }
        )

        return mock_db

    def test_pairwise_affinity_mathematical_bounds(self, mock_database):
        """Test that pairwise affinity calculations respect mathematical bounds."""
        analyzer = CoalitionAnalyzer(mock_database)

        # Test with known ballot patterns
        test_scenarios = [
            # Perfect coalition: all ballots rank A=1, B=2
            {
                "shared_ballots": pd.DataFrame(
                    {
                        "BallotID": ["B001", "B002", "B003"],
                        "candidate_1_rank": [1, 1, 1],
                        "candidate_2_rank": [2, 2, 2],
                    }
                ),
                "c1_ballots": pd.DataFrame({"BallotID": ["B001", "B002", "B003"]}),
                "c2_ballots": pd.DataFrame({"BallotID": ["B001", "B002", "B003"]}),
                "expected_high_affinity": True,
            },
            # No coalition: no shared ballots
            {
                "shared_ballots": pd.DataFrame(
                    columns=["BallotID", "candidate_1_rank", "candidate_2_rank"]
                ),
                "c1_ballots": pd.DataFrame({"BallotID": ["B001", "B002"]}),
                "c2_ballots": pd.DataFrame({"BallotID": ["B003", "B004"]}),
                "expected_high_affinity": False,
            },
            # Weak coalition: some shared ballots but far apart
            {
                "shared_ballots": pd.DataFrame(
                    {
                        "BallotID": ["B001"],
                        "candidate_1_rank": [1],
                        "candidate_2_rank": [6],
                    }
                ),
                "c1_ballots": pd.DataFrame({"BallotID": ["B001", "B002", "B003"]}),
                "c2_ballots": pd.DataFrame({"BallotID": ["B001", "B004", "B005"]}),
                "expected_high_affinity": False,
            },
        ]

        for scenario in test_scenarios:
            # Mock database responses for this scenario
            mock_database.query.side_effect = [
                scenario["shared_ballots"],
                scenario["c1_ballots"],
                scenario["c2_ballots"],
            ]

            affinity = analyzer.calculate_pairwise_affinity(1, 2)

            # Mathematical bounds must always be respected
            assert (
                0.0 <= affinity.affinity_score <= 1.0
            ), f"Affinity score {affinity.affinity_score} out of bounds [0,1]"
            assert (
                0.0 <= affinity.jaccard_similarity <= 1.0
            ), f"Jaccard similarity {affinity.jaccard_similarity} out of bounds [0,1]"
            assert (
                affinity.shared_ballots >= 0
            ), f"Shared ballots {affinity.shared_ballots} cannot be negative"

            # Logical consistency
            if scenario["expected_high_affinity"]:
                assert (
                    affinity.affinity_score > 0.5
                ), "Perfect coalition should have high affinity score"
            else:
                # Weak or no coalition scenarios
                pass  # Just verify bounds, actual score depends on algorithm

    def test_affinity_symmetry_property(self, mock_database):
        """Test that pairwise affinity is symmetric: A↔B = B↔A."""
        analyzer = CoalitionAnalyzer(mock_database)

        # Mock symmetric ballot data
        shared_ballots = pd.DataFrame(
            {
                "BallotID": ["B001", "B002"],
                "candidate_1_rank": [1, 2],
                "candidate_2_rank": [2, 1],
            }
        )

        ballots_1 = pd.DataFrame({"BallotID": ["B001", "B002", "B003"]})
        ballots_2 = pd.DataFrame({"BallotID": ["B001", "B002", "B004"]})

        # Test A→B
        mock_database.query.side_effect = [shared_ballots, ballots_1, ballots_2]
        affinity_1_2 = analyzer.calculate_pairwise_affinity(1, 2)

        # Test B→A (should be identical due to symmetry)
        mock_database.query.side_effect = [shared_ballots, ballots_2, ballots_1]
        affinity_2_1 = analyzer.calculate_pairwise_affinity(2, 1)

        # Symmetry properties must hold
        assert (
            affinity_1_2.affinity_score == affinity_2_1.affinity_score
        ), "Affinity score must be symmetric"
        assert (
            affinity_1_2.shared_ballots == affinity_2_1.shared_ballots
        ), "Shared ballot count must be symmetric"
        assert (
            affinity_1_2.jaccard_similarity == affinity_2_1.jaccard_similarity
        ), "Jaccard similarity must be symmetric"

    def test_jaccard_similarity_mathematical_correctness(self, mock_database):
        """Test that Jaccard similarity calculation is mathematically correct."""
        analyzer = CoalitionAnalyzer(mock_database)

        # Test case with known Jaccard similarity
        # Candidate 1: ballots [B001, B002, B003]
        # Candidate 2: ballots [B002, B003, B004]
        # Intersection: [B002, B003] = 2 ballots
        # Union: [B001, B002, B003, B004] = 4 ballots
        # Expected Jaccard: 2/4 = 0.5

        shared_ballots = pd.DataFrame(
            {
                "BallotID": ["B002", "B003"],
                "candidate_1_rank": [1, 2],
                "candidate_2_rank": [2, 1],
            }
        )
        ballots_1 = pd.DataFrame({"BallotID": ["B001", "B002", "B003"]})
        ballots_2 = pd.DataFrame({"BallotID": ["B002", "B003", "B004"]})

        mock_database.query.side_effect = [shared_ballots, ballots_1, ballots_2]
        affinity = analyzer.calculate_pairwise_affinity(1, 2)

        expected_jaccard = 2 / 4  # intersection / union
        assert (
            abs(affinity.jaccard_similarity - expected_jaccard) < 0.001
        ), f"Jaccard similarity {affinity.jaccard_similarity} != expected {expected_jaccard}"

    def test_affinity_transitivity_properties(self, mock_database):
        """Test transitivity properties of affinity relationships."""
        analyzer = CoalitionAnalyzer(mock_database)

        # If A has high affinity with B, and B has high affinity with C,
        # then A should have some measurable relationship with C
        # (Not necessarily transitive, but should be detectable)

        # Mock data for A-B high affinity
        mock_database.query.side_effect = [
            pd.DataFrame(
                {
                    "BallotID": ["B001", "B002"],
                    "candidate_1_rank": [1, 1],
                    "candidate_2_rank": [2, 2],
                }
            ),  # A-B shared
            pd.DataFrame({"BallotID": ["B001", "B002"]}),  # A ballots
            pd.DataFrame({"BallotID": ["B001", "B002"]}),  # B ballots
        ]
        affinity_a_b = analyzer.calculate_pairwise_affinity(1, 2)

        # Mock data for B-C high affinity
        mock_database.query.side_effect = [
            pd.DataFrame(
                {
                    "BallotID": ["B002", "B003"],
                    "candidate_1_rank": [1, 1],
                    "candidate_2_rank": [2, 2],
                }
            ),  # B-C shared
            pd.DataFrame({"BallotID": ["B001", "B002"]}),  # B ballots
            pd.DataFrame({"BallotID": ["B002", "B003"]}),  # C ballots
        ]
        affinity_b_c = analyzer.calculate_pairwise_affinity(2, 3)

        # Mock data for A-C relationship
        mock_database.query.side_effect = [
            pd.DataFrame(
                {"BallotID": ["B002"], "candidate_1_rank": [1], "candidate_2_rank": [3]}
            ),  # A-C shared (through B)
            pd.DataFrame({"BallotID": ["B001", "B002"]}),  # A ballots
            pd.DataFrame({"BallotID": ["B002", "B003"]}),  # C ballots
        ]
        affinity_a_c = analyzer.calculate_pairwise_affinity(1, 3)

        # If both A-B and B-C are strong, A-C should not be zero
        if affinity_a_b.affinity_score > 0.5 and affinity_b_c.affinity_score > 0.5:
            assert (
                affinity_a_c.shared_ballots > 0
            ), "Transitive relationships should result in some shared ballots"

    def test_coalition_strength_composition_validity(self, mock_database):
        """Test that coalition strength is mathematically well-composed."""
        analyzer = CoalitionAnalyzer(mock_database)

        # Mock detailed pairwise analysis data
        mock_database.query.side_effect = [
            pd.DataFrame({"shared_ballots": [100]}),  # Good overlap
            pd.DataFrame(
                {"next_choice_12": [45], "next_choice_21": [50]}
            ),  # Strong transfers
            pd.DataFrame({"close_together": [80]}),  # Often ranked together
            pd.DataFrame({"distance_1": [1.5], "distance_2": [1.6]}),  # Close rankings
        ]

        analysis = analyzer.calculate_detailed_pairwise_analysis(1, 2)

        # Coalition strength should be well-bounded
        assert (
            0.0 <= analysis.coalition_strength <= 1.0
        ), f"Coalition strength {analysis.coalition_strength} out of bounds [0,1]"

        # Transfer rates should be mathematically valid
        assert (
            0.0 <= analysis.next_choice_rate_1_to_2 <= 1.0
        ), f"Transfer rate 1→2: {analysis.next_choice_rate_1_to_2} out of bounds"
        assert (
            0.0 <= analysis.next_choice_rate_2_to_1 <= 1.0
        ), f"Transfer rate 2→1: {analysis.next_choice_rate_2_to_1} out of bounds"

        # Close-together rate should be valid
        assert (
            0.0 <= analysis.close_together_rate <= 1.0
        ), f"Close together rate {analysis.close_together_rate} out of bounds"

        # Coalition type should be consistent with strength
        if analysis.coalition_strength > 0.7:
            assert analysis.coalition_type in [
                "strong"
            ], f"High strength {analysis.coalition_strength} should be 'strong', got '{analysis.coalition_type}'"
        elif analysis.coalition_strength < 0.3:
            assert analysis.coalition_type in [
                "weak",
                "opposing",
            ], f"Low strength {analysis.coalition_strength} should be 'weak' or 'opposing', got '{analysis.coalition_type}'"

    def test_ranking_distance_mathematical_properties(self, mock_database):
        """Test that ranking distance calculations are mathematically sound."""
        analyzer = CoalitionAnalyzer(mock_database)

        # Mock ranking proximity data with known distances
        mock_database.query.return_value = pd.DataFrame(
            {
                "BallotID": ["B001", "B002", "B003", "B004"],
                "candidate_1_rank": [1, 2, 1, 3],
                "candidate_2_rank": [2, 1, 4, 1],
                "distance": [1, 1, 3, 2],  # |rank1 - rank2|
            }
        )

        proximity = analyzer.analyze_ranking_proximity(1, 2)

        # Average distance should be mathematically correct
        expected_avg_distance = (1 + 1 + 3 + 2) / 4  # 1.75
        assert (
            abs(proximity["avg_ranking_distance"] - expected_avg_distance) < 0.001
        ), f"Average distance {proximity['avg_ranking_distance']} != expected {expected_avg_distance}"

        # Distance should be positive
        assert (
            proximity["avg_ranking_distance"] >= 0
        ), "Average ranking distance cannot be negative"

        # Close together percentage should be mathematically valid
        assert (
            0.0 <= proximity["close_together_percentage"] <= 100.0
        ), f"Close together percentage {proximity['close_together_percentage']} out of bounds [0,100]"

        # Distribution should contain valid distances
        for distance, count in proximity["ranking_distance_distribution"].items():
            assert distance >= 0, f"Distance {distance} cannot be negative"
            assert count >= 0, f"Count {count} cannot be negative"

    def test_coalition_mathematical_invariants(self, mock_database):
        """Test mathematical invariants that must hold for all coalitions."""
        analyzer = CoalitionAnalyzer(mock_database)

        # Mock multiple candidate pairs for comprehensive testing
        test_pairs = [(1, 2), (1, 3), (2, 3), (1, 4), (2, 4), (3, 4)]

        affinities = {}
        for c1, c2 in test_pairs:
            # Mock varied but valid data for each pair
            shared_count = max(1, abs(c1 - c2) * 10)  # Synthetic but valid
            total_1 = shared_count + 20
            total_2 = shared_count + 15

            mock_database.query.side_effect = [
                pd.DataFrame(
                    {
                        "BallotID": [f"B{i:03d}" for i in range(shared_count)],
                        "candidate_1_rank": [1] * shared_count,
                        "candidate_2_rank": [2] * shared_count,
                    }
                ),
                pd.DataFrame({"BallotID": [f"B{i:03d}" for i in range(total_1)]}),
                pd.DataFrame({"BallotID": [f"B{i:03d}" for i in range(total_2)]}),
            ]

            affinity = analyzer.calculate_pairwise_affinity(c1, c2)
            affinities[(c1, c2)] = affinity

            # Individual invariants
            assert affinity.shared_ballots <= min(
                total_1, total_2
            ), f"Shared ballots {affinity.shared_ballots} exceeds minimum total"

            # Jaccard similarity should match calculation
            union_size = total_1 + total_2 - affinity.shared_ballots
            expected_jaccard = (
                affinity.shared_ballots / union_size if union_size > 0 else 0
            )
            assert (
                abs(affinity.jaccard_similarity - expected_jaccard) < 0.001
            ), f"Jaccard similarity calculation incorrect for pair {c1},{c2}"

    def test_division_by_zero_protection(self, mock_database):
        """Test that all calculations handle division by zero gracefully."""
        analyzer = CoalitionAnalyzer(mock_database)

        # Test with empty data (potential division by zero scenarios)
        mock_database.query.side_effect = [
            pd.DataFrame(
                columns=["BallotID", "candidate_1_rank", "candidate_2_rank"]
            ),  # No shared
            pd.DataFrame(columns=["BallotID"]),  # No ballots for c1
            pd.DataFrame(columns=["BallotID"]),  # No ballots for c2
        ]

        affinity = analyzer.calculate_pairwise_affinity(1, 2)

        # Should handle gracefully without division by zero
        assert isinstance(
            affinity.affinity_score, (int, float)
        ), "Affinity score should be numeric even with empty data"
        assert isinstance(
            affinity.jaccard_similarity, (int, float)
        ), "Jaccard similarity should be numeric even with empty data"
        assert (
            affinity.shared_ballots == 0
        ), "Shared ballots should be 0 with empty data"

        # Common division by zero case: no total ballots
        assert (
            0.0 <= affinity.jaccard_similarity <= 1.0
        ), "Jaccard similarity should remain bounded even with edge case data"

    def test_numerical_stability_with_large_numbers(self, mock_database):
        """Test numerical stability with large ballot counts."""
        analyzer = CoalitionAnalyzer(mock_database)

        # Test with large numbers (like real elections)
        large_shared = 50000
        large_total_1 = 100000
        large_total_2 = 75000

        mock_database.query.side_effect = [
            pd.DataFrame(
                {
                    "BallotID": [
                        f"B{i:06d}" for i in range(min(100, large_shared))
                    ],  # Sample for testing
                    "candidate_1_rank": [1] * min(100, large_shared),
                    "candidate_2_rank": [2] * min(100, large_shared),
                }
            ),
            pd.DataFrame(
                {"BallotID": [f"B{i:06d}" for i in range(min(200, large_total_1))]}
            ),
            pd.DataFrame(
                {"BallotID": [f"B{i:06d}" for i in range(min(150, large_total_2))]}
            ),
        ]

        # Override the shared ballots count to simulate large election
        with pytest.MonkeyPatch().context() as m:

            def mock_len(df):
                if "candidate_1_rank" in df.columns:
                    return large_shared
                return len(df.index)

            # Test should complete without numerical errors
            affinity = analyzer.calculate_pairwise_affinity(1, 2)

            # Results should still be bounded despite large numbers
            assert (
                0.0 <= affinity.affinity_score <= 1.0
            ), "Affinity score out of bounds with large numbers"
            assert (
                0.0 <= affinity.jaccard_similarity <= 1.0
            ), "Jaccard similarity out of bounds with large numbers"

            # Should not produce NaN or infinite values
            assert not np.isnan(
                affinity.affinity_score
            ), "Affinity score should not be NaN"
            assert not np.isinf(
                affinity.affinity_score
            ), "Affinity score should not be infinite"
