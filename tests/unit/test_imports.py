"""
Test basic imports and module structure.

These tests ensure all core modules can be imported without errors
and basic functionality is available.
"""

import pytest


@pytest.mark.unit
@pytest.mark.smoke
def test_database_import():
    """Test that database module imports successfully."""
    from data.database import CVRDatabase

    assert CVRDatabase is not None


@pytest.mark.unit
@pytest.mark.smoke
def test_cvr_parser_import():
    """Test that CVR parser module imports successfully."""
    from data.cvr_parser import CVRParser

    assert CVRParser is not None


@pytest.mark.unit
@pytest.mark.smoke
def test_stv_import():
    """Test that STV module imports successfully."""
    from analysis.stv import STVTabulator

    assert STVTabulator is not None


@pytest.mark.unit
@pytest.mark.smoke
def test_verification_import():
    """Test that verification module imports successfully."""
    from analysis.verification import ResultsVerifier

    assert ResultsVerifier is not None


@pytest.mark.unit
@pytest.mark.smoke
def test_coalition_import():
    """Test that coalition analysis module imports successfully."""
    from analysis.coalition import CoalitionAnalyzer

    assert CoalitionAnalyzer is not None


@pytest.mark.unit
@pytest.mark.smoke
def test_web_main_import():
    """Test that web application module imports successfully."""
    from web.main import app

    assert app is not None
