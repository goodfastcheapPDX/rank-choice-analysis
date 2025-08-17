"""
Advanced candidate metrics analysis for ranked-choice voting elections.

This module provides comprehensive analytics focused on individual candidates,
including preference strength analysis, polarization metrics, transfer efficiency,
and voter behavior patterns.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class CandidateProfile:
    """Comprehensive candidate profile with advanced metrics."""
    candidate_id: int
    candidate_name: str
    total_ballots: int
    first_choice_votes: int
    first_choice_percentage: float
    vote_strength_index: float
    cross_camp_appeal: float
    transfer_efficiency: float
    ranking_consistency: float
    elimination_round: Optional[int]
    final_status: str  # 'winner', 'eliminated', 'continuing'
    vote_progression: List[Dict[str, Any]]
    top_coalition_partners: List[Dict[str, Any]]
    supporter_demographics: Dict[str, Any]

@dataclass
class TransferEfficiency:
    """Analysis of how effectively a candidate's votes transfer."""
    candidate_id: int
    candidate_name: str
    total_transferable_votes: int
    successful_transfers: int
    transfer_efficiency_rate: float
    avg_transfer_distance: float
    top_transfer_destinations: List[Dict[str, Any]]
    transfer_pattern_type: str  # 'concentrated', 'dispersed', 'mixed'

@dataclass
class VoterBehaviorAnalysis:
    """Analysis of voter behavior patterns for a candidate."""
    candidate_id: int
    candidate_name: str
    bullet_voters: int  # Voters who only ranked this candidate
    bullet_voter_percentage: float
    avg_ranking_position: float
    ranking_distribution: Dict[int, int]  # Position -> count
    consistency_score: float
    polarization_index: float

class CandidateMetrics:
    """Advanced metrics calculator for individual candidates."""
    
    def __init__(self, database):
        """Initialize with database connection."""
        self.db = database
        
    def get_comprehensive_candidate_profile(self, candidate_id: int) -> Optional[CandidateProfile]:
        """Get complete candidate profile with all advanced metrics."""
        try:
            # Get basic candidate info
            candidate_info = self.db.query(f"""
                SELECT candidate_id, candidate_name 
                FROM candidates 
                WHERE candidate_id = {candidate_id}
            """)
            
            if candidate_info.empty:
                return None
                
            candidate_name = candidate_info.iloc[0]['candidate_name']
            
            # Calculate all metrics
            basic_stats = self._calculate_basic_stats(candidate_id)
            strength_index = self._calculate_vote_strength_index(candidate_id)
            cross_camp = self._calculate_cross_camp_appeal(candidate_id)
            transfer_eff = self._calculate_transfer_efficiency(candidate_id)
            consistency = self._calculate_ranking_consistency(candidate_id)
            progression = self._get_vote_progression(candidate_id)
            coalition_partners = self._get_top_coalition_partners(candidate_id)
            demographics = self._analyze_supporter_demographics(candidate_id)
            
            return CandidateProfile(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                total_ballots=basic_stats['total_ballots'],
                first_choice_votes=basic_stats['first_choice_votes'],
                first_choice_percentage=basic_stats['first_choice_percentage'],
                vote_strength_index=strength_index,
                cross_camp_appeal=cross_camp,
                transfer_efficiency=transfer_eff,
                ranking_consistency=consistency,
                elimination_round=progression.get('elimination_round'),
                final_status=progression.get('final_status', 'unknown'),
                vote_progression=progression.get('round_by_round', []),
                top_coalition_partners=coalition_partners,
                supporter_demographics=demographics
            )
            
        except Exception as e:
            logger.error(f"Error creating candidate profile for {candidate_id}: {e}")
            return None
    
    def _calculate_basic_stats(self, candidate_id: int) -> Dict[str, Any]:
        """Calculate basic candidate statistics."""
        # Total ballots where candidate appears
        total_ballots = self.db.query(f"""
            SELECT COUNT(DISTINCT BallotID) as count
            FROM ballots_long 
            WHERE candidate_id = {candidate_id}
        """).iloc[0]['count']
        
        # First choice votes
        first_choice = self.db.query(f"""
            SELECT COUNT(*) as count
            FROM ballots_long 
            WHERE candidate_id = {candidate_id} AND rank_position = 1
        """).iloc[0]['count']
        
        # Total ballots in election
        total_election_ballots = self.db.query("""
            SELECT COUNT(DISTINCT BallotID) as count FROM ballots_long
        """).iloc[0]['count']
        
        first_choice_percentage = (first_choice / total_election_ballots) * 100 if total_election_ballots > 0 else 0
        
        return {
            'total_ballots': total_ballots,
            'first_choice_votes': first_choice,
            'first_choice_percentage': round(first_choice_percentage, 2)
        }
    
    def _calculate_vote_strength_index(self, candidate_id: int) -> float:
        """
        Calculate Vote Strength Index - measures intensity of voter preference.
        Higher scores indicate voters rank this candidate early and consistently.
        """
        try:
            # Get ranking distribution
            ranking_data = self.db.query(f"""
                SELECT 
                    rank_position,
                    COUNT(*) as votes
                FROM ballots_long 
                WHERE candidate_id = {candidate_id}
                GROUP BY rank_position
                ORDER BY rank_position
            """)
            
            if ranking_data.empty:
                return 0.0
            
            # Calculate weighted score (earlier ranks worth more)
            total_weighted_score = 0
            total_votes = 0
            
            for _, row in ranking_data.iterrows():
                rank = row['rank_position']
                votes = row['votes']
                # Weight decreases with rank position (1st=6pts, 2nd=5pts, etc.)
                weight = max(0, 7 - rank)
                total_weighted_score += weight * votes
                total_votes += votes
            
            # Normalize to 0-1 scale
            max_possible_score = total_votes * 6  # All first choice would be max
            strength_index = total_weighted_score / max_possible_score if max_possible_score > 0 else 0
            
            return round(strength_index, 4)
            
        except Exception as e:
            logger.error(f"Error calculating vote strength index for {candidate_id}: {e}")
            return 0.0
    
    def _calculate_cross_camp_appeal(self, candidate_id: int) -> float:
        """
        Calculate Cross-Camp Appeal - measures how well candidate attracts 
        votes across different political groupings.
        """
        try:
            # Get voters who ranked this candidate
            candidate_voters = self.db.query(f"""
                SELECT DISTINCT BallotID
                FROM ballots_long 
                WHERE candidate_id = {candidate_id}
            """)
            
            if candidate_voters.empty:
                return 0.0
            
            # Analyze diversity of other candidates these voters also ranked
            ballot_list = "'" + "','".join(candidate_voters['BallotID']) + "'"
            
            diversity_analysis = self.db.query(f"""
                SELECT 
                    bl.BallotID,
                    COUNT(DISTINCT bl.candidate_id) as unique_candidates_ranked,
                    STRING_AGG(DISTINCT c.candidate_name, '|' ORDER BY bl.rank_position) as ranking_sequence
                FROM ballots_long bl
                JOIN candidates c ON bl.candidate_id = c.candidate_id
                WHERE bl.BallotID IN ({ballot_list})
                GROUP BY bl.BallotID
            """)
            
            if diversity_analysis.empty:
                return 0.0
            
            # Calculate cross-camp appeal based on ranking diversity
            avg_unique_candidates = diversity_analysis['unique_candidates_ranked'].mean()
            max_possible_candidates = min(6, len(self.db.query("SELECT DISTINCT candidate_id FROM candidates")))
            
            # Normalize to 0-1 scale
            cross_camp_appeal = (avg_unique_candidates - 1) / (max_possible_candidates - 1) if max_possible_candidates > 1 else 0
            
            return round(cross_camp_appeal, 4)
            
        except Exception as e:
            logger.error(f"Error calculating cross-camp appeal for {candidate_id}: {e}")
            return 0.0
    
    def _calculate_transfer_efficiency(self, candidate_id: int) -> float:
        """
        Calculate Transfer Efficiency - measures how effectively this candidate's 
        votes transfer to preferred alternatives when eliminated.
        """
        try:
            # Get ballots that ranked this candidate
            candidate_ballots = self.db.query(f"""
                SELECT 
                    BallotID,
                    rank_position as candidate_rank
                FROM ballots_long 
                WHERE candidate_id = {candidate_id}
            """)
            
            if candidate_ballots.empty:
                return 0.0
            
            # Analyze transfer potential - how many have next preferences
            transfer_analysis = self.db.query(f"""
                WITH candidate_ballots AS (
                    SELECT BallotID, rank_position as candidate_rank
                    FROM ballots_long 
                    WHERE candidate_id = {candidate_id}
                ),
                next_preferences AS (
                    SELECT 
                        cb.BallotID,
                        cb.candidate_rank,
                        COUNT(bl2.candidate_id) as next_choices_available
                    FROM candidate_ballots cb
                    LEFT JOIN ballots_long bl2 ON cb.BallotID = bl2.BallotID 
                        AND bl2.rank_position > cb.candidate_rank
                        AND bl2.candidate_id != {candidate_id}
                    GROUP BY cb.BallotID, cb.candidate_rank
                )
                SELECT 
                    AVG(CASE WHEN next_choices_available > 0 THEN 1.0 ELSE 0.0 END) as transfer_rate,
                    AVG(next_choices_available) as avg_next_choices
                FROM next_preferences
            """)
            
            if transfer_analysis.empty:
                return 0.0
            
            transfer_rate = transfer_analysis.iloc[0]['transfer_rate'] or 0
            return round(transfer_rate, 4)
            
        except Exception as e:
            logger.error(f"Error calculating transfer efficiency for {candidate_id}: {e}")
            return 0.0
    
    def _calculate_ranking_consistency(self, candidate_id: int) -> float:
        """
        Calculate Ranking Consistency - measures how consistently voters 
        rank this candidate across different ballot positions.
        """
        try:
            ranking_distribution = self.db.query(f"""
                SELECT 
                    rank_position,
                    COUNT(*) as votes,
                    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
                FROM ballots_long 
                WHERE candidate_id = {candidate_id}
                GROUP BY rank_position
                ORDER BY rank_position
            """)
            
            if ranking_distribution.empty:
                return 0.0
            
            # Calculate consistency using entropy-based measure
            percentages = ranking_distribution['percentage'].values / 100.0
            # Higher concentration = higher consistency
            entropy = -sum(p * np.log2(p) for p in percentages if p > 0)
            max_entropy = np.log2(len(percentages))
            
            # Convert to consistency score (0 = scattered, 1 = concentrated)
            consistency = 1 - (entropy / max_entropy) if max_entropy > 0 else 1
            
            return round(consistency, 4)
            
        except Exception as e:
            logger.error(f"Error calculating ranking consistency for {candidate_id}: {e}")
            return 0.0
    
    def _get_vote_progression(self, candidate_id: int) -> Dict[str, Any]:
        """Get vote progression through STV rounds (requires STV results)."""
        try:
            # This would require running STV and tracking vote counts
            # For now, return basic progression info
            return {
                'elimination_round': None,
                'final_status': 'unknown',
                'round_by_round': []
            }
        except Exception as e:
            logger.error(f"Error getting vote progression for {candidate_id}: {e}")
            return {'elimination_round': None, 'final_status': 'unknown', 'round_by_round': []}
    
    def _get_top_coalition_partners(self, candidate_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top coalition partners for this candidate."""
        try:
            # Get shared ballot analysis
            coalition_data = self.db.query(f"""
                WITH candidate_ballots AS (
                    SELECT DISTINCT BallotID
                    FROM ballots_long 
                    WHERE candidate_id = {candidate_id}
                ),
                shared_ballots AS (
                    SELECT 
                        bl.candidate_id as other_candidate_id,
                        c.candidate_name as other_candidate_name,
                        COUNT(*) as shared_ballots,
                        AVG(ABS(bl.rank_position - main.rank_position)) as avg_rank_distance
                    FROM candidate_ballots cb
                    JOIN ballots_long main ON cb.BallotID = main.BallotID AND main.candidate_id = {candidate_id}
                    JOIN ballots_long bl ON cb.BallotID = bl.BallotID AND bl.candidate_id != {candidate_id}
                    JOIN candidates c ON bl.candidate_id = c.candidate_id
                    GROUP BY bl.candidate_id, c.candidate_name
                    HAVING COUNT(*) >= 100
                )
                SELECT 
                    other_candidate_id,
                    other_candidate_name,
                    shared_ballots,
                    avg_rank_distance,
                    shared_ballots / (avg_rank_distance + 1) as coalition_score
                FROM shared_ballots
                ORDER BY coalition_score DESC
                LIMIT {limit}
            """)
            
            return coalition_data.to_dict('records')
            
        except Exception as e:
            logger.error(f"Error getting coalition partners for {candidate_id}: {e}")
            return []
    
    def _analyze_supporter_demographics(self, candidate_id: int) -> Dict[str, Any]:
        """Analyze demographics and patterns of candidate supporters."""
        try:
            # Get basic supporter statistics
            supporter_stats = self.db.query(f"""
                WITH candidate_supporters AS (
                    SELECT DISTINCT BallotID
                    FROM ballots_long 
                    WHERE candidate_id = {candidate_id}
                ),
                supporter_analysis AS (
                    SELECT 
                        cs.BallotID,
                        COUNT(bl.candidate_id) as total_candidates_ranked,
                        MIN(bl.rank_position) as earliest_rank,
                        MAX(bl.rank_position) as latest_rank
                    FROM candidate_supporters cs
                    JOIN ballots_long bl ON cs.BallotID = bl.BallotID
                    GROUP BY cs.BallotID
                )
                SELECT 
                    COUNT(*) as total_supporters,
                    AVG(total_candidates_ranked) as avg_candidates_ranked,
                    AVG(earliest_rank) as avg_earliest_rank,
                    AVG(latest_rank) as avg_latest_rank,
                    COUNT(CASE WHEN total_candidates_ranked = 1 THEN 1 END) as bullet_voters
                FROM supporter_analysis
            """)
            
            if supporter_stats.empty:
                return {}
            
            stats = supporter_stats.iloc[0]
            return {
                'total_supporters': int(stats['total_supporters']),
                'avg_candidates_ranked': round(float(stats['avg_candidates_ranked']), 2),
                'avg_earliest_rank': round(float(stats['avg_earliest_rank']), 2),
                'avg_latest_rank': round(float(stats['avg_latest_rank']), 2),
                'bullet_voters': int(stats['bullet_voters']),
                'bullet_voter_percentage': round((stats['bullet_voters'] / stats['total_supporters']) * 100, 2)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing supporter demographics for {candidate_id}: {e}")
            return {}
    
    def get_transfer_efficiency_analysis(self, candidate_id: int) -> Optional[TransferEfficiency]:
        """Get detailed transfer efficiency analysis for a candidate."""
        try:
            candidate_info = self.db.query(f"""
                SELECT candidate_name FROM candidates WHERE candidate_id = {candidate_id}
            """)
            
            if candidate_info.empty:
                return None
                
            candidate_name = candidate_info.iloc[0]['candidate_name']
            
            # Analyze transfer patterns
            transfer_data = self.db.query(f"""
                WITH candidate_ballots AS (
                    SELECT 
                        BallotID,
                        rank_position as candidate_rank
                    FROM ballots_long 
                    WHERE candidate_id = {candidate_id}
                ),
                transfer_destinations AS (
                    SELECT 
                        cb.BallotID,
                        bl.candidate_id as destination_candidate,
                        c.candidate_name as destination_name,
                        bl.rank_position,
                        bl.rank_position - cb.candidate_rank as rank_distance
                    FROM candidate_ballots cb
                    JOIN ballots_long bl ON cb.BallotID = bl.BallotID 
                        AND bl.rank_position > cb.candidate_rank
                        AND bl.candidate_id != {candidate_id}
                    JOIN candidates c ON bl.candidate_id = c.candidate_id
                )
                SELECT 
                    destination_candidate,
                    destination_name,
                    COUNT(*) as transfer_votes,
                    AVG(rank_distance) as avg_transfer_distance,
                    MIN(rank_distance) as min_transfer_distance
                FROM transfer_destinations
                GROUP BY destination_candidate, destination_name
                ORDER BY transfer_votes DESC
                LIMIT 10
            """)
            
            total_transferable = self.db.query(f"""
                SELECT COUNT(DISTINCT BallotID) as count
                FROM ballots_long bl1
                WHERE bl1.candidate_id = {candidate_id}
                AND EXISTS (
                    SELECT 1 FROM ballots_long bl2 
                    WHERE bl2.BallotID = bl1.BallotID 
                    AND bl2.rank_position > bl1.rank_position
                    AND bl2.candidate_id != {candidate_id}
                )
            """).iloc[0]['count']
            
            successful_transfers = transfer_data['transfer_votes'].sum() if not transfer_data.empty else 0
            transfer_efficiency_rate = (successful_transfers / total_transferable) if total_transferable > 0 else 0
            avg_transfer_distance = transfer_data['avg_transfer_distance'].mean() if not transfer_data.empty else 0
            
            # Determine transfer pattern type
            if transfer_data.empty:
                pattern_type = 'none'
            elif len(transfer_data) <= 3:
                pattern_type = 'concentrated'
            elif transfer_data.iloc[0]['transfer_votes'] / successful_transfers > 0.5:
                pattern_type = 'concentrated'
            else:
                pattern_type = 'dispersed'
            
            return TransferEfficiency(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                total_transferable_votes=total_transferable,
                successful_transfers=successful_transfers,
                transfer_efficiency_rate=round(transfer_efficiency_rate, 4),
                avg_transfer_distance=round(avg_transfer_distance, 2),
                top_transfer_destinations=transfer_data.to_dict('records'),
                transfer_pattern_type=pattern_type
            )
            
        except Exception as e:
            logger.error(f"Error analyzing transfer efficiency for {candidate_id}: {e}")
            return None
    
    def get_voter_behavior_analysis(self, candidate_id: int) -> Optional[VoterBehaviorAnalysis]:
        """Get detailed voter behavior analysis for a candidate."""
        try:
            candidate_info = self.db.query(f"""
                SELECT candidate_name FROM candidates WHERE candidate_id = {candidate_id}
            """)
            
            if candidate_info.empty:
                return None
                
            candidate_name = candidate_info.iloc[0]['candidate_name']
            
            # Analyze voting patterns
            voting_patterns = self.db.query(f"""
                WITH candidate_voters AS (
                    SELECT 
                        bl.BallotID,
                        bl.rank_position,
                        COUNT(bl2.candidate_id) as total_ranked_by_voter
                    FROM ballots_long bl
                    LEFT JOIN ballots_long bl2 ON bl.BallotID = bl2.BallotID
                    WHERE bl.candidate_id = {candidate_id}
                    GROUP BY bl.BallotID, bl.rank_position
                )
                SELECT 
                    COUNT(*) as total_voters,
                    AVG(rank_position) as avg_ranking_position,
                    COUNT(CASE WHEN total_ranked_by_voter = 1 THEN 1 END) as bullet_voters
                FROM candidate_voters
            """)
            
            ranking_distribution = self.db.query(f"""
                SELECT 
                    rank_position,
                    COUNT(*) as count
                FROM ballots_long 
                WHERE candidate_id = {candidate_id}
                GROUP BY rank_position
                ORDER BY rank_position
            """)
            
            if voting_patterns.empty:
                return None
            
            stats = voting_patterns.iloc[0]
            total_voters = int(stats['total_voters'])
            bullet_voters = int(stats['bullet_voters'])
            bullet_percentage = (bullet_voters / total_voters * 100) if total_voters > 0 else 0
            
            # Calculate consistency and polarization
            consistency_score = self._calculate_ranking_consistency(candidate_id)
            
            # Simple polarization index based on bullet voting and ranking spread
            polarization_index = bullet_percentage / 100.0  # Higher bullet voting = more polarizing
            
            ranking_dist_dict = dict(zip(ranking_distribution['rank_position'], ranking_distribution['count']))
            
            return VoterBehaviorAnalysis(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                bullet_voters=bullet_voters,
                bullet_voter_percentage=round(bullet_percentage, 2),
                avg_ranking_position=round(float(stats['avg_ranking_position']), 2),
                ranking_distribution=ranking_dist_dict,
                consistency_score=consistency_score,
                polarization_index=round(polarization_index, 4)
            )
            
        except Exception as e:
            logger.error(f"Error analyzing voter behavior for {candidate_id}: {e}")
            return None
    
    def get_all_candidates_summary(self) -> List[Dict[str, Any]]:
        """Get summary metrics for all candidates."""
        try:
            candidates = self.db.query("SELECT candidate_id, candidate_name FROM candidates ORDER BY candidate_name")
            
            summaries = []
            for _, candidate in candidates.iterrows():
                candidate_id = candidate['candidate_id']
                
                # Get basic metrics
                basic_stats = self._calculate_basic_stats(candidate_id)
                strength_index = self._calculate_vote_strength_index(candidate_id)
                cross_camp = self._calculate_cross_camp_appeal(candidate_id)
                
                summaries.append({
                    'candidate_id': candidate_id,
                    'candidate_name': candidate['candidate_name'],
                    'total_ballots': basic_stats['total_ballots'],
                    'first_choice_votes': basic_stats['first_choice_votes'],
                    'first_choice_percentage': basic_stats['first_choice_percentage'],
                    'vote_strength_index': strength_index,
                    'cross_camp_appeal': cross_camp
                })
            
            return summaries
            
        except Exception as e:
            logger.error(f"Error getting candidates summary: {e}")
            return []