import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass
import logging
try:
    from ..data.database import CVRDatabase
except ImportError:
    from data.database import CVRDatabase

logger = logging.getLogger(__name__)


@dataclass
class STVRound:
    """Represents one round of STV tabulation."""
    round_number: int
    continuing_candidates: List[int]
    vote_totals: Dict[int, float]
    quota: float
    winners_this_round: List[int]
    eliminated_this_round: List[int]
    transfers: Dict[int, Dict[int, float]]  # from_candidate -> {to_candidate: weight}
    exhausted_votes: float
    total_continuing_votes: float


class STVTabulator:
    """
    Single Transferable Vote tabulation engine.
    Implements multi-winner RCV using the Droop quota.
    """
    
    def __init__(self, db: CVRDatabase, seats: int = 3):
        """
        Initialize STV tabulator.
        
        Args:
            db: Database connection with normalized ballot data
            seats: Number of seats to fill (default 3 for Portland District 2)
        """
        self.db = db
        self.seats = seats
        self.rounds: List[STVRound] = []
        self.winners: List[int] = []
        self.eliminated: List[int] = []
        
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
        return self.db.query("""
            SELECT 
                candidate_id,
                candidate_name,
                COUNT(*) as votes,
                1.0 * COUNT(*) as weight
            FROM ballots_long 
            WHERE rank_position = 1
            GROUP BY candidate_id, candidate_name
            ORDER BY votes DESC
        """)
        
    def get_ballot_preferences(self) -> pd.DataFrame:
        """
        Get all ballot preferences in order for transfer calculations.
        
        Returns:
            DataFrame with BallotID, candidate_id, rank_position
        """
        return self.db.query("""
            SELECT 
                BallotID,
                candidate_id,
                rank_position
            FROM ballots_long
            ORDER BY BallotID, rank_position
        """)
        
    def calculate_transfers(self, 
                          from_candidate: int, 
                          transfer_value: float,
                          continuing_candidates: List[int]) -> Dict[int, float]:
        """
        Calculate vote transfers from an eliminated or surplus candidate.
        
        Args:
            from_candidate: Candidate being eliminated or having surplus
            transfer_value: Value of each vote being transferred (1.0 for elimination, <1.0 for surplus)
            continuing_candidates: List of candidates still in the race
            
        Returns:
            Dictionary mapping candidate_id to transferred votes
        """
        # Get all ballots that have the from_candidate at any rank
        ballots_query = f"""
            WITH candidate_ballots AS (
                SELECT DISTINCT BallotID
                FROM ballots_long
                WHERE candidate_id = {from_candidate}
            ),
            ballot_preferences AS (
                SELECT 
                    bl.BallotID,
                    bl.candidate_id,
                    bl.rank_position,
                    ROW_NUMBER() OVER (PARTITION BY bl.BallotID ORDER BY bl.rank_position) as pref_order
                FROM ballots_long bl
                WHERE bl.BallotID IN (SELECT BallotID FROM candidate_ballots)
                  AND bl.candidate_id IN ({','.join(map(str, continuing_candidates))})
                ORDER BY bl.BallotID, bl.rank_position
            )
            SELECT 
                BallotID,
                candidate_id,
                rank_position
            FROM ballot_preferences
            WHERE pref_order = 1  -- Next continuing preference
        """
        
        transfer_df = self.db.query(ballots_query)
        
        # Count transfers to each candidate
        transfers = {}
        for candidate_id in continuing_candidates:
            count = len(transfer_df[transfer_df['candidate_id'] == candidate_id])
            if count > 0:
                transfers[candidate_id] = count * transfer_value
                
        return transfers
        
    def run_stv_tabulation(self) -> List[STVRound]:
        """
        Run complete STV tabulation.
        
        Returns:
            List of STVRound objects representing each round
        """
        logger.info("Starting STV tabulation")
        
        # Get initial vote counts
        initial_votes = self.get_initial_vote_counts()
        total_votes = initial_votes['votes'].sum()
        quota = self.calculate_droop_quota(total_votes)
        
        logger.info(f"Total first preference votes: {total_votes}")
        logger.info(f"Droop quota: {quota}")
        logger.info(f"Seats to fill: {self.seats}")
        
        # Initialize continuing candidates
        continuing = list(initial_votes['candidate_id'])
        vote_totals = dict(zip(initial_votes['candidate_id'], initial_votes['weight']))
        
        round_num = 1
        
        while len(self.winners) < self.seats and len(continuing) > 0:
            logger.info(f"\n=== Round {round_num} ===")
            
            # Check for winners (candidates meeting quota)
            round_winners = []
            for candidate_id in continuing:
                if vote_totals[candidate_id] >= quota:
                    round_winners.append(candidate_id)
                    self.winners.append(candidate_id)
                    logger.info(f"Candidate {candidate_id} elected with {vote_totals[candidate_id]:.1f} votes")
            
            # Remove winners from continuing candidates
            for winner in round_winners:
                continuing.remove(winner)
            
            # Calculate transfers from surplus votes
            transfers = {}
            for winner in round_winners:
                if vote_totals[winner] > quota:
                    surplus = vote_totals[winner] - quota
                    transfer_value = surplus / vote_totals[winner]
                    
                    logger.info(f"Transferring surplus from candidate {winner}: {surplus:.1f} votes at value {transfer_value:.3f}")
                    
                    winner_transfers = self.calculate_transfers(winner, transfer_value, continuing)
                    transfers[winner] = winner_transfers
                    
                    # Apply transfers
                    for to_candidate, transfer_amount in winner_transfers.items():
                        vote_totals[to_candidate] += transfer_amount
                        logger.info(f"  -> {transfer_amount:.1f} votes to candidate {to_candidate}")
            
            # If no winners and we still have seats to fill, eliminate lowest candidate
            round_eliminated = []
            if len(round_winners) == 0 and len(self.winners) < self.seats and len(continuing) > 0:
                # Find candidate with lowest vote total
                min_votes = min(vote_totals[c] for c in continuing)
                lowest_candidate = next(c for c in continuing if vote_totals[c] == min_votes)
                
                round_eliminated.append(lowest_candidate)
                self.eliminated.append(lowest_candidate)
                continuing.remove(lowest_candidate)
                
                logger.info(f"Eliminating candidate {lowest_candidate} with {vote_totals[lowest_candidate]:.1f} votes")
                
                # Transfer eliminated candidate's votes at full value
                eliminated_transfers = self.calculate_transfers(lowest_candidate, 1.0, continuing)
                transfers[lowest_candidate] = eliminated_transfers
                
                # Apply transfers
                for to_candidate, transfer_amount in eliminated_transfers.items():
                    vote_totals[to_candidate] += transfer_amount
                    logger.info(f"  -> {transfer_amount:.1f} votes to candidate {to_candidate}")
            
            # Calculate exhausted votes (for now, simplified)
            total_continuing = sum(vote_totals[c] for c in continuing) + sum(vote_totals[w] for w in self.winners)
            exhausted = total_votes - total_continuing
            
            # Create round record
            round_record = STVRound(
                round_number=round_num,
                continuing_candidates=continuing.copy(),
                vote_totals=vote_totals.copy(),
                quota=quota,
                winners_this_round=round_winners,
                eliminated_this_round=round_eliminated,
                transfers=transfers,
                exhausted_votes=exhausted,
                total_continuing_votes=total_continuing
            )
            
            self.rounds.append(round_record)
            round_num += 1
            
            # Safety check to prevent infinite loops
            if round_num > 50:
                logger.warning("Stopping after 50 rounds - possible infinite loop")
                break
        
        logger.info(f"\nSTV tabulation complete:")
        logger.info(f"Winners: {self.winners}")
        logger.info(f"Total rounds: {len(self.rounds)}")
        
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
                summary_data.append({
                    'round': round_obj.round_number,
                    'candidate_id': candidate_id,
                    'votes': round_obj.vote_totals[candidate_id],
                    'quota': round_obj.quota,
                    'status': self._get_candidate_status(candidate_id, round_obj),
                    'exhausted_votes': round_obj.exhausted_votes
                })
                
        return pd.DataFrame(summary_data)
        
    def _get_candidate_status(self, candidate_id: int, round_obj: STVRound) -> str:
        """Get the status of a candidate in a given round."""
        if candidate_id in round_obj.winners_this_round:
            return 'elected'
        elif candidate_id in round_obj.eliminated_this_round:
            return 'eliminated'
        elif candidate_id in self.winners:
            return 'already_elected'
        elif candidate_id in self.eliminated:
            return 'already_eliminated'
        else:
            return 'continuing'
            
    def get_final_results(self) -> pd.DataFrame:
        """
        Get final election results.
        
        Returns:
            DataFrame with final results for all candidates
        """
        if not self.rounds:
            return pd.DataFrame()
            
        # Get candidate names
        candidates = self.db.query("SELECT candidate_id, candidate_name FROM candidates")
        candidate_names = dict(zip(candidates['candidate_id'], candidates['candidate_name']))
        
        final_round = self.rounds[-1]
        
        results_data = []
        for candidate_id, votes in final_round.vote_totals.items():
            results_data.append({
                'candidate_id': candidate_id,
                'candidate_name': candidate_names.get(candidate_id, f'Unknown-{candidate_id}'),
                'final_votes': votes,
                'status': 'elected' if candidate_id in self.winners else 'not_elected',
                'election_round': next((r.round_number for r in self.rounds if candidate_id in r.winners_this_round), None)
            })
            
        return pd.DataFrame(results_data).sort_values('final_votes', ascending=False)