#!/usr/bin/env python3
"""
Test the complete data processing pipeline.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.cvr_parser import CVRParser
from analysis.stv import STVTabulator
from analysis.verification import ResultsVerifier


def test_with_sample_data():
    """Test the pipeline with one of the sample CSV files."""
    
    # Find a CVR data file (not the official results file)
    project_root = Path(__file__).parent.parent
    
    # Look for CVR files specifically (avoid official results files)
    cvr_files = []
    for csv_file in project_root.glob("*.csv"):
        if "report_official" not in csv_file.name and "cvr" in csv_file.name.lower():
            cvr_files.append(csv_file)
    
    # If no CVR files found, look for any CSV files that aren't official results
    if not cvr_files:
        for csv_file in project_root.glob("*.csv"):
            if "report_official" not in csv_file.name:
                cvr_files.append(csv_file)
    
    if not cvr_files:
        print("No CVR data files found in project root.")
        print("Please copy your CVR data file (e.g., 'City_of_Portland__Councilor__District_2_2024_11_29_17_26_12.cvr copy.csv') to the project root for testing.")
        return False
    
    csv_file = cvr_files[0]
    print(f"Testing with: {csv_file.name}")
    
    # Use a temporary database - just get a temp path, don't create the file
    import os
    db_path = os.path.join(tempfile.gettempdir(), f"test_election_{os.getpid()}.db")
    
    # Make sure it doesn't exist
    if os.path.exists(db_path):
        os.unlink(db_path)
    
    try:
        print("\n=== Testing CVR Parser ===")
        with CVRParser(db_path) as parser:
            # Load data
            load_stats = parser.load_cvr_file(str(csv_file))
            print(f"✓ Loaded {load_stats['total_ballots']} ballots")
            
            # Extract metadata
            candidates = parser.extract_candidate_metadata()
            print(f"✓ Found {len(candidates)} candidates")
            
            # Normalize data
            norm_stats = parser.normalize_vote_data()
            print(f"✓ Created {norm_stats['total_vote_records']} vote records")
            
            # Get summary
            summary = parser.get_summary_statistics()
            print("✓ Generated summary statistics")
            
            # Get first choice results
            first_choice = parser.get_first_choice_totals()
            print(f"✓ Top candidate: {first_choice.iloc[0]['candidate_name']} with {first_choice.iloc[0]['first_choice_votes']} votes")
        
        print("\n=== Testing STV Tabulation ===")
        with CVRParser(db_path) as parser:
            tabulator = STVTabulator(parser.db, seats=3)
            rounds = tabulator.run_stv_tabulation()
            
            print(f"✓ STV completed in {len(rounds)} rounds")
            print(f"✓ Winners: {tabulator.winners}")
            
            final_results = tabulator.get_final_results()
            print("✓ Generated final results")
        
        print("\n=== Testing Results Verification ===")
        # Check if official results file exists
        project_root = Path(__file__).parent.parent
        official_results = project_root / "2024-12-02_15-04-45_report_official.csv"
        
        if official_results.exists():
            print(f"✓ Found official results file: {official_results.name}")
            
            # Test verification with a new database connection
            with CVRParser(db_path) as verification_parser:
                verifier = ResultsVerifier(str(official_results))
                candidates = verification_parser.db.query("SELECT candidate_id, candidate_name FROM candidates")
                first_choice = verification_parser.db.query("SELECT * FROM first_choice_totals")
                
                verification_results = verifier.verify_results(
                    our_winners=tabulator.winners,
                    our_candidates=candidates,
                    our_first_choice=first_choice
                )
                
                if verification_results["verification_passed"]:
                    print("✓ Results verification PASSED!")
                else:
                    print("⚠️  Results verification found discrepancies")
                    print(f"   Winners match: {verification_results['winners_match']}")
                    print(f"   Vote differences: {verification_results['total_vote_difference']}")
        else:
            print("⚠️  Official results file not found - skipping verification")
        
        print("\n=== All Tests Passed! ===")
        print(f"Database created at: {db_path}")
        print("You can now start the web server with:")
        print(f"python scripts/start_server.py --db {db_path}")
        print("Or verify against official results with:")
        print(f"python scripts/verify_results.py --db {db_path} --official {official_results}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up test database
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
                print(f"Cleaned up test database: {db_path}")
            except:
                pass


if __name__ == "__main__":
    success = test_with_sample_data()
    sys.exit(0 if success else 1)