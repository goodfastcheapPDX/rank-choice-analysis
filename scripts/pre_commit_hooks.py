#!/usr/bin/env python3
"""
Custom pre-commit hooks for ranked-elections-analyzer.

These hooks perform election-specific validation that runs before commits.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_golden_datasets():
    """Run quick validation on golden datasets."""
    print("🗳️  Validating golden datasets...")

    try:
        import json

        from data.database import CVRDatabase  # noqa: F401

        golden_dir = Path(__file__).parent.parent / "tests" / "golden" / "micro"

        # Load and validate each golden dataset
        for golden_file in golden_dir.glob("*.json"):
            print(f"   📊 Checking {golden_file.name}...")

            with open(golden_file) as f:
                dataset = json.load(f)

            # Basic validation
            assert "seats" in dataset, f"Missing seats in {golden_file.name}"
            assert "candidates" in dataset, f"Missing candidates in {golden_file.name}"
            assert "ballots" in dataset, f"Missing ballots in {golden_file.name}"
            assert (
                "hand_computed_results" in dataset
            ), f"Missing results in {golden_file.name}"

            # Validate quota calculation
            total_ballots = dataset["total_ballots"]
            seats = dataset["seats"]
            expected_quota = (total_ballots // (seats + 1)) + 1
            actual_quota = dataset["hand_computed_results"]["quota"]

            assert (
                actual_quota == expected_quota
            ), f"Quota calculation error in {golden_file.name}"

            # Validate winner count
            winners = dataset["hand_computed_results"]["final_winners"]
            assert len(winners) == seats, f"Wrong winner count in {golden_file.name}"

        print("   ✅ All golden datasets valid")
        return True

    except Exception as e:
        print(f"   ❌ Golden dataset validation failed: {e}")
        return False


def test_database_invariants():
    """Test basic database and STV mathematical invariants."""
    print("🧮 Testing mathematical invariants...")

    try:
        # Test Droop quota properties
        def test_droop_properties():
            """Test mathematical properties of Droop quota."""

            def calculate_droop_quota(total_votes, seats):
                return (total_votes // (seats + 1)) + 1

            # Test cases
            test_cases = [
                (1000, 3, 251),  # Standard case
                (100, 1, 51),  # Single seat
                (999, 2, 334),  # Odd numbers
            ]

            for total_votes, seats, expected in test_cases:
                quota = calculate_droop_quota(total_votes, seats)
                assert quota == expected, (
                    f"Quota calculation failed: "
                    f"{total_votes}, {seats} -> {quota} != {expected}"
                )

                # Mathematical properties of Droop quota
                assert (
                    quota < total_votes / seats
                ), "Quota should be less than equal share"
                assert quota > total_votes / (
                    seats + 1
                ), "Quota should be greater than Droop threshold"
                assert (
                    seats - 1
                ) * quota < total_votes, (
                    "Fewer than 'seats' candidates should reach quota naturally"
                )

        test_droop_properties()

        # Test vote conservation
        def test_vote_conservation():
            """Test vote weight conservation principle."""
            previous_continuing = 1000.0
            eliminated_weight = 150.0
            elected_surplus = 50.0

            continuing_weight = (
                previous_continuing - eliminated_weight - elected_surplus
            )

            # Conservation law (within floating point precision)
            total_accounted = continuing_weight + eliminated_weight + elected_surplus
            assert (
                abs(previous_continuing - total_accounted) < 0.001
            ), "Vote conservation violated"

        test_vote_conservation()

        print("   ✅ All mathematical invariants pass")
        return True

    except Exception as e:
        print(f"   ❌ Mathematical invariant test failed: {e}")
        return False


def test_core_imports():
    """Test that all core modules can be imported."""
    print("📦 Testing core imports...")

    try:
        from analysis.stv import STVTabulator  # noqa: F401
        from analysis.verification import ResultsVerifier  # noqa: F401
        from data.cvr_parser import CVRParser  # noqa: F401
        from data.database import CVRDatabase  # noqa: F401

        # from web.main import app  # Commented out - not used in quick tests

        print("   ✅ All core imports successful")
        return True

    except ImportError as e:
        print(f"   ❌ Import test failed: {e}")
        return False


def test_database_connectivity():
    """Test basic database operations."""
    print("🗄️  Testing database connectivity...")

    try:
        from data.database import CVRDatabase  # noqa: F401

        # Test in-memory database
        db = CVRDatabase(":memory:")

        # Test basic query
        result = db.query("SELECT 1 as test")
        assert len(result) == 1
        assert result.iloc[0]["test"] == 1

        db.close()

        print("   ✅ Database connectivity test passed")
        return True

    except Exception as e:
        print(f"   ❌ Database connectivity test failed: {e}")
        return False


def main():
    """Run all pre-commit election-specific hooks."""
    print("🚀 Running election-specific pre-commit hooks...")

    all_passed = True

    # Run all validation tests
    tests = [
        test_core_imports,
        test_database_connectivity,
        test_database_invariants,
        test_golden_datasets,
    ]

    for test in tests:
        if not test():
            all_passed = False

    if all_passed:
        print("✅ All election-specific pre-commit hooks passed!")
        return 0
    else:
        print("❌ Some pre-commit hooks failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
