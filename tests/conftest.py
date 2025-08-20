"""
Shared pytest configuration and fixtures for ranked-elections-analyzer.

This module provides common test fixtures and utilities used across
all test modules.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.database import CVRDatabase  # noqa: E402


@pytest.fixture
def temp_db():
    """Provide a temporary in-memory database for testing."""
    db = CVRDatabase(":memory:")
    yield db
    db.close()


@pytest.fixture
def temp_db_file():
    """Provide a temporary database file for testing."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)  # Close file descriptor, keep path

    try:
        yield db_path
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
def sample_candidates():
    """Provide sample candidate data for testing."""
    return [
        {"candidate_id": 1, "candidate_name": "Alice", "rank_columns": 3},
        {"candidate_id": 2, "candidate_name": "Bob", "rank_columns": 3},
        {"candidate_id": 3, "candidate_name": "Charlie", "rank_columns": 3},
        {"candidate_id": 4, "candidate_name": "Diana", "rank_columns": 3},
    ]


@pytest.fixture
def sample_ballots():
    """Provide sample ballot data for testing."""
    return [
        # Ballot 1: Alice=1, Bob=2, Charlie=3
        {"BallotID": "B001", "PrecinctID": 1, "candidate_id": 1, "rank": 1},
        {"BallotID": "B001", "PrecinctID": 1, "candidate_id": 2, "rank": 2},
        {"BallotID": "B001", "PrecinctID": 1, "candidate_id": 3, "rank": 3},
        # Ballot 2: Bob=1, Alice=2
        {"BallotID": "B002", "PrecinctID": 1, "candidate_id": 2, "rank": 1},
        {"BallotID": "B002", "PrecinctID": 1, "candidate_id": 1, "rank": 2},
        # Ballot 3: Charlie=1, Diana=2, Alice=3
        {"BallotID": "B003", "PrecinctID": 2, "candidate_id": 3, "rank": 1},
        {"BallotID": "B003", "PrecinctID": 2, "candidate_id": 4, "rank": 2},
        {"BallotID": "B003", "PrecinctID": 2, "candidate_id": 1, "rank": 3},
    ]


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, no external dependencies)"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (medium speed, database required)",
    )
    config.addinivalue_line(
        "markers",
        "golden: marks tests as golden dataset validation (slow, full verification)",
    )
    config.addinivalue_line(
        "markers", "invariant: marks tests as mathematical invariant validation"
    )
    config.addinivalue_line(
        "markers", "smoke: marks tests as smoke tests (basic functionality check)"
    )
