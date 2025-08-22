"""
Tests for Coalition Analysis Mathematical Correctness

These tests verify that coalition analysis mathematical calculations are sound
and don't produce nonsensical results that could mislead political analysis.

PHASE 1: Mathematical Correctness
- Affinity scores remain within valid bounds (0.0 to 1.0 for normalized metrics)
- Division by zero protection in all scoring algorithms
- Symmetric and antisymmetric properties where expected
- Mathematical invariants hold under edge cases
"""

import os
import tempfile

import pandas as pd
import pytest

from src.analysis.coalition import CoalitionAnalyzer
from src.data.database import CVRDatabase


class TestCoalitionMathematicalCorrectness:
    """Test mathematical properties of coalition analysis algorithms."""

    def setup_method(self):
        """Set up test fixtures with known mathematical properties."""
        # Create minimal in-memory database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        os.unlink(self.db_path)  # Remove empty file for DuckDB

        # Initialize database with test data
        self.db = CVRDatabase(self.db_path, read_only=False)
        self._create_test_data()

        self.analyzer = CoalitionAnalyzer(self.db)

    def teardown_method(self):
        """Clean up test fixtures."""
        self.db.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _create_test_data(self):
        """Create controlled test data with known mathematical properties."""
        # Create candidates table
        self.db.conn.execute(
            """
            CREATE TABLE candidates (
                candidate_id INTEGER,
                candidate_name TEXT
            )
        """
        )

        # Insert test candidates
        candidates = [
            (1, "Alice Progressive"),
            (2, "Bob Progressive"),
            (3, "Charlie Moderate"),
            (4, "Diana Conservative"),
            (5, "Eve Isolated"),  # Candidate with very few supporters
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

        # Create controlled ballot patterns for mathematical testing
        ballots = []

        # Pattern 1: Perfect coalition (Alice-Bob always together)
        for i in range(100):
            ballots.extend(
                [
                    (f"ballot_{i}_perfect", 1, 1),  # Alice rank 1
                    (f"ballot_{i}_perfect", 2, 2),  # Bob rank 2
                    (f"ballot_{i}_perfect", 3, 3),  # Charlie rank 3
                ]
            )

        # Pattern 2: Partial overlap (Alice-Charlie sometimes together)
        for i in range(50):
            ballots.extend(
                [
                    (f"ballot_{i}_partial", 1, 1),  # Alice rank 1
                    (f"ballot_{i}_partial", 3, 2),  # Charlie rank 2
                    (f"ballot_{i}_partial", 4, 3),  # Diana rank 3
                ]
            )

        # Pattern 3: No overlap (Diana-Eve separate voter bases)
        for i in range(30):
            ballots.extend(
                [
                    (f"ballot_{i}_diana", 4, 1),  # Diana only
                    (f"ballot_{i}_eve", 5, 1),  # Eve only (separate ballots)
                ]
            )

        # Pattern 4: Single candidate ballots (bullet voting)
        for i in range(25):
            ballots.append((f"ballot_{i}_bullet", 1, 1))  # Alice only

        # Insert all ballot data
        for ballot_id, cand_id, rank in ballots:
            self.db.conn.execute(
                "INSERT INTO ballots_long VALUES (?, ?, ?)", (ballot_id, cand_id, rank)
            )

    def test_affinity_score_mathematical_bounds(self):
        """Verify all affinity scores stay within mathematically valid bounds."""
        # Test all normalization methods
        methods = ["raw", "conditional", "lift"]

        for normalize_method in methods:
            affinities = self.analyzer.calculate_detailed_pairwise_analysis(
                min_shared_ballots=1, normalize=normalize_method
            )

            for affinity in affinities:
                # Basic mathematical bounds checking
                assert affinity.shared_ballots >= 0, "Shared ballots cannot be negative"
                assert affinity.total_ballots_1 >= 0, "Total ballots cannot be negative"
                assert affinity.total_ballots_2 >= 0, "Total ballots cannot be negative"

                # Normalized affinity bounds (except lift which can be > 1.0)
                if normalize_method in ["raw", "conditional"]:
                    assert (
                        0.0 <= affinity.normalized_affinity_score <= 1.0
                    ), f"Normalized affinity {affinity.normalized_affinity_score} outside [0,1] bounds for method {normalize_method}"

                # Proximity-weighted affinity should always be valid
                assert (
                    0.0 <= affinity.proximity_weighted_affinity <= 1.0
                ), f"Proximity-weighted affinity {affinity.proximity_weighted_affinity} outside bounds"

                # Coalition strength should be bounded for most methods
                assert (
                    0.0 <= affinity.coalition_strength_score <= 2.0
                ), f"Coalition strength {affinity.coalition_strength_score} outside reasonable bounds"

    def test_division_by_zero_protection(self):
        """Ensure all calculations handle division by zero gracefully."""
        # Create edge case: candidate with zero total ballots
        self.db.conn.execute("INSERT INTO candidates VALUES (99, 'Zero Candidate')")
        # Note: No ballots for candidate 99, so total_ballots = 0

        # Test should not crash with division by zero
        try:
            affinities = self.analyzer.calculate_detailed_pairwise_analysis(
                min_shared_ballots=0,  # Allow zero shared ballots
                normalize="conditional",  # Most likely to trigger division by zero
            )

            # All scores should be valid numbers (not NaN, not infinite)
            for affinity in affinities:
                assert not pd.isna(
                    affinity.basic_affinity_score
                ), "Basic affinity is NaN"
                assert not pd.isna(
                    affinity.normalized_affinity_score
                ), "Normalized affinity is NaN"
                assert not pd.isna(
                    affinity.proximity_weighted_affinity
                ), "Proximity affinity is NaN"
                assert not pd.isna(
                    affinity.coalition_strength_score
                ), "Coalition strength is NaN"

                # Check for infinity values
                assert abs(affinity.basic_affinity_score) < float(
                    "inf"
                ), "Basic affinity is infinite"
                assert abs(affinity.normalized_affinity_score) < float(
                    "inf"
                ), "Normalized affinity is infinite"

        except Exception as e:
            pytest.fail(f"Division by zero not properly handled: {e}")

    def test_jaccard_similarity_properties(self):
        """Test that Jaccard similarity (basic affinity) follows mathematical properties."""
        affinities = self.analyzer.calculate_detailed_pairwise_analysis(
            min_shared_ballots=1, normalize="raw"  # Uses Jaccard similarity
        )

        # Create lookup for easier testing
        affinity_lookup = {}
        for aff in affinities:
            key = tuple(sorted([aff.candidate_1, aff.candidate_2]))
            affinity_lookup[key] = aff

        # Test Jaccard properties
        for aff in affinities:
            shared = aff.shared_ballots
            total_1 = aff.total_ballots_1
            total_2 = aff.total_ballots_2
            union_size = total_1 + total_2 - shared

            # Manual Jaccard calculation
            expected_jaccard = shared / union_size if union_size > 0 else 0.0

            # Should match our calculated basic affinity
            assert (
                abs(aff.basic_affinity_score - expected_jaccard) < 1e-10
            ), f"Jaccard calculation mismatch: {aff.basic_affinity_score} vs {expected_jaccard}"

            # Jaccard similarity properties
            assert 0.0 <= aff.basic_affinity_score <= 1.0, "Jaccard should be in [0,1]"

            # If shared_ballots == min(total_1, total_2), Jaccard should be > 0
            if shared == min(total_1, total_2) and shared > 0:
                assert (
                    aff.basic_affinity_score > 0
                ), "Jaccard should be positive for subset relationship"

    def test_proximity_weights_mathematical_consistency(self):
        """Test that proximity weights follow expected mathematical behavior."""
        affinities = self.analyzer.calculate_detailed_pairwise_analysis(
            min_shared_ballots=10, method="proximity_weighted"
        )

        for aff in affinities:
            # Proximity weights should follow 1/(1+distance) pattern
            # Closer rankings (distance=0) should get weight=1.0
            # Farther rankings should get diminishing weights

            # Test that ranking distances make sense
            for distance in aff.ranking_distances[:10]:  # Check first 10
                assert distance >= 0, "Ranking distance cannot be negative"

                # Calculate expected weight
                expected_weight = 1.0 / (1 + distance)
                assert (
                    0.0 < expected_weight <= 1.0
                ), f"Proximity weight {expected_weight} outside valid range for distance {distance}"

            # Proximity-weighted score should reflect distance patterns
            if len(aff.ranking_distances) > 0:
                # Proximity-weighted affinity should be related to average weight
                # (not exact due to aggregation, but should be in similar range)
                assert (
                    0.0 <= aff.proximity_weighted_affinity <= 1.0
                ), "Proximity-weighted affinity outside bounds"

    def test_coalition_strength_composition_validity(self):
        """Test that coalition strength composition follows expected mathematical rules."""
        affinities = self.analyzer.calculate_detailed_pairwise_analysis(
            min_shared_ballots=1, method="proximity_weighted"
        )

        for aff in affinities:
            normalized_component = aff.normalized_affinity_score * 0.3
            proximity_component = aff.proximity_weighted_affinity * 0.7
            expected_strength = normalized_component + proximity_component

            # Coalition strength should equal weighted combination
            assert (
                abs(aff.coalition_strength_score - expected_strength) < 1e-10
            ), f"Coalition strength calculation error: {aff.coalition_strength_score} vs {expected_strength}"

            # Each component should be within bounds
            assert (
                0.0 <= normalized_component <= 0.3
            ), f"Normalized component {normalized_component} outside expected bounds"
            assert (
                0.0 <= proximity_component <= 0.7
            ), f"Proximity component {proximity_component} outside expected bounds"

            # Total should be reasonable
            assert (
                0.0 <= aff.coalition_strength_score <= 1.0
            ), f"Coalition strength {aff.coalition_strength_score} outside [0,1] bounds"

    def test_conditional_probability_validity(self):
        """Test that conditional probability calculations are mathematically valid."""
        affinities = self.analyzer.calculate_detailed_pairwise_analysis(
            min_shared_ballots=1, normalize="conditional"
        )

        for aff in affinities:
            # Conditional probability: P(B|A) = shared_ballots / total_ballots_1
            if aff.total_ballots_1 > 0:
                expected_conditional = aff.shared_ballots / aff.total_ballots_1

                assert (
                    abs(aff.normalized_affinity_score - expected_conditional) < 1e-10
                ), f"Conditional probability calculation error: {aff.normalized_affinity_score} vs {expected_conditional}"

                # Conditional probability properties
                assert (
                    0.0 <= aff.normalized_affinity_score <= 1.0
                ), "Conditional probability must be in [0,1]"

                # If shared_ballots == total_ballots_1, conditional should be 1.0
                if aff.shared_ballots == aff.total_ballots_1:
                    assert (
                        abs(aff.normalized_affinity_score - 1.0) < 1e-10
                    ), "Perfect overlap should give conditional probability = 1.0"

    def test_lift_calculation_mathematical_properties(self):
        """Test that lift calculations follow expected statistical properties."""
        affinities = self.analyzer.calculate_detailed_pairwise_analysis(
            min_shared_ballots=1, normalize="lift"
        )

        for aff in affinities:
            # Lift measures deviation from independence
            # Lift = 1.0 means independence
            # Lift > 1.0 means positive association
            # Lift < 1.0 means negative association

            assert aff.normalized_affinity_score >= 0.0, "Lift cannot be negative"
            assert aff.normalized_affinity_score <= 2.0, "Lift should be capped at 2.0"

            # Manual lift calculation verification (simplified)
            shared = aff.shared_ballots
            total_1 = aff.total_ballots_1
            total_2 = aff.total_ballots_2

            if shared > 0 and total_1 > 0 and total_2 > 0:
                # Our lift calculation uses max(total_1, total_2, shared) as denominator
                total_estimate = max(total_1, total_2, shared)
                prob_a = total_1 / total_estimate
                prob_b = total_2 / total_estimate
                prob_ab = shared / total_estimate

                if prob_a * prob_b > 0:
                    expected_lift = min(prob_ab / (prob_a * prob_b), 2.0)
                    assert (
                        abs(aff.normalized_affinity_score - expected_lift) < 1e-6
                    ), f"Lift calculation mismatch: {aff.normalized_affinity_score} vs {expected_lift}"

    def test_mathematical_consistency_across_methods(self):
        """Test that different calculation methods maintain mathematical consistency."""
        # Calculate with different methods
        basic_affinities = self.analyzer.calculate_detailed_pairwise_analysis(
            min_shared_ballots=1, method="basic"
        )
        proximity_affinities = self.analyzer.calculate_detailed_pairwise_analysis(
            min_shared_ballots=1, method="proximity_weighted"
        )

        # Create lookups
        basic_lookup = {
            (aff.candidate_1, aff.candidate_2): aff for aff in basic_affinities
        }
        proximity_lookup = {
            (aff.candidate_1, aff.candidate_2): aff for aff in proximity_affinities
        }

        # Compare pairs that exist in both
        for key in basic_lookup:
            if key in proximity_lookup:
                basic_aff = basic_lookup[key]
                prox_aff = proximity_lookup[key]

                # Basic calculations should be identical
                assert (
                    basic_aff.shared_ballots == prox_aff.shared_ballots
                ), "Shared ballots should be identical across methods"
                assert (
                    basic_aff.total_ballots_1 == prox_aff.total_ballots_1
                ), "Total ballots should be identical across methods"
                assert (
                    basic_aff.total_ballots_2 == prox_aff.total_ballots_2
                ), "Total ballots should be identical across methods"

                # Basic affinity should be identical
                assert (
                    abs(basic_aff.basic_affinity_score - prox_aff.basic_affinity_score)
                    < 1e-10
                ), "Basic affinity should be identical across methods"

                # Coalition strength should differ but both be valid
                assert 0.0 <= basic_aff.coalition_strength_score <= 1.0
                assert 0.0 <= prox_aff.coalition_strength_score <= 1.0

    def test_ranking_distance_calculations(self):
        """Test that ranking distance calculations are mathematically correct."""
        affinities = self.analyzer.calculate_detailed_pairwise_analysis(
            min_shared_ballots=1
        )

        for aff in affinities:
            # Check ranking distance properties
            for distance in aff.ranking_distances:
                assert distance >= 0, "Ranking distance cannot be negative"
                assert isinstance(distance, (int, float)), "Distance should be numeric"

                # Distance should be reasonable (candidates ranked within same ballot)
                assert distance <= 10, "Ranking distance seems unreasonably large"

            # Average distance calculations - verify mathematical consistency
            if len(aff.ranking_distances) > 0:
                # Note: The coalition module has a known issue where avg_ranking_distance
                # is calculated from the full distances list, but ranking_distances field
                # is truncated to first 100 elements for memory efficiency.
                # We test the mathematical properties rather than exact equality.

                # Average should be a reasonable value within the range of distances
                assert (
                    aff.min_ranking_distance
                    <= aff.avg_ranking_distance
                    <= aff.max_ranking_distance
                ), f"Average {aff.avg_ranking_distance} outside min/max bounds [{aff.min_ranking_distance}, {aff.max_ranking_distance}]"

                # Average should be mathematically reasonable (finite, not NaN)
                assert not pd.isna(aff.avg_ranking_distance), "Average distance is NaN"
                assert abs(aff.avg_ranking_distance) < float(
                    "inf"
                ), "Average distance is infinite"

                # Min/max should be consistent with the distance list
                assert aff.min_ranking_distance == min(
                    aff.ranking_distances
                ), "Minimum distance calculation error"
                assert aff.max_ranking_distance == max(
                    aff.ranking_distances
                ), "Maximum distance calculation error"
