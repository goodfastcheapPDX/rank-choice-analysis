"""
Analysis module for ranked-choice voting election analysis.

This module provides STV (Single Transferable Vote) tabulation implementations:
- PyRankVoteSTVTabulator: Production implementation using PyRankVote library (default)
- OriginalSTVTabulator: Custom implementation for detailed round analysis

The default STVTabulator uses PyRankVote for industry-standard reliability.
"""

# Import shared data structures
# Keep original implementation available for comparison/testing
from .stv import STVRound
from .stv import STVTabulator as OriginalSTVTabulator

# Import the PyRankVote implementation as the default
from .stv_pyrankvote import PyRankVoteSTVTabulator as STVTabulator

# Import verification utilities
from .verification import ResultsVerifier

__all__ = [
    "STVTabulator",  # Default: PyRankVote implementation
    "OriginalSTVTabulator",  # Original custom implementation
    "STVRound",  # Shared data structure
    "ResultsVerifier",  # Verification utilities
]
