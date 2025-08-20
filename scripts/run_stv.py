#!/usr/bin/env python3
"""
Run STV tabulation on processed CVR data.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analysis.stv import STVTabulator  # noqa: E402
from data.database import CVRDatabase  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run STV tabulation")
    parser.add_argument("--db", help="Path to DuckDB database file with processed data")
    parser.add_argument(
        "--seats", type=int, default=3, help="Number of seats to fill (default: 3)"
    )
    parser.add_argument("--export", help="Export results to CSV file")

    args = parser.parse_args()

    if not args.db or not Path(args.db).exists():
        logger.error(
            "Database file required and must exist. Run process_data.py first."
        )
        sys.exit(1)

    try:
        with CVRDatabase(args.db) as db:
            # Check that required tables exist
            required_tables = ["ballots_long", "candidates"]
            for table in required_tables:
                if not db.table_exists(table):
                    logger.error(
                        f"Required table '{table}' not found. Run process_data.py first."
                    )
                    sys.exit(1)

            # Initialize STV tabulator
            logger.info(f"=== STV Tabulation ({args.seats} seats) ===")
            tabulator = STVTabulator(db, seats=args.seats)

            # Run tabulation
            tabulator.run_stv_tabulation()  # Store results in tabulator object

            # Display round-by-round results
            print("\n=== Round-by-Round Results ===")
            round_summary = tabulator.get_round_summary()

            # Get candidate names for display
            candidates = db.query("SELECT candidate_id, candidate_name FROM candidates")
            candidate_names = dict(
                zip(candidates["candidate_id"], candidates["candidate_name"])
            )

            for round_num in sorted(round_summary["round"].unique()):
                round_data = round_summary[round_summary["round"] == round_num]
                print(f"\nRound {round_num}:")
                print(f"Quota: {round_data.iloc[0]['quota']:.1f}")

                for _, row in round_data.sort_values(
                    "votes", ascending=False
                ).iterrows():
                    candidate_name = candidate_names.get(
                        row["candidate_id"], f"ID-{row['candidate_id']}"
                    )
                    status_symbol = {
                        "elected": "🏆",
                        "eliminated": "❌",
                        "continuing": "  ",
                        "already_elected": "✓ ",
                        "already_eliminated": "- ",
                    }.get(row["status"], "  ")

                    print(
                        f"  {status_symbol} {candidate_name:25s}: {row['votes']:8.1f} votes"
                    )

                if round_data.iloc[0]["exhausted_votes"] > 0:
                    print(
                        f"     {'Exhausted':25s}: {round_data.iloc[0]['exhausted_votes']:8.1f} votes"
                    )

            # Display final results
            print("\n=== Final Results ===")
            final_results = tabulator.get_final_results()

            print(f"\nElected ({len(tabulator.winners)} of {args.seats} seats):")
            elected = final_results[final_results["status"] == "elected"]
            for i, (_, row) in enumerate(elected.iterrows(), 1):
                print(
                    f"  {i}. {row['candidate_name']:30s}: {row['final_votes']:8.1f} votes (Round {row['election_round']})"
                )

            print("\nNot Elected:")
            not_elected = final_results[final_results["status"] == "not_elected"].head(
                10
            )
            for _, row in not_elected.iterrows():
                print(
                    f"     {row['candidate_name']:30s}: {row['final_votes']:8.1f} votes"
                )

            # Export results if requested
            if args.export:
                export_path = Path(args.export)

                # Export final results
                final_results.to_csv(export_path.with_suffix(".csv"), index=False)
                print(
                    f"\n✓ Final results exported to: {export_path.with_suffix('.csv')}"
                )

                # Export round summary
                round_summary_export = round_summary.merge(
                    candidates[["candidate_id", "candidate_name"]],
                    on="candidate_id",
                    how="left",
                )
                round_summary_export.to_csv(
                    export_path.with_stem(export_path.stem + "_rounds").with_suffix(
                        ".csv"
                    ),
                    index=False,
                )
                print(
                    f"✓ Round summary exported to: {export_path.with_stem(export_path.stem + '_rounds').with_suffix('.csv')}"
                )

            print("\n✓ STV tabulation completed successfully")

    except Exception as e:
        logger.error(f"Error running STV tabulation: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
