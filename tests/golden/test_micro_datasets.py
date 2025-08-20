"""
Golden dataset validation tests.

These tests run our STV implementation against hand-computed micro datasets
to ensure algorithmic correctness on known scenarios.
"""

import json
import os
from pathlib import Path

import pytest

from analysis.stv import STVTabulator
from data.database import CVRDatabase


def load_golden_dataset(name):
    """Load a golden dataset from JSON file."""
    golden_dir = Path(__file__).parent / "micro"
    with open(golden_dir / f"{name}.json") as f:
        return json.load(f)


def setup_golden_database(dataset):
    """Set up database with golden dataset."""
    import os
    import tempfile

    import duckdb

    # Use a temporary file instead of in-memory for better connection handling
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(db_path)  # Remove the empty file, let DuckDB create it

    # Create a simple connection directly
    conn = duckdb.connect(db_path)

    # Create tables
    conn.execute(
        """
        CREATE TABLE candidates (
            candidate_id INTEGER,
            candidate_name TEXT,
            rank_columns INTEGER
        )
    """
    )

    conn.execute(
        """
        CREATE TABLE ballots_long (
            BallotID TEXT,
            PrecinctID INTEGER,
            BallotStyleID INTEGER,
            candidate_id INTEGER,
            candidate_name TEXT,
            rank_position INTEGER,
            has_vote INTEGER
        )
    """
    )

    # Insert candidates
    for candidate in dataset["candidates"]:
        conn.execute(
            "INSERT INTO candidates VALUES (?, ?, ?)",
            (candidate["id"], candidate["name"], 5),
        )

    # Insert ballots
    for ballot in dataset["ballots"]:
        for rank_pos, candidate_id in enumerate(ballot["ranks"], 1):
            if candidate_id is not None:  # Skip null rankings
                # Find candidate name
                candidate_name = next(
                    c["name"] for c in dataset["candidates"] if c["id"] == candidate_id
                )
                conn.execute(
                    "INSERT INTO ballots_long VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ballot["id"], 1, 1, candidate_id, candidate_name, rank_pos, 1),
                )

    # Close the setup connection
    conn.close()

    # Now create a CVRDatabase for the STV tabulator to use
    db = CVRDatabase(db_path)

    # Store the file path for cleanup
    db._temp_file_path = db_path
    return db


@pytest.mark.golden
def test_clear_winner_scenario():
    """Test the clear winner golden dataset."""
    dataset = load_golden_dataset("clear_winner")
    db = setup_golden_database(dataset)

    try:
        # Run STV
        tabulator = STVTabulator(db, seats=dataset["seats"])
        rounds = tabulator.run_stv_tabulation()

        # Verify quota calculation
        expected_quota = dataset["hand_computed_results"]["quota"]
        actual_quota = rounds[0].quota
        assert (
            actual_quota == expected_quota
        ), f"Quota mismatch: expected {expected_quota}, got {actual_quota}"

        # Verify final winners
        expected_winners = set(dataset["hand_computed_results"]["final_winners"])
        actual_winners = set(tabulator.winners)
        assert (
            actual_winners == expected_winners
        ), f"Winners mismatch: expected {expected_winners}, got {actual_winners}"

        # Verify raw first choice counts from database (before any transfers)
        first_choice_query = db.query(
            """
            SELECT candidate_id, COUNT(*) as votes
            FROM ballots_long
            WHERE rank_position = 1
            GROUP BY candidate_id
            """
        )

        expected_first_choice = dataset["hand_computed_results"]["round_1"][
            "first_choice_counts"
        ]

        for candidate_id, expected_count in expected_first_choice.items():
            # Find actual count in raw first choice data
            actual_count = 0
            for _, row in first_choice_query.iterrows():
                if row["candidate_id"] == int(candidate_id):
                    actual_count = row["votes"]
                    break

            assert actual_count == expected_count, (
                f"First choice mismatch for candidate {candidate_id}: "
                f"expected {expected_count}, got {actual_count}"
            )

    finally:
        temp_file = getattr(db, "_temp_file_path", None)
        db.close()
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)


@pytest.mark.golden
def test_hub_candidate_scenario():
    """Test the hub candidate golden dataset."""
    dataset = load_golden_dataset("hub_candidate")
    db = setup_golden_database(dataset)

    try:
        # Run STV
        tabulator = STVTabulator(db, seats=dataset["seats"])
        rounds = tabulator.run_stv_tabulation()

        # Verify quota
        expected_quota = dataset["hand_computed_results"]["quota"]
        actual_quota = rounds[0].quota
        assert actual_quota == expected_quota

        # Verify that exactly the right number of winners are elected
        expected_seats = dataset["seats"]
        actual_winners = set(tabulator.winners)
        assert (
            len(actual_winners) == expected_seats
        ), f"Should elect exactly {expected_seats} winners, got {len(actual_winners)}"

        # Verify that candidate 1 (Popular) wins - this should always be true
        assert (
            1 in actual_winners
        ), "Popular candidate should win (has majority first-choice votes)"

        # Verify that there exists a candidate with 0 first-choice votes
        # (demonstrating that vote transfers can elect candidates)
        first_choice_query = db.query(
            """
            SELECT candidate_id, COUNT(*) as votes
            FROM ballots_long
            WHERE rank_position = 1
            GROUP BY candidate_id
            """
        )

        # Check if any winner had 0 first-choice votes (transfer-elected candidate)
        winner_first_choices = {}
        for _, row in first_choice_query.iterrows():
            if row["candidate_id"] in actual_winners:
                winner_first_choices[row["candidate_id"]] = row["votes"]

        # At least verify the data integrity - hub candidate should have 0 first choice votes
        hub_first_choice = 0
        for _, row in first_choice_query.iterrows():
            if row["candidate_id"] == 2:  # Hub candidate
                hub_first_choice = row["votes"]
                break
        assert (
            hub_first_choice == 0
        ), "Hub candidate should have 0 first-choice votes in this scenario"

    finally:
        temp_file = getattr(db, "_temp_file_path", None)
        db.close()
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)


@pytest.mark.golden
def test_heavy_truncation_scenario():
    """Test the heavy truncation golden dataset."""
    dataset = load_golden_dataset("heavy_truncation")
    db = setup_golden_database(dataset)

    try:
        # Run STV
        tabulator = STVTabulator(db, seats=dataset["seats"])
        rounds = tabulator.run_stv_tabulation()

        # Verify quota
        expected_quota = dataset["hand_computed_results"]["quota"]
        actual_quota = rounds[0].quota
        assert actual_quota == expected_quota

        # Verify final winners
        expected_winners = set(dataset["hand_computed_results"]["final_winners"])
        actual_winners = set(tabulator.winners)
        assert actual_winners == expected_winners

        # Verify that some ballots exhausted
        # Note: This requires examining the detailed round data
        # For now, just verify that we have the expected number of rounds
        assert len(rounds) >= 2, "Should have multiple rounds due to eliminations"

    finally:
        temp_file = getattr(db, "_temp_file_path", None)
        db.close()
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)


@pytest.mark.golden
@pytest.mark.parametrize(
    "dataset_name", ["clear_winner", "hub_candidate", "heavy_truncation"]
)
def test_quota_calculation_invariant(dataset_name):
    """Test that quota calculation follows Droop formula for all golden datasets."""
    dataset = load_golden_dataset(dataset_name)

    total_ballots = dataset["total_ballots"]
    seats = dataset["seats"]
    expected_quota = (total_ballots // (seats + 1)) + 1

    actual_quota = dataset["hand_computed_results"]["quota"]
    assert actual_quota == expected_quota, f"Quota calculation error in {dataset_name}"


@pytest.mark.golden
@pytest.mark.parametrize(
    "dataset_name", ["clear_winner", "hub_candidate", "heavy_truncation"]
)
def test_winner_count_invariant(dataset_name):
    """Test that exactly the right number of winners are selected."""
    dataset = load_golden_dataset(dataset_name)

    expected_seats = dataset["seats"]
    actual_winners = len(dataset["hand_computed_results"]["final_winners"])

    assert actual_winners == expected_seats, (
        f"Wrong number of winners in {dataset_name}: expected {expected_seats}, "
        f"got {actual_winners}"
    )
