"""
Golden dataset validation tests.

These tests run our STV implementation against hand-computed micro datasets
to ensure algorithmic correctness on known scenarios.
"""

import json
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
    db = CVRDatabase(":memory:")

    # Create tables
    db.conn.execute(
        """
        CREATE TABLE candidates (
            candidate_id INTEGER,
            candidate_name TEXT,
            rank_columns INTEGER
        )
    """
    )

    db.conn.execute(
        """
        CREATE TABLE ballots_long (
            BallotID TEXT,
            PrecinctID INTEGER,
            candidate_id INTEGER,
            rank INTEGER
        )
    """
    )

    # Insert candidates
    for candidate in dataset["candidates"]:
        db.conn.execute(
            "INSERT INTO candidates VALUES (?, ?, ?)",
            (candidate["id"], candidate["name"], 5),
        )

    # Insert ballots
    for ballot in dataset["ballots"]:
        for rank_pos, candidate_id in enumerate(ballot["ranks"], 1):
            if candidate_id is not None:  # Skip null rankings
                db.conn.execute(
                    "INSERT INTO ballots_long VALUES (?, ?, ?, ?)",
                    (ballot["id"], 1, candidate_id, rank_pos),
                )

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

        # Verify first round first choice counts
        expected_first_choice = dataset["hand_computed_results"]["round_1"][
            "first_choice_counts"
        ]

        for candidate_id, expected_count in expected_first_choice.items():
            # Find actual count in round 1 data
            candidate_votes = rounds[0].candidate_votes.get(int(candidate_id), 0)
            assert (
                candidate_votes == expected_count
            ), f"First choice mismatch for candidate {candidate_id}: expected {expected_count}, got {candidate_votes}"

    finally:
        db.close()


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

        # Verify final winners
        expected_winners = set(dataset["hand_computed_results"]["final_winners"])
        actual_winners = set(tabulator.winners)
        assert actual_winners == expected_winners

        # Verify that candidate 2 (Hub) won despite 0 first-choice votes
        expected_first_choice = dataset["hand_computed_results"]["round_1"][
            "first_choice_counts"
        ]
        hub_first_choice = rounds[0].candidate_votes.get(2, 0)
        assert hub_first_choice == 0, "Hub candidate should have 0 first-choice votes"
        assert (
            2 in tabulator.winners
        ), "Hub candidate should still win through transfers"

    finally:
        db.close()


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
        db.close()


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

    assert (
        actual_winners == expected_seats
    ), f"Wrong number of winners in {dataset_name}: expected {expected_seats}, got {actual_winners}"
