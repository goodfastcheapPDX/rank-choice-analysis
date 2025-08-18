"""
Basic database functionality unit tests.

These tests verify core database operations without requiring
external data files or complex setups.
"""

import pandas as pd
import pytest


@pytest.mark.unit
def test_database_creation(temp_db):
    """Test that database can be created and closed."""
    assert temp_db is not None
    assert temp_db.conn is not None


@pytest.mark.unit
def test_basic_query(temp_db):
    """Test basic SQL query execution."""
    result = temp_db.query("SELECT 1 as test_value")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["test_value"] == 1


@pytest.mark.unit
def test_table_creation(temp_db):
    """Test creating a simple table."""
    temp_db.conn.execute(
        """
        CREATE TABLE test_table (
            id INTEGER,
            name TEXT
        )
    """
    )

    # Insert test data
    temp_db.conn.execute("INSERT INTO test_table VALUES (1, 'test')")

    # Query the data
    result = temp_db.query("SELECT * FROM test_table")
    assert len(result) == 1
    assert result.iloc[0]["id"] == 1
    assert result.iloc[0]["name"] == "test"


@pytest.mark.unit
def test_candidates_table_schema(temp_db):
    """Test creating candidates table with correct schema."""
    temp_db.conn.execute(
        """
        CREATE TABLE candidates (
            candidate_id INTEGER,
            candidate_name TEXT,
            rank_columns INTEGER
        )
    """
    )

    # Test table exists
    tables = temp_db.query("SELECT name FROM sqlite_master WHERE type='table'")
    assert "candidates" in tables["name"].values


@pytest.mark.unit
def test_ballots_long_table_schema(temp_db):
    """Test creating ballots_long table with correct schema."""
    temp_db.conn.execute(
        """
        CREATE TABLE ballots_long (
            BallotID TEXT,
            PrecinctID INTEGER,
            candidate_id INTEGER,
            rank INTEGER
        )
    """
    )

    # Test table exists
    tables = temp_db.query("SELECT name FROM sqlite_master WHERE type='table'")
    assert "ballots_long" in tables["name"].values
