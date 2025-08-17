from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd
from pathlib import Path
import logging
import json
from typing import Optional, List

try:
    from ..data.database import CVRDatabase
    from ..data.cvr_parser import CVRParser
    from ..analysis.stv import STVTabulator
    from ..analysis.verification import ResultsVerifier
    from ..analysis.coalition import CoalitionAnalyzer, convert_numpy_types
except ImportError:
    from data.database import CVRDatabase
    from data.cvr_parser import CVRParser
    from analysis.stv import STVTabulator
    from analysis.verification import ResultsVerifier
    from analysis.coalition import CoalitionAnalyzer, convert_numpy_types

logger = logging.getLogger(__name__)

app = FastAPI(title="Ranked Elections Analyzer", description="Portland STV Election Analysis Platform")

# Global database path - connections are now managed automatically
db_path = None

# Templates and static files
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

@app.on_event("startup")
async def startup_event():
    """Initialize the application."""
    logger.info("Starting Ranked Elections Analyzer")

@app.on_event("shutdown") 
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Shutting down Ranked Elections Analyzer")

def get_database() -> CVRDatabase:
    """
    Get database connection using improved connection management.
    Creates read-only connections by default to avoid locking issues.
    """
    global db_path
    if not db_path:
        raise HTTPException(status_code=500, detail="Database not configured")
    return CVRDatabase(db_path, read_only=True)

def set_database_path(path: str):
    """Set the database path for the application."""
    global db_path
    db_path = path
    logger.info(f"Database path set to: {path}")
    
    # Test connection to ensure database is accessible
    try:
        test_db = CVRDatabase(db_path, read_only=True)
        test_db.table_exists("ballots_long")  # This will use a temporary connection
        logger.info("Database connection test successful")
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        raise

# API Routes
@app.get("/coalition")
async def coalition_analysis(request: Request):
    """Coalition analysis page."""
    return templates.TemplateResponse("coalition.html", {"request": request})

@app.get("/vote-flow")
async def vote_flow_visualization(request: Request):
    """Vote flow visualization page."""
    return templates.TemplateResponse("vote_flow.html", {"request": request})

@app.get("/")
async def root(request: Request):
    """Main dashboard page."""
    try:
        database = get_database()
        if not database:
            return templates.TemplateResponse("setup.html", {"request": request})
        
        # Check if data is loaded
        if not database.table_exists("ballots_long"):
            return templates.TemplateResponse("setup.html", {"request": request})
        
        # Get basic statistics
        summary = database.query("SELECT * FROM summary_stats")
        summary_dict = dict(zip(summary['metric'], summary['value']))
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "summary": summary_dict
        })
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)})

@app.get("/api/summary")
async def get_summary():
    """Get summary statistics."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    summary = database.query_with_retry("SELECT * FROM summary_stats")
    return summary.to_dict('records')

@app.get("/api/candidates")
async def get_candidates():
    """Get list of all candidates."""
    database = get_database()
    if not database or not database.table_exists("candidates"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    candidates = database.query_with_retry("SELECT * FROM candidates ORDER BY candidate_name")
    return candidates.to_dict('records')

@app.get("/api/first-choice")
async def get_first_choice_results():
    """Get first choice voting results."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    results = database.query_with_retry("SELECT * FROM first_choice_totals")
    return results.to_dict('records')

@app.get("/api/votes-by-rank")
async def get_votes_by_rank():
    """Get vote distribution by rank position."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    results = database.query("SELECT * FROM votes_by_rank WHERE rank_order <= 5 ORDER BY rank_position, rank_order")
    return results.to_dict('records')

@app.get("/api/ballot/{ballot_id}")
async def get_ballot(ballot_id: str):
    """Get details for a specific ballot."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    ballot = database.query(f"""
        SELECT 
            rank_position,
            candidate_name,
            candidate_id
        FROM ballots_long 
        WHERE BallotID = '{ballot_id}'
        ORDER BY rank_position
    """)
    
    if ballot.empty:
        raise HTTPException(status_code=404, detail="Ballot not found")
    
    return ballot.to_dict('records')

@app.get("/api/search-ballots")
async def search_ballots(candidate: str, rank: int = 1, limit: int = 10):
    """Search for ballots that rank a candidate at a specific position."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    results = database.query(f"""
        SELECT DISTINCT 
            bl.BallotID,
            bc.ranking_sequence
        FROM ballots_long bl
        JOIN ballot_completion bc ON bl.BallotID = bc.BallotID
        WHERE bl.candidate_name = '{candidate}' 
          AND bl.rank_position = {rank}
        LIMIT {limit}
    """)
    
    return results.to_dict('records')

@app.get("/api/stv-results")
async def get_stv_results(seats: int = 3):
    """Run STV tabulation and return results."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        # Run STV tabulation
        tabulator = STVTabulator(database, seats=seats)
        rounds = tabulator.run_stv_tabulation()
        
        # Get results
        final_results = tabulator.get_final_results()
        round_summary = tabulator.get_round_summary()
        
        return {
            "final_results": final_results.to_dict('records'),
            "round_summary": round_summary.to_dict('records'),
            "winners": tabulator.winners,
            "total_rounds": len(rounds)
        }
    except Exception as e:
        logger.error(f"Error running STV: {e}")
        raise HTTPException(status_code=500, detail=f"STV calculation failed: {str(e)}")

@app.get("/api/stv-flow-data")
async def get_stv_flow_data(seats: int = 3):
    """Get complete vote flow data for visualization."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        # Run STV tabulation with detailed tracking enabled
        tabulator = STVTabulator(database, seats=seats, detailed_tracking=True)
        rounds = tabulator.run_stv_tabulation()
        
        # Get vote flow data
        vote_flow = tabulator.get_vote_flow()
        if not vote_flow:
            raise HTTPException(status_code=500, detail="Vote flow tracking failed")
        
        # Convert to JSON-serializable format
        flow_data = {
            "rounds": [
                {
                    "round_number": r.round_number,
                    "continuing_candidates": r.continuing_candidates,
                    "vote_totals": r.vote_totals,
                    "quota": r.quota,
                    "winners_this_round": r.winners_this_round,
                    "eliminated_this_round": r.eliminated_this_round,
                    "transfers": r.transfers,
                    "exhausted_votes": r.exhausted_votes,
                    "total_continuing_votes": r.total_continuing_votes
                }
                for r in vote_flow.rounds
            ],
            "transfer_patterns": [
                {
                    "round_number": p.round_number,
                    "from_candidate": p.from_candidate,
                    "from_candidate_name": p.from_candidate_name,
                    "to_candidate": p.to_candidate,
                    "to_candidate_name": p.to_candidate_name,
                    "votes_transferred": p.votes_transferred,
                    "transfer_type": p.transfer_type,
                    "transfer_value": p.transfer_value,
                    "ballot_count": p.ballot_count
                }
                for p in vote_flow.transfer_patterns
            ],
            "candidate_flow_summary": vote_flow.candidate_flow_summary,
            "flow_metadata": vote_flow.flow_metadata
        }
        
        return flow_data
        
    except Exception as e:
        logger.error(f"Error generating vote flow data: {e}")
        raise HTTPException(status_code=500, detail=f"Vote flow generation failed: {str(e)}")

@app.get("/api/vote-transfers/round/{round_number}")
async def get_round_transfers(round_number: int, seats: int = 3):
    """Get vote transfer details for a specific round."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        # Run STV tabulation with detailed tracking
        tabulator = STVTabulator(database, seats=seats, detailed_tracking=True)
        rounds = tabulator.run_stv_tabulation()
        
        vote_flow = tabulator.get_vote_flow()
        if not vote_flow:
            raise HTTPException(status_code=500, detail="Vote flow tracking failed")
        
        # Find transfers for the requested round
        round_transfers = [
            {
                "from_candidate": p.from_candidate,
                "from_candidate_name": p.from_candidate_name,
                "to_candidate": p.to_candidate,
                "to_candidate_name": p.to_candidate_name,
                "votes_transferred": p.votes_transferred,
                "transfer_type": p.transfer_type,
                "transfer_value": p.transfer_value,
                "ballot_count": p.ballot_count
            }
            for p in vote_flow.transfer_patterns
            if p.round_number == round_number
        ]
        
        if not round_transfers:
            raise HTTPException(status_code=404, detail=f"No transfers found for round {round_number}")
        
        # Get round summary
        round_info = None
        for r in vote_flow.rounds:
            if r.round_number == round_number:
                round_info = {
                    "round_number": r.round_number,
                    "quota": r.quota,
                    "winners_this_round": r.winners_this_round,
                    "eliminated_this_round": r.eliminated_this_round,
                    "exhausted_votes": r.exhausted_votes,
                    "total_continuing_votes": r.total_continuing_votes
                }
                break
        
        return {
            "round_info": round_info,
            "transfers": round_transfers,
            "transfer_count": len(round_transfers)
        }
        
    except Exception as e:
        logger.error(f"Error getting round transfers: {e}")
        raise HTTPException(status_code=500, detail=f"Round transfer lookup failed: {str(e)}")

@app.get("/api/candidate-analysis/{candidate_name}")
async def analyze_candidate(candidate_name: str):
    """Get detailed analysis for a specific candidate."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        # Get candidate's vote totals by rank
        vote_totals = database.query(f"""
            SELECT 
                rank_position,
                COUNT(*) as votes,
                ROUND(100.0 * COUNT(*) / (SELECT COUNT(DISTINCT BallotID) FROM ballots_long), 2) as percentage
            FROM ballots_long
            WHERE candidate_name = '{candidate_name}'
            GROUP BY rank_position
            ORDER BY rank_position
        """)
        
        # Get who their first-choice supporters also rank
        database.query("CREATE TABLE IF NOT EXISTS temp_analysis AS SELECT * FROM analyze_candidate_partners(?)")
        partners = database.query(f"SELECT * FROM analyze_candidate_partners('{candidate_name}') WHERE rank_within_position <= 3")
        
        return {
            "candidate_name": candidate_name,
            "vote_totals": vote_totals.to_dict('records'),
            "top_partners": partners.to_dict('records')
        }
    except Exception as e:
        logger.error(f"Error analyzing candidate {candidate_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# CSV Export endpoints
@app.get("/api/export/summary")
async def export_summary():
    """Export summary data as CSV."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    summary = database.query("SELECT * FROM summary_stats")
    
    # Save to temporary file
    temp_path = "/tmp/summary.csv"
    summary.to_csv(temp_path, index=False)
    
    return FileResponse(
        temp_path,
        media_type="text/csv",
        filename="election_summary.csv"
    )

@app.get("/api/export/first-choice")
async def export_first_choice():
    """Export first choice results as CSV."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    results = database.query("SELECT * FROM first_choice_totals")
    
    # Save to temporary file
    temp_path = "/tmp/first_choice.csv"
    results.to_csv(temp_path, index=False)
    
    return FileResponse(
        temp_path,
        media_type="text/csv",
        filename="first_choice_results.csv"
    )

@app.get("/api/verify-results")
async def verify_results(official_results_path: str = "2024-12-02_15-04-45_report_official.csv"):
    """Verify our results against official results."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    # Check if official results file exists
    official_path = Path(official_results_path)
    if not official_path.exists():
        # Try relative to project root
        project_root = Path(__file__).parent.parent.parent
        official_path = project_root / official_results_path
        
    if not official_path.exists():
        raise HTTPException(status_code=404, detail=f"Official results file not found: {official_results_path}")
    
    try:
        # Run our STV tabulation
        tabulator = STVTabulator(database, seats=3)
        rounds = tabulator.run_stv_tabulation()
        
        # Get our results
        candidates = database.query("SELECT candidate_id, candidate_name FROM candidates")
        first_choice = database.query("SELECT * FROM first_choice_totals")
        
        # Verify against official results
        verifier = ResultsVerifier(str(official_path))
        verification_results = verifier.verify_results(
            our_winners=tabulator.winners,
            our_candidates=candidates,
            our_first_choice=first_choice
        )
        
        # Generate readable report
        report = verifier.generate_verification_report(verification_results)
        
        return {
            "verification_passed": verification_results["verification_passed"],
            "winners_match": verification_results["winners_match"],
            "official_winners": verification_results["official_winners"],
            "our_winners": verification_results["our_winners"],
            "total_vote_difference": verification_results["total_vote_difference"],
            "vote_comparisons": verification_results["vote_comparisons"].to_dict('records'),
            "report": report,
            "official_metadata": verification_results["official_metadata"]
        }
        
    except Exception as e:
        logger.error(f"Error during verification: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

@app.get("/api/coalition/affinities")
async def get_candidate_affinities(min_shared_ballots: int = 1000):
    """Get candidate affinity analysis showing which candidates have overlapping supporter bases."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        analyzer = CoalitionAnalyzer(database)
        affinities = analyzer.calculate_pairwise_affinity(min_shared_ballots=min_shared_ballots)
        
        # Convert to JSON-serializable format
        result = []
        for affinity in affinities:
            result.append({
                "candidate_1": affinity.candidate_1,
                "candidate_1_name": affinity.candidate_1_name,
                "candidate_2": affinity.candidate_2,
                "candidate_2_name": affinity.candidate_2_name,
                "shared_ballots": affinity.shared_ballots,
                "total_ballots_1": affinity.total_ballots_1,
                "total_ballots_2": affinity.total_ballots_2,
                "affinity_score": round(affinity.affinity_score, 4),
                "overlap_percentage": round(affinity.overlap_percentage, 2)
            })
        
        return {"affinities": result, "count": len(result)}
    except Exception as e:
        logger.error(f"Coalition affinity analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/coalition/transfers/{candidate_id}")
async def get_vote_transfers(candidate_id: int):
    """Get vote transfer patterns for a specific candidate - where their supporters' votes would go."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        analyzer = CoalitionAnalyzer(database)
        transfers = analyzer.find_vote_transfer_patterns(candidate_id)
        
        # Get candidate name
        candidate_query = database.query(f"SELECT candidate_name FROM candidates WHERE candidate_id = {candidate_id}")
        if candidate_query.empty:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        candidate_name = candidate_query.iloc[0]['candidate_name']
        
        # Convert to list format
        transfer_list = []
        for cand_id, info in transfers.items():
            transfer_list.append({
                "candidate_id": cand_id,
                "candidate_name": info['candidate_name'],
                "transfer_votes": info['transfer_votes'],
                "avg_rank_position": info['avg_rank_position'],
                "transfer_percentage": round(info['transfer_percentage'], 2)
            })
        
        # Sort by transfer votes descending
        transfer_list.sort(key=lambda x: x['transfer_votes'], reverse=True)
        
        return {
            "from_candidate_id": candidate_id,
            "from_candidate_name": candidate_name,
            "transfers": transfer_list,
            "total_transfers": sum(t['transfer_votes'] for t in transfer_list)
        }
    except Exception as e:
        logger.error(f"Vote transfer analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/coalition/summary/{candidate_id}")
async def get_candidate_coalition_summary(candidate_id: int):
    """Get comprehensive coalition analysis for a specific candidate."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        analyzer = CoalitionAnalyzer(database)
        summary = analyzer.get_candidate_coalition_summary(candidate_id)
        
        if "error" in summary:
            raise HTTPException(status_code=404, detail=summary["error"])
        
        # Convert affinities to JSON-serializable format
        affinities_json = []
        for affinity in summary["top_affinities"]:
            affinities_json.append({
                "candidate_1": affinity.candidate_1,
                "candidate_1_name": affinity.candidate_1_name,
                "candidate_2": affinity.candidate_2,
                "candidate_2_name": affinity.candidate_2_name,
                "shared_ballots": affinity.shared_ballots,
                "affinity_score": round(affinity.affinity_score, 4),
                "overlap_percentage": round(affinity.overlap_percentage, 2)
            })
        
        return {
            "candidate_id": summary["candidate_id"],
            "candidate_name": summary["candidate_name"],
            "total_ballots": summary["total_ballots"],
            "top_affinities": affinities_json,
            "vote_transfers": summary["vote_transfers"],
            "coalition_strength": summary["coalition_strength"]
        }
    except Exception as e:
        logger.error(f"Coalition summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/coalition/winners")
async def get_winner_coalition_analysis():
    """Get coalition analysis specifically for the three winning candidates."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        # Portland District 2 winners: Sameer Kanal (36), Elana Pirtle-Guiney (46), Dan Ryan (55)
        winners = [36, 46, 55]
        
        analyzer = CoalitionAnalyzer(database)
        
        winner_analysis = {}
        for winner_id in winners:
            summary = analyzer.get_candidate_coalition_summary(winner_id)
            if "error" not in summary:
                # Simplified format for winners overview
                winner_analysis[str(winner_id)] = {
                    "candidate_id": int(winner_id),
                    "candidate_name": summary["candidate_name"],
                    "total_ballots": int(summary["total_ballots"]),
                    "top_3_affinities": [
                        {
                            "other_candidate": (affinity.candidate_2_name if affinity.candidate_1 == winner_id 
                                              else affinity.candidate_1_name),
                            "shared_ballots": int(affinity.shared_ballots),
                            "affinity_score": round(float(affinity.affinity_score), 4)
                        }
                        for affinity in summary["top_affinities"][:3]
                    ],
                    "top_3_transfers": [
                        {
                            "to_candidate": info['candidate_name'],
                            "transfer_votes": info['transfer_votes'],
                            "transfer_percentage": round(info['transfer_percentage'], 2)
                        }
                        for info in list(summary["vote_transfers"].values())[:3]
                    ]
                }
        
        return {"winner_coalitions": winner_analysis}
    except Exception as e:
        logger.error(f"Winner coalition analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/coalition/pairs/all")
async def get_all_candidate_pairs_analysis(min_shared_ballots: int = 50):
    """Get detailed analysis for all candidate pairs meeting minimum threshold."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        analyzer = CoalitionAnalyzer(database)
        detailed_pairs = analyzer.calculate_detailed_pairwise_analysis(min_shared_ballots=min_shared_ballots)
        
        # Convert to JSON-serializable format
        result = []
        for pair in detailed_pairs:
            result.append({
                "candidate_1": pair.candidate_1,
                "candidate_1_name": pair.candidate_1_name,
                "candidate_2": pair.candidate_2,
                "candidate_2_name": pair.candidate_2_name,
                "shared_ballots": pair.shared_ballots,
                "total_ballots_1": pair.total_ballots_1,
                "total_ballots_2": pair.total_ballots_2,
                "avg_ranking_distance": round(pair.avg_ranking_distance, 2),
                "min_ranking_distance": pair.min_ranking_distance,
                "max_ranking_distance": pair.max_ranking_distance,
                "strong_coalition_votes": pair.strong_coalition_votes,
                "weak_coalition_votes": pair.weak_coalition_votes,
                "transfer_votes_1_to_2": pair.transfer_votes_1_to_2,
                "transfer_votes_2_to_1": pair.transfer_votes_2_to_1,
                "basic_affinity_score": round(pair.basic_affinity_score, 4),
                "proximity_weighted_affinity": round(pair.proximity_weighted_affinity, 4),
                "coalition_strength_score": round(pair.coalition_strength_score, 4),
                "coalition_type": pair.coalition_type
            })
        
        final_result = {"detailed_pairs": result, "count": len(result)}
        return convert_numpy_types(final_result)
    except Exception as e:
        logger.error(f"Detailed pairs analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/coalition/pairs/{candidate_1_id}/{candidate_2_id}")
async def get_detailed_pair_analysis(candidate_1_id: int, candidate_2_id: int):
    """Get comprehensive analysis of a specific candidate pair."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        analyzer = CoalitionAnalyzer(database)
        pair = analyzer.get_detailed_pair_analysis(candidate_1_id, candidate_2_id)
        
        if not pair:
            raise HTTPException(status_code=404, detail="Candidate pair not found or insufficient data")
        
        # Also get proximity analysis
        proximity = analyzer.analyze_ranking_proximity(candidate_1_id, candidate_2_id)
        
        result = {
            "pair_analysis": {
                "candidate_1": pair.candidate_1,
                "candidate_1_name": pair.candidate_1_name,
                "candidate_2": pair.candidate_2,
                "candidate_2_name": pair.candidate_2_name,
                "shared_ballots": pair.shared_ballots,
                "total_ballots_1": pair.total_ballots_1,
                "total_ballots_2": pair.total_ballots_2,
                "avg_ranking_distance": round(pair.avg_ranking_distance, 2),
                "min_ranking_distance": pair.min_ranking_distance,
                "max_ranking_distance": pair.max_ranking_distance,
                "strong_coalition_votes": pair.strong_coalition_votes,
                "weak_coalition_votes": pair.weak_coalition_votes,
                "transfer_votes_1_to_2": pair.transfer_votes_1_to_2,
                "transfer_votes_2_to_1": pair.transfer_votes_2_to_1,
                "basic_affinity_score": round(pair.basic_affinity_score, 4),
                "proximity_weighted_affinity": round(pair.proximity_weighted_affinity, 4),
                "coalition_strength_score": round(pair.coalition_strength_score, 4),
                "coalition_type": pair.coalition_type
            },
            "proximity_analysis": proximity
        }
        return convert_numpy_types(result)
    except Exception as e:
        logger.error(f"Detailed pair analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/coalition/proximity/{candidate_1_id}/{candidate_2_id}")
async def get_proximity_analysis(candidate_1_id: int, candidate_2_id: int):
    """Get ranking proximity analysis for a specific candidate pair."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        analyzer = CoalitionAnalyzer(database)
        proximity = analyzer.analyze_ranking_proximity(candidate_1_id, candidate_2_id)
        
        if "error" in proximity:
            raise HTTPException(status_code=404, detail=proximity["error"])
        
        return proximity
    except Exception as e:
        logger.error(f"Proximity analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/coalition/types")
async def get_coalition_type_breakdown():
    """Get breakdown of different coalition types across all pairs."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    try:
        analyzer = CoalitionAnalyzer(database)
        breakdown = analyzer.get_coalition_type_breakdown()
        
        return breakdown
    except Exception as e:
        logger.error(f"Coalition type breakdown failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)