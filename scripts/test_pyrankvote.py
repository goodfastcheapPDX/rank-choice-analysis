#!/usr/bin/env python3
"""
Test PyRankVote implementation against real election data.

This script compares results from our custom STV implementation
with PyRankVote library on actual Portland election data.
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analysis.stv import STVTabulator
from analysis.stv_pyrankvote import PyRankVoteSTVTabulator
from data.database import CVRDatabase

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def test_implementations(db_path: str):
    """
    Test both STV implementations on real data.

    Args:
        db_path: Path to the election database
    """
    if not Path(db_path).exists():
        logger.error(f"Database file not found: {db_path}")
        logger.info(
            "Please run: python scripts/process_data.py your_election_file.csv --db election_data.db"
        )
        return

    logger.info("=== Testing STV Implementations ===")
    logger.info(f"Database: {db_path}")

    # Connect to database
    db = CVRDatabase(db_path)

    try:
        # Test basic database connection
        candidates = db.query("SELECT COUNT(*) as count FROM candidates")
        ballots = db.query("SELECT COUNT(DISTINCT BallotID) as count FROM ballots_long")

        logger.info(
            f"Database contains {candidates.iloc[0]['count']} candidates and {ballots.iloc[0]['count']} ballots"
        )

        # Run original implementation
        logger.info("\n=== Running Original STV Implementation ===")
        original_tabulator = STVTabulator(db, seats=3)
        original_rounds = original_tabulator.run_stv_tabulation()
        original_results = original_tabulator.get_final_results()

        logger.info(f"Original winners: {original_tabulator.winners}")
        logger.info(f"Original rounds: {len(original_rounds)}")

        # Run PyRankVote implementation
        logger.info("\n=== Running PyRankVote STV Implementation ===")
        pyrankvote_tabulator = PyRankVoteSTVTabulator(db, seats=3)
        pyrankvote_rounds = pyrankvote_tabulator.run_stv_tabulation()
        pyrankvote_results = pyrankvote_tabulator.get_final_results()

        logger.info(f"PyRankVote winners: {pyrankvote_tabulator.winners}")
        logger.info(f"PyRankVote rounds: {len(pyrankvote_rounds)}")

        # Compare results
        logger.info("\n=== Comparison ===")

        # Winner comparison
        original_winners = set(original_tabulator.winners)
        pyrankvote_winners = set(pyrankvote_tabulator.winners)

        if original_winners == pyrankvote_winners:
            logger.info("✅ Winners match exactly!")
        else:
            logger.warning("❌ Winners differ:")
            logger.warning(f"  Original: {sorted(original_winners)}")
            logger.warning(f"  PyRankVote: {sorted(pyrankvote_winners)}")
            logger.warning(
                f"  Only in original: {sorted(original_winners - pyrankvote_winners)}"
            )
            logger.warning(
                f"  Only in PyRankVote: {sorted(pyrankvote_winners - original_winners)}"
            )

        # Quota comparison
        original_quota = original_rounds[0].quota if original_rounds else 0
        pyrankvote_quota = pyrankvote_rounds[0].quota if pyrankvote_rounds else 0

        if original_quota == pyrankvote_quota:
            logger.info(f"✅ Quota matches: {original_quota}")
        else:
            logger.warning(
                f"❌ Quota differs: Original={original_quota}, PyRankVote={pyrankvote_quota}"
            )

        # Show detailed results if different
        if original_winners != pyrankvote_winners:
            logger.info("\n=== Detailed Original Results ===")
            print(
                original_results[
                    ["candidate_id", "candidate_name", "final_votes", "status"]
                ].head(10)
            )

            logger.info("\n=== Detailed PyRankVote Results ===")
            print(
                pyrankvote_results[
                    ["candidate_id", "candidate_name", "final_votes", "status"]
                ].head(10)
            )

        # Show PyRankVote detailed output if available
        if hasattr(pyrankvote_tabulator, "get_pyrankvote_detailed_results"):
            detailed = pyrankvote_tabulator.get_pyrankvote_detailed_results()
            if detailed and detailed != "No PyRankVote results available":
                logger.info("\n=== PyRankVote Detailed Results ===")
                print(detailed)

    except Exception as e:
        logger.error(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Test PyRankVote implementation")
    parser.add_argument("--db", default="election_data.db", help="Database file path")

    args = parser.parse_args()

    test_implementations(args.db)


if __name__ == "__main__":
    main()
