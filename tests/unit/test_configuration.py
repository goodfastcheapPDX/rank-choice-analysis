"""
Configuration and environment unit tests.

These tests verify that the project configuration is valid
and all required dependencies are available.
"""

import sys
from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.smoke
def test_python_version():
    """Test that Python version meets requirements."""
    assert sys.version_info >= (3, 9), f"Python 3.9+ required, got {sys.version_info}"


@pytest.mark.unit
@pytest.mark.smoke
def test_project_structure():
    """Test that essential project directories exist."""
    project_root = Path(__file__).parent.parent.parent

    # Essential directories
    assert (project_root / "src").exists(), "src directory missing"
    assert (project_root / "src" / "data").exists(), "src/data directory missing"
    assert (
        project_root / "src" / "analysis"
    ).exists(), "src/analysis directory missing"
    assert (project_root / "src" / "web").exists(), "src/web directory missing"
    assert (project_root / "scripts").exists(), "scripts directory missing"
    assert (project_root / "tests").exists(), "tests directory missing"


@pytest.mark.unit
@pytest.mark.smoke
def test_required_files():
    """Test that essential configuration files exist."""
    project_root = Path(__file__).parent.parent.parent

    # Configuration files
    assert (project_root / "pyproject.toml").exists(), "pyproject.toml missing"
    assert (project_root / "CLAUDE.md").exists(), "CLAUDE.md missing"
    assert (
        project_root / ".pre-commit-config.yaml"
    ).exists(), ".pre-commit-config.yaml missing"


@pytest.mark.unit
@pytest.mark.smoke
def test_core_dependencies():
    """Test that core dependencies can be imported."""
    try:
        import duckdb
        import fastapi
        import numpy
        import pandas
        import plotly
    except ImportError as e:
        pytest.fail(f"Core dependency import failed: {e}")


@pytest.mark.unit
@pytest.mark.smoke
def test_development_dependencies():
    """Test that development dependencies are available."""
    try:
        import black
        import isort
        import pytest
    except ImportError as e:
        pytest.fail(f"Development dependency import failed: {e}")


@pytest.mark.unit
def test_src_path_configuration():
    """Test that src path is properly configured for imports."""
    project_root = Path(__file__).parent.parent.parent
    src_path = str(project_root / "src")

    # Check if src is in path (added by conftest.py)
    assert src_path in sys.path or any(src_path in p for p in sys.path)
