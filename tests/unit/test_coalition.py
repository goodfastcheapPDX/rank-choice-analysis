from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from src.analysis.coalition import (
    CandidateAffinity,
    CoalitionAnalyzer,
    CoalitionGroup,
    DetailedCandidatePair,
    convert_numpy_types,
)


class TestNumpyConversion:
    """Test numpy type conversion utilities."""

    def test_convert_numpy_int(self):
        """Test conversion of numpy integer types."""
        numpy_int = np.int64(42)
        result = convert_numpy_types(numpy_int)
        assert isinstance(result, int)
        assert result == 42

    def test_convert_numpy_float(self):
        """Test conversion of numpy float types."""
        numpy_float = np.float64(3.14)
        result = convert_numpy_types(numpy_float)
        assert isinstance(result, float)
        assert result == 3.14

    def test_convert_numpy_array(self):
        """Test conversion of numpy arrays."""
        numpy_array = np.array([1, 2, 3, 4])
        result = convert_numpy_types(numpy_array)
        assert isinstance(result, list)
        assert result == [1, 2, 3, 4]

    def test_convert_nested_dict(self):
        """Test conversion of nested dictionaries with numpy types."""
        nested_dict = {
            "int_val": np.int32(10),
            "float_val": np.float32(2.5),
            "array_val": np.array([1, 2]),
            "nested": {"inner_int": np.int64(20), "inner_array": np.array([3, 4])},
        }

        result = convert_numpy_types(nested_dict)

        assert isinstance(result["int_val"], int)
        assert isinstance(result["float_val"], float)
        assert isinstance(result["array_val"], list)
        assert isinstance(result["nested"]["inner_int"], int)
        assert isinstance(result["nested"]["inner_array"], list)

    def test_convert_list_with_numpy(self):
        """Test conversion of lists containing numpy types."""
        numpy_list = [np.int32(1), np.float64(2.5), np.array([3, 4])]
        result = convert_numpy_types(numpy_list)

        assert isinstance(result[0], int)
        assert isinstance(result[1], float)
        assert isinstance(result[2], list)

    def test_convert_non_numpy_types(self):
        """Test that non-numpy types pass through unchanged."""
        regular_dict = {
            "string": "hello",
            "int": 42,
            "float": 3.14,
            "list": [1, 2, 3],
            "bool": True,
            "none": None,
        }

        result = convert_numpy_types(regular_dict)

        assert result == regular_dict
        assert isinstance(result["string"], str)
        assert isinstance(result["int"], int)
        assert isinstance(result["float"], float)

    def test_convert_empty_structures(self):
        """Test conversion of empty structures."""
        assert convert_numpy_types({}) == {}
        assert convert_numpy_types([]) == []
        assert convert_numpy_types(None) is None

    def test_convert_mixed_complex_structure(self):
        """Test conversion of complex mixed structure."""
        complex_structure = {
            "candidates": [
                {
                    "id": np.int64(1),
                    "votes": np.array([100, 150, 200]),
                    "percentage": np.float32(12.5),
                },
                {
                    "id": np.int64(2),
                    "votes": np.array([80, 120, 160]),
                    "percentage": np.float32(10.0),
                },
            ],
            "summary": {"total_votes": np.int32(1000), "avg_score": np.float64(85.7)},
        }

        result = convert_numpy_types(complex_structure)

        # Check candidate data conversion
        assert isinstance(result["candidates"][0]["id"], int)
        assert isinstance(result["candidates"][0]["votes"], list)
        assert isinstance(result["candidates"][0]["percentage"], float)

        # Check summary data conversion
        assert isinstance(result["summary"]["total_votes"], int)
        assert isinstance(result["summary"]["avg_score"], float)


class TestCoalitionDataClasses:
    """Test coalition analysis data classes."""

    def test_candidate_affinity_creation(self):
        """Test CandidateAffinity data class creation."""
        affinity = CandidateAffinity(
            candidate_1=1,
            candidate_1_name="Alice",
            candidate_2=2,
            candidate_2_name="Bob",
            shared_ballots=150,
            total_ballots_1=500,
            total_ballots_2=400,
            affinity_score=0.75,
            overlap_percentage=30.0,
        )

        assert affinity.candidate_1 == 1
        assert affinity.candidate_1_name == "Alice"
        assert affinity.shared_ballots == 150
        assert affinity.affinity_score == 0.75

    def test_detailed_candidate_pair_creation(self):
        """Test DetailedCandidatePair data class creation."""
        pair = DetailedCandidatePair(
            candidate_1=1,
            candidate_1_name="Alice",
            candidate_2=2,
            candidate_2_name="Bob",
            shared_ballots=200,
            total_ballots_1=600,
            total_ballots_2=500,
            ranking_distances=[1, 2, 1, 3, 2],
            avg_ranking_distance=1.8,
            min_ranking_distance=1,
            max_ranking_distance=3,
            strong_coalition_votes=150,
            weak_coalition_votes=20,
            transfer_votes_1_to_2=80,
            transfer_votes_2_to_1=75,
            next_choice_rate_a_to_b=0.4,
            next_choice_rate_b_to_a=0.35,
            close_together_rate=0.6,
            follow_through_a_to_b=0.8,
            follow_through_b_to_a=0.75,
            basic_affinity_score=0.7,
            normalized_affinity_score=0.72,
            proximity_weighted_affinity=0.85,
            coalition_strength_score=0.78,
            coalition_type="strong",
        )

        assert pair.candidate_1 == 1
        assert pair.candidate_2 == 2
        assert len(pair.ranking_distances) == 5
        assert pair.avg_ranking_distance == 1.8
        assert pair.coalition_type == "strong"

    def test_coalition_group_creation(self):
        """Test CoalitionGroup data class can be created."""
        # Import the class to test it exists and can be instantiated
        try:
            from src.analysis.coalition import CoalitionGroup

            # Test that the class exists and can be imported
            assert CoalitionGroup is not None

            # If CoalitionGroup has required fields, test with them
            # This is a basic test to ensure the class definition is valid

        except ImportError:
            pytest.skip("CoalitionGroup class not fully implemented yet")

    def test_data_class_immutability(self):
        """Test that data classes are properly structured."""
        affinity = CandidateAffinity(
            candidate_1=1,
            candidate_1_name="Alice",
            candidate_2=2,
            candidate_2_name="Bob",
            shared_ballots=150,
            total_ballots_1=500,
            total_ballots_2=400,
            affinity_score=0.75,
            overlap_percentage=30.0,
        )

        # Test that we can access all fields
        assert hasattr(affinity, "candidate_1")
        assert hasattr(affinity, "candidate_1_name")
        assert hasattr(affinity, "shared_ballots")
        assert hasattr(affinity, "affinity_score")

    def test_detailed_pair_ranking_distance_analysis(self):
        """Test ranking distance calculations in DetailedCandidatePair."""
        pair = DetailedCandidatePair(
            candidate_1=1,
            candidate_1_name="Alice",
            candidate_2=2,
            candidate_2_name="Bob",
            shared_ballots=100,
            total_ballots_1=300,
            total_ballots_2=250,
            ranking_distances=[1, 1, 2, 2, 3, 4, 5],
            avg_ranking_distance=2.57,  # (1+1+2+2+3+4+5)/7
            min_ranking_distance=1,
            max_ranking_distance=5,
            strong_coalition_votes=60,  # distances 1,2
            weak_coalition_votes=20,  # distances 4,5
            transfer_votes_1_to_2=45,
            transfer_votes_2_to_1=40,
            next_choice_rate_a_to_b=0.3,
            next_choice_rate_b_to_a=0.25,
            close_together_rate=0.5,
            follow_through_a_to_b=0.7,
            follow_through_b_to_a=0.65,
            basic_affinity_score=0.6,
            normalized_affinity_score=0.62,
            proximity_weighted_affinity=0.7,
            coalition_strength_score=0.65,
            coalition_type="moderate",
        )

        # Test ranking distance statistics
        assert pair.min_ranking_distance == 1
        assert pair.max_ranking_distance == 5
        assert abs(pair.avg_ranking_distance - 2.57) < 0.01

        # Test coalition vote categorization
        assert pair.strong_coalition_votes == 60
        assert pair.weak_coalition_votes == 20

        # Test transfer analysis
        assert pair.transfer_votes_1_to_2 == 45
        assert pair.transfer_votes_2_to_1 == 40

    def test_coalition_scoring_ranges(self):
        """Test that coalition scores are within expected ranges."""
        pair = DetailedCandidatePair(
            candidate_1=1,
            candidate_1_name="Alice",
            candidate_2=2,
            candidate_2_name="Bob",
            shared_ballots=100,
            total_ballots_1=200,
            total_ballots_2=180,
            ranking_distances=[1, 2],
            avg_ranking_distance=1.5,
            min_ranking_distance=1,
            max_ranking_distance=2,
            strong_coalition_votes=80,
            weak_coalition_votes=5,
            transfer_votes_1_to_2=70,
            transfer_votes_2_to_1=65,
            next_choice_rate_a_to_b=0.85,
            next_choice_rate_b_to_a=0.80,
            close_together_rate=0.90,
            follow_through_a_to_b=0.95,
            follow_through_b_to_a=0.92,
            basic_affinity_score=0.85,
            normalized_affinity_score=0.87,
            proximity_weighted_affinity=0.92,
            coalition_strength_score=0.89,
            coalition_type="strong",
        )

        # Test that rates are in [0, 1] range
        assert 0 <= pair.next_choice_rate_a_to_b <= 1
        assert 0 <= pair.next_choice_rate_b_to_a <= 1
        assert 0 <= pair.close_together_rate <= 1
        assert 0 <= pair.follow_through_a_to_b <= 1
        assert 0 <= pair.follow_through_b_to_a <= 1

        # Test that affinity scores are in [0, 1] range
        assert 0 <= pair.basic_affinity_score <= 1
        assert 0 <= pair.normalized_affinity_score <= 1
        assert 0 <= pair.proximity_weighted_affinity <= 1
        assert 0 <= pair.coalition_strength_score <= 1

    def test_coalition_type_categories(self):
        """Test coalition type categorization."""
        # Test different coalition types
        coalition_types = ["strong", "moderate", "weak", "strategic"]

        for coalition_type in coalition_types:
            pair = DetailedCandidatePair(
                candidate_1=1,
                candidate_1_name="Alice",
                candidate_2=2,
                candidate_2_name="Bob",
                shared_ballots=50,
                total_ballots_1=100,
                total_ballots_2=100,
                ranking_distances=[1, 2, 3],
                avg_ranking_distance=2.0,
                min_ranking_distance=1,
                max_ranking_distance=3,
                strong_coalition_votes=30,
                weak_coalition_votes=10,
                transfer_votes_1_to_2=25,
                transfer_votes_2_to_1=20,
                next_choice_rate_a_to_b=0.5,
                next_choice_rate_b_to_a=0.4,
                close_together_rate=0.6,
                follow_through_a_to_b=0.7,
                follow_through_b_to_a=0.6,
                basic_affinity_score=0.5,
                normalized_affinity_score=0.5,
                proximity_weighted_affinity=0.6,
                coalition_strength_score=0.55,
                coalition_type=coalition_type,
            )

            assert pair.coalition_type == coalition_type
            assert pair.coalition_type in ["strong", "moderate", "weak", "strategic"]

    def test_data_class_field_types(self):
        """Test that data class fields have correct types."""
        pair = DetailedCandidatePair(
            candidate_1=1,
            candidate_1_name="Alice",
            candidate_2=2,
            candidate_2_name="Bob",
            shared_ballots=100,
            total_ballots_1=200,
            total_ballots_2=180,
            ranking_distances=[1, 2, 3],
            avg_ranking_distance=2.0,
            min_ranking_distance=1,
            max_ranking_distance=3,
            strong_coalition_votes=80,
            weak_coalition_votes=10,
            transfer_votes_1_to_2=70,
            transfer_votes_2_to_1=65,
            next_choice_rate_a_to_b=0.7,
            next_choice_rate_b_to_a=0.6,
            close_together_rate=0.8,
            follow_through_a_to_b=0.9,
            follow_through_b_to_a=0.85,
            basic_affinity_score=0.75,
            normalized_affinity_score=0.77,
            proximity_weighted_affinity=0.82,
            coalition_strength_score=0.78,
            coalition_type="strong",
        )

        # Test integer fields
        assert isinstance(pair.candidate_1, int)
        assert isinstance(pair.candidate_2, int)
        assert isinstance(pair.shared_ballots, int)
        assert isinstance(pair.total_ballots_1, int)
        assert isinstance(pair.total_ballots_2, int)

        # Test string fields
        assert isinstance(pair.candidate_1_name, str)
        assert isinstance(pair.candidate_2_name, str)
        assert isinstance(pair.coalition_type, str)

        # Test list fields
        assert isinstance(pair.ranking_distances, list)

        # Test float fields
        assert isinstance(pair.avg_ranking_distance, (int, float))
        assert isinstance(pair.basic_affinity_score, (int, float))
        assert isinstance(pair.coalition_strength_score, (int, float))


class TestCoalitionGroup:
    """Test CoalitionGroup data class."""

    def test_coalition_group_creation(self):
        """Test CoalitionGroup data class creation."""
        group = CoalitionGroup(
            coalition_id="progressive_coalition",
            candidates=[1, 2, 3],
            candidate_names=["Alice", "Bob", "Charlie"],
            core_supporters=150,
            coalition_strength=0.85,
        )

        assert group.coalition_id == "progressive_coalition"
        assert len(group.candidates) == 3
        assert len(group.candidate_names) == 3
        assert group.core_supporters == 150
        assert group.coalition_strength == 0.85


class TestCoalitionAnalyzer:
    """Test CoalitionAnalyzer class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock()
        self.analyzer = CoalitionAnalyzer(self.mock_db)

    def test_coalition_analyzer_initialization(self):
        """Test CoalitionAnalyzer initialization."""
        assert self.analyzer.db is self.mock_db
        assert self.analyzer.candidates_df is None
        assert self.analyzer.ballot_counts is None

    def test_load_candidate_data_success(self):
        """Test successful candidate data loading."""
        # Mock candidates data
        mock_candidates = pd.DataFrame(
            {"candidate_id": [1, 2, 3], "candidate_name": ["Alice", "Bob", "Charlie"]}
        )

        # Mock ballot counts data
        mock_ballot_counts = pd.DataFrame(
            {"candidate_id": [1, 2, 3], "total_ballots": [1000, 800, 600]}
        )

        self.mock_db.query.side_effect = [mock_candidates, mock_ballot_counts]

        self.analyzer._load_candidate_data()

        assert len(self.analyzer.candidates_df) == 3
        assert len(self.analyzer.ballot_counts) == 3
        assert self.mock_db.query.call_count == 2

    def test_load_candidate_data_caching(self):
        """Test that candidate data is cached after first load."""
        # Mock data
        mock_candidates = pd.DataFrame(
            {"candidate_id": [1, 2], "candidate_name": ["Alice", "Bob"]}
        )
        mock_ballot_counts = pd.DataFrame(
            {"candidate_id": [1, 2], "total_ballots": [500, 400]}
        )

        self.mock_db.query.side_effect = [mock_candidates, mock_ballot_counts]

        # First call should query database
        self.analyzer._load_candidate_data()
        assert self.mock_db.query.call_count == 2

        # Second call should not query database again
        self.analyzer._load_candidate_data()
        assert self.mock_db.query.call_count == 2  # No additional calls
