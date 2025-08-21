import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.analysis.verification import (
    OfficialResultsParser,
    ResultsVerifier,
    normalize_candidate_name,
)


class TestCandidateNameNormalization:
    """Test candidate name normalization functionality."""

    def test_basic_normalization(self):
        """Test basic name normalization."""
        assert normalize_candidate_name("John Smith") == "john smith"
        assert normalize_candidate_name("  Mary Jones  ") == "mary jones"
        assert normalize_candidate_name("") == ""

    def test_extra_whitespace_removal(self):
        """Test removal of extra whitespace."""
        assert normalize_candidate_name("John   Smith") == "john smith"
        assert normalize_candidate_name("Mary  Jane  Doe") == "mary jane doe"

    def test_parentheses_removal(self):
        """Test removal of parenthetical content."""
        assert normalize_candidate_name("John Smith (Mike)") == "john smith"
        assert normalize_candidate_name("Mary (Jane) Doe") == "mary doe"
        assert normalize_candidate_name("Bob (Robert) Johnson (Jr.)") == "bob johnson"

    def test_hyphen_normalization(self):
        """Test hyphen spacing normalization."""
        assert normalize_candidate_name("Mary-Jane Smith") == "mary-jane smith"
        assert normalize_candidate_name("Mary - Jane Smith") == "mary-jane smith"
        assert normalize_candidate_name("Mary-Jane  Smith") == "mary-jane smith"

    def test_edge_cases(self):
        """Test edge cases."""
        assert normalize_candidate_name(None) == ""
        assert normalize_candidate_name("   ") == ""
        assert normalize_candidate_name("A") == "a"
        assert normalize_candidate_name("(Mike)") == ""


class TestOfficialResultsParser:
    """Test official results parsing functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_csv_content = """Election Date,Nov 05, 2024
Report Date,Nov 29, 2024
Election,City of Portland - Councilor - District 2
Registered Voters in District,123456
Election Threshold,25000
,# votes,% of votes,# votes,% of votes,# votes,% of votes
Met threshold for election,Dan Ryan; Elana Pirtle-Guiney; Nat West
Defeated,All others

,# votes,% of votes,# votes,% of votes,# votes,% of votes
Dan Ryan,25123,15.23%,28456,17.25%,35678,21.6%
Elana Pirtle-Guiney,23456,14.21%,26789,16.23%,33445,20.3%
Nat West,22789,13.81%,25234,15.28%,31567,19.1%
John Doe,15678,9.51%,12345,7.48%,0,0%
Jane Smith,12345,7.48%,0,0%,0,0%
"""

    def create_temp_csv(self, content):
        """Create a temporary CSV file with given content."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        temp_file.write(content)
        temp_file.close()
        return temp_file.name

    def test_parser_initialization(self):
        """Test parser initialization."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            parser = OfficialResultsParser(temp_file)
            assert parser.csv_path == Path(temp_file)
            assert parser.raw_data is None
            assert parser.metadata == {}
            assert parser.winners == []
        finally:
            os.unlink(temp_file)

    def test_metadata_parsing(self):
        """Test metadata extraction."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            parser = OfficialResultsParser(temp_file)
            results = parser.parse_results()

            metadata = results["metadata"]
            assert metadata["election_date"] == "Nov 05, 2024"
            assert metadata["report_date"] == "Nov 29, 2024"
            assert metadata["registered_voters"] == 123456
            assert metadata["threshold"] == 25000
        finally:
            os.unlink(temp_file)

    def test_winners_parsing(self):
        """Test winners extraction."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            parser = OfficialResultsParser(temp_file)
            results = parser.parse_results()

            winners = results["winners"]
            assert len(winners) == 3
            assert "Dan Ryan" in winners
            assert "Elana Pirtle-Guiney" in winners
            assert "Nat West" in winners
        finally:
            os.unlink(temp_file)

    def test_candidate_data_parsing(self):
        """Test candidate data extraction."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            parser = OfficialResultsParser(temp_file)
            results = parser.parse_results()

            final_results = results["final_results"]
            assert len(final_results) == 5

            # Check Dan Ryan's data
            dan_ryan = final_results[
                final_results["candidate_name"] == "Dan Ryan"
            ].iloc[0]
            assert dan_ryan["first_choice_votes"] == 25123
            assert dan_ryan["final_votes"] == 35678
            assert dan_ryan["is_winner"] is True

            # Check eliminated candidate
            jane_smith = final_results[
                final_results["candidate_name"] == "Jane Smith"
            ].iloc[0]
            assert jane_smith["first_choice_votes"] == 12345
            assert jane_smith["final_votes"] == 0
            assert jane_smith["is_winner"] is False
        finally:
            os.unlink(temp_file)

    def test_malformed_csv_handling(self):
        """Test handling of malformed CSV files."""
        malformed_content = """Some random content
Without proper structure
"""
        temp_file = self.create_temp_csv(malformed_content)
        try:
            parser = OfficialResultsParser(temp_file)
            with pytest.raises(ValueError, match="Could not find data section"):
                parser.parse_results()
        finally:
            os.unlink(temp_file)


class TestResultsVerifier:
    """Test results verification functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_csv_content = """Election Date,Nov 05, 2024
Report Date,Nov 29, 2024
Election,City of Portland - Councilor - District 2
Registered Voters in District,123456
Election Threshold,25000
,# votes,% of votes,# votes,% of votes,# votes,% of votes
Met threshold for election,Dan Ryan; Elana Pirtle-Guiney; Nat West
Defeated,All others

,# votes,% of votes,# votes,% of votes,# votes,% of votes
Dan Ryan,25123,15.23%,28456,17.25%,35678,21.6%
Elana Pirtle-Guiney,23456,14.21%,26789,16.23%,33445,20.3%
Nat West,22789,13.81%,25234,15.28%,31567,19.1%
John Doe,15678,9.51%,12345,7.48%,0,0%
Jane Smith,12345,7.48%,0,0%,0,0%
"""

        # Sample data for our results
        self.our_candidates = pd.DataFrame(
            {
                "candidate_id": [1, 2, 3, 4, 5],
                "candidate_name": [
                    "Dan Ryan",
                    "Elana Pirtle-Guiney",
                    "Nat West",
                    "John Doe",
                    "Jane Smith",
                ],
            }
        )

        self.our_first_choice = pd.DataFrame(
            {
                "candidate_name": [
                    "Dan Ryan",
                    "Elana Pirtle-Guiney",
                    "Nat West",
                    "John Doe",
                    "Jane Smith",
                ],
                "first_choice_votes": [25123, 23456, 22789, 15678, 12345],
            }
        )

    def create_temp_csv(self, content):
        """Create a temporary CSV file with given content."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        temp_file.write(content)
        temp_file.close()
        return temp_file.name

    def test_verifier_initialization(self):
        """Test verifier initialization."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            verifier = ResultsVerifier(temp_file)
            assert verifier.parser is not None
            assert verifier.official_data is None
        finally:
            os.unlink(temp_file)

    def test_load_official_results(self):
        """Test loading official results."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            verifier = ResultsVerifier(temp_file)
            official_data = verifier.load_official_results()

            assert "metadata" in official_data
            assert "winners" in official_data
            assert "final_results" in official_data
            assert len(official_data["winners"]) == 3
        finally:
            os.unlink(temp_file)

    def test_perfect_match_verification(self):
        """Test verification when results match perfectly."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            verifier = ResultsVerifier(temp_file)
            our_winners = [1, 2, 3]  # Dan Ryan, Elana Pirtle-Guiney, Nat West

            results = verifier.verify_results(
                our_winners, self.our_candidates, self.our_first_choice
            )

            assert results["winners_match"] is True
            assert results["verification_passed"] is True
            assert results["total_vote_difference"] == 0
            assert results["candidates_with_differences"] == 0
            assert len(results["missing_winners"]) == 0
            assert len(results["extra_winners"]) == 0
        finally:
            os.unlink(temp_file)

    def test_wrong_winners_verification(self):
        """Test verification when winners don't match."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            verifier = ResultsVerifier(temp_file)
            our_winners = [1, 2, 4]  # Dan Ryan, Elana Pirtle-Guiney, John Doe (wrong)

            results = verifier.verify_results(
                our_winners, self.our_candidates, self.our_first_choice
            )

            assert results["winners_match"] is False
            assert results["verification_passed"] is False
            assert len(results["missing_winners"]) == 1
            assert len(results["extra_winners"]) == 1
            assert "Nat West" in results["missing_winners"]
            assert "John Doe" in results["extra_winners"]
        finally:
            os.unlink(temp_file)

    def test_vote_count_discrepancy(self):
        """Test verification with vote count discrepancies."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            # Create first choice data with discrepancies
            our_first_choice_wrong = self.our_first_choice.copy()
            our_first_choice_wrong.loc[0, "first_choice_votes"] = 25000  # Off by 123

            verifier = ResultsVerifier(temp_file)
            our_winners = [1, 2, 3]

            results = verifier.verify_results(
                our_winners, self.our_candidates, our_first_choice_wrong
            )

            assert results["winners_match"] is True  # Winners still match
            assert results["verification_passed"] is False  # But vote counts don't
            assert results["total_vote_difference"] == 123
            assert results["candidates_with_differences"] == 1
        finally:
            os.unlink(temp_file)

    def test_name_normalization_in_verification(self):
        """Test that name normalization works in verification."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            # Create candidates with slight name variations
            our_candidates_normalized = pd.DataFrame(
                {
                    "candidate_id": [1, 2, 3, 4, 5],
                    "candidate_name": [
                        "Dan  Ryan",  # Extra space
                        "Elana Pirtle-Guiney",
                        "Nat West",
                        "John Doe",
                        "Jane Smith",
                    ],
                }
            )

            our_first_choice_normalized = pd.DataFrame(
                {
                    "candidate_name": [
                        "Dan  Ryan",  # Extra space
                        "Elana Pirtle-Guiney",
                        "Nat West",
                        "John Doe",
                        "Jane Smith",
                    ],
                    "first_choice_votes": [25123, 23456, 22789, 15678, 12345],
                }
            )

            verifier = ResultsVerifier(temp_file)
            our_winners = [1, 2, 3]

            results = verifier.verify_results(
                our_winners, our_candidates_normalized, our_first_choice_normalized
            )

            assert results["winners_match"] is True
            assert results["verification_passed"] is True
        finally:
            os.unlink(temp_file)

    def test_generate_verification_report(self):
        """Test verification report generation."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            verifier = ResultsVerifier(temp_file)
            our_winners = [1, 2, 3]

            results = verifier.verify_results(
                our_winners, self.our_candidates, self.our_first_choice
            )

            report = verifier.generate_verification_report(results)

            assert "ELECTION RESULTS VERIFICATION REPORT" in report
            assert "VERIFICATION PASSED" in report
            assert "Winners match official results" in report
            assert "Dan Ryan" in report
            assert "OFFICIAL ELECTION METADATA" in report
        finally:
            os.unlink(temp_file)

    def test_failed_verification_report(self):
        """Test verification report for failed verification."""
        temp_file = self.create_temp_csv(self.sample_csv_content)
        try:
            verifier = ResultsVerifier(temp_file)
            our_winners = [1, 2, 4]  # Wrong winners

            results = verifier.verify_results(
                our_winners, self.our_candidates, self.our_first_choice
            )

            report = verifier.generate_verification_report(results)

            assert "VERIFICATION FAILED" in report
            assert "Winners do not match" in report
            assert "Missing winners" in report
            assert "Extra winners" in report
        finally:
            os.unlink(temp_file)
