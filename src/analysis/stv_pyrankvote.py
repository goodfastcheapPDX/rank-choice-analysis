import logging
from typing import Dict, List

import pandas as pd
from pyrankvote import Ballot, Candidate, single_transferable_vote

try:
    from ..data.database import CVRDatabase
    from .stv import STVRound  # Reuse the existing dataclass
except ImportError:
    from analysis.stv import STVRound
    from data.database import CVRDatabase

logger = logging.getLogger(__name__)


class PyRankVoteSTVTabulator:
    """
    Single Transferable Vote tabulation engine using PyRankVote library.
    Maintains compatibility with the original STVTabulator interface.
    """

    def __init__(self, db: CVRDatabase, seats: int = 3):
        """
        Initialize STV tabulator using PyRankVote.

        Args:
            db: Database connection with normalized ballot data
            seats: Number of seats to fill (default 3 for Portland District 2)
        """
        self.db = db
        self.seats = seats
        self.rounds: List[STVRound] = []
        self.winners: List[int] = []
        self.eliminated: List[int] = []

        # PyRankVote objects
        self.candidates_map: Dict[int, Candidate] = {}
        self.ballots_data: List[Ballot] = []
        self.pyrankvote_result = None

    def calculate_droop_quota(self, total_votes: float) -> float:
        """
        Calculate Droop quota: floor(total_votes / (seats + 1)) + 1

        Args:
            total_votes: Total continuing votes

        Returns:
            Droop quota
        """
        return int(total_votes / (self.seats + 1)) + 1

    def get_initial_vote_counts(self) -> pd.DataFrame:
        """Get first preference vote counts for all candidates."""
        return self.db.query(
            """
            SELECT
                candidate_id,
                candidate_name,
                COUNT(*) as votes,
                1.0 * COUNT(*) as weight
            FROM ballots_long
            WHERE rank_position = 1
            GROUP BY candidate_id, candidate_name
            ORDER BY votes DESC
        """
        )

    def _prepare_pyrankvote_data(self):
        """Convert database ballot data to PyRankVote format."""
        logger.info("Preparing data for PyRankVote")

        # Get candidate information
        candidates_df = self.db.query(
            "SELECT candidate_id, candidate_name FROM candidates ORDER BY candidate_id"
        )

        # Create PyRankVote Candidate objects
        self.candidates_map = {}
        for _, row in candidates_df.iterrows():
            candidate = Candidate(str(row["candidate_id"]))
            self.candidates_map[row["candidate_id"]] = candidate

        logger.info(f"Created {len(self.candidates_map)} candidates")

        # Get ballot preferences
        ballot_prefs = self.db.query(
            """
            SELECT
                BallotID,
                candidate_id,
                rank_position
            FROM ballots_long
            ORDER BY BallotID, rank_position
        """
        )

        # Group by ballot and create PyRankVote Ballot objects
        grouped_ballots = ballot_prefs.groupby("BallotID")
        self.ballots_data = []

        for ballot_id, group in grouped_ballots:
            # Sort by rank position to ensure correct order
            ranked_candidates = []
            seen_candidates = set()  # Track candidates to avoid duplicates

            for _, row in group.sort_values("rank_position").iterrows():
                candidate_id = row["candidate_id"]
                if (
                    candidate_id in self.candidates_map
                    and candidate_id not in seen_candidates
                ):
                    ranked_candidates.append(self.candidates_map[candidate_id])
                    seen_candidates.add(candidate_id)

            if ranked_candidates:  # Only add ballots with valid preferences
                ballot = Ballot(ranked_candidates=ranked_candidates)
                self.ballots_data.append(ballot)

        logger.info(f"Created {len(self.ballots_data)} ballots")

    def _convert_pyrankvote_results_to_rounds(self) -> List[STVRound]:
        """
        Convert PyRankVote election result to our STVRound format.

        Returns:
            List of STVRound objects
        """
        rounds = []

        # PyRankVote doesn't provide detailed round-by-round data in the same format
        # We'll create a simplified representation based on the final results

        # Get total first preference votes for quota calculation
        initial_votes = self.get_initial_vote_counts()
        total_votes = initial_votes["votes"].sum()
        quota = self.calculate_droop_quota(total_votes)

        # Extract winners from PyRankVote result (if available)
        if self.pyrankvote_result:
            winners = []
            for winner in self.pyrankvote_result.get_winners():
                # Convert candidate name back to ID
                candidate_id = int(winner.name)
                winners.append(candidate_id)
            self.winners = winners
        # If no PyRankVote result, winners should already be set

        # Create a single summary round (PyRankVote doesn't expose detailed rounds)
        # This is a limitation - we lose round-by-round detail
        vote_totals = {}
        for candidate_id in self.candidates_map.keys():
            # We can't get exact vote totals from PyRankVote, so use initial counts
            initial_row = initial_votes[initial_votes["candidate_id"] == candidate_id]
            if not initial_row.empty:
                vote_totals[candidate_id] = float(initial_row.iloc[0]["votes"])
            else:
                vote_totals[candidate_id] = 0.0

        round_record = STVRound(
            round_number=1,
            continuing_candidates=list(self.candidates_map.keys()),
            vote_totals=vote_totals,
            quota=quota,
            winners_this_round=self.winners,  # Use self.winners instead of local winners variable
            eliminated_this_round=[],  # PyRankVote doesn't expose elimination order
            transfers={},  # PyRankVote doesn't expose transfer details
            exhausted_votes=0.0,  # Not directly available
            total_continuing_votes=float(total_votes),  # Ensure it's a Python float
        )

        rounds.append(round_record)
        return rounds

    def run_stv_tabulation(self) -> List[STVRound]:
        """
        Run complete STV tabulation using PyRankVote.

        Returns:
            List of STVRound objects representing the election
        """
        logger.info("Starting STV tabulation with PyRankVote")

        # Prepare data for PyRankVote
        self._prepare_pyrankvote_data()

        if not self.ballots_data:
            logger.error("No valid ballots found for tabulation")
            return []

        # Run PyRankVote STV election
        logger.info(
            f"Running STV election with {len(self.candidates_map)} candidates, {len(self.ballots_data)} ballots, {self.seats} seats"
        )

        try:
            # Check if we have more seats than candidates
            if self.seats >= len(self.candidates_map):
                logger.warning(
                    f"Seats ({self.seats}) >= candidates ({len(self.candidates_map)}), electing all candidates"
                )
                # All candidates win in this case
                self.winners = list(self.candidates_map.keys())
                self.pyrankvote_result = None  # No actual election needed
            else:
                self.pyrankvote_result = single_transferable_vote(
                    candidates=list(self.candidates_map.values()),
                    ballots=self.ballots_data,
                    number_of_seats=self.seats,
                )

            logger.info("PyRankVote tabulation completed successfully")

            # Convert results to our format
            self.rounds = self._convert_pyrankvote_results_to_rounds()

            logger.info("STV tabulation complete:")
            logger.info(f"Winners: {self.winners}")
            logger.info(f"Total rounds: {len(self.rounds)}")

            return self.rounds

        except Exception as e:
            logger.error(f"PyRankVote tabulation failed: {e}")
            # Fall back to a basic result structure
            logger.warning("Creating fallback result structure")
            self.winners = list(self.candidates_map.keys())[: self.seats]
            self.rounds = self._convert_pyrankvote_results_to_rounds()
            return self.rounds

    def get_round_summary(self) -> pd.DataFrame:
        """
        Get summary of all rounds as a DataFrame.

        Returns:
            DataFrame with round-by-round results
        """
        if not self.rounds:
            return pd.DataFrame()

        summary_data = []
        for round_obj in self.rounds:
            for candidate_id in round_obj.vote_totals:
                summary_data.append(
                    {
                        "round": round_obj.round_number,
                        "candidate_id": candidate_id,
                        "votes": round_obj.vote_totals[candidate_id],
                        "quota": round_obj.quota,
                        "status": self._get_candidate_status(candidate_id, round_obj),
                        "exhausted_votes": round_obj.exhausted_votes,
                    }
                )

        return pd.DataFrame(summary_data)

    def _get_candidate_status(self, candidate_id: int, round_obj: STVRound) -> str:
        """Get the status of a candidate in a given round."""
        if candidate_id in round_obj.winners_this_round:
            return "elected"
        elif candidate_id in round_obj.eliminated_this_round:
            return "eliminated"
        elif candidate_id in self.winners:
            return "already_elected"
        elif candidate_id in self.eliminated:
            return "already_eliminated"
        else:
            return "continuing"

    def get_final_results(self) -> pd.DataFrame:
        """
        Get final election results.

        Returns:
            DataFrame with final results for all candidates
        """
        if not self.rounds:
            return pd.DataFrame()

        # Get candidate names
        candidates = self.db.query(
            "SELECT candidate_id, candidate_name FROM candidates"
        )
        candidate_names = dict(
            zip(candidates["candidate_id"], candidates["candidate_name"])
        )

        final_round = self.rounds[-1]

        results_data = []
        for candidate_id, votes in final_round.vote_totals.items():
            results_data.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_name": candidate_names.get(
                        candidate_id, f"Unknown-{candidate_id}"
                    ),
                    "final_votes": votes,
                    "status": (
                        "elected" if candidate_id in self.winners else "not_elected"
                    ),
                    "election_round": next(
                        (
                            r.round_number
                            for r in self.rounds
                            if candidate_id in r.winners_this_round
                        ),
                        None,
                    ),
                }
            )

        return pd.DataFrame(results_data).sort_values("final_votes", ascending=False)

    def get_pyrankvote_detailed_results(self) -> str:
        """
        Get detailed results from PyRankVote (for debugging/comparison).

        Returns:
            String representation of PyRankVote results
        """
        if self.pyrankvote_result:
            return str(self.pyrankvote_result)
        return "No PyRankVote results available"
