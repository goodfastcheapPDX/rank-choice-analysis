import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class OfficialResultsParser:
    """
    Parses official election results from CSV format for verification.
    """
    
    def __init__(self, csv_path: str):
        """
        Initialize parser with official results CSV file.
        
        Args:
            csv_path: Path to official results CSV file
        """
        self.csv_path = Path(csv_path)
        self.raw_data = None
        self.metadata = {}
        self.winners = []
        self.final_results = None
        self.round_data = None
        
    def parse_results(self) -> Dict:
        """
        Parse the official results CSV file.
        
        Returns:
            Dictionary with parsed results
        """
        logger.info(f"Parsing official results from: {self.csv_path}")
        
        # Read the CSV file
        with open(self.csv_path, 'r') as f:
            lines = f.readlines()
        
        # Parse metadata from header
        self._parse_metadata(lines)
        
        # Find the data section
        data_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith(',# votes,% of votes'):
                data_start = i
                break
        
        if data_start is None:
            raise ValueError("Could not find data section in official results")
        
        # Parse the results data
        self._parse_results_data(lines[data_start:])
        
        return {
            "metadata": self.metadata,
            "winners": self.winners,
            "final_results": self.final_results,
            "round_data": self.round_data
        }
    
    def _parse_metadata(self, lines: List[str]):
        """Parse metadata from the header section."""
        for line in lines[:10]:
            line = line.strip()
            if "Election Date" in line:
                self.metadata["election_date"] = line.split(",")[1]
            elif "Report Date" in line:
                self.metadata["report_date"] = line.split(",")[1]
            elif "Registered Voters in District" in line:
                self.metadata["registered_voters"] = int(line.split(",")[1])
            elif "Election Threshold" in line:
                # Extract threshold number
                threshold_text = line.split(",")[1]
                self.metadata["threshold"] = int(threshold_text.split()[0])
    
    def _parse_results_data(self, data_lines: List[str]):
        """Parse the results data section."""
        # Find winners and defeated candidates
        winners_line = None
        defeated_line = None
        
        for line in data_lines:
            if line.startswith("Met threshold for election"):
                winners_line = line
            elif line.startswith("Defeated"):
                defeated_line = line
        
        # Extract winners
        if winners_line:
            winner_parts = winners_line.split(",,")
            for part in winner_parts:
                if part.strip() and "Met threshold" not in part:
                    # Handle multiple winners in same cell (e.g., "Dan Ryan; Elana Pirtle-Guiney")
                    if ";" in part:
                        names = [name.strip() for name in part.split(";")]
                        self.winners.extend(names)
                    else:
                        self.winners.append(part.strip())
        
        # Parse candidate data
        candidate_data = []
        for line in data_lines[3:]:  # Skip header lines
            if line.strip() and not line.startswith(",") and not line.startswith("Met threshold") and not line.startswith("Defeated"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) > 1 and parts[0]:  # Has candidate name
                    candidate_name = parts[0]
                    
                    # Extract round 1 data (first choice votes)
                    first_choice_votes = 0
                    if len(parts) > 1 and parts[1]:
                        try:
                            first_choice_votes = float(parts[1])
                        except:
                            pass
                    
                    # Extract final round data (last non-empty vote count)
                    final_votes = 0
                    final_percentage = 0
                    
                    # Work backwards to find final vote count
                    for i in range(len(parts) - 1, 0, -1):
                        if parts[i] and parts[i] != "":
                            try:
                                # Check if it's a vote count (not a percentage)
                                if "%" not in parts[i] and "." in parts[i]:
                                    final_votes = float(parts[i])
                                    break
                            except:
                                continue
                    
                    candidate_data.append({
                        "candidate_name": candidate_name,
                        "first_choice_votes": first_choice_votes,
                        "final_votes": final_votes,
                        "is_winner": candidate_name in self.winners
                    })
        
        self.final_results = pd.DataFrame(candidate_data)
        logger.info(f"Parsed {len(candidate_data)} candidates from official results")


class ResultsVerifier:
    """
    Verifies our STV results against official results.
    """
    
    def __init__(self, official_results_path: str):
        """
        Initialize verifier.
        
        Args:
            official_results_path: Path to official results CSV
        """
        self.parser = OfficialResultsParser(official_results_path)
        self.official_data = None
        
    def load_official_results(self) -> Dict:
        """Load and parse official results."""
        self.official_data = self.parser.parse_results()
        return self.official_data
    
    def verify_results(self, our_winners: List[int], our_candidates: pd.DataFrame, 
                      our_first_choice: pd.DataFrame) -> Dict:
        """
        Verify our results against official results.
        
        Args:
            our_winners: List of candidate IDs we calculated as winners
            our_candidates: DataFrame with candidate ID to name mapping
            our_first_choice: DataFrame with our first choice vote counts
            
        Returns:
            Verification report dictionary
        """
        if not self.official_data:
            self.load_official_results()
        
        logger.info("Verifying results against official data")
        
        # Create candidate name mapping
        candidate_map = dict(zip(our_candidates['candidate_id'], our_candidates['candidate_name']))
        our_winner_names = [candidate_map.get(winner_id, f"ID-{winner_id}") for winner_id in our_winners]
        
        # Verify winners
        official_winners = set(self.official_data["winners"])
        our_winner_names_set = set(our_winner_names)
        
        winners_match = official_winners == our_winner_names_set
        
        # Verify first choice vote counts
        vote_comparisons = []
        official_results = self.official_data["final_results"]
        
        for _, official_row in official_results.iterrows():
            candidate_name = official_row["candidate_name"]
            official_votes = official_row["first_choice_votes"]
            
            # Find our vote count for this candidate
            our_row = our_first_choice[our_first_choice['candidate_name'] == candidate_name]
            our_votes = our_row['first_choice_votes'].iloc[0] if not our_row.empty else 0
            
            vote_comparisons.append({
                "candidate_name": candidate_name,
                "official_votes": official_votes,
                "our_votes": our_votes,
                "difference": our_votes - official_votes,
                "percentage_diff": ((our_votes - official_votes) / official_votes * 100) if official_votes > 0 else 0
            })
        
        vote_comparison_df = pd.DataFrame(vote_comparisons)
        
        # Calculate verification metrics
        total_vote_difference = abs(vote_comparison_df['difference'].sum())
        max_candidate_difference = vote_comparison_df['difference'].abs().max()
        candidates_with_differences = len(vote_comparison_df[vote_comparison_df['difference'] != 0])
        
        verification_report = {
            "winners_match": winners_match,
            "official_winners": list(official_winners),
            "our_winners": our_winner_names,
            "missing_winners": list(official_winners - our_winner_names_set),
            "extra_winners": list(our_winner_names_set - official_winners),
            "vote_comparisons": vote_comparison_df,
            "total_vote_difference": total_vote_difference,
            "max_candidate_difference": max_candidate_difference,
            "candidates_with_differences": candidates_with_differences,
            "verification_passed": winners_match and total_vote_difference == 0,
            "official_metadata": self.official_data["metadata"]
        }
        
        return verification_report
    
    def generate_verification_report(self, verification_results: Dict) -> str:
        """
        Generate a human-readable verification report.
        
        Args:
            verification_results: Results from verify_results()
            
        Returns:
            Formatted verification report string
        """
        report = []
        report.append("=" * 60)
        report.append("ELECTION RESULTS VERIFICATION REPORT")
        report.append("=" * 60)
        
        # Overall status
        if verification_results["verification_passed"]:
            report.append("✅ VERIFICATION PASSED - Results match official results!")
        else:
            report.append("❌ VERIFICATION FAILED - Discrepancies found")
        
        report.append("")
        
        # Winners verification
        report.append("WINNERS VERIFICATION:")
        if verification_results["winners_match"]:
            report.append("✅ Winners match official results")
        else:
            report.append("❌ Winners do not match official results")
        
        report.append(f"Official winners: {', '.join(verification_results['official_winners'])}")
        report.append(f"Our winners: {', '.join(verification_results['our_winners'])}")
        
        if verification_results["missing_winners"]:
            report.append(f"Missing winners: {', '.join(verification_results['missing_winners'])}")
        if verification_results["extra_winners"]:
            report.append(f"Extra winners: {', '.join(verification_results['extra_winners'])}")
        
        report.append("")
        
        # Vote count verification
        report.append("FIRST CHOICE VOTE COUNT VERIFICATION:")
        vote_df = verification_results["vote_comparisons"]
        
        report.append(f"Total vote difference: {verification_results['total_vote_difference']}")
        report.append(f"Max candidate difference: {verification_results['max_candidate_difference']}")
        report.append(f"Candidates with differences: {verification_results['candidates_with_differences']}")
        
        # Show candidates with largest differences
        if verification_results['candidates_with_differences'] > 0:
            report.append("\nLargest discrepancies:")
            top_diffs = vote_df.nlargest(5, 'difference', keep='all')[['candidate_name', 'official_votes', 'our_votes', 'difference']]
            for _, row in top_diffs.iterrows():
                report.append(f"  {row['candidate_name']}: Official={row['official_votes']}, Ours={row['our_votes']}, Diff={row['difference']}")
        
        # Metadata
        report.append("")
        report.append("OFFICIAL ELECTION METADATA:")
        metadata = verification_results["official_metadata"]
        for key, value in metadata.items():
            report.append(f"  {key.replace('_', ' ').title()}: {value}")
        
        return "\n".join(report)