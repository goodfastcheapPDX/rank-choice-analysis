import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
try:
    from .database import CVRDatabase
except ImportError:
    from database import CVRDatabase

logger = logging.getLogger(__name__)


class CVRParser:
    """
    Parses Cast Vote Record (CVR) data and transforms it for analysis.
    Uses DuckDB scripts for efficient processing.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize CVR parser.
        
        Args:
            db_path: Path to DuckDB database file
        """
        self.db = CVRDatabase(db_path)
        self._loaded = False
        self._candidates = None
        
    def load_cvr_file(self, csv_path: str) -> Dict[str, int]:
        """
        Load CVR data from CSV file into database.
        
        Args:
            csv_path: Path to CVR CSV file
            
        Returns:
            Dictionary with loading statistics
        """
        logger.info(f"Loading CVR data from: {csv_path}")
        
        # Execute loading script
        result = self.db.execute_script("01_load_data", [csv_path])
        
        # Get validation stats
        stats = result.to_dict('records')[0] if not result.empty else {}
        
        logger.info(f"Loaded {stats.get('total_ballots', 0)} ballots")
        
        if stats.get('duplicate_ballots', 0) > 0:
            logger.warning(f"Found {stats['duplicate_ballots']} duplicate ballot IDs")
            
        self._loaded = True
        return stats
        
    def extract_candidate_metadata(self) -> pd.DataFrame:
        """
        Extract candidate information from column headers.
        
        Returns:
            DataFrame with candidate metadata
        """
        if not self._loaded:
            raise RuntimeError("Must load CVR data first")
            
        logger.info("Extracting candidate metadata")
        
        # Create candidate columns table
        self.db.execute_script("02_create_metadata")
        
        # Get candidate list
        candidates = self.db.query("SELECT * FROM candidates ORDER BY candidate_id")
        
        logger.info(f"Found {len(candidates)} candidates")
        
        self._candidates = candidates
        return candidates
        
    def normalize_vote_data(self) -> Dict[str, int]:
        """
        Transform wide-format voting data to normalized long format.
        
        Returns:
            Dictionary with normalization statistics
        """
        if not self._loaded:
            raise RuntimeError("Must load CVR data first")
            
        logger.info("Normalizing vote data (wide to long format)")
        
        # Get the choice columns from metadata
        choice_columns = self.db.query("SELECT DISTINCT column_name FROM candidate_columns")
        column_list = "', '".join(choice_columns['column_name'].tolist())
        
        # Create dynamic SQL for unpivoting using UNION ALL approach
        # Build individual SELECT statements for each choice column
        select_statements = []
        for _, row in choice_columns.iterrows():
            col_name = row['column_name']
            # Escape single quotes in column names
            escaped_col = col_name.replace("'", "''")
            select_statements.append(f"""
                SELECT 
                    BallotID,
                    PrecinctID,
                    BallotStyleID,
                    '{escaped_col}' as column_name,
                    CAST("{col_name}" AS INTEGER) as has_vote
                FROM rcv_data
                WHERE Status = 0 AND "{col_name}" = 1
            """)
        
        union_sql = " UNION ALL ".join(select_statements)
        
        normalize_sql = f"""
        CREATE OR REPLACE TABLE ballots_long AS
        WITH unpivoted AS (
            {union_sql}
        )
        SELECT 
            u.BallotID,
            u.PrecinctID,
            u.BallotStyleID,
            cc.candidate_id,
            cc.candidate_name,
            cc.rank_position,
            u.has_vote
        FROM unpivoted u
        JOIN candidate_columns cc ON u.column_name = cc.column_name;
        """
        
        # Execute the dynamic SQL
        self.db.conn.execute(normalize_sql)
        
        # Get validation stats
        result = self.db.query("""
            SELECT 
                COUNT(*) as total_vote_records,
                COUNT(DISTINCT BallotID) as ballots_with_votes,
                COUNT(DISTINCT candidate_id) as candidates_receiving_votes,
                MIN(rank_position) as min_rank,
                MAX(rank_position) as max_rank
            FROM ballots_long
        """)
        
        stats = result.to_dict('records')[0] if not result.empty else {}
        
        logger.info(f"Created {stats.get('total_vote_records', 0)} vote records")
        
        return stats
        
    def get_summary_statistics(self) -> pd.DataFrame:
        """Get basic summary statistics about the data."""
        self.db.execute_script("04_basic_analysis")
        return self.db.query("SELECT * FROM summary_stats")
        
    def get_first_choice_totals(self) -> pd.DataFrame:
        """Get first choice vote totals for all candidates."""
        return self.db.query("SELECT * FROM first_choice_totals")
        
    def get_votes_by_rank(self) -> pd.DataFrame:
        """Get vote totals by rank position."""
        return self.db.query("SELECT * FROM votes_by_rank")
        
    def get_ballot_completion_stats(self) -> pd.DataFrame:
        """Get statistics about ballot completion patterns."""
        return self.db.query("""
            SELECT 
                ranks_used,
                COUNT(*) as ballot_count,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
            FROM ballot_completion 
            GROUP BY ranks_used 
            ORDER BY ranks_used
        """)
        
    def analyze_candidate_partners(self, candidate_name: str) -> pd.DataFrame:
        """
        Analyze who a candidate's supporters also rank.
        
        Args:
            candidate_name: Name of candidate to analyze
            
        Returns:
            DataFrame with partner analysis
        """
        self.db.execute_script("05_candidate_analysis")
        return self.db.query(f"SELECT * FROM analyze_candidate_partners('{candidate_name}')")
        
    def get_ballot_by_id(self, ballot_id: str) -> pd.DataFrame:
        """
        Get the complete ranking for a specific ballot.
        
        Args:
            ballot_id: Ballot ID to look up
            
        Returns:
            DataFrame with ballot ranking
        """
        return self.db.query(f"""
            SELECT 
                rank_position,
                candidate_name,
                candidate_id
            FROM ballots_long 
            WHERE BallotID = '{ballot_id}'
            ORDER BY rank_position
        """)
        
    def search_ballots(self, candidate_name: str, rank_position: int = 1, limit: int = 10) -> pd.DataFrame:
        """
        Search for ballots that rank a specific candidate at a specific position.
        
        Args:
            candidate_name: Candidate to search for
            rank_position: Rank position (1-6)
            limit: Maximum number of ballots to return
            
        Returns:
            DataFrame with matching ballots
        """
        return self.db.query(f"""
            SELECT DISTINCT 
                bl.BallotID,
                bc.ranking_sequence
            FROM ballots_long bl
            JOIN ballot_completion bc ON bl.BallotID = bc.BallotID
            WHERE bl.candidate_name = '{candidate_name}' 
              AND bl.rank_position = {rank_position}
            LIMIT {limit}
        """)
        
    def get_candidates(self) -> pd.DataFrame:
        """Get list of all candidates."""
        if self._candidates is None:
            self._candidates = self.db.query("SELECT * FROM candidates ORDER BY candidate_id")
        return self._candidates
        
    def close(self):
        """Close database connection."""
        self.db.close()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()