#!/usr/bin/env python3
"""
Verify our STV results against official election results.
"""

import sys
import logging
from pathlib import Path
import argparse

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.database import CVRDatabase
from data.cvr_parser import CVRParser
from analysis.stv import STVTabulator
from analysis.verification import ResultsVerifier

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Verify STV results against official results")
    parser.add_argument("--db", required=True, help="Path to DuckDB database file with processed data")
    parser.add_argument("--official", required=True, help="Path to official results CSV file")
    parser.add_argument("--seats", type=int, default=3, help="Number of seats to fill (default: 3)")
    parser.add_argument("--export", help="Export verification report to file")
    
    args = parser.parse_args()
    
    if not Path(args.db).exists():
        logger.error("Database file not found. Run process_data.py first.")
        sys.exit(1)
        
    if not Path(args.official).exists():
        logger.error(f"Official results file not found: {args.official}")
        sys.exit(1)
        
    try:
        with CVRDatabase(args.db) as db:
            logger.info("=== Running STV Tabulation ===")
            
            # Run our STV tabulation
            tabulator = STVTabulator(db, seats=args.seats)
            rounds = tabulator.run_stv_tabulation()
            
            # Get our results
            our_winners = tabulator.winners
            candidates = db.query("SELECT candidate_id, candidate_name FROM candidates")
            first_choice = db.query("SELECT * FROM first_choice_totals")
            
            logger.info(f"Our winners: {our_winners}")
            
            logger.info("=== Loading Official Results ===")
            
            # Load official results
            verifier = ResultsVerifier(args.official)
            official_data = verifier.load_official_results()
            
            logger.info(f"Official winners: {official_data['winners']}")
            logger.info(f"Official threshold: {official_data['metadata'].get('threshold', 'Unknown')}")
            
            logger.info("=== Verifying Results ===")
            
            # Verify our results
            verification_results = verifier.verify_results(
                our_winners=our_winners,
                our_candidates=candidates,
                our_first_choice=first_choice
            )
            
            # Generate report
            report = verifier.generate_verification_report(verification_results)
            print(report)
            
            # Export if requested
            if args.export:
                export_path = Path(args.export)
                with open(export_path, 'w') as f:
                    f.write(report)
                print(f"\n✓ Verification report exported to: {export_path}")
                
                # Also export detailed vote comparison CSV
                vote_comparison_path = export_path.with_stem(export_path.stem + "_vote_comparison").with_suffix('.csv')
                verification_results["vote_comparisons"].to_csv(vote_comparison_path, index=False)
                print(f"✓ Vote comparison data exported to: {vote_comparison_path}")
            
            # Exit with appropriate code
            if verification_results["verification_passed"]:
                print("\n🎉 Verification PASSED!")
                sys.exit(0)
            else:
                print("\n⚠️  Verification FAILED - see report above for details")
                sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()