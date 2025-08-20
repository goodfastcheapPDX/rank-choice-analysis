#!/usr/bin/env python3
"""
Data processing pipeline for CVR data.
Loads, transforms, and validates Cast Vote Record data.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.cvr_parser import CVRParser  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Process CVR data")
    parser.add_argument("csv_file", help="Path to CVR CSV file")
    parser.add_argument(
        "--db", help="Path to DuckDB database file (default: in-memory)"
    )
    parser.add_argument("--validate", action="store_true", help="Run validation checks")

    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)

    try:
        with CVRParser(args.db) as parser:
            # Step 1: Load raw CVR data
            logger.info("=== Step 1: Loading CVR Data ===")
            load_stats = parser.load_cvr_file(str(csv_path))
            print(f"✓ Loaded {load_stats['total_ballots']} ballots")
            print(f"✓ Found {load_stats['unique_ballots']} unique ballot IDs")

            if load_stats["duplicate_ballots"] > 0:
                print(
                    f"⚠️  Warning: {load_stats['duplicate_ballots']} duplicate ballot IDs"
                )

            # Step 2: Extract candidate metadata
            logger.info("=== Step 2: Extracting Candidate Metadata ===")
            candidates = parser.extract_candidate_metadata()
            print(f"✓ Found {len(candidates)} candidates")
            print("\nCandidates:")
            for _, candidate in candidates.iterrows():
                print(
                    f"  {candidate['candidate_id']:2d}: {candidate['candidate_name']}"
                )

            # Step 3: Normalize vote data
            logger.info("=== Step 3: Normalizing Vote Data ===")
            norm_stats = parser.normalize_vote_data()
            print(f"✓ Created {norm_stats['total_vote_records']} vote records")
            print(f"✓ Processing {norm_stats['ballots_with_votes']} ballots with votes")

            # Step 4: Generate summary statistics
            logger.info("=== Step 4: Summary Statistics ===")
            summary = parser.get_summary_statistics()
            print("\nSummary:")
            for _, row in summary.iterrows():
                print(f"  {row['metric']}: {row['value']}")

            # Step 5: First choice results
            logger.info("=== Step 5: First Choice Results ===")
            first_choice = parser.get_first_choice_totals()
            print("\nTop 10 First Choice Results:")
            for _, row in first_choice.head(10).iterrows():
                print(
                    f"  {row['candidate_name']:25s}: {row['first_choice_votes']:5d} votes ({row['percentage']:5.1f}%)"
                )

            # Step 6: Ballot completion patterns
            completion = parser.get_ballot_completion_stats()
            print("\nBallot Completion Patterns:")
            for _, row in completion.iterrows():
                print(
                    f"  {row['ranks_used']} ranks: {row['ballot_count']:5d} ballots ({row['percentage']:5.1f}%)"
                )

            if args.validate:
                logger.info("=== Validation Checks ===")

                # Check for any obvious data issues
                votes_by_rank = parser.get_votes_by_rank()
                total_ballots = load_stats["unique_ballots"]

                # Check that rank 1 has reasonable participation
                rank1_votes = votes_by_rank[votes_by_rank["rank_position"] == 1][
                    "total_votes"
                ].sum()
                rank1_rate = rank1_votes / total_ballots

                print("\nValidation Results:")
                print(
                    f"✓ Rank 1 participation: {rank1_rate:.1%} ({rank1_votes}/{total_ballots})"
                )

                if rank1_rate < 0.8:
                    print("⚠️  Warning: Low rank 1 participation rate")

                print("✓ Data processing completed successfully")

    except Exception as e:
        logger.error(f"Error processing data: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
