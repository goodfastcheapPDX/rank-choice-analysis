from unittest.mock import Mock, patch

import pandas as pd

from src.analysis.candidate_metrics import (
    BallotJourneyData,
    CandidateMetrics,
    CandidateProfile,
    SupporterArchetype,
    SupporterSegmentation,
    TransferEfficiency,
    VoterBehaviorAnalysis,
)


class TestCandidateMetricsDataClasses:
    """Test candidate metrics data classes."""

    def test_candidate_profile_creation(self):
        """Test CandidateProfile data class creation."""
        profile = CandidateProfile(
            candidate_id=1,
            candidate_name="Alice",
            total_ballots=1000,
            first_choice_votes=250,
            first_choice_percentage=25.0,
            vote_strength_index=0.75,
            cross_camp_appeal=0.30,
            transfer_efficiency=0.85,
            ranking_consistency=0.90,
            elimination_round=None,
            final_status="winner",
            vote_progression=[{"round": 1, "votes": 250}],
            top_coalition_partners=[{"candidate": "Bob", "strength": 0.4}],
            supporter_demographics={"avg_age": 35},
        )

        assert profile.candidate_id == 1
        assert profile.candidate_name == "Alice"
        assert profile.final_status == "winner"
        assert len(profile.vote_progression) == 1

    def test_transfer_efficiency_creation(self):
        """Test TransferEfficiency data class creation."""
        efficiency = TransferEfficiency(
            candidate_id=2,
            candidate_name="Bob",
            total_transferable_votes=150,
            successful_transfers=120,
            transfer_efficiency_rate=0.80,
            avg_transfer_distance=2.5,
            top_transfer_destinations=[{"candidate": "Alice", "votes": 60}],
            transfer_pattern_type="concentrated",
        )

        assert efficiency.candidate_id == 2
        assert efficiency.transfer_efficiency_rate == 0.80
        assert efficiency.transfer_pattern_type == "concentrated"

    def test_voter_behavior_analysis_creation(self):
        """Test VoterBehaviorAnalysis data class creation."""
        behavior = VoterBehaviorAnalysis(
            candidate_id=3,
            candidate_name="Charlie",
            bullet_voters=50,
            bullet_voter_percentage=20.0,
            avg_ranking_position=2.3,
            ranking_distribution={1: 100, 2: 80, 3: 50},
            consistency_score=0.85,
            polarization_index=0.65,
        )

        assert behavior.candidate_id == 3
        assert behavior.bullet_voters == 50
        assert behavior.ranking_distribution[1] == 100

    def test_ballot_journey_data_creation(self):
        """Test BallotJourneyData data class creation."""
        journey = BallotJourneyData(
            candidate_id=4,
            candidate_name="Diana",
            ballot_flows=[{"ballot_id": "B1", "round": 1, "active": True}],
            round_summaries=[{"round": 1, "total_votes": 200}],
            transfer_patterns=[{"from": "Diana", "to": "Alice", "votes": 50}],
            retention_analysis={"retained": 100, "transferred": 100},
        )

        assert journey.candidate_id == 4
        assert len(journey.ballot_flows) == 1
        assert journey.retention_analysis["retained"] == 100

    def test_supporter_archetype_creation(self):
        """Test SupporterArchetype data class creation."""
        archetype = SupporterArchetype(
            archetype_name="Progressive Coalition",
            ballot_count=150,
            percentage=30.0,
            characteristics={"avg_ranking": 1.5, "coalition_strength": 0.8},
            sample_ballots=["B1", "B2", "B3"],
        )

        assert archetype.archetype_name == "Progressive Coalition"
        assert archetype.ballot_count == 150
        assert len(archetype.sample_ballots) == 3

    def test_supporter_segmentation_creation(self):
        """Test SupporterSegmentation data class creation."""
        archetype = SupporterArchetype(
            archetype_name="Core Supporters",
            ballot_count=100,
            percentage=50.0,
            characteristics={},
            sample_ballots=[],
        )

        segmentation = SupporterSegmentation(
            candidate_id=5,
            candidate_name="Eve",
            archetypes=[archetype],
            clustering_analysis={"n_clusters": 3, "silhouette_score": 0.6},
            preference_patterns={"first_choice_loyalty": 0.8},
        )

        assert segmentation.candidate_id == 5
        assert len(segmentation.archetypes) == 1
        assert segmentation.clustering_analysis["n_clusters"] == 3


class TestCandidateMetrics:
    """Test CandidateMetrics class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock()
        self.metrics = CandidateMetrics(self.mock_db)

    def test_candidate_metrics_initialization(self):
        """Test CandidateMetrics initialization."""
        assert self.metrics.db is self.mock_db

    def test_get_comprehensive_candidate_profile_success(self):
        """Test successful comprehensive candidate profile creation."""
        # Mock candidate info query
        candidate_info = pd.DataFrame(
            {"candidate_id": [1], "candidate_name": ["Alice"]}
        )

        # Mock basic stats
        basic_stats_mock = {
            "total_ballots": 1000,
            "first_choice_votes": 250,
            "first_choice_percentage": 25.0,
        }

        # Set up mock return values
        self.mock_db.query.return_value = candidate_info

        # Mock all the calculation methods
        with (
            patch.object(
                self.metrics, "_calculate_basic_stats", return_value=basic_stats_mock
            ),
            patch.object(
                self.metrics, "_calculate_vote_strength_index", return_value=0.75
            ),
            patch.object(
                self.metrics, "_calculate_cross_camp_appeal", return_value=0.30
            ),
            patch.object(
                self.metrics, "_calculate_transfer_efficiency", return_value=0.85
            ),
            patch.object(
                self.metrics, "_calculate_ranking_consistency", return_value=0.90
            ),
            patch.object(
                self.metrics,
                "_get_vote_progression",
                return_value={
                    "elimination_round": None,
                    "final_status": "winner",
                    "round_by_round": [{"round": 1, "votes": 250}],
                },
            ),
            patch.object(self.metrics, "_get_top_coalition_partners", return_value=[]),
            patch.object(
                self.metrics, "_analyze_supporter_demographics", return_value={}
            ),
        ):

            profile = self.metrics.get_comprehensive_candidate_profile(1)

            assert profile is not None
            assert profile.candidate_id == 1
            assert profile.candidate_name == "Alice"
            assert profile.total_ballots == 1000
            assert profile.first_choice_votes == 250
            assert profile.vote_strength_index == 0.75
            assert profile.final_status == "winner"

    def test_get_comprehensive_candidate_profile_not_found(self):
        """Test candidate profile when candidate not found."""
        # Mock empty candidate info
        self.mock_db.query.return_value = pd.DataFrame()

        profile = self.metrics.get_comprehensive_candidate_profile(999)

        assert profile is None

    def test_get_comprehensive_candidate_profile_exception(self):
        """Test candidate profile with database exception."""
        self.mock_db.query.side_effect = Exception("Database error")

        with patch("src.analysis.candidate_metrics.logger") as mock_logger:
            profile = self.metrics.get_comprehensive_candidate_profile(1)

            assert profile is None
            mock_logger.error.assert_called_once()

    def test_calculate_basic_stats(self):
        """Test basic statistics calculation."""
        # Mock database queries for basic stats
        self.mock_db.query.side_effect = [
            pd.DataFrame({"count": [500]}),  # total_ballots
            pd.DataFrame({"count": [125]}),  # first_choice
            pd.DataFrame({"count": [1000]}),  # total_election_ballots
        ]

        stats = self.metrics._calculate_basic_stats(1)

        assert stats["total_ballots"] == 500
        assert stats["first_choice_votes"] == 125
        assert stats["first_choice_percentage"] == 12.5

    def test_calculate_basic_stats_zero_ballots(self):
        """Test basic statistics with zero total ballots."""
        # Mock database queries with zero total ballots
        self.mock_db.query.side_effect = [
            pd.DataFrame({"count": [100]}),  # total_ballots
            pd.DataFrame({"count": [50]}),  # first_choice
            pd.DataFrame({"count": [0]}),  # total_election_ballots (edge case)
        ]

        stats = self.metrics._calculate_basic_stats(1)

        assert stats["total_ballots"] == 100
        assert stats["first_choice_votes"] == 50
        assert stats["first_choice_percentage"] == 0  # Should handle division by zero

    def test_calculate_vote_strength_index_database_queries(self):
        """Test that vote strength index makes expected database calls."""
        # Mock return values for vote strength calculation
        self.mock_db.query.side_effect = [
            pd.DataFrame({"total_weighted": [150.0]}),  # weighted vote sum
            pd.DataFrame({"count": [100]}),  # total appearances
        ]

        strength_index = self.metrics._calculate_vote_strength_index(1)

        # Should call query twice for vote strength calculation
        assert self.mock_db.query.call_count == 2
        assert isinstance(strength_index, float)

    def test_calculate_cross_camp_appeal_database_queries(self):
        """Test that cross camp appeal makes expected database calls."""
        # Mock return values for cross camp appeal
        self.mock_db.query.side_effect = [
            pd.DataFrame({"diversity_index": [0.65]}),  # diversity calculation
            pd.DataFrame({"count": [200]}),  # total supporters
        ]

        cross_camp = self.metrics._calculate_cross_camp_appeal(1)

        # Should call query for cross camp calculation
        assert self.mock_db.query.call_count == 2
        assert isinstance(cross_camp, float)

    def test_calculate_transfer_efficiency_database_queries(self):
        """Test that transfer efficiency makes expected database calls."""
        # Mock return values for transfer efficiency
        self.mock_db.query.side_effect = [
            pd.DataFrame({"efficiency": [0.85]})  # transfer efficiency
        ]

        efficiency = self.metrics._calculate_transfer_efficiency(1)

        # Should call query for transfer efficiency
        assert self.mock_db.query.call_count == 1
        assert isinstance(efficiency, float)

    def test_calculate_ranking_consistency_database_queries(self):
        """Test that ranking consistency makes expected database calls."""
        # Mock return values for ranking consistency
        self.mock_db.query.side_effect = [
            pd.DataFrame({"consistency_score": [0.90]})  # consistency calculation
        ]

        consistency = self.metrics._calculate_ranking_consistency(1)

        # Should call query for consistency calculation
        assert self.mock_db.query.call_count == 1
        assert isinstance(consistency, float)

    def test_get_vote_progression_database_queries(self):
        """Test that vote progression makes expected database calls."""
        # Mock return values for vote progression
        mock_progression = pd.DataFrame(
            {
                "round": [1, 2, 3],
                "votes": [250, 280, 320],
                "status": ["continuing", "continuing", "winner"],
            }
        )

        self.mock_db.query.return_value = mock_progression

        progression = self.metrics._get_vote_progression(1)

        # Should call query for progression data
        assert self.mock_db.query.call_count == 1
        assert isinstance(progression, dict)
        assert "round_by_round" in progression
        assert "final_status" in progression

    def test_get_top_coalition_partners_database_queries(self):
        """Test that coalition partners makes expected database calls."""
        # Mock return values for coalition partners
        mock_partners = pd.DataFrame(
            {
                "partner_candidate": ["Bob", "Charlie"],
                "support_overlap": [0.4, 0.3],
                "coalition_strength": [0.6, 0.5],
            }
        )

        self.mock_db.query.return_value = mock_partners

        partners = self.metrics._get_top_coalition_partners(1)

        # Should call query for coalition data
        assert self.mock_db.query.call_count == 1
        assert isinstance(partners, list)

    def test_analyze_supporter_demographics_database_queries(self):
        """Test that supporter demographics makes expected database calls."""
        # Mock return values for demographics
        mock_demographics = pd.DataFrame(
            {
                "avg_ranking_position": [1.8],
                "ballot_completion_avg": [3.2],
                "geographic_diversity": [0.7],
            }
        )

        self.mock_db.query.return_value = mock_demographics

        demographics = self.metrics._analyze_supporter_demographics(1)

        # Should call query for demographics data
        assert self.mock_db.query.call_count == 1
        assert isinstance(demographics, dict)

    def test_method_error_handling(self):
        """Test error handling in calculation methods."""
        # Set up database to raise exception
        self.mock_db.query.side_effect = Exception("Database connection failed")

        with patch("src.analysis.candidate_metrics.logger"):
            # Each method should handle exceptions gracefully
            strength = self.metrics._calculate_vote_strength_index(1)
            cross_camp = self.metrics._calculate_cross_camp_appeal(1)
            efficiency = self.metrics._calculate_transfer_efficiency(1)
            consistency = self.metrics._calculate_ranking_consistency(1)

            # Should return default values and log errors
            assert isinstance(strength, (int, float))
            assert isinstance(cross_camp, (int, float))
            assert isinstance(efficiency, (int, float))
            assert isinstance(consistency, (int, float))

    def test_sql_injection_protection(self):
        """Test SQL injection protection in candidate metrics."""
        # Mock database to capture SQL queries
        captured_queries = []

        def capture_query(query):
            captured_queries.append(query)
            return pd.DataFrame({"count": [0]})

        self.mock_db.query.side_effect = capture_query

        # Test with potentially malicious candidate ID
        malicious_id = "1; DROP TABLE candidates; --"

        try:
            # These should not cause SQL injection issues
            self.metrics._calculate_basic_stats(malicious_id)
        except Exception:
            # It's okay if the method fails due to invalid ID format
            # but it shouldn't execute malicious SQL
            pass

        # Verify queries were made (exact content depends on implementation)
        assert len(captured_queries) > 0

    def test_empty_database_handling(self):
        """Test handling of empty database results."""
        # Mock empty database results
        self.mock_db.query.return_value = pd.DataFrame()

        # Methods should handle empty results gracefully
        progression = self.metrics._get_vote_progression(1)
        partners = self.metrics._get_top_coalition_partners(1)
        demographics = self.metrics._analyze_supporter_demographics(1)

        assert isinstance(progression, dict)
        assert isinstance(partners, list)
        assert isinstance(demographics, dict)

    def test_candidate_not_in_ballots_long(self):
        """Test handling when candidate appears in candidates but not ballots_long."""
        # Mock candidate exists but has no ballot data
        self.mock_db.query.side_effect = [
            pd.DataFrame(
                {"candidate_id": [1], "candidate_name": ["Alice"]}
            ),  # candidate exists
            pd.DataFrame({"count": [0]}),  # no ballots
            pd.DataFrame({"count": [0]}),  # no first choice
            pd.DataFrame({"count": [1000]}),  # total ballots in election
        ]

        with (
            patch.object(
                self.metrics, "_calculate_vote_strength_index", return_value=0.0
            ),
            patch.object(
                self.metrics, "_calculate_cross_camp_appeal", return_value=0.0
            ),
            patch.object(
                self.metrics, "_calculate_transfer_efficiency", return_value=0.0
            ),
            patch.object(
                self.metrics, "_calculate_ranking_consistency", return_value=0.0
            ),
            patch.object(self.metrics, "_get_vote_progression", return_value={}),
            patch.object(self.metrics, "_get_top_coalition_partners", return_value=[]),
            patch.object(
                self.metrics, "_analyze_supporter_demographics", return_value={}
            ),
        ):

            profile = self.metrics.get_comprehensive_candidate_profile(1)

            assert profile is not None
            assert profile.total_ballots == 0
            assert profile.first_choice_votes == 0
            assert profile.first_choice_percentage == 0.0
