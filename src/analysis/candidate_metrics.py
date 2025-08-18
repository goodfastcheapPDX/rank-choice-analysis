"""
Advanced candidate metrics analysis for ranked-choice voting elections.

This module provides comprehensive analytics focused on individual candidates,
including preference strength analysis, polarization metrics, transfer efficiency,
and voter behavior patterns.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CandidateProfile:
    """Comprehensive candidate profile with advanced metrics."""

    candidate_id: int
    candidate_name: str
    total_ballots: int
    first_choice_votes: int
    first_choice_percentage: float
    vote_strength_index: float
    cross_camp_appeal: float
    transfer_efficiency: float
    ranking_consistency: float
    elimination_round: Optional[int]
    final_status: str  # 'winner', 'eliminated', 'continuing'
    vote_progression: List[Dict[str, Any]]
    top_coalition_partners: List[Dict[str, Any]]
    supporter_demographics: Dict[str, Any]


@dataclass
class TransferEfficiency:
    """Analysis of how effectively a candidate's votes transfer."""

    candidate_id: int
    candidate_name: str
    total_transferable_votes: int
    successful_transfers: int
    transfer_efficiency_rate: float
    avg_transfer_distance: float
    top_transfer_destinations: List[Dict[str, Any]]
    transfer_pattern_type: str  # 'concentrated', 'dispersed', 'mixed'


@dataclass
class VoterBehaviorAnalysis:
    """Analysis of voter behavior patterns for a candidate."""

    candidate_id: int
    candidate_name: str
    bullet_voters: int  # Voters who only ranked this candidate
    bullet_voter_percentage: float
    avg_ranking_position: float
    ranking_distribution: Dict[int, int]  # Position -> count
    consistency_score: float
    polarization_index: float


@dataclass
class BallotJourneyData:
    """Tracks how ballots that ranked a candidate moved through STV rounds."""

    candidate_id: int
    candidate_name: str
    ballot_flows: List[Dict[str, Any]]  # Individual ballot journeys
    round_summaries: List[Dict[str, Any]]  # Summary by round
    transfer_patterns: List[Dict[str, Any]]  # Where votes went
    retention_analysis: Dict[str, Any]  # How many votes stayed vs transferred


@dataclass
class SupporterArchetype:
    """Analysis of different types of supporters for a candidate."""

    archetype_name: str
    ballot_count: int
    percentage: float
    characteristics: Dict[str, Any]
    sample_ballots: List[str]  # Sample ballot IDs


@dataclass
class SupporterSegmentation:
    """Comprehensive supporter segmentation analysis."""

    candidate_id: int
    candidate_name: str
    archetypes: List[SupporterArchetype]
    clustering_analysis: Dict[str, Any]
    preference_patterns: Dict[str, Any]


class CandidateMetrics:
    """Advanced metrics calculator for individual candidates."""

    def __init__(self, database):
        """Initialize with database connection."""
        self.db = database

    def get_comprehensive_candidate_profile(
        self, candidate_id: int
    ) -> Optional[CandidateProfile]:
        """Get complete candidate profile with all advanced metrics."""
        try:
            # Get basic candidate info
            candidate_info = self.db.query(
                f"""
                SELECT candidate_id, candidate_name
                FROM candidates
                WHERE candidate_id = {candidate_id}
            """
            )

            if candidate_info.empty:
                return None

            candidate_name = candidate_info.iloc[0]["candidate_name"]

            # Calculate all metrics
            basic_stats = self._calculate_basic_stats(candidate_id)
            strength_index = self._calculate_vote_strength_index(candidate_id)
            cross_camp = self._calculate_cross_camp_appeal(candidate_id)
            transfer_eff = self._calculate_transfer_efficiency(candidate_id)
            consistency = self._calculate_ranking_consistency(candidate_id)
            progression = self._get_vote_progression(candidate_id)
            coalition_partners = self._get_top_coalition_partners(candidate_id)
            demographics = self._analyze_supporter_demographics(candidate_id)

            return CandidateProfile(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                total_ballots=basic_stats["total_ballots"],
                first_choice_votes=basic_stats["first_choice_votes"],
                first_choice_percentage=basic_stats["first_choice_percentage"],
                vote_strength_index=strength_index,
                cross_camp_appeal=cross_camp,
                transfer_efficiency=transfer_eff,
                ranking_consistency=consistency,
                elimination_round=progression.get("elimination_round"),
                final_status=progression.get("final_status", "unknown"),
                vote_progression=progression.get("round_by_round", []),
                top_coalition_partners=coalition_partners,
                supporter_demographics=demographics,
            )

        except Exception as e:
            logger.error(f"Error creating candidate profile for {candidate_id}: {e}")
            return None

    def _calculate_basic_stats(self, candidate_id: int) -> Dict[str, Any]:
        """Calculate basic candidate statistics."""
        # Total ballots where candidate appears
        total_ballots = self.db.query(
            f"""
            SELECT COUNT(DISTINCT BallotID) as count
            FROM ballots_long
            WHERE candidate_id = {candidate_id}
        """
        ).iloc[0]["count"]

        # First choice votes
        first_choice = self.db.query(
            f"""
            SELECT COUNT(*) as count
            FROM ballots_long
            WHERE candidate_id = {candidate_id} AND rank_position = 1
        """
        ).iloc[0]["count"]

        # Total ballots in election
        total_election_ballots = self.db.query(
            """
            SELECT COUNT(DISTINCT BallotID) as count FROM ballots_long
        """
        ).iloc[0]["count"]

        first_choice_percentage = (
            (first_choice / total_election_ballots) * 100
            if total_election_ballots > 0
            else 0
        )

        return {
            "total_ballots": total_ballots,
            "first_choice_votes": first_choice,
            "first_choice_percentage": round(first_choice_percentage, 2),
        }

    def _calculate_vote_strength_index(self, candidate_id: int) -> float:
        """
        Calculate Vote Strength Index - measures intensity of voter preference.
        Higher scores indicate voters rank this candidate early and consistently.
        """
        try:
            # Get ranking distribution
            ranking_data = self.db.query(
                f"""
                SELECT
                    rank_position,
                    COUNT(*) as votes
                FROM ballots_long
                WHERE candidate_id = {candidate_id}
                GROUP BY rank_position
                ORDER BY rank_position
            """
            )

            if ranking_data.empty:
                return 0.0

            # Calculate weighted score (earlier ranks worth more)
            total_weighted_score = 0
            total_votes = 0

            for _, row in ranking_data.iterrows():
                rank = row["rank_position"]
                votes = row["votes"]
                # Weight decreases with rank position (1st=6pts, 2nd=5pts, etc.)
                weight = max(0, 7 - rank)
                total_weighted_score += weight * votes
                total_votes += votes

            # Normalize to 0-1 scale
            max_possible_score = total_votes * 6  # All first choice would be max
            strength_index = (
                total_weighted_score / max_possible_score
                if max_possible_score > 0
                else 0
            )

            return round(strength_index, 4)

        except Exception as e:
            logger.error(
                f"Error calculating vote strength index for {candidate_id}: {e}"
            )
            return 0.0

    def _calculate_cross_camp_appeal(self, candidate_id: int) -> float:
        """
        Calculate Cross-Camp Appeal - measures how well candidate attracts
        votes across different political groupings.
        """
        try:
            # Get voters who ranked this candidate
            candidate_voters = self.db.query(
                f"""
                SELECT DISTINCT BallotID
                FROM ballots_long
                WHERE candidate_id = {candidate_id}
            """
            )

            if candidate_voters.empty:
                return 0.0

            # Analyze diversity of other candidates these voters also ranked
            ballot_list = "'" + "','".join(candidate_voters["BallotID"]) + "'"

            diversity_analysis = self.db.query(
                f"""
                SELECT
                    bl.BallotID,
                    COUNT(DISTINCT bl.candidate_id) as unique_candidates_ranked,
                    STRING_AGG(DISTINCT c.candidate_name, '|' ORDER BY bl.rank_position) as ranking_sequence
                FROM ballots_long bl
                JOIN candidates c ON bl.candidate_id = c.candidate_id
                WHERE bl.BallotID IN ({ballot_list})
                GROUP BY bl.BallotID
            """
            )

            if diversity_analysis.empty:
                return 0.0

            # Calculate cross-camp appeal based on ranking diversity
            avg_unique_candidates = diversity_analysis[
                "unique_candidates_ranked"
            ].mean()
            max_possible_candidates = min(
                6, len(self.db.query("SELECT DISTINCT candidate_id FROM candidates"))
            )

            # Normalize to 0-1 scale
            cross_camp_appeal = (
                (avg_unique_candidates - 1) / (max_possible_candidates - 1)
                if max_possible_candidates > 1
                else 0
            )

            return round(cross_camp_appeal, 4)

        except Exception as e:
            logger.error(f"Error calculating cross-camp appeal for {candidate_id}: {e}")
            return 0.0

    def _calculate_transfer_efficiency(self, candidate_id: int) -> float:
        """
        Calculate Transfer Efficiency - measures how effectively this candidate's
        votes transfer to preferred alternatives when eliminated.
        """
        try:
            # Get ballots that ranked this candidate
            candidate_ballots = self.db.query(
                f"""
                SELECT
                    BallotID,
                    rank_position as candidate_rank
                FROM ballots_long
                WHERE candidate_id = {candidate_id}
            """
            )

            if candidate_ballots.empty:
                return 0.0

            # Analyze transfer potential - how many have next preferences
            transfer_analysis = self.db.query(
                f"""
                WITH candidate_ballots AS (
                    SELECT BallotID, rank_position as candidate_rank
                    FROM ballots_long
                    WHERE candidate_id = {candidate_id}
                ),
                next_preferences AS (
                    SELECT
                        cb.BallotID,
                        cb.candidate_rank,
                        COUNT(bl2.candidate_id) as next_choices_available
                    FROM candidate_ballots cb
                    LEFT JOIN ballots_long bl2 ON cb.BallotID = bl2.BallotID
                        AND bl2.rank_position > cb.candidate_rank
                        AND bl2.candidate_id != {candidate_id}
                    GROUP BY cb.BallotID, cb.candidate_rank
                )
                SELECT
                    AVG(CASE WHEN next_choices_available > 0 THEN 1.0 ELSE 0.0 END) as transfer_rate,
                    AVG(next_choices_available) as avg_next_choices
                FROM next_preferences
            """
            )

            if transfer_analysis.empty:
                return 0.0

            transfer_rate = transfer_analysis.iloc[0]["transfer_rate"] or 0
            return round(transfer_rate, 4)

        except Exception as e:
            logger.error(
                f"Error calculating transfer efficiency for {candidate_id}: {e}"
            )
            return 0.0

    def _calculate_ranking_consistency(self, candidate_id: int) -> float:
        """
        Calculate Ranking Consistency - measures how consistently voters
        rank this candidate across different ballot positions.
        """
        try:
            ranking_distribution = self.db.query(
                f"""
                SELECT
                    rank_position,
                    COUNT(*) as votes,
                    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
                FROM ballots_long
                WHERE candidate_id = {candidate_id}
                GROUP BY rank_position
                ORDER BY rank_position
            """
            )

            if ranking_distribution.empty:
                return 0.0

            # Calculate consistency using entropy-based measure
            percentages = ranking_distribution["percentage"].values / 100.0
            # Higher concentration = higher consistency
            entropy = -sum(p * np.log2(p) for p in percentages if p > 0)
            max_entropy = np.log2(len(percentages))

            # Convert to consistency score (0 = scattered, 1 = concentrated)
            consistency = 1 - (entropy / max_entropy) if max_entropy > 0 else 1

            return round(consistency, 4)

        except Exception as e:
            logger.error(
                f"Error calculating ranking consistency for {candidate_id}: {e}"
            )
            return 0.0

    def _get_vote_progression(self, candidate_id: int) -> Dict[str, Any]:
        """Get vote progression through STV rounds (requires STV results)."""
        try:
            # This would require running STV and tracking vote counts
            # For now, return basic progression info
            return {
                "elimination_round": None,
                "final_status": "unknown",
                "round_by_round": [],
            }
        except Exception as e:
            logger.error(f"Error getting vote progression for {candidate_id}: {e}")
            return {
                "elimination_round": None,
                "final_status": "unknown",
                "round_by_round": [],
            }

    def _get_top_coalition_partners(
        self, candidate_id: int, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top coalition partners for this candidate."""
        try:
            # Get shared ballot analysis
            coalition_data = self.db.query(
                f"""
                WITH candidate_ballots AS (
                    SELECT DISTINCT BallotID
                    FROM ballots_long
                    WHERE candidate_id = {candidate_id}
                ),
                shared_ballots AS (
                    SELECT
                        bl.candidate_id as other_candidate_id,
                        c.candidate_name as other_candidate_name,
                        COUNT(*) as shared_ballots,
                        AVG(ABS(bl.rank_position - main.rank_position)) as avg_rank_distance
                    FROM candidate_ballots cb
                    JOIN ballots_long main ON cb.BallotID = main.BallotID AND main.candidate_id = {candidate_id}
                    JOIN ballots_long bl ON cb.BallotID = bl.BallotID AND bl.candidate_id != {candidate_id}
                    JOIN candidates c ON bl.candidate_id = c.candidate_id
                    GROUP BY bl.candidate_id, c.candidate_name
                    HAVING COUNT(*) >= 100
                )
                SELECT
                    other_candidate_id,
                    other_candidate_name,
                    shared_ballots,
                    avg_rank_distance,
                    shared_ballots / (avg_rank_distance + 1) as coalition_score
                FROM shared_ballots
                ORDER BY coalition_score DESC
                LIMIT {limit}
            """
            )

            return coalition_data.to_dict("records")

        except Exception as e:
            logger.error(f"Error getting coalition partners for {candidate_id}: {e}")
            return []

    def _analyze_supporter_demographics(self, candidate_id: int) -> Dict[str, Any]:
        """Analyze demographics and patterns of candidate supporters."""
        try:
            # Get basic supporter statistics
            supporter_stats = self.db.query(
                f"""
                WITH candidate_supporters AS (
                    SELECT DISTINCT BallotID
                    FROM ballots_long
                    WHERE candidate_id = {candidate_id}
                ),
                supporter_analysis AS (
                    SELECT
                        cs.BallotID,
                        COUNT(bl.candidate_id) as total_candidates_ranked,
                        MIN(bl.rank_position) as earliest_rank,
                        MAX(bl.rank_position) as latest_rank
                    FROM candidate_supporters cs
                    JOIN ballots_long bl ON cs.BallotID = bl.BallotID
                    GROUP BY cs.BallotID
                )
                SELECT
                    COUNT(*) as total_supporters,
                    AVG(total_candidates_ranked) as avg_candidates_ranked,
                    AVG(earliest_rank) as avg_earliest_rank,
                    AVG(latest_rank) as avg_latest_rank,
                    COUNT(CASE WHEN total_candidates_ranked = 1 THEN 1 END) as bullet_voters
                FROM supporter_analysis
            """
            )

            if supporter_stats.empty:
                return {}

            stats = supporter_stats.iloc[0]
            return {
                "total_supporters": int(stats["total_supporters"]),
                "avg_candidates_ranked": round(
                    float(stats["avg_candidates_ranked"]), 2
                ),
                "avg_earliest_rank": round(float(stats["avg_earliest_rank"]), 2),
                "avg_latest_rank": round(float(stats["avg_latest_rank"]), 2),
                "bullet_voters": int(stats["bullet_voters"]),
                "bullet_voter_percentage": round(
                    (stats["bullet_voters"] / stats["total_supporters"]) * 100, 2
                ),
            }

        except Exception as e:
            logger.error(
                f"Error analyzing supporter demographics for {candidate_id}: {e}"
            )
            return {}

    def get_transfer_efficiency_analysis(
        self, candidate_id: int
    ) -> Optional[TransferEfficiency]:
        """Get detailed transfer efficiency analysis for a candidate."""
        try:
            candidate_info = self.db.query(
                f"""
                SELECT candidate_name FROM candidates WHERE candidate_id = {candidate_id}
            """
            )

            if candidate_info.empty:
                return None

            candidate_name = candidate_info.iloc[0]["candidate_name"]

            # Analyze transfer patterns
            transfer_data = self.db.query(
                f"""
                WITH candidate_ballots AS (
                    SELECT
                        BallotID,
                        rank_position as candidate_rank
                    FROM ballots_long
                    WHERE candidate_id = {candidate_id}
                ),
                transfer_destinations AS (
                    SELECT
                        cb.BallotID,
                        bl.candidate_id as destination_candidate,
                        c.candidate_name as destination_name,
                        bl.rank_position,
                        bl.rank_position - cb.candidate_rank as rank_distance
                    FROM candidate_ballots cb
                    JOIN ballots_long bl ON cb.BallotID = bl.BallotID
                        AND bl.rank_position > cb.candidate_rank
                        AND bl.candidate_id != {candidate_id}
                    JOIN candidates c ON bl.candidate_id = c.candidate_id
                )
                SELECT
                    destination_candidate,
                    destination_name,
                    COUNT(*) as transfer_votes,
                    AVG(rank_distance) as avg_transfer_distance,
                    MIN(rank_distance) as min_transfer_distance
                FROM transfer_destinations
                GROUP BY destination_candidate, destination_name
                ORDER BY transfer_votes DESC
                LIMIT 10
            """
            )

            total_transferable = self.db.query(
                f"""
                SELECT COUNT(DISTINCT BallotID) as count
                FROM ballots_long bl1
                WHERE bl1.candidate_id = {candidate_id}
                AND EXISTS (
                    SELECT 1 FROM ballots_long bl2
                    WHERE bl2.BallotID = bl1.BallotID
                    AND bl2.rank_position > bl1.rank_position
                    AND bl2.candidate_id != {candidate_id}
                )
            """
            ).iloc[0]["count"]

            successful_transfers = (
                transfer_data["transfer_votes"].sum() if not transfer_data.empty else 0
            )
            transfer_efficiency_rate = (
                (successful_transfers / total_transferable)
                if total_transferable > 0
                else 0
            )
            avg_transfer_distance = (
                transfer_data["avg_transfer_distance"].mean()
                if not transfer_data.empty
                else 0
            )

            # Determine transfer pattern type
            if transfer_data.empty:
                pattern_type = "none"
            elif len(transfer_data) <= 3:
                pattern_type = "concentrated"
            elif transfer_data.iloc[0]["transfer_votes"] / successful_transfers > 0.5:
                pattern_type = "concentrated"
            else:
                pattern_type = "dispersed"

            return TransferEfficiency(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                total_transferable_votes=total_transferable,
                successful_transfers=successful_transfers,
                transfer_efficiency_rate=round(transfer_efficiency_rate, 4),
                avg_transfer_distance=round(avg_transfer_distance, 2),
                top_transfer_destinations=transfer_data.to_dict("records"),
                transfer_pattern_type=pattern_type,
            )

        except Exception as e:
            logger.error(f"Error analyzing transfer efficiency for {candidate_id}: {e}")
            return None

    def get_voter_behavior_analysis(
        self, candidate_id: int
    ) -> Optional[VoterBehaviorAnalysis]:
        """Get detailed voter behavior analysis for a candidate."""
        try:
            candidate_info = self.db.query(
                f"""
                SELECT candidate_name FROM candidates WHERE candidate_id = {candidate_id}
            """
            )

            if candidate_info.empty:
                return None

            candidate_name = candidate_info.iloc[0]["candidate_name"]

            # Analyze voting patterns
            voting_patterns = self.db.query(
                f"""
                WITH candidate_voters AS (
                    SELECT
                        bl.BallotID,
                        bl.rank_position,
                        COUNT(bl2.candidate_id) as total_ranked_by_voter
                    FROM ballots_long bl
                    LEFT JOIN ballots_long bl2 ON bl.BallotID = bl2.BallotID
                    WHERE bl.candidate_id = {candidate_id}
                    GROUP BY bl.BallotID, bl.rank_position
                )
                SELECT
                    COUNT(*) as total_voters,
                    AVG(rank_position) as avg_ranking_position,
                    COUNT(CASE WHEN total_ranked_by_voter = 1 THEN 1 END) as bullet_voters
                FROM candidate_voters
            """
            )

            ranking_distribution = self.db.query(
                f"""
                SELECT
                    rank_position,
                    COUNT(*) as count
                FROM ballots_long
                WHERE candidate_id = {candidate_id}
                GROUP BY rank_position
                ORDER BY rank_position
            """
            )

            if voting_patterns.empty:
                return None

            stats = voting_patterns.iloc[0]
            total_voters = int(stats["total_voters"])
            bullet_voters = int(stats["bullet_voters"])
            bullet_percentage = (
                (bullet_voters / total_voters * 100) if total_voters > 0 else 0
            )

            # Calculate consistency and polarization
            consistency_score = self._calculate_ranking_consistency(candidate_id)

            # Simple polarization index based on bullet voting and ranking spread
            polarization_index = (
                bullet_percentage / 100.0
            )  # Higher bullet voting = more polarizing

            ranking_dist_dict = dict(
                zip(
                    ranking_distribution["rank_position"], ranking_distribution["count"]
                )
            )

            return VoterBehaviorAnalysis(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                bullet_voters=bullet_voters,
                bullet_voter_percentage=round(bullet_percentage, 2),
                avg_ranking_position=round(float(stats["avg_ranking_position"]), 2),
                ranking_distribution=ranking_dist_dict,
                consistency_score=consistency_score,
                polarization_index=round(polarization_index, 4),
            )

        except Exception as e:
            logger.error(f"Error analyzing voter behavior for {candidate_id}: {e}")
            return None

    def get_all_candidates_summary(self) -> List[Dict[str, Any]]:
        """Get summary metrics for all candidates."""
        try:
            candidates = self.db.query(
                "SELECT candidate_id, candidate_name FROM candidates ORDER BY candidate_name"
            )

            summaries = []
            for _, candidate in candidates.iterrows():
                candidate_id = candidate["candidate_id"]

                # Get basic metrics
                basic_stats = self._calculate_basic_stats(candidate_id)
                strength_index = self._calculate_vote_strength_index(candidate_id)
                cross_camp = self._calculate_cross_camp_appeal(candidate_id)

                summaries.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_name": candidate["candidate_name"],
                        "total_ballots": basic_stats["total_ballots"],
                        "first_choice_votes": basic_stats["first_choice_votes"],
                        "first_choice_percentage": basic_stats[
                            "first_choice_percentage"
                        ],
                        "vote_strength_index": strength_index,
                        "cross_camp_appeal": cross_camp,
                    }
                )

            return summaries

        except Exception as e:
            logger.error(f"Error getting candidates summary: {e}")
            return []

    def get_ballot_journey_analysis(
        self, candidate_id: int
    ) -> Optional[BallotJourneyData]:
        """Get detailed ballot journey analysis showing how ballots that ranked this candidate moved through STV."""
        try:
            candidate_info = self.db.query(
                f"""
                SELECT candidate_name FROM candidates WHERE candidate_id = {candidate_id}
            """
            )

            if candidate_info.empty:
                return None

            candidate_name = candidate_info.iloc[0]["candidate_name"]

            # Get all ballots that ranked this candidate
            candidate_ballots = self.db.query(
                f"""
                SELECT
                    BallotID,
                    rank_position,
                    candidate_id
                FROM ballots_long
                WHERE candidate_id = {candidate_id}
            """
            )

            if candidate_ballots.empty:
                return BallotJourneyData(
                    candidate_id=candidate_id,
                    candidate_name=candidate_name,
                    ballot_flows=[],
                    round_summaries=[],
                    transfer_patterns=[],
                    retention_analysis={},
                )

            # For detailed ballot journey analysis, we need to run STV with tracking
            # This would require integration with the STV tabulator
            # For now, we'll provide static analysis of ranking patterns

            # Sample a subset of ballots for performance (limit to 100 ballots for demo)
            sample_ballots = candidate_ballots.head(100)

            ballot_flows = []
            for _, ballot in sample_ballots.iterrows():
                ballot_id = ballot["BallotID"]

                # Get full ranking sequence for this ballot
                full_ballot = self.db.query(
                    f"""
                    SELECT
                        bl.candidate_id,
                        bl.rank_position,
                        c.candidate_name
                    FROM ballots_long bl
                    JOIN candidates c ON bl.candidate_id = c.candidate_id
                    WHERE bl.BallotID = '{ballot_id}'
                    ORDER BY bl.rank_position
                """
                )

                ranking_sequence = []
                for _, ranking in full_ballot.iterrows():
                    ranking_sequence.append(
                        {
                            "candidate_id": ranking["candidate_id"],
                            "candidate_name": ranking["candidate_name"],
                            "rank_position": ranking["rank_position"],
                        }
                    )

                ballot_flows.append(
                    {
                        "ballot_id": ballot_id,
                        "candidate_rank_position": ballot["rank_position"],
                        "full_ranking_sequence": ranking_sequence,
                        "transfer_potential": len(ranking_sequence)
                        - ballot["rank_position"],
                    }
                )

            # Analyze transfer patterns from ranking data
            transfer_patterns = self._analyze_ranking_transfer_patterns(
                candidate_id, candidate_ballots
            )

            # Calculate retention analysis
            retention_analysis = self._calculate_retention_analysis(
                candidate_id, candidate_ballots
            )

            # Generate round summaries (simplified without actual STV run)
            round_summaries = self._generate_simplified_round_summaries(
                candidate_id, transfer_patterns
            )

            return BallotJourneyData(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                ballot_flows=ballot_flows,
                round_summaries=round_summaries,
                transfer_patterns=transfer_patterns,
                retention_analysis=retention_analysis,
            )

        except Exception as e:
            logger.error(
                f"Error analyzing ballot journey for candidate {candidate_id}: {e}"
            )
            return None

    def _analyze_ranking_transfer_patterns(
        self, candidate_id: int, candidate_ballots: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """Analyze where votes would transfer based on ranking patterns."""
        try:
            transfer_patterns = []

            # Get potential transfer destinations for each ballot
            transfer_data = self.db.query(
                f"""
                WITH candidate_ballots AS (
                    SELECT
                        BallotID,
                        rank_position as candidate_rank
                    FROM ballots_long
                    WHERE candidate_id = {candidate_id}
                ),
                next_choices AS (
                    SELECT
                        cb.BallotID,
                        cb.candidate_rank,
                        bl.candidate_id as next_candidate_id,
                        c.candidate_name as next_candidate_name,
                        bl.rank_position as next_rank,
                        bl.rank_position - cb.candidate_rank as transfer_distance
                    FROM candidate_ballots cb
                    JOIN ballots_long bl ON cb.BallotID = bl.BallotID
                        AND bl.rank_position > cb.candidate_rank
                        AND bl.candidate_id != {candidate_id}
                    JOIN candidates c ON bl.candidate_id = c.candidate_id
                )
                SELECT
                    next_candidate_id,
                    next_candidate_name,
                    COUNT(*) as transfer_votes,
                    AVG(transfer_distance) as avg_transfer_distance,
                    MIN(transfer_distance) as min_transfer_distance,
                    STRING_AGG(DISTINCT BallotID, ',') as sample_ballots
                FROM next_choices
                WHERE transfer_distance = 1  -- Immediate next choice
                GROUP BY next_candidate_id, next_candidate_name
                ORDER BY transfer_votes DESC
            """
            )

            for _, row in transfer_data.iterrows():
                transfer_patterns.append(
                    {
                        "destination_candidate_id": row["next_candidate_id"],
                        "destination_candidate_name": row["next_candidate_name"],
                        "transfer_votes": row["transfer_votes"],
                        "avg_transfer_distance": round(row["avg_transfer_distance"], 2),
                        "min_transfer_distance": row["min_transfer_distance"],
                        "sample_ballots": (
                            row["sample_ballots"].split(",")[:5]
                            if row["sample_ballots"]
                            else []
                        ),
                    }
                )

            return transfer_patterns

        except Exception as e:
            logger.error(f"Error analyzing transfer patterns: {e}")
            return []

    def _calculate_retention_analysis(
        self, candidate_id: int, candidate_ballots: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calculate how many votes stay vs transfer."""
        try:
            total_ballots = len(candidate_ballots)

            # Count ballots with next preferences
            ballots_with_transfers = self.db.query(
                f"""
                WITH candidate_ballots AS (
                    SELECT
                        BallotID,
                        rank_position as candidate_rank
                    FROM ballots_long
                    WHERE candidate_id = {candidate_id}
                )
                SELECT COUNT(DISTINCT cb.BallotID) as count
                FROM candidate_ballots cb
                JOIN ballots_long bl ON cb.BallotID = bl.BallotID
                    AND bl.rank_position > cb.candidate_rank
                    AND bl.candidate_id != {candidate_id}
            """
            ).iloc[0]["count"]

            # Count bullet voters (would exhaust)
            bullet_voters = total_ballots - ballots_with_transfers

            return {
                "total_ballots": total_ballots,
                "ballots_with_transfers": ballots_with_transfers,
                "bullet_voters": bullet_voters,
                "transfer_rate": (
                    round((ballots_with_transfers / total_ballots) * 100, 2)
                    if total_ballots > 0
                    else 0
                ),
                "exhaustion_rate": (
                    round((bullet_voters / total_ballots) * 100, 2)
                    if total_ballots > 0
                    else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error calculating retention analysis: {e}")
            return {}

    def _generate_simplified_round_summaries(
        self, candidate_id: int, transfer_patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate simplified round summaries without full STV run."""
        try:
            # This is a simplified version - in reality we'd need actual STV round data
            summaries = []

            if transfer_patterns:
                summaries.append(
                    {
                        "round_type": "elimination_simulation",
                        "description": "Potential vote transfer if candidate eliminated",
                        "top_destinations": transfer_patterns[:5],
                        "total_transferable": sum(
                            p["transfer_votes"] for p in transfer_patterns
                        ),
                    }
                )

            return summaries

        except Exception as e:
            logger.error(f"Error generating round summaries: {e}")
            return []

    def get_supporter_segmentation_analysis(
        self, candidate_id: int
    ) -> Optional[SupporterSegmentation]:
        """Analyze different types of supporters and their characteristics."""
        try:
            candidate_info = self.db.query(
                f"""
                SELECT candidate_name FROM candidates WHERE candidate_id = {candidate_id}
            """
            )

            if candidate_info.empty:
                return None

            candidate_name = candidate_info.iloc[0]["candidate_name"]

            # Analyze different supporter archetypes
            archetypes = []

            # 1. Bullet Voters - only ranked this candidate
            bullet_voters = self.db.query(
                f"""
                WITH candidate_supporters AS (
                    SELECT DISTINCT BallotID
                    FROM ballots_long
                    WHERE candidate_id = {candidate_id}
                ),
                ballot_completeness AS (
                    SELECT
                        cs.BallotID,
                        COUNT(bl.candidate_id) as total_candidates_ranked
                    FROM candidate_supporters cs
                    JOIN ballots_long bl ON cs.BallotID = bl.BallotID
                    GROUP BY cs.BallotID
                )
                SELECT
                    COUNT(*) as bullet_count,
                    STRING_AGG(BallotID, ',') as sample_ballots
                FROM ballot_completeness
                WHERE total_candidates_ranked = 1
            """
            )

            bullet_count = bullet_voters.iloc[0]["bullet_count"]
            bullet_samples = (
                bullet_voters.iloc[0]["sample_ballots"].split(",")[:3]
                if bullet_voters.iloc[0]["sample_ballots"]
                else []
            )

            # 2. Strategic Rankers - ranked many candidates with this one highly
            strategic_rankers = self.db.query(
                f"""
                WITH candidate_supporters AS (
                    SELECT
                        BallotID,
                        rank_position as candidate_rank
                    FROM ballots_long
                    WHERE candidate_id = {candidate_id}
                ),
                ballot_completeness AS (
                    SELECT
                        cs.BallotID,
                        cs.candidate_rank,
                        COUNT(bl.candidate_id) as total_candidates_ranked
                    FROM candidate_supporters cs
                    JOIN ballots_long bl ON cs.BallotID = bl.BallotID
                    GROUP BY cs.BallotID, cs.candidate_rank
                )
                SELECT
                    COUNT(*) as strategic_count,
                    STRING_AGG(BallotID, ',') as sample_ballots
                FROM ballot_completeness
                WHERE total_candidates_ranked >= 4 AND candidate_rank <= 2
            """
            )

            strategic_count = strategic_rankers.iloc[0]["strategic_count"]
            strategic_samples = (
                strategic_rankers.iloc[0]["sample_ballots"].split(",")[:3]
                if strategic_rankers.iloc[0]["sample_ballots"]
                else []
            )

            # 3. Coalition Builders - ranked this candidate with many others
            coalition_builders = self.db.query(
                f"""
                WITH candidate_supporters AS (
                    SELECT
                        BallotID,
                        rank_position as candidate_rank
                    FROM ballots_long
                    WHERE candidate_id = {candidate_id}
                ),
                ballot_completeness AS (
                    SELECT
                        cs.BallotID,
                        cs.candidate_rank,
                        COUNT(bl.candidate_id) as total_candidates_ranked
                    FROM candidate_supporters cs
                    JOIN ballots_long bl ON cs.BallotID = bl.BallotID
                    GROUP BY cs.BallotID, cs.candidate_rank
                )
                SELECT
                    COUNT(*) as coalition_count,
                    STRING_AGG(BallotID, ',') as sample_ballots
                FROM ballot_completeness
                WHERE total_candidates_ranked >= 5 AND candidate_rank >= 3
            """
            )

            coalition_count = coalition_builders.iloc[0]["coalition_count"]
            coalition_samples = (
                coalition_builders.iloc[0]["sample_ballots"].split(",")[:3]
                if coalition_builders.iloc[0]["sample_ballots"]
                else []
            )

            # Get total supporters for percentage calculations
            total_supporters = self.db.query(
                f"""
                SELECT COUNT(DISTINCT BallotID) as count
                FROM ballots_long
                WHERE candidate_id = {candidate_id}
            """
            ).iloc[0]["count"]

            # Create archetype objects
            if bullet_count > 0:
                archetypes.append(
                    SupporterArchetype(
                        archetype_name="Bullet Voters",
                        ballot_count=bullet_count,
                        percentage=(
                            round((bullet_count / total_supporters) * 100, 2)
                            if total_supporters > 0
                            else 0
                        ),
                        characteristics={
                            "description": "Voted only for this candidate",
                            "loyalty": "Extremely High",
                            "engagement": "Focused",
                            "transfer_potential": "None (votes exhaust)",
                        },
                        sample_ballots=bullet_samples,
                    )
                )

            if strategic_count > 0:
                archetypes.append(
                    SupporterArchetype(
                        archetype_name="Strategic Rankers",
                        ballot_count=strategic_count,
                        percentage=(
                            round((strategic_count / total_supporters) * 100, 2)
                            if total_supporters > 0
                            else 0
                        ),
                        characteristics={
                            "description": "Ranked this candidate highly among many choices",
                            "loyalty": "High",
                            "engagement": "Strategic",
                            "transfer_potential": "High (good backup plans)",
                        },
                        sample_ballots=strategic_samples,
                    )
                )

            if coalition_count > 0:
                archetypes.append(
                    SupporterArchetype(
                        archetype_name="Coalition Builders",
                        ballot_count=coalition_count,
                        percentage=(
                            round((coalition_count / total_supporters) * 100, 2)
                            if total_supporters > 0
                            else 0
                        ),
                        characteristics={
                            "description": "Ranked many candidates including this one",
                            "loyalty": "Moderate",
                            "engagement": "Broad",
                            "transfer_potential": "Very High (many alternatives)",
                        },
                        sample_ballots=coalition_samples,
                    )
                )

            # Generate clustering analysis
            clustering_analysis = {
                "total_supporters": total_supporters,
                "archetypes_identified": len(archetypes),
                "largest_segment": (
                    max(archetypes, key=lambda x: x.ballot_count).archetype_name
                    if archetypes
                    else None
                ),
                "diversity_score": len(archetypes)
                / 3.0,  # Score out of 1.0 for max diversity
            }

            # Analyze preference patterns
            preference_patterns = self._analyze_preference_patterns(candidate_id)

            return SupporterSegmentation(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                archetypes=archetypes,
                clustering_analysis=clustering_analysis,
                preference_patterns=preference_patterns,
            )

        except Exception as e:
            logger.error(
                f"Error analyzing supporter segmentation for candidate {candidate_id}: {e}"
            )
            return None

    def _analyze_preference_patterns(self, candidate_id: int) -> Dict[str, Any]:
        """Analyze common preference patterns among supporters."""
        try:
            # Find most common co-ranked candidates
            common_coranked = self.db.query(
                f"""
                WITH candidate_ballots AS (
                    SELECT DISTINCT BallotID
                    FROM ballots_long
                    WHERE candidate_id = {candidate_id}
                )
                SELECT
                    bl.candidate_id,
                    c.candidate_name,
                    COUNT(*) as co_appearances,
                    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM candidate_ballots), 2) as percentage
                FROM candidate_ballots cb
                JOIN ballots_long bl ON cb.BallotID = bl.BallotID AND bl.candidate_id != {candidate_id}
                JOIN candidates c ON bl.candidate_id = c.candidate_id
                GROUP BY bl.candidate_id, c.candidate_name
                ORDER BY co_appearances DESC
                LIMIT 10
            """
            )

            # Analyze ranking position patterns
            position_patterns = self.db.query(
                f"""
                SELECT
                    rank_position,
                    COUNT(*) as votes,
                    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
                FROM ballots_long
                WHERE candidate_id = {candidate_id}
                GROUP BY rank_position
                ORDER BY rank_position
            """
            )

            return {
                "most_common_coranked": common_coranked.to_dict("records"),
                "ranking_position_distribution": position_patterns.to_dict("records"),
                "primary_ranking_position": (
                    position_patterns.loc[position_patterns["votes"].idxmax()][
                        "rank_position"
                    ]
                    if not position_patterns.empty
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"Error analyzing preference patterns: {e}")
            return {}

    def get_coalition_centrality_analysis(self, candidate_id: int) -> Dict[str, Any]:
        """
        Analyze how central this candidate is to coalition networks.
        Uses network analysis concepts to determine influence and positioning.
        """
        try:
            candidate_info = self.db.query(
                f"""
                SELECT candidate_name FROM candidates WHERE candidate_id = {candidate_id}
            """
            )

            if candidate_info.empty:
                return {"error": "Candidate not found"}

            candidate_name = candidate_info.iloc[0]["candidate_name"]

            # Get all coalition relationships for this candidate
            coalition_relationships = self.db.query(
                f"""
                WITH candidate_ballots AS (
                    SELECT DISTINCT BallotID
                    FROM ballots_long
                    WHERE candidate_id = {candidate_id}
                ),
                shared_ballots AS (
                    SELECT
                        bl.candidate_id as other_candidate_id,
                        c.candidate_name as other_candidate_name,
                        COUNT(*) as shared_ballots,
                        AVG(ABS(bl.rank_position - main.rank_position)) as avg_rank_distance
                    FROM candidate_ballots cb
                    JOIN ballots_long main ON cb.BallotID = main.BallotID AND main.candidate_id = {candidate_id}
                    JOIN ballots_long bl ON cb.BallotID = bl.BallotID AND bl.candidate_id != {candidate_id}
                    JOIN candidates c ON bl.candidate_id = c.candidate_id
                    GROUP BY bl.candidate_id, c.candidate_name
                    HAVING COUNT(*) >= 50  -- Minimum threshold for meaningful relationship
                )
                SELECT
                    other_candidate_id,
                    other_candidate_name,
                    shared_ballots,
                    avg_rank_distance,
                    -- Simple coalition strength based on shared ballots and proximity
                    shared_ballots / (avg_rank_distance + 1) as coalition_strength
                FROM shared_ballots
                ORDER BY coalition_strength DESC
            """
            )

            if coalition_relationships.empty:
                return {
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_name,
                    "centrality_score": 0,
                    "network_position": "isolated",
                    "influence_metrics": {},
                    "coalition_connections": [],
                }

            # Calculate centrality metrics
            total_connections = len(coalition_relationships)
            strong_connections = len(
                coalition_relationships[
                    coalition_relationships["coalition_strength"] > 50
                ]
            )
            total_shared_ballots = coalition_relationships["shared_ballots"].sum()
            avg_coalition_strength = coalition_relationships[
                "coalition_strength"
            ].mean()

            # Calculate influence metrics
            # Degree centrality - how many significant connections
            all_candidates_count = self.db.query(
                "SELECT COUNT(*) as count FROM candidates"
            ).iloc[0]["count"]
            degree_centrality = total_connections / (
                all_candidates_count - 1
            )  # Normalized by max possible connections

            # Strength centrality - weighted by coalition strength
            max_possible_strength = (
                coalition_relationships["coalition_strength"].max() * total_connections
            )
            strength_centrality = (
                coalition_relationships["coalition_strength"].sum()
                / max_possible_strength
                if max_possible_strength > 0
                else 0
            )

            # Bridge score - how well this candidate connects different groups
            # Simple heuristic: candidates with diverse coalition partners score higher
            bridge_score = min(
                1.0, total_connections / 10.0
            )  # Max score when connected to 10+ candidates

            # Overall centrality score (0-1 scale)
            centrality_score = (
                degree_centrality * 0.4 + strength_centrality * 0.4 + bridge_score * 0.2
            )

            # Determine network position
            if centrality_score > 0.7:
                network_position = "central_hub"
            elif centrality_score > 0.5:
                network_position = "well_connected"
            elif centrality_score > 0.3:
                network_position = "moderately_connected"
            elif centrality_score > 0.1:
                network_position = "periphery"
            else:
                network_position = "isolated"

            # Get top coalition connections
            top_connections = []
            for _, row in coalition_relationships.head(10).iterrows():
                top_connections.append(
                    {
                        "candidate_id": row["other_candidate_id"],
                        "candidate_name": row["other_candidate_name"],
                        "shared_ballots": int(row["shared_ballots"]),
                        "avg_rank_distance": round(row["avg_rank_distance"], 2),
                        "coalition_strength": round(row["coalition_strength"], 2),
                    }
                )

            return {
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "centrality_score": round(centrality_score, 4),
                "network_position": network_position,
                "influence_metrics": {
                    "degree_centrality": round(degree_centrality, 4),
                    "strength_centrality": round(strength_centrality, 4),
                    "bridge_score": round(bridge_score, 4),
                    "total_connections": total_connections,
                    "strong_connections": strong_connections,
                    "total_shared_ballots": int(total_shared_ballots),
                    "avg_coalition_strength": round(avg_coalition_strength, 2),
                },
                "coalition_connections": top_connections,
                "network_insights": self._generate_network_insights(
                    network_position, centrality_score, total_connections
                ),
            }

        except Exception as e:
            logger.error(
                f"Error analyzing coalition centrality for candidate {candidate_id}: {e}"
            )
            return {"error": f"Analysis failed: {str(e)}"}

    def _generate_network_insights(
        self, network_position: str, centrality_score: float, total_connections: int
    ) -> List[str]:
        """Generate human-readable insights about network position."""
        insights = []

        position_insights = {
            "central_hub": [
                "This candidate is a central figure in coalition networks",
                "Has strong connections across the political spectrum",
                "Could be a kingmaker or consensus-building candidate",
                "Elimination would significantly reshape coalition dynamics",
            ],
            "well_connected": [
                "This candidate has good coalition-building potential",
                "Maintains meaningful relationships with many other candidates",
                "Could serve as a bridge between different political groups",
                "Has significant influence on vote transfers",
            ],
            "moderately_connected": [
                "This candidate has some coalition relationships",
                "Limited but meaningful connections to other candidates",
                "May appeal to specific voter segments",
                "Moderate influence on overall election dynamics",
            ],
            "periphery": [
                "This candidate has few strong coalition relationships",
                "May appeal to a distinct voter base",
                "Limited influence on vote transfers",
                "Could be an independent or outsider candidate",
            ],
            "isolated": [
                "This candidate has minimal coalition connections",
                "Very distinct voter base with little overlap",
                "Minimal influence on other candidates' vote totals",
                "Could be a highly polarizing or niche candidate",
            ],
        }

        insights.extend(position_insights.get(network_position, []))

        # Add quantitative insights
        if total_connections > 15:
            insights.append(
                f"Connected to {total_connections} candidates - exceptionally broad appeal"
            )
        elif total_connections > 10:
            insights.append(
                f"Connected to {total_connections} candidates - broad coalition potential"
            )
        elif total_connections > 5:
            insights.append(
                f"Connected to {total_connections} candidates - moderate coalition scope"
            )
        else:
            insights.append(
                f"Connected to only {total_connections} candidates - limited coalition scope"
            )

        return insights
