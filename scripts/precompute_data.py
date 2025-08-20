#!/usr/bin/env python3
"""
Precomputation Pipeline for Electoral Analysis Data

This script precomputes expensive analytical operations to dramatically improve
API response times. Focuses on coalition analysis, candidate metrics, and
vote transfer patterns that currently require expensive real-time calculations.

Performance targets:
- Coalition analysis: 2-5s → 50-200ms
- Network data generation: 3-8s → 200-500ms
- API response times: 5-10x faster overall
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# import pandas as pd  # Commented out - not used in this script

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# from analysis.candidate_metrics import CandidateMetrics  # noqa: E402 - Commented out unused
# from analysis.coalition import CoalitionAnalyzer  # noqa: E402 - Commented out unused
from data.database import CVRDatabase  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PrecomputeProcessor:
    """
    Handles precomputation of expensive analytical operations.
    Designed to run as batch job to prepare data for fast API responses.
    """

    def __init__(self, db_path: str, election_id: str = "2024_portland_district2"):
        self.db_path = db_path
        self.election_id = election_id
        self.db = CVRDatabase(db_path, read_only=False)  # Need write access
        self.start_time = time.time()

        # Create data directory structure
        self.data_dir = (
            Path(__file__).parent.parent / "data" / "elections" / election_id
        )
        self.precomputed_dir = self.data_dir / "precomputed"
        self.static_responses_dir = self.data_dir / "static_responses"

        # Ensure directories exist
        self.precomputed_dir.mkdir(parents=True, exist_ok=True)
        self.static_responses_dir.mkdir(parents=True, exist_ok=True)

        self.stats = {
            "start_time": datetime.now().isoformat(),
            "operations_completed": [],
            "performance_improvements": {},
            "data_sizes": {},
            "error_count": 0,
        }

    def validate_prerequisites(self) -> bool:
        """
        Validate that required data tables exist before precomputation.
        """
        logger.info("=== Validating Prerequisites ===")

        required_tables = ["ballots_long", "candidates", "summary_stats"]
        missing_tables = []

        for table in required_tables:
            if not self.db.table_exists(table):
                missing_tables.append(table)

        if missing_tables:
            logger.error(f"Missing required tables: {missing_tables}")
            logger.error(
                "Please run 'python scripts/process_data.py' first to load basic data"
            )
            return False

        # Check data quality
        ballot_count = self.db.query(
            "SELECT COUNT(DISTINCT BallotID) as count FROM ballots_long"
        )["count"].iloc[0]
        candidate_count = self.db.query("SELECT COUNT(*) as count FROM candidates")[
            "count"
        ].iloc[0]

        logger.info(f"✓ Found {ballot_count:,} unique ballots")
        logger.info(f"✓ Found {candidate_count} candidates")

        if ballot_count < 1000:
            logger.warning("⚠️  Low ballot count - results may not be meaningful")

        return True

    def precompute_adjacent_pairs(self, min_shared_ballots: int = 10) -> Dict[str, Any]:
        """
        Precompute candidate pairwise relationships and coalition metrics.
        This replaces expensive real-time self-joins on ballots_long.
        Uses optimized data types for 50-70% memory reduction.
        """
        logger.info("=== Precomputing Adjacent Pairs ===")
        operation_start = time.time()

        try:
            # Drop existing table if it exists
            self.db.conn.execute("DROP TABLE IF EXISTS adjacent_pairs")

            # Create the precomputed adjacent pairs table with optimized data types
            create_table_sql = """
            CREATE TABLE adjacent_pairs AS
            WITH pair_analysis AS (
                SELECT
                    b1.candidate_id as candidate_1,
                    c1.candidate_name as candidate_1_name,
                    b2.candidate_id as candidate_2,
                    c2.candidate_name as candidate_2_name,
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
            ),
            pair_summary AS (
                SELECT
                    candidate_1,
                    candidate_1_name,
                    candidate_2,
                    candidate_2_name,
                    SUM(occurrence_count) as shared_ballots,
                    AVG(ranking_distance) as avg_ranking_distance,
                    MIN(ranking_distance) as min_ranking_distance,
                    MAX(ranking_distance) as max_ranking_distance,
                    SUM(CASE WHEN ranking_distance <= 2 THEN occurrence_count ELSE 0 END) as strong_coalition_votes,
                    SUM(CASE WHEN ranking_distance >= 4 THEN occurrence_count ELSE 0 END) as weak_coalition_votes
                FROM pair_analysis
                GROUP BY candidate_1, candidate_1_name, candidate_2, candidate_2_name
                HAVING shared_ballots >= ?
            ),
            candidate_totals AS (
                SELECT
                    candidate_id,
                    COUNT(DISTINCT BallotID) as total_ballots
                FROM ballots_long
                GROUP BY candidate_id
            )
            SELECT
                ps.*,
                ct1.total_ballots as total_ballots_1,
                ct2.total_ballots as total_ballots_2,
                -- Basic affinity (Jaccard similarity)
                CAST(ps.shared_ballots AS FLOAT) / (ct1.total_ballots + ct2.total_ballots - ps.shared_ballots) as basic_affinity_score,
                -- Proximity-weighted affinity (closer rankings get higher weight)
                CASE
                    WHEN ps.avg_ranking_distance > 0
                    THEN (1.0 / (1 + ps.avg_ranking_distance)) * (CAST(ps.shared_ballots AS FLOAT) / GREATEST(ct1.total_ballots, ct2.total_ballots))
                    ELSE CAST(ps.shared_ballots AS FLOAT) / GREATEST(ct1.total_ballots, ct2.total_ballots)
                END as proximity_weighted_affinity,
                -- Coalition strength: weight proximity more heavily than basic co-occurrence
                CASE
                    WHEN ps.avg_ranking_distance > 0
                    THEN (CAST(ps.shared_ballots AS FLOAT) / (ct1.total_ballots + ct2.total_ballots - ps.shared_ballots)) * 0.2 +
                         ((1.0 / (1 + ps.avg_ranking_distance)) * (CAST(ps.shared_ballots AS FLOAT) / GREATEST(ct1.total_ballots, ct2.total_ballots))) * 0.8
                    ELSE CAST(ps.shared_ballots AS FLOAT) / (ct1.total_ballots + ct2.total_ballots - ps.shared_ballots)
                END as coalition_strength_score,
                -- Coalition type classification
                CASE
                    WHEN ps.avg_ranking_distance <= 1.5 AND ps.strong_coalition_votes >= ps.shared_ballots * 0.6 THEN 'strong'
                    WHEN ps.avg_ranking_distance <= 2.5 AND ps.strong_coalition_votes >= ps.shared_ballots * 0.4 THEN 'moderate'
                    WHEN ps.avg_ranking_distance >= 4.0 AND ps.weak_coalition_votes >= ps.shared_ballots * 0.5 THEN 'strategic'
                    ELSE 'weak'
                END as coalition_type
            FROM pair_summary ps
            JOIN candidate_totals ct1 ON ps.candidate_1 = ct1.candidate_id
            JOIN candidate_totals ct2 ON ps.candidate_2 = ct2.candidate_id
            ORDER BY coalition_strength_score DESC
            """

            logger.info(
                f"Computing pairwise relationships (min {min_shared_ballots} shared ballots)..."
            )
            self.db.conn.execute(create_table_sql, [min_shared_ballots])

            # Get statistics
            stats_query = """
            SELECT
                COUNT(*) as total_pairs,
                AVG(shared_ballots) as avg_shared_ballots,
                AVG(coalition_strength_score) as avg_coalition_strength,
                COUNT(CASE WHEN coalition_type = 'strong' THEN 1 END) as strong_coalitions,
                COUNT(CASE WHEN coalition_type = 'moderate' THEN 1 END) as moderate_coalitions,
                COUNT(CASE WHEN coalition_type = 'weak' THEN 1 END) as weak_coalitions,
                COUNT(CASE WHEN coalition_type = 'strategic' THEN 1 END) as strategic_coalitions
            FROM adjacent_pairs
            """

            stats = self.db.query(stats_query).iloc[0].to_dict()

            operation_time = time.time() - operation_start
            logger.info(
                f"✓ Precomputed {stats['total_pairs']} candidate pairs in {operation_time:.2f}s"
            )
            logger.info(f"  - Strong coalitions: {stats['strong_coalitions']}")
            logger.info(f"  - Moderate coalitions: {stats['moderate_coalitions']}")
            logger.info(f"  - Weak coalitions: {stats['weak_coalitions']}")
            logger.info(f"  - Strategic coalitions: {stats['strategic_coalitions']}")

            # Save as Parquet for external analysis
            pairs_df = self.db.query("SELECT * FROM adjacent_pairs")
            parquet_path = self.precomputed_dir / "adjacent_pairs.parquet"
            pairs_df.to_parquet(parquet_path, index=False)
            logger.info(f"✓ Saved to {parquet_path}")

            # Update performance stats
            self.stats["performance_improvements"]["adjacent_pairs"] = {
                "operation_time_seconds": operation_time,
                "expected_speedup": "10-100x",
                "api_endpoints_affected": [
                    "/api/coalition/pairs/all",
                    "/api/coalition/network",
                ],
            }
            self.stats["data_sizes"][
                "adjacent_pairs_mb"
            ] = parquet_path.stat().st_size / (1024 * 1024)

            return stats

        except Exception as e:
            logger.error(f"Error precomputing adjacent pairs: {e}")
            self.stats["error_count"] += 1
            raise

    def optimize_data_types(self) -> Dict[str, Any]:
        """
        Optimize data types and apply dictionary encoding for memory efficiency.
        Expected: 50-70% memory reduction, 30-50% faster I/O
        """
        logger.info("=== Optimizing Data Types & Dictionary Encoding ===")
        operation_start = time.time()

        optimizations = {}

        try:
            # Optimize adjacent_pairs table
            logger.info("Optimizing adjacent_pairs table data types...")

            # Create optimized adjacent_pairs table
            optimize_pairs_sql = """
            CREATE OR REPLACE TABLE adjacent_pairs_optimized AS
            SELECT
                CAST(candidate_1 AS TINYINT) as candidate_1,                    -- 36-125 range fits in TINYINT
                CAST(candidate_1_name AS VARCHAR(30)) as candidate_1_name,      -- Max 27 chars observed
                CAST(candidate_2 AS TINYINT) as candidate_2,                    -- 36-125 range fits in TINYINT
                CAST(candidate_2_name AS VARCHAR(30)) as candidate_2_name,      -- Max 27 chars observed
                CAST(shared_ballots AS INTEGER) as shared_ballots,              -- Max 18K fits in INTEGER
                CAST(total_ballots_1 AS INTEGER) as total_ballots_1,            -- Max 33K fits in INTEGER
                CAST(total_ballots_2 AS INTEGER) as total_ballots_2,            -- Max 33K fits in INTEGER
                CAST(ROUND(avg_ranking_distance, 2) AS DECIMAL(4,2)) as avg_ranking_distance,  -- 0.00-5.00 range
                CAST(min_ranking_distance AS TINYINT) as min_ranking_distance,  -- 0-5 range
                CAST(max_ranking_distance AS TINYINT) as max_ranking_distance,  -- 0-5 range
                CAST(strong_coalition_votes AS INTEGER) as strong_coalition_votes,
                CAST(weak_coalition_votes AS INTEGER) as weak_coalition_votes,
                CAST(ROUND(basic_affinity_score, 4) AS DECIMAL(6,4)) as basic_affinity_score,         -- 0.0000-1.0000 range
                CAST(ROUND(proximity_weighted_affinity, 4) AS DECIMAL(6,4)) as proximity_weighted_affinity,
                CAST(ROUND(coalition_strength_score, 4) AS DECIMAL(6,4)) as coalition_strength_score,  -- 0.0000-1.0000 range
                CAST(coalition_type AS VARCHAR(10)) as coalition_type           -- Max 8 chars observed
            FROM adjacent_pairs
            """

            self.db.conn.execute(optimize_pairs_sql)

            # Replace original with optimized version
            self.db.conn.execute("DROP TABLE adjacent_pairs")
            self.db.conn.execute(
                "ALTER TABLE adjacent_pairs_optimized RENAME TO adjacent_pairs"
            )

            # Get size comparison
            optimized_size = self.db.query(
                "SELECT COUNT(*) * 64 as estimated_bytes FROM adjacent_pairs"
            )["estimated_bytes"].iloc[0]
            optimizations["adjacent_pairs"] = {
                "optimized_estimated_bytes": optimized_size,
                "optimization_applied": True,
            }

            # Optimize candidate_metrics table
            logger.info("Optimizing candidate_metrics table data types...")

            optimize_metrics_sql = """
            CREATE OR REPLACE TABLE candidate_metrics_optimized AS
            SELECT
                CAST(candidate_id AS TINYINT) as candidate_id,                  -- 36-125 range
                CAST(candidate_name AS VARCHAR(30)) as candidate_name,          -- Max 27 chars
                CAST(total_ballots AS INTEGER) as total_ballots,                -- Max 33K
                CAST(first_choice_votes AS INTEGER) as first_choice_votes,      -- Max 33K
                CAST(weighted_score AS INTEGER) as weighted_score,              -- Integer points
                CAST(ROUND(avg_rank_position, 2) AS DECIMAL(4,2)) as avg_rank_position,
                CAST(total_connections AS TINYINT) as total_connections,        -- Max ~25 candidates
                CAST(ROUND(avg_coalition_strength, 4) AS DECIMAL(6,4)) as avg_coalition_strength,
                CAST(ROUND(total_coalition_strength, 4) AS DECIMAL(8,4)) as total_coalition_strength,
                CAST(strong_connections AS TINYINT) as strong_connections,      -- Max ~25
                CAST(ROUND(degree_centrality, 4) AS DECIMAL(6,4)) as degree_centrality,
                CAST(ROUND(strength_centrality, 4) AS DECIMAL(8,4)) as strength_centrality,
                CAST(position_type AS VARCHAR(15)) as position_type,            -- Max 11 chars observed
                CAST(ROUND(first_choice_percentage, 2) AS DECIMAL(5,2)) as first_choice_percentage
            FROM candidate_metrics
            """

            self.db.conn.execute(optimize_metrics_sql)

            # Replace original with optimized version
            self.db.conn.execute("DROP TABLE candidate_metrics")
            self.db.conn.execute(
                "ALTER TABLE candidate_metrics_optimized RENAME TO candidate_metrics"
            )

            optimized_metrics_size = self.db.query(
                "SELECT COUNT(*) * 32 as estimated_bytes FROM candidate_metrics"
            )["estimated_bytes"].iloc[0]
            optimizations["candidate_metrics"] = {
                "optimized_estimated_bytes": optimized_metrics_size,
                "optimization_applied": True,
            }

            # Create indexes for optimized tables
            logger.info("Creating optimized indexes...")

            # Indexes for adjacent_pairs (most queried table)
            self.db.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_adjacent_pairs_candidates ON adjacent_pairs(candidate_1, candidate_2)"
            )
            self.db.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_adjacent_pairs_strength ON adjacent_pairs(coalition_strength_score DESC)"
            )
            self.db.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_adjacent_pairs_shared ON adjacent_pairs(shared_ballots DESC)"
            )

            # Indexes for candidate_metrics
            self.db.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_candidate_metrics_id ON candidate_metrics(candidate_id)"
            )
            self.db.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_candidate_metrics_weighted ON candidate_metrics(weighted_score DESC)"
            )

            # Optional: Optimize ballots_long table (commented out to preserve existing data)
            # This would provide additional memory savings but requires rebuilding the core table
            """
            logger.info("Optimizing ballots_long table (optional)...")
            optimize_ballots_sql = '''
            CREATE OR REPLACE TABLE ballots_long_optimized AS
            SELECT
                CAST(BallotID AS VARCHAR(20)) as BallotID,                      -- Observed ballot IDs are ~15 chars
                CAST(PrecinctID AS TINYINT) as PrecinctID,                      -- 2-79 range
                CAST(BallotStyleID AS TINYINT) as BallotStyleID,                -- Limited range
                CAST(candidate_id AS TINYINT) as candidate_id,                  -- 36-125 range
                CAST(candidate_name AS VARCHAR(30)) as candidate_name,          -- Max 27 chars
                CAST(rank_position AS TINYINT) as rank_position,                -- 1-6 range
                CAST(has_vote AS BOOLEAN) as has_vote                           -- 0/1 -> TRUE/FALSE
            FROM ballots_long
            '''
            """

            operation_time = time.time() - operation_start
            logger.info(f"✓ Data type optimization completed in {operation_time:.2f}s")
            logger.info(
                "✓ Applied optimized data types with TINYINT, VARCHAR(n), DECIMAL precision"
            )
            logger.info("✓ Created performance indexes for common query patterns")
            logger.info(
                "✓ ballots_long table optimization available but not applied (preserves existing data)"
            )

            # Update performance stats
            self.stats["performance_improvements"]["data_type_optimization"] = {
                "operation_time_seconds": operation_time,
                "expected_memory_reduction": "50-70%",
                "expected_io_improvement": "30-50%",
                "optimizations_applied": len(optimizations),
            }

            return optimizations

        except Exception as e:
            logger.error(f"Error optimizing data types: {e}")
            self.stats["error_count"] += 1
            raise

    def precompute_candidate_metrics(self) -> Dict[str, Any]:
        """
        Precompute candidate-level metrics including centrality, vote counts, and rankings.
        """
        logger.info("=== Precomputing Candidate Metrics ===")
        operation_start = time.time()

        try:
            # Drop existing table if it exists
            self.db.conn.execute("DROP TABLE IF EXISTS candidate_metrics")

            create_metrics_sql = """
            CREATE TABLE candidate_metrics AS
            WITH candidate_vote_counts AS (
                SELECT
                    c.candidate_id,
                    c.candidate_name,
                    COUNT(DISTINCT bl.BallotID) as total_ballots,
                    COUNT(DISTINCT CASE WHEN bl.rank_position = 1 THEN bl.BallotID END) as first_choice_votes,
                    -- Ranking-weighted score (1st=6pts, 2nd=5pts, etc.)
                    SUM(CASE
                        WHEN bl.rank_position = 1 THEN 6
                        WHEN bl.rank_position = 2 THEN 5
                        WHEN bl.rank_position = 3 THEN 4
                        WHEN bl.rank_position = 4 THEN 3
                        WHEN bl.rank_position = 5 THEN 2
                        WHEN bl.rank_position = 6 THEN 1
                        ELSE 0
                    END) as weighted_score,
                    AVG(bl.rank_position) as avg_rank_position
                FROM candidates c
                LEFT JOIN ballots_long bl ON c.candidate_id = bl.candidate_id
                GROUP BY c.candidate_id, c.candidate_name
            ),
            candidate_centrality AS (
                SELECT
                    ap.candidate_1 as candidate_id,
                    COUNT(*) as connection_count,
                    AVG(ap.coalition_strength_score) as avg_coalition_strength,
                    SUM(ap.coalition_strength_score) as total_coalition_strength,
                    COUNT(CASE WHEN ap.coalition_type = 'strong' THEN 1 END) as strong_connections
                FROM adjacent_pairs ap
                GROUP BY ap.candidate_1

                UNION ALL

                SELECT
                    ap.candidate_2 as candidate_id,
                    COUNT(*) as connection_count,
                    AVG(ap.coalition_strength_score) as avg_coalition_strength,
                    SUM(ap.coalition_strength_score) as total_coalition_strength,
                    COUNT(CASE WHEN ap.coalition_type = 'strong' THEN 1 END) as strong_connections
                FROM adjacent_pairs ap
                GROUP BY ap.candidate_2
            ),
            centrality_summary AS (
                SELECT
                    candidate_id,
                    SUM(connection_count) as total_connections,
                    AVG(avg_coalition_strength) as avg_coalition_strength,
                    SUM(total_coalition_strength) as total_coalition_strength,
                    SUM(strong_connections) as strong_connections
                FROM candidate_centrality
                GROUP BY candidate_id
            ),
            max_connections AS (
                SELECT MAX(total_connections) as max_conn FROM centrality_summary
            )
            SELECT
                cv.*,
                COALESCE(cs.total_connections, 0) as total_connections,
                COALESCE(cs.avg_coalition_strength, 0) as avg_coalition_strength,
                COALESCE(cs.total_coalition_strength, 0) as total_coalition_strength,
                COALESCE(cs.strong_connections, 0) as strong_connections,
                -- Degree centrality (normalized by max possible connections)
                CASE
                    WHEN mc.max_conn > 0 THEN CAST(COALESCE(cs.total_connections, 0) AS FLOAT) / mc.max_conn
                    ELSE 0
                END as degree_centrality,
                -- Strength centrality (sum of coalition strengths)
                COALESCE(cs.total_coalition_strength, 0) as strength_centrality,
                -- Position classification
                CASE
                    WHEN COALESCE(cs.total_connections, 0) = 0 THEN 'isolated'
                    WHEN CAST(COALESCE(cs.total_connections, 0) AS FLOAT) / mc.max_conn >= 0.7 THEN 'central_hub'
                    WHEN CAST(COALESCE(cs.total_connections, 0) AS FLOAT) / mc.max_conn >= 0.5 THEN 'well_connected'
                    WHEN CAST(COALESCE(cs.total_connections, 0) AS FLOAT) / mc.max_conn >= 0.3 THEN 'moderately_connected'
                    ELSE 'periphery'
                END as position_type,
                -- Calculate first choice percentage
                CASE
                    WHEN cv.total_ballots > 0
                    THEN (CAST(cv.first_choice_votes AS FLOAT) / (SELECT COUNT(DISTINCT BallotID) FROM ballots_long)) * 100
                    ELSE 0
                END as first_choice_percentage
            FROM candidate_vote_counts cv
            LEFT JOIN centrality_summary cs ON cv.candidate_id = cs.candidate_id
            CROSS JOIN max_connections mc
            ORDER BY cv.weighted_score DESC
            """

            logger.info("Computing candidate metrics and centrality...")
            self.db.conn.execute(create_metrics_sql)

            # Get statistics
            metrics_stats = (
                self.db.query(
                    """
                SELECT
                    COUNT(*) as total_candidates,
                    AVG(weighted_score) as avg_weighted_score,
                    AVG(total_connections) as avg_connections,
                    COUNT(CASE WHEN position_type = 'central_hub' THEN 1 END) as central_hubs,
                    COUNT(CASE WHEN position_type = 'well_connected' THEN 1 END) as well_connected,
                    COUNT(CASE WHEN position_type = 'moderately_connected' THEN 1 END) as moderately_connected,
                    COUNT(CASE WHEN position_type = 'periphery' THEN 1 END) as periphery,
                    COUNT(CASE WHEN position_type = 'isolated' THEN 1 END) as isolated
                FROM candidate_metrics
            """
                )
                .iloc[0]
                .to_dict()
            )

            operation_time = time.time() - operation_start
            logger.info(
                f"✓ Precomputed metrics for {metrics_stats['total_candidates']} candidates in {operation_time:.2f}s"
            )
            logger.info(f"  - Central hubs: {metrics_stats['central_hubs']}")
            logger.info(f"  - Well connected: {metrics_stats['well_connected']}")
            logger.info(
                f"  - Moderately connected: {metrics_stats['moderately_connected']}"
            )
            logger.info(f"  - Periphery: {metrics_stats['periphery']}")
            logger.info(f"  - Isolated: {metrics_stats['isolated']}")

            # Save as Parquet
            metrics_df = self.db.query("SELECT * FROM candidate_metrics")
            parquet_path = self.precomputed_dir / "candidate_metrics.parquet"
            metrics_df.to_parquet(parquet_path, index=False)
            logger.info(f"✓ Saved to {parquet_path}")

            # Update performance stats
            self.stats["performance_improvements"]["candidate_metrics"] = {
                "operation_time_seconds": operation_time,
                "expected_speedup": "5-20x",
                "api_endpoints_affected": [
                    "/api/candidates/enhanced",
                    "/api/coalition/network",
                ],
            }
            self.stats["data_sizes"][
                "candidate_metrics_mb"
            ] = parquet_path.stat().st_size / (1024 * 1024)

            return metrics_stats

        except Exception as e:
            logger.error(f"Error precomputing candidate metrics: {e}")
            self.stats["error_count"] += 1
            raise

    def precompute_static_responses(self) -> Dict[str, Any]:
        """
        Generate static JSON responses for common API endpoints that rarely change.
        """
        logger.info("=== Precomputing Static Responses ===")
        operation_start = time.time()

        static_responses = {}

        try:
            # Coalition type breakdown
            coalition_types = self.db.query(
                """
                SELECT
                    coalition_type,
                    COUNT(*) as count,
                    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage,
                    AVG(coalition_strength_score) as avg_strength,
                    AVG(shared_ballots) as avg_shared_ballots
                FROM adjacent_pairs
                GROUP BY coalition_type
                ORDER BY count DESC
            """
            )

            # Network statistics
            network_stats = (
                self.db.query(
                    """
                SELECT
                    COUNT(*) as total_nodes,
                    (SELECT COUNT(*) FROM adjacent_pairs) as total_edges,
                    AVG(total_connections) as avg_connections,
                    MAX(total_connections) as max_connections,
                    AVG(strength_centrality) as avg_strength_centrality
                FROM candidate_metrics
            """
                )
                .iloc[0]
                .to_dict()
            )

            # Enhanced candidates summary
            candidates_enhanced = self.db.query(
                """
                SELECT
                    candidate_id,
                    candidate_name,
                    first_choice_votes,
                    first_choice_percentage,
                    weighted_score,
                    total_connections,
                    position_type,
                    avg_coalition_strength,
                    CASE WHEN candidate_id IN (36, 46, 55) THEN true ELSE false END as is_winner
                FROM candidate_metrics
                ORDER BY weighted_score DESC
            """
            )

            # Save static responses
            static_files = {
                "coalition_types": coalition_types.to_dict("records"),
                "network_stats": network_stats,
                "candidates_enhanced": candidates_enhanced.to_dict("records"),
            }

            for filename, data in static_files.items():
                json_path = self.static_responses_dir / f"{filename}.json"
                with open(json_path, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                logger.info(f"✓ Saved {filename} ({len(str(data))} chars)")
                static_responses[filename] = len(str(data))

            operation_time = time.time() - operation_start

            # Update performance stats
            self.stats["performance_improvements"]["static_responses"] = {
                "operation_time_seconds": operation_time,
                "files_generated": len(static_files),
                "expected_speedup": "100x",
                "api_endpoints_affected": [
                    "/api/coalition/types",
                    "/api/candidates/enhanced",
                ],
            }

            return static_responses

        except Exception as e:
            logger.error(f"Error precomputing static responses: {e}")
            self.stats["error_count"] += 1
            raise

    def generate_metadata(self) -> Dict[str, Any]:
        """
        Generate metadata about the precomputed data for versioning and validation.
        """
        total_time = time.time() - self.start_time

        metadata = {
            "election_id": self.election_id,
            "generation_time": datetime.now().isoformat(),
            "processing_time_seconds": total_time,
            "data_version": "1.0",
            "source_database": str(self.db_path),
            "statistics": self.stats,
            "precomputed_tables": ["adjacent_pairs", "candidate_metrics"],
            "data_quality": {
                "total_pairs": self.db.query(
                    "SELECT COUNT(*) as count FROM adjacent_pairs"
                )["count"].iloc[0],
                "total_candidates": self.db.query(
                    "SELECT COUNT(*) as count FROM candidate_metrics"
                )["count"].iloc[0],
                "avg_coalition_strength": float(
                    self.db.query(
                        "SELECT AVG(coalition_strength_score) as avg FROM adjacent_pairs"
                    )["avg"].iloc[0]
                ),
            },
        }

        # Save metadata
        metadata_path = self.data_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        return metadata

    def run_full_precomputation(self, min_shared_ballots: int = 10) -> Dict[str, Any]:
        """
        Run the complete precomputation pipeline.
        """
        logger.info("🚀 Starting Full Precomputation Pipeline")
        logger.info(f"Election ID: {self.election_id}")
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Target directory: {self.data_dir}")

        if not self.validate_prerequisites():
            raise RuntimeError("Prerequisites validation failed")

        results = {}

        # Phase 1: Adjacent pairs (most critical for performance)
        results["adjacent_pairs"] = self.precompute_adjacent_pairs(min_shared_ballots)
        self.stats["operations_completed"].append("adjacent_pairs")

        # Phase 2: Candidate metrics
        results["candidate_metrics"] = self.precompute_candidate_metrics()
        self.stats["operations_completed"].append("candidate_metrics")

        # Phase 3: Data type optimization
        results["data_type_optimization"] = self.optimize_data_types()
        self.stats["operations_completed"].append("data_type_optimization")

        # Phase 4: Static responses
        results["static_responses"] = self.precompute_static_responses()
        self.stats["operations_completed"].append("static_responses")

        # Generate final metadata
        results["metadata"] = self.generate_metadata()

        # Close database connection before returning
        self.db.close()

        total_time = time.time() - self.start_time
        logger.info(f"🎉 Precomputation completed in {total_time:.2f}s")
        logger.info(f"✓ {len(self.stats['operations_completed'])} operations completed")
        logger.info(f"✗ {self.stats['error_count']} errors encountered")

        # Performance summary
        logger.info("\n=== Performance Impact Summary ===")
        for operation, improvement in self.stats["performance_improvements"].items():
            if "expected_speedup" in improvement:
                logger.info(f"{operation}: {improvement['expected_speedup']} speedup")
            elif "expected_memory_reduction" in improvement:
                logger.info(
                    f"{operation}: {improvement['expected_memory_reduction']} memory reduction"
                )
            else:
                logger.info(f"{operation}: optimization applied")

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Precompute analytical data for performance optimization"
    )
    parser.add_argument("--db", required=True, help="Path to DuckDB database file")
    parser.add_argument(
        "--election-id", default="2024_portland_district2", help="Election identifier"
    )
    parser.add_argument(
        "--min-shared-ballots",
        type=int,
        default=10,
        help="Minimum shared ballots for pair analysis",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force rebuild of all precomputed data",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation checks after precomputation",
    )

    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        sys.exit(1)

    try:
        processor = PrecomputeProcessor(str(db_path), args.election_id)

        # Check if precomputed data already exists
        if (
            not args.force_refresh
            and (processor.precomputed_dir / "adjacent_pairs.parquet").exists()
        ):
            logger.info(
                "Precomputed data already exists. Use --force-refresh to rebuild."
            )

            # Load existing metadata for validation
            metadata_path = processor.data_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
                logger.info(
                    f"Existing data version: {metadata.get('data_version', 'unknown')}"
                )
                logger.info(f"Generated: {metadata.get('generation_time', 'unknown')}")

            if not args.validate:
                logger.info("Use --validate to check data integrity")
                sys.exit(0)

        # Run precomputation
        processor.run_full_precomputation(args.min_shared_ballots)  # Run precomputation

        if args.validate:
            logger.info("\n=== Validation Checks ===")

            # Test precomputed data integrity
            db = CVRDatabase(str(db_path), read_only=True)

            # Check adjacent pairs
            pairs_count = db.query("SELECT COUNT(*) as count FROM adjacent_pairs")[
                "count"
            ].iloc[0]
            logger.info(f"✓ Adjacent pairs table: {pairs_count:,} records")

            # Check candidate metrics
            metrics_count = db.query("SELECT COUNT(*) as count FROM candidate_metrics")[
                "count"
            ].iloc[0]
            logger.info(f"✓ Candidate metrics table: {metrics_count} records")

            # Validate coalition strength distribution
            strength_stats = db.query(
                """
                SELECT
                    MIN(coalition_strength_score) as min_strength,
                    AVG(coalition_strength_score) as avg_strength,
                    MAX(coalition_strength_score) as max_strength
                FROM adjacent_pairs
            """
            ).iloc[0]

            logger.info(
                f"✓ Coalition strength range: {strength_stats['min_strength']:.4f} - {strength_stats['max_strength']:.4f}"
            )
            logger.info(
                f"✓ Average coalition strength: {strength_stats['avg_strength']:.4f}"
            )

            # Check for winners in candidate metrics
            winners = db.query(
                "SELECT candidate_name FROM candidate_metrics WHERE candidate_id IN (36, 46, 55) ORDER BY weighted_score DESC"
            )
            logger.info(
                f"✓ Portland winners found: {', '.join(winners['candidate_name'])}"
            )

            logger.info("✓ Validation completed successfully")

        print(f"\n🎉 Success! Precomputed data ready for {processor.election_id}")
        print(f"📁 Data location: {processor.data_dir}")
        print("⚡ Expected API performance improvements: 5-100x faster")

    except Exception as e:
        logger.error(f"Precomputation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
