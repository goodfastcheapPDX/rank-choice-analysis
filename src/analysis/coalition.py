"""
Coalition Analysis Module

Analyzes voting patterns and candidate affinities in ranked-choice voting elections.
Reveals coalitions, supporter overlaps, and vote transfer patterns.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def convert_numpy_types(obj: Any) -> Any:
    """Convert numpy types to native Python types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj


try:
    from ..data.database import CVRDatabase
except ImportError:
    from data.database import CVRDatabase

logger = logging.getLogger(__name__)


@dataclass
class CandidateAffinity:
    """Represents affinity between two candidates."""

    candidate_1: int
    candidate_1_name: str
    candidate_2: int
    candidate_2_name: str
    shared_ballots: int
    total_ballots_1: int
    total_ballots_2: int
    affinity_score: float  # 0-1 scale
    overlap_percentage: (
        float  # Percentage of candidate_1's supporters who also support candidate_2
    )


@dataclass
class DetailedCandidatePair:
    """Comprehensive analysis of a candidate pair relationship."""

    candidate_1: int
    candidate_1_name: str
    candidate_2: int
    candidate_2_name: str

    # Basic co-occurrence
    shared_ballots: int
    total_ballots_1: int
    total_ballots_2: int

    # Ranking proximity analysis
    ranking_distances: List[int]  # All observed distances between rankings
    avg_ranking_distance: float
    min_ranking_distance: int
    max_ranking_distance: int

    # Proximity-weighted metrics
    strong_coalition_votes: int  # Ballots with candidates ranked close (distance ≤ 2)
    weak_coalition_votes: int  # Ballots with candidates ranked far apart (distance ≥ 4)

    # Transfer analysis
    transfer_votes_1_to_2: int  # If 1 eliminated, how many go to 2
    transfer_votes_2_to_1: int  # If 2 eliminated, how many go to 1

    # Affinity scores
    basic_affinity_score: float  # Current Jaccard similarity
    proximity_weighted_affinity: float  # New proximity-weighted score
    coalition_strength_score: float  # Combined metric
    coalition_type: str  # "strong", "moderate", "weak", "strategic"


@dataclass
class CoalitionGroup:
    """Represents a coalition of candidates."""

    coalition_id: str
    candidates: List[int]
    candidate_names: List[str]
    core_supporters: int  # Ballots that rank ALL candidates in this coalition
    coalition_strength: float  # 0-1 scale indicating how cohesive this coalition is


class CoalitionAnalyzer:
    """
    Analyzes voting coalitions and candidate affinities in ranked-choice elections.
    """

    def __init__(self, db: CVRDatabase):
        """
        Initialize coalition analyzer.

        Args:
            db: Database connection with ballot data
        """
        self.db = db
        self.candidates_df = None
        self.ballot_counts = None

    def _load_candidate_data(self):
        """Load candidate information."""
        if self.candidates_df is None:
            self.candidates_df = self.db.query(
                """
                SELECT candidate_id, candidate_name
                FROM candidates
                ORDER BY candidate_id
            """
            )

        if self.ballot_counts is None:
            self.ballot_counts = self.db.query(
                """
                SELECT
                    candidate_id,
                    COUNT(DISTINCT BallotID) as total_ballots
                FROM ballots_long
                GROUP BY candidate_id
            """
            )

    def calculate_pairwise_affinity(
        self, min_shared_ballots: int = 100
    ) -> List[CandidateAffinity]:
        """
        Calculate affinity scores between all candidate pairs.

        Args:
            min_shared_ballots: Minimum shared ballots to include in results

        Returns:
            List of CandidateAffinity objects sorted by affinity score
        """
        logger.info("Calculating pairwise candidate affinities")
        self._load_candidate_data()

        # Get co-occurrence data
        cooccur_query = """
        SELECT
            b1.candidate_id as candidate_1,
            c1.candidate_name as name_1,
            b2.candidate_id as candidate_2,
            c2.candidate_name as name_2,
            COUNT(DISTINCT b1.BallotID) as shared_ballots
        FROM ballots_long b1
        JOIN ballots_long b2 ON b1.BallotID = b2.BallotID AND b1.candidate_id < b2.candidate_id
        JOIN candidates c1 ON b1.candidate_id = c1.candidate_id
        JOIN candidates c2 ON b2.candidate_id = c2.candidate_id
        GROUP BY b1.candidate_id, b2.candidate_id, c1.candidate_name, c2.candidate_name
        HAVING shared_ballots >= ?
        ORDER BY shared_ballots DESC
        """

        cooccur_df = self.db.query(cooccur_query.replace("?", str(min_shared_ballots)))

        # Create candidate ballot count lookup
        ballot_lookup = dict(
            zip(self.ballot_counts["candidate_id"], self.ballot_counts["total_ballots"])
        )

        affinities = []
        for _, row in cooccur_df.iterrows():
            cand1_id = row["candidate_1"]
            cand2_id = row["candidate_2"]
            shared = row["shared_ballots"]

            total_1 = ballot_lookup.get(cand1_id, 0)
            total_2 = ballot_lookup.get(cand2_id, 0)

            if total_1 > 0 and total_2 > 0:
                # Affinity score: Jaccard similarity (shared / union)
                union_size = total_1 + total_2 - shared
                affinity_score = shared / union_size if union_size > 0 else 0.0

                # Overlap percentage: what % of candidate 1's supporters also support candidate 2
                overlap_pct = (shared / total_1) * 100 if total_1 > 0 else 0.0

                affinities.append(
                    CandidateAffinity(
                        candidate_1=cand1_id,
                        candidate_1_name=row["name_1"],
                        candidate_2=cand2_id,
                        candidate_2_name=row["name_2"],
                        shared_ballots=shared,
                        total_ballots_1=total_1,
                        total_ballots_2=total_2,
                        affinity_score=affinity_score,
                        overlap_percentage=overlap_pct,
                    )
                )

        # Sort by affinity score descending
        affinities.sort(key=lambda x: x.affinity_score, reverse=True)

        logger.info(f"Calculated {len(affinities)} candidate affinities")
        return affinities

    def calculate_detailed_pairwise_analysis(
        self, min_shared_ballots: int = 10
    ) -> List[DetailedCandidatePair]:
        """
        Calculate comprehensive analysis for all candidate pairs with ranking proximity.

        Args:
            min_shared_ballots: Minimum shared ballots to include in results

        Returns:
            List of DetailedCandidatePair objects sorted by coalition strength
        """
        logger.info("Calculating detailed pairwise analysis with ranking proximity")
        self._load_candidate_data()

        # Get detailed co-occurrence with ranking information
        proximity_query = """
        SELECT
            b1.candidate_id as candidate_1,
            c1.candidate_name as name_1,
            b2.candidate_id as candidate_2,
            c2.candidate_name as name_2,
            b1.rank_position as rank_1,
            b2.rank_position as rank_2,
            ABS(b1.rank_position - b2.rank_position) as ranking_distance,
            COUNT(*) as occurrence_count
        FROM ballots_long b1
        JOIN ballots_long b2 ON b1.BallotID = b2.BallotID AND b1.candidate_id < b2.candidate_id
        JOIN candidates c1 ON b1.candidate_id = c1.candidate_id
        JOIN candidates c2 ON b2.candidate_id = c2.candidate_id
        GROUP BY b1.candidate_id, b2.candidate_id, c1.candidate_name, c2.candidate_name,
                 b1.rank_position, b2.rank_position, ranking_distance
        ORDER BY b1.candidate_id, b2.candidate_id, ranking_distance
        """

        proximity_df = self.db.query(proximity_query)

        # Create candidate ballot count lookup
        ballot_lookup = dict(
            zip(self.ballot_counts["candidate_id"], self.ballot_counts["total_ballots"])
        )

        # Group by candidate pair and calculate detailed metrics
        pair_groups = proximity_df.groupby(
            ["candidate_1", "candidate_2", "name_1", "name_2"]
        )

        detailed_pairs = []
        for (cand1_id, cand2_id, name1, name2), group in pair_groups:
            # Calculate basic metrics
            shared_ballots = group["occurrence_count"].sum()

            if shared_ballots < min_shared_ballots:
                continue

            total_1 = ballot_lookup.get(cand1_id, 0)
            total_2 = ballot_lookup.get(cand2_id, 0)

            # Ranking proximity analysis
            distances = []
            for _, row in group.iterrows():
                distances.extend([row["ranking_distance"]] * row["occurrence_count"])

            avg_distance = np.mean(distances) if distances else 0.0
            min_distance = min(distances) if distances else 0
            max_distance = max(distances) if distances else 0

            # Proximity-weighted metrics
            strong_votes = group[group["ranking_distance"] <= 2][
                "occurrence_count"
            ].sum()
            weak_votes = group[group["ranking_distance"] >= 4]["occurrence_count"].sum()

            # Basic affinity (Jaccard similarity)
            union_size = total_1 + total_2 - shared_ballots
            basic_affinity = shared_ballots / union_size if union_size > 0 else 0.0

            # Proximity-weighted affinity (closer rankings get higher weight)
            proximity_weights = [
                1.0 / (1 + d) for d in distances
            ]  # Closer = higher weight
            proximity_weighted_affinity = (
                sum(proximity_weights) / len(distances) if distances else 0.0
            )

            # Coalition strength: weight proximity more heavily than basic co-occurrence
            # This emphasizes HOW CLOSE candidates are ranked when they do appear together
            coalition_strength = (basic_affinity * 0.2) + (
                proximity_weighted_affinity * 0.8
            )

            # Debug logging for first few pairs
            if len(detailed_pairs) < 5:
                logger.info(
                    f"Debug pair {name1} & {name2}: basic_affinity={basic_affinity:.4f}, proximity_weighted={proximity_weighted_affinity:.4f}, coalition_strength={coalition_strength:.4f}, avg_distance={avg_distance:.2f}"
                )

            # Classify coalition type
            coalition_type = self._classify_coalition_type(
                avg_distance, strong_votes, weak_votes, shared_ballots
            )

            # Get transfer patterns (simplified for now)
            transfers_1_to_2 = self._estimate_transfer_votes(cand1_id, cand2_id)
            transfers_2_to_1 = self._estimate_transfer_votes(cand2_id, cand1_id)

            detailed_pair = DetailedCandidatePair(
                candidate_1=cand1_id,
                candidate_1_name=name1,
                candidate_2=cand2_id,
                candidate_2_name=name2,
                shared_ballots=shared_ballots,
                total_ballots_1=total_1,
                total_ballots_2=total_2,
                ranking_distances=distances[:100],  # Limit for memory efficiency
                avg_ranking_distance=avg_distance,
                min_ranking_distance=min_distance,
                max_ranking_distance=max_distance,
                strong_coalition_votes=strong_votes,
                weak_coalition_votes=weak_votes,
                transfer_votes_1_to_2=transfers_1_to_2,
                transfer_votes_2_to_1=transfers_2_to_1,
                basic_affinity_score=basic_affinity,
                proximity_weighted_affinity=proximity_weighted_affinity,
                coalition_strength_score=coalition_strength,
                coalition_type=coalition_type,
            )

            detailed_pairs.append(detailed_pair)

        # Sort by coalition strength descending
        detailed_pairs.sort(key=lambda x: x.coalition_strength_score, reverse=True)

        logger.info(
            f"Calculated detailed analysis for {len(detailed_pairs)} candidate pairs"
        )
        return detailed_pairs

    def _classify_coalition_type(
        self, avg_distance: float, strong_votes: int, weak_votes: int, total_votes: int
    ) -> str:
        """Classify coalition type based on ranking proximity patterns."""
        strong_ratio = strong_votes / total_votes if total_votes > 0 else 0
        weak_ratio = weak_votes / total_votes if total_votes > 0 else 0

        if avg_distance <= 1.5 and strong_ratio >= 0.6:
            return "strong"
        elif avg_distance <= 2.5 and strong_ratio >= 0.4:
            return "moderate"
        elif weak_ratio >= 0.5:
            return "strategic"
        else:
            return "weak"

    def _estimate_transfer_votes(self, from_candidate: int, to_candidate: int) -> int:
        """Estimate transfer votes between specific candidates."""
        transfer_query = f"""
        WITH candidate_ballots AS (
            SELECT DISTINCT BallotID
            FROM ballots_long
            WHERE candidate_id = {from_candidate}
        ),
        next_preferences AS (
            SELECT bl.BallotID
            FROM ballots_long bl
            WHERE bl.BallotID IN (SELECT BallotID FROM candidate_ballots)
              AND bl.candidate_id = {to_candidate}
        )
        SELECT COUNT(*) as transfer_count
        FROM next_preferences
        """

        result = self.db.query(transfer_query)
        return result.iloc[0]["transfer_count"] if not result.empty else 0

    def find_vote_transfer_patterns(self, from_candidate: int) -> Dict[int, Dict]:
        """
        Analyze where votes would transfer if a specific candidate was eliminated.

        Args:
            from_candidate: Candidate ID to analyze transfers from

        Returns:
            Dictionary mapping candidate IDs to transfer information
        """
        logger.info(f"Analyzing vote transfer patterns from candidate {from_candidate}")

        # Get ballots that ranked the from_candidate
        transfer_query = """
        WITH candidate_ballots AS (
            SELECT DISTINCT BallotID
            FROM ballots_long
            WHERE candidate_id = ?
        ),
        next_preferences AS (
            SELECT
                bl.BallotID,
                bl.candidate_id as next_candidate,
                bl.rank_position,
                ROW_NUMBER() OVER (PARTITION BY bl.BallotID ORDER BY bl.rank_position) as pref_order
            FROM ballots_long bl
            WHERE bl.BallotID IN (SELECT BallotID FROM candidate_ballots)
              AND bl.candidate_id != ?
        )
        SELECT
            np.next_candidate,
            c.candidate_name,
            COUNT(DISTINCT np.BallotID) as transfer_votes,
            ROUND(AVG(np.rank_position), 2) as avg_rank_position
        FROM next_preferences np
        JOIN candidates c ON np.next_candidate = c.candidate_id
        WHERE np.pref_order = 1  -- Next highest preference
        GROUP BY np.next_candidate, c.candidate_name
        ORDER BY transfer_votes DESC
        """

        # Execute with parameter substitution
        query_with_params = transfer_query.replace("?", str(from_candidate))
        transfers_df = self.db.query(query_with_params)

        # Convert to dictionary format
        transfers = {}
        total_transfers = (
            transfers_df["transfer_votes"].sum() if not transfers_df.empty else 0
        )

        for _, row in transfers_df.iterrows():
            transfers[row["next_candidate"]] = {
                "candidate_name": row["candidate_name"],
                "transfer_votes": row["transfer_votes"],
                "avg_rank_position": row["avg_rank_position"],
                "transfer_percentage": (
                    (row["transfer_votes"] / total_transfers * 100)
                    if total_transfers > 0
                    else 0
                ),
            }

        logger.info(f"Found transfer patterns for {len(transfers)} candidates")
        return transfers

    def identify_coalitions(
        self, min_coalition_size: int = 2, min_support: int = 500
    ) -> List[CoalitionGroup]:
        """
        Identify voting coalitions based on candidate co-occurrence patterns.

        Args:
            min_coalition_size: Minimum number of candidates in a coalition
            min_support: Minimum number of ballots that must support the full coalition

        Returns:
            List of CoalitionGroup objects
        """
        logger.info("Identifying voting coalitions")

        # Start with high-affinity pairs and build up
        affinities = self.calculate_pairwise_affinity(min_shared_ballots=min_support)

        coalitions = []

        # Simple coalition detection: group candidates with high mutual affinity
        # TODO: Implement more sophisticated coalition detection algorithm

        # For now, identify the strongest pairwise coalitions
        for i, affinity in enumerate(affinities[:10]):  # Top 10 affinities
            if affinity.shared_ballots >= min_support:
                coalition = CoalitionGroup(
                    coalition_id=f"coalition_{i+1}",
                    candidates=[affinity.candidate_1, affinity.candidate_2],
                    candidate_names=[
                        affinity.candidate_1_name,
                        affinity.candidate_2_name,
                    ],
                    core_supporters=affinity.shared_ballots,
                    coalition_strength=affinity.affinity_score,
                )
                coalitions.append(coalition)

        logger.info(f"Identified {len(coalitions)} coalitions")
        return coalitions

    def get_candidate_coalition_summary(self, candidate_id: int) -> Dict:
        """
        Get a summary of a candidate's coalition patterns.

        Args:
            candidate_id: Candidate to analyze

        Returns:
            Dictionary with coalition summary information
        """
        self._load_candidate_data()

        # Get candidate name
        candidate_row = self.candidates_df[
            self.candidates_df["candidate_id"] == candidate_id
        ]
        if candidate_row.empty:
            return {"error": f"Candidate {candidate_id} not found"}

        candidate_name = candidate_row.iloc[0]["candidate_name"]

        # Get top affinities
        affinities = self.calculate_pairwise_affinity()

        # Find affinities involving this candidate
        candidate_affinities = [
            a
            for a in affinities
            if a.candidate_1 == candidate_id or a.candidate_2 == candidate_id
        ][
            :10
        ]  # Top 10

        # Get transfer patterns
        transfers = self.find_vote_transfer_patterns(candidate_id)

        # Get ballot count
        ballot_count = self.ballot_counts[
            self.ballot_counts["candidate_id"] == candidate_id
        ]
        total_ballots = (
            ballot_count.iloc[0]["total_ballots"] if not ballot_count.empty else 0
        )

        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "total_ballots": total_ballots,
            "top_affinities": candidate_affinities,
            "vote_transfers": transfers,
            "coalition_strength": len(candidate_affinities),
        }

    def analyze_ranking_proximity(self, candidate_1: int, candidate_2: int) -> Dict:
        """
        Analyze how close two candidates typically appear in rankings.

        Args:
            candidate_1: First candidate ID
            candidate_2: Second candidate ID

        Returns:
            Dictionary with proximity analysis
        """
        logger.info(
            f"Analyzing ranking proximity for candidates {candidate_1} and {candidate_2}"
        )

        proximity_query = f"""
        SELECT
            b1.rank_position as rank_1,
            b2.rank_position as rank_2,
            ABS(b1.rank_position - b2.rank_position) as ranking_distance,
            COUNT(*) as occurrence_count
        FROM ballots_long b1
        JOIN ballots_long b2 ON b1.BallotID = b2.BallotID
        WHERE b1.candidate_id = {candidate_1}
          AND b2.candidate_id = {candidate_2}
        GROUP BY b1.rank_position, b2.rank_position, ranking_distance
        ORDER BY ranking_distance, occurrence_count DESC
        """

        proximity_df = self.db.query(proximity_query)

        if proximity_df.empty:
            return {
                "error": f"No shared ballots found for candidates {candidate_1} and {candidate_2}"
            }

        # Calculate statistics
        total_shared = proximity_df["occurrence_count"].sum()
        distances = []
        for _, row in proximity_df.iterrows():
            distances.extend([row["ranking_distance"]] * row["occurrence_count"])

        avg_distance = np.mean(distances) if distances else 0.0
        median_distance = np.median(distances) if distances else 0.0

        # Proximity distribution - convert numpy types to native Python types
        distance_counts = {
            int(k): int(v)
            for k, v in proximity_df.groupby("ranking_distance")["occurrence_count"]
            .sum()
            .to_dict()
            .items()
        }

        # Get candidate names
        self._load_candidate_data()
        names = dict(
            zip(
                self.candidates_df["candidate_id"], self.candidates_df["candidate_name"]
            )
        )

        result = {
            "candidate_1": candidate_1,
            "candidate_1_name": names.get(candidate_1, f"Candidate {candidate_1}"),
            "candidate_2": candidate_2,
            "candidate_2_name": names.get(candidate_2, f"Candidate {candidate_2}"),
            "total_shared_ballots": total_shared,
            "avg_ranking_distance": round(avg_distance, 2),
            "median_ranking_distance": median_distance,
            "min_distance": min(distances) if distances else 0,
            "max_distance": max(distances) if distances else 0,
            "distance_distribution": distance_counts,
            "close_rankings": sum(
                count for dist, count in distance_counts.items() if dist <= 2
            ),
            "distant_rankings": sum(
                count for dist, count in distance_counts.items() if dist >= 4
            ),
        }
        return convert_numpy_types(result)

    def get_coalition_type_breakdown(self) -> Dict:
        """
        Get breakdown of coalition types across all candidate pairs.

        Returns:
            Dictionary with coalition type statistics
        """
        logger.info("Calculating coalition type breakdown")

        detailed_pairs = self.calculate_detailed_pairwise_analysis(
            min_shared_ballots=50
        )

        type_counts = {}
        type_examples = {}

        for pair in detailed_pairs:
            coalition_type = pair.coalition_type

            if coalition_type not in type_counts:
                type_counts[coalition_type] = 0
                type_examples[coalition_type] = []

            type_counts[coalition_type] += 1

            # Store top 3 examples for each type
            if len(type_examples[coalition_type]) < 3:
                type_examples[coalition_type].append(
                    {
                        "candidate_1_name": pair.candidate_1_name,
                        "candidate_2_name": pair.candidate_2_name,
                        "shared_ballots": int(pair.shared_ballots),
                        "avg_distance": float(round(pair.avg_ranking_distance, 2)),
                        "coalition_strength": float(
                            round(pair.coalition_strength_score, 3)
                        ),
                    }
                )

        total_pairs = len(detailed_pairs)
        type_percentages = (
            {
                coalition_type: round((count / total_pairs * 100), 1)
                for coalition_type, count in type_counts.items()
            }
            if total_pairs > 0
            else {}
        )

        result = {
            "total_pairs_analyzed": total_pairs,
            "coalition_type_counts": type_counts,
            "coalition_type_percentages": type_percentages,
            "examples": type_examples,
        }
        return convert_numpy_types(result)

    def get_detailed_pair_analysis(
        self, candidate_1: int, candidate_2: int
    ) -> Optional[DetailedCandidatePair]:
        """
        Get comprehensive analysis for a specific candidate pair.

        Args:
            candidate_1: First candidate ID
            candidate_2: Second candidate ID

        Returns:
            DetailedCandidatePair object or None if not found
        """
        # Ensure consistent ordering (lower ID first)
        if candidate_1 > candidate_2:
            candidate_1, candidate_2 = candidate_2, candidate_1

        detailed_pairs = self.calculate_detailed_pairwise_analysis(min_shared_ballots=1)

        for pair in detailed_pairs:
            if pair.candidate_1 == candidate_1 and pair.candidate_2 == candidate_2:
                return pair

        return None

    def detect_coalition_clusters(
        self, min_strength: float = 0.2, min_group_size: int = 3
    ) -> List[List[int]]:
        """
        Detect natural coalition clusters using graph-based clustering.

        Args:
            min_strength: Minimum coalition strength to consider as connection
            min_group_size: Minimum size for a valid coalition cluster

        Returns:
            List of clusters, where each cluster is a list of candidate IDs
        """
        logger.info(f"Detecting coalition clusters with min_strength={min_strength}")

        try:
            # Get detailed pairs for clustering
            detailed_pairs = self.calculate_detailed_pairwise_analysis(
                min_shared_ballots=50
            )

            # Build adjacency graph of strong connections
            connections = {}
            for pair in detailed_pairs:
                if pair.coalition_strength_score >= min_strength:
                    # Add bidirectional connections
                    if pair.candidate_1 not in connections:
                        connections[pair.candidate_1] = set()
                    if pair.candidate_2 not in connections:
                        connections[pair.candidate_2] = set()

                    connections[pair.candidate_1].add(pair.candidate_2)
                    connections[pair.candidate_2].add(pair.candidate_1)

            # Find connected components using DFS
            visited = set()
            clusters = []

            def dfs(node, cluster):
                if node in visited:
                    return
                visited.add(node)
                cluster.append(node)

                if node in connections:
                    for neighbor in connections[node]:
                        if neighbor not in visited:
                            dfs(neighbor, cluster)

            # Find all connected components
            for candidate in connections:
                if candidate not in visited:
                    cluster = []
                    dfs(candidate, cluster)
                    if len(cluster) >= min_group_size:
                        clusters.append(cluster)

            # Sort clusters by size (largest first)
            clusters.sort(key=len, reverse=True)

            logger.info(f"Detected {len(clusters)} coalition clusters")
            return clusters

        except Exception as e:
            logger.error(f"Error detecting coalition clusters: {e}")
            return []

    def get_cluster_analysis(self, clusters: List[List[int]]) -> Dict[str, Any]:
        """
        Analyze detected coalition clusters for insights.

        Args:
            clusters: List of candidate ID clusters

        Returns:
            Dictionary with cluster analysis
        """
        if not clusters:
            return {"clusters": [], "summary": {"total_clusters": 0}}

        self._load_candidate_data()
        candidate_names = dict(
            zip(
                self.candidates_df["candidate_id"], self.candidates_df["candidate_name"]
            )
        )

        cluster_analysis = []

        for i, cluster in enumerate(clusters):
            cluster_info = {
                "cluster_id": i + 1,
                "size": len(cluster),
                "candidates": [
                    {
                        "id": cand_id,
                        "name": candidate_names.get(cand_id, f"Candidate {cand_id}"),
                    }
                    for cand_id in cluster
                ],
                "internal_strength": 0.0,
                "winners_in_cluster": 0,
            }

            # Calculate internal coalition strength
            detailed_pairs = self.calculate_detailed_pairwise_analysis(
                min_shared_ballots=10
            )
            internal_pairs = [
                pair
                for pair in detailed_pairs
                if pair.candidate_1 in cluster and pair.candidate_2 in cluster
            ]

            if internal_pairs:
                cluster_info["internal_strength"] = sum(
                    p.coalition_strength_score for p in internal_pairs
                ) / len(internal_pairs)

            # Count winners in cluster
            winners = [36, 46, 55]  # Portland winners
            cluster_info["winners_in_cluster"] = len(
                [c for c in cluster if c in winners]
            )
            cluster_info["has_winners"] = cluster_info["winners_in_cluster"] > 0

            cluster_analysis.append(cluster_info)

        # Summary statistics
        total_candidates_clustered = sum(len(cluster) for cluster in clusters)
        avg_cluster_size = total_candidates_clustered / len(clusters) if clusters else 0
        largest_cluster_size = (
            max(len(cluster) for cluster in clusters) if clusters else 0
        )

        summary = {
            "total_clusters": len(clusters),
            "total_candidates_clustered": total_candidates_clustered,
            "avg_cluster_size": round(avg_cluster_size, 1),
            "largest_cluster_size": largest_cluster_size,
            "clusters_with_winners": len(
                [c for c in cluster_analysis if c["has_winners"]]
            ),
        }

        return {"clusters": cluster_analysis, "summary": summary}
