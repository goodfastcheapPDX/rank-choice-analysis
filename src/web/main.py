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
except ImportError:
    from data.database import CVRDatabase
    from data.cvr_parser import CVRParser
    from analysis.stv import STVTabulator
    from analysis.verification import ResultsVerifier

logger = logging.getLogger(__name__)

app = FastAPI(title="Ranked Elections Analyzer", description="Portland STV Election Analysis Platform")

# Global database connection - in production this should be properly managed
db_path = None
db = None

# Templates and static files
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

@app.on_event("startup")
async def startup_event():
    """Initialize the application."""
    logger.info("Starting Ranked Elections Analyzer")

@app.on_event("shutdown") 
async def shutdown_event():
    """Clean up on shutdown."""
    global db
    if db:
        db.close()

def get_database() -> CVRDatabase:
    """Get database connection."""
    global db, db_path
    if not db and db_path:
        db = CVRDatabase(db_path)
    return db

def set_database_path(path: str):
    """Set the database path for the application."""
    global db_path, db
    db_path = path
    if db:
        db.close()
    db = CVRDatabase(db_path)

# API Routes
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
    
    summary = database.query("SELECT * FROM summary_stats")
    return summary.to_dict('records')

@app.get("/api/candidates")
async def get_candidates():
    """Get list of all candidates."""
    database = get_database()
    if not database or not database.table_exists("candidates"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    candidates = database.query("SELECT * FROM candidates ORDER BY candidate_name")
    return candidates.to_dict('records')

@app.get("/api/first-choice")
async def get_first_choice_results():
    """Get first choice voting results."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")
    
    results = database.query("SELECT * FROM first_choice_totals")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)