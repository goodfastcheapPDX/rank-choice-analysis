import logging
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates

try:
    from ..analysis.candidate_metrics import CandidateMetrics
    from ..analysis.coalition import CoalitionAnalyzer, convert_numpy_types
    from ..analysis.stv import STVTabulator
    from ..analysis.verification import ResultsVerifier
    from ..data.database import CVRDatabase
except ImportError:
    from analysis.candidate_metrics import CandidateMetrics
    from analysis.coalition import CoalitionAnalyzer, convert_numpy_types
    from analysis.stv import STVTabulator
    from analysis.verification import ResultsVerifier
    from data.database import CVRDatabase

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ranked Elections Analyzer",
    description="Portland STV Election Analysis Platform",
)

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


def has_precomputed_data() -> bool:
    """Check if precomputed data tables are available."""
    try:
        database = get_database()
        return database.table_exists("adjacent_pairs") and database.table_exists(
            "candidate_metrics"
        )
    except Exception:
        return False


def get_precomputed_pairs(min_shared_ballots: int = 50) -> pd.DataFrame:
    """Get precomputed adjacent pairs data with filtering."""
    database = get_database()

    # Query precomputed data with filtering
    query = """
    SELECT
        candidate_1,
        candidate_1_name,
        candidate_2,
        candidate_2_name,
        shared_ballots,
        total_ballots_1,
        total_ballots_2,
        avg_ranking_distance,
        min_ranking_distance,
        max_ranking_distance,
        strong_coalition_votes,
        weak_coalition_votes,
        basic_affinity_score,
        proximity_weighted_affinity,
        coalition_strength_score,
        coalition_type
    FROM adjacent_pairs
    WHERE shared_ballots >= ?
    ORDER BY coalition_strength_score DESC
    """

    return database.query_with_retry(query.replace("?", str(min_shared_ballots)))


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
        summary_dict = dict(zip(summary["metric"], summary["value"]))

        return templates.TemplateResponse(
            "dashboard.html", {"request": request, "summary": summary_dict}
        )
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return templates.TemplateResponse(
            "error.html", {"request": request, "error": str(e)}
        )


@app.get("/api/summary")
async def get_summary():
    """Get summary statistics."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    summary = database.query_with_retry("SELECT * FROM summary_stats")
    return summary.to_dict("records")


@app.get("/api/candidates")
async def get_candidates():
    """Get list of all candidates."""
    database = get_database()
    if not database or not database.table_exists("candidates"):
        raise HTTPException(status_code=400, detail="No data loaded")

    candidates = database.query_with_retry(
        "SELECT * FROM candidates ORDER BY candidate_name"
    )
    return candidates.to_dict("records")


@app.get("/api/first-choice")
async def get_first_choice_results():
    """Get first choice voting results."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    results = database.query_with_retry("SELECT * FROM first_choice_totals")
    return results.to_dict("records")


@app.get("/api/votes-by-rank")
async def get_votes_by_rank():
    """Get vote distribution by rank position."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    results = database.query(
        "SELECT * FROM votes_by_rank WHERE rank_order <= 5 ORDER BY rank_position, rank_order"
    )
    return results.to_dict("records")


@app.get("/api/ballot/{ballot_id}")
async def get_ballot(ballot_id: str):
    """Get details for a specific ballot."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    ballot = database.query(
        f"""
        SELECT
            rank_position,
            candidate_name,
            candidate_id
        FROM ballots_long
        WHERE BallotID = '{ballot_id}'
        ORDER BY rank_position
    """
    )

    if ballot.empty:
        raise HTTPException(status_code=404, detail="Ballot not found")

    return ballot.to_dict("records")


@app.get("/api/search-ballots")
async def search_ballots(candidate: str, rank: int = 1, limit: int = 10):
    """Search for ballots that rank a candidate at a specific position."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    results = database.query(
        f"""
        SELECT DISTINCT
            bl.BallotID,
            bc.ranking_sequence
        FROM ballots_long bl
        JOIN ballot_completion bc ON bl.BallotID = bc.BallotID
        WHERE bl.candidate_name = '{candidate}'
          AND bl.rank_position = {rank}
        LIMIT {limit}
    """
    )

    return results.to_dict("records")


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
            "final_results": final_results.to_dict("records"),
            "round_summary": round_summary.to_dict("records"),
            "winners": tabulator.winners,
            "total_rounds": len(rounds),
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
                    "total_continuing_votes": r.total_continuing_votes,
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
                    "ballot_count": p.ballot_count,
                }
                for p in vote_flow.transfer_patterns
            ],
            "candidate_flow_summary": vote_flow.candidate_flow_summary,
            "flow_metadata": vote_flow.flow_metadata,
        }

        return flow_data

    except Exception as e:
        logger.error(f"Error generating vote flow data: {e}")
        raise HTTPException(
            status_code=500, detail=f"Vote flow generation failed: {str(e)}"
        )


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
                "ballot_count": p.ballot_count,
            }
            for p in vote_flow.transfer_patterns
            if p.round_number == round_number
        ]

        if not round_transfers:
            raise HTTPException(
                status_code=404, detail=f"No transfers found for round {round_number}"
            )

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
                    "total_continuing_votes": r.total_continuing_votes,
                }
                break

        return {
            "round_info": round_info,
            "transfers": round_transfers,
            "transfer_count": len(round_transfers),
        }

    except Exception as e:
        logger.error(f"Error getting round transfers: {e}")
        raise HTTPException(
            status_code=500, detail=f"Round transfer lookup failed: {str(e)}"
        )


@app.get("/api/candidate-analysis/{candidate_name}")
async def analyze_candidate(candidate_name: str):
    """Get detailed analysis for a specific candidate."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        # Get candidate's vote totals by rank
        vote_totals = database.query(
            f"""
            SELECT
                rank_position,
                COUNT(*) as votes,
                ROUND(100.0 * COUNT(*) / (SELECT COUNT(DISTINCT BallotID) FROM ballots_long), 2) as percentage
            FROM ballots_long
            WHERE candidate_name = '{candidate_name}'
            GROUP BY rank_position
            ORDER BY rank_position
        """
        )

        # Get who their first-choice supporters also rank
        database.query(
            "CREATE TABLE IF NOT EXISTS temp_analysis AS SELECT * FROM analyze_candidate_partners(?)"
        )
        partners = database.query(
            f"SELECT * FROM analyze_candidate_partners('{candidate_name}') WHERE rank_within_position <= 3"
        )

        return {
            "candidate_name": candidate_name,
            "vote_totals": vote_totals.to_dict("records"),
            "top_partners": partners.to_dict("records"),
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
        temp_path, media_type="text/csv", filename="election_summary.csv"
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
        temp_path, media_type="text/csv", filename="first_choice_results.csv"
    )


@app.get("/api/verify-results")
async def verify_results(
    official_results_path: str = "2024-12-02_15-04-45_report_official.csv",
):
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
        raise HTTPException(
            status_code=404,
            detail=f"Official results file not found: {official_results_path}",
        )

    try:
        # Run our STV tabulation
        tabulator = STVTabulator(database, seats=3)
        rounds = tabulator.run_stv_tabulation()

        # Get our results
        candidates = database.query(
            "SELECT candidate_id, candidate_name FROM candidates"
        )
        first_choice = database.query("SELECT * FROM first_choice_totals")

        # Verify against official results
        verifier = ResultsVerifier(str(official_path))
        verification_results = verifier.verify_results(
            our_winners=tabulator.winners,
            our_candidates=candidates,
            our_first_choice=first_choice,
        )

        # Generate readable report
        report = verifier.generate_verification_report(verification_results)

        return {
            "verification_passed": verification_results["verification_passed"],
            "winners_match": verification_results["winners_match"],
            "official_winners": verification_results["official_winners"],
            "our_winners": verification_results["our_winners"],
            "total_vote_difference": verification_results["total_vote_difference"],
            "vote_comparisons": verification_results["vote_comparisons"].to_dict(
                "records"
            ),
            "report": report,
            "official_metadata": verification_results["official_metadata"],
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
        affinities = analyzer.calculate_pairwise_affinity(
            min_shared_ballots=min_shared_ballots
        )

        # Convert to JSON-serializable format
        result = []
        for affinity in affinities:
            result.append(
                {
                    "candidate_1": affinity.candidate_1,
                    "candidate_1_name": affinity.candidate_1_name,
                    "candidate_2": affinity.candidate_2,
                    "candidate_2_name": affinity.candidate_2_name,
                    "shared_ballots": affinity.shared_ballots,
                    "total_ballots_1": affinity.total_ballots_1,
                    "total_ballots_2": affinity.total_ballots_2,
                    "affinity_score": round(affinity.affinity_score, 4),
                    "overlap_percentage": round(affinity.overlap_percentage, 2),
                }
            )

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
        candidate_query = database.query(
            f"SELECT candidate_name FROM candidates WHERE candidate_id = {candidate_id}"
        )
        if candidate_query.empty:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate_name = candidate_query.iloc[0]["candidate_name"]

        # Convert to list format
        transfer_list = []
        for cand_id, info in transfers.items():
            transfer_list.append(
                {
                    "candidate_id": cand_id,
                    "candidate_name": info["candidate_name"],
                    "transfer_votes": info["transfer_votes"],
                    "avg_rank_position": info["avg_rank_position"],
                    "transfer_percentage": round(info["transfer_percentage"], 2),
                }
            )

        # Sort by transfer votes descending
        transfer_list.sort(key=lambda x: x["transfer_votes"], reverse=True)

        return {
            "from_candidate_id": candidate_id,
            "from_candidate_name": candidate_name,
            "transfers": transfer_list,
            "total_transfers": sum(t["transfer_votes"] for t in transfer_list),
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
            affinities_json.append(
                {
                    "candidate_1": affinity.candidate_1,
                    "candidate_1_name": affinity.candidate_1_name,
                    "candidate_2": affinity.candidate_2,
                    "candidate_2_name": affinity.candidate_2_name,
                    "shared_ballots": affinity.shared_ballots,
                    "affinity_score": round(affinity.affinity_score, 4),
                    "overlap_percentage": round(affinity.overlap_percentage, 2),
                }
            )

        return {
            "candidate_id": summary["candidate_id"],
            "candidate_name": summary["candidate_name"],
            "total_ballots": summary["total_ballots"],
            "top_affinities": affinities_json,
            "vote_transfers": summary["vote_transfers"],
            "coalition_strength": summary["coalition_strength"],
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
                            "other_candidate": (
                                affinity.candidate_2_name
                                if affinity.candidate_1 == winner_id
                                else affinity.candidate_1_name
                            ),
                            "shared_ballots": int(affinity.shared_ballots),
                            "affinity_score": round(float(affinity.affinity_score), 4),
                        }
                        for affinity in summary["top_affinities"][:3]
                    ],
                    "top_3_transfers": [
                        {
                            "to_candidate": info["candidate_name"],
                            "transfer_votes": info["transfer_votes"],
                            "transfer_percentage": round(
                                info["transfer_percentage"], 2
                            ),
                        }
                        for info in list(summary["vote_transfers"].values())[:3]
                    ],
                }

        return {"winner_coalitions": winner_analysis}
    except Exception as e:
        logger.error(f"Winner coalition analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/coalition/pairs/all")
async def get_all_candidate_pairs_analysis(
    min_shared_ballots: int = 50,
    method: str = "proximity_weighted",
    normalize: str = "raw",
    ballot_length_filter: bool = False,
    confidence_intervals: bool = False,
):
    """
    Get detailed analysis for all candidate pairs with enhanced statistical controls.

    Args:
        min_shared_ballots: Minimum shared ballots to include in results
        method: Statistical method - "basic", "proximity_weighted", "directional"
        normalize: Normalization approach - "raw", "conditional", "lift"
        ballot_length_filter: Filter to ballots with sufficient length for both candidates
        confidence_intervals: Calculate bootstrap confidence intervals
    """
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        # Check if we can use precomputed data (only if using exact default parameters)
        use_precomputed = (
            has_precomputed_data()
            and method == "proximity_weighted"
            and normalize == "raw"
            and not ballot_length_filter
            and not confidence_intervals
        )

        if use_precomputed:
            logger.info(
                f"Using precomputed data for coalition pairs (min_shared_ballots={min_shared_ballots})"
            )
            pairs_df = get_precomputed_pairs(min_shared_ballots)

            # Convert to the expected format
            result = []
            for _, pair in pairs_df.iterrows():
                result.append(
                    {
                        "candidate_1": int(pair["candidate_1"]),
                        "candidate_1_name": pair["candidate_1_name"],
                        "candidate_2": int(pair["candidate_2"]),
                        "candidate_2_name": pair["candidate_2_name"],
                        "shared_ballots": int(pair["shared_ballots"]),
                        "total_ballots_1": int(pair["total_ballots_1"]),
                        "total_ballots_2": int(pair["total_ballots_2"]),
                        "avg_ranking_distance": round(
                            float(pair["avg_ranking_distance"]), 2
                        ),
                        "min_ranking_distance": int(pair["min_ranking_distance"]),
                        "max_ranking_distance": int(pair["max_ranking_distance"]),
                        "strong_coalition_votes": int(pair["strong_coalition_votes"]),
                        "weak_coalition_votes": int(pair["weak_coalition_votes"]),
                        "transfer_votes_1_to_2": 0,  # Not precomputed yet, can add later
                        "transfer_votes_2_to_1": 0,  # Not precomputed yet, can add later
                        "basic_affinity_score": round(
                            float(pair["basic_affinity_score"]), 4
                        ),
                        "proximity_weighted_affinity": round(
                            float(pair["proximity_weighted_affinity"]), 4
                        ),
                        "coalition_strength_score": round(
                            float(pair["coalition_strength_score"]), 4
                        ),
                        "coalition_type": pair["coalition_type"],
                    }
                )

            final_result = {"detailed_pairs": result, "count": len(result)}
            return convert_numpy_types(final_result)

        else:
            # Use live computation with enhanced toggle controls
            if use_precomputed is False:
                logger.info(
                    f"Using enhanced coalition analysis with method={method}, normalize={normalize}, ballot_length_filter={ballot_length_filter}"
                )
            else:
                logger.warning(
                    "Precomputed data not available, falling back to live computation"
                )
            analyzer = CoalitionAnalyzer(database)
            detailed_pairs = analyzer.calculate_detailed_pairwise_analysis(
                min_shared_ballots=min_shared_ballots,
                method=method,
                normalize=normalize,
                ballot_length_filter=ballot_length_filter,
                confidence_intervals=confidence_intervals,
            )

            # Convert to JSON-serializable format
            result = []
            for pair in detailed_pairs:
                result.append(
                    {
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
                        "next_choice_rate_a_to_b": round(pair.next_choice_rate_a_to_b, 2),
                        "next_choice_rate_b_to_a": round(pair.next_choice_rate_b_to_a, 2),
                        "close_together_rate": round(pair.close_together_rate, 2),
                        "follow_through_a_to_b": round(pair.follow_through_a_to_b, 2),
                        "follow_through_b_to_a": round(pair.follow_through_b_to_a, 2),
                        "basic_affinity_score": round(pair.basic_affinity_score, 4),
                        "normalized_affinity_score": round(
                            pair.normalized_affinity_score, 4
                        ),
                        "proximity_weighted_affinity": round(
                            pair.proximity_weighted_affinity, 4
                        ),
                        "coalition_strength_score": round(
                            pair.coalition_strength_score, 4
                        ),
                        "coalition_type": pair.coalition_type,
                    }
                )

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
        # Try to use precomputed data first
        if has_precomputed_data():
            logger.info(
                f"Using precomputed data for pair analysis: {candidate_1_id} vs {candidate_2_id}"
            )

            # Query for specific pair (handle both orderings since we store candidate_1 < candidate_2)
            query = """
            SELECT * FROM adjacent_pairs
            WHERE (candidate_1 = ? AND candidate_2 = ?)
               OR (candidate_1 = ? AND candidate_2 = ?)
            """

            pairs_df = database.query_with_retry(
                query.replace("?", "{}").format(
                    min(candidate_1_id, candidate_2_id),
                    max(candidate_1_id, candidate_2_id),
                    max(candidate_1_id, candidate_2_id),
                    min(candidate_1_id, candidate_2_id),
                )
            )

            if pairs_df.empty:
                raise HTTPException(
                    status_code=404,
                    detail="Candidate pair not found or insufficient shared ballots",
                )

            pair = pairs_df.iloc[0]

            # Prepare the result with precomputed data
            result = {
                "pair_analysis": {
                    "candidate_1": int(pair["candidate_1"]),
                    "candidate_1_name": pair["candidate_1_name"],
                    "candidate_2": int(pair["candidate_2"]),
                    "candidate_2_name": pair["candidate_2_name"],
                    "shared_ballots": int(pair["shared_ballots"]),
                    "total_ballots_1": int(pair["total_ballots_1"]),
                    "total_ballots_2": int(pair["total_ballots_2"]),
                    "avg_ranking_distance": round(
                        float(pair["avg_ranking_distance"]), 2
                    ),
                    "min_ranking_distance": int(pair["min_ranking_distance"]),
                    "max_ranking_distance": int(pair["max_ranking_distance"]),
                    "strong_coalition_votes": int(pair["strong_coalition_votes"]),
                    "weak_coalition_votes": int(pair["weak_coalition_votes"]),
                    "transfer_votes_1_to_2": 0,  # Not precomputed yet
                    "transfer_votes_2_to_1": 0,  # Not precomputed yet
                    "basic_affinity_score": round(
                        float(pair["basic_affinity_score"]), 4
                    ),
                    "proximity_weighted_affinity": round(
                        float(pair["proximity_weighted_affinity"]), 4
                    ),
                    "coalition_strength_score": round(
                        float(pair["coalition_strength_score"]), 4
                    ),
                    "coalition_type": pair["coalition_type"],
                },
                "proximity_analysis": {
                    "avg_distance": round(float(pair["avg_ranking_distance"]), 2),
                    "min_distance": int(pair["min_ranking_distance"]),
                    "max_distance": int(pair["max_ranking_distance"]),
                    "strong_proximity_votes": int(pair["strong_coalition_votes"]),
                    "weak_proximity_votes": int(pair["weak_coalition_votes"]),
                    "source": "precomputed",
                },
            }
            return convert_numpy_types(result)

        else:
            # Fallback to live computation
            logger.warning(
                "Precomputed data not available, falling back to live computation for pair analysis"
            )
            analyzer = CoalitionAnalyzer(database)
            pair = analyzer.get_detailed_pair_analysis(candidate_1_id, candidate_2_id)

            if not pair:
                raise HTTPException(
                    status_code=404,
                    detail="Candidate pair not found or insufficient data",
                )

            # Also get proximity analysis
            proximity = analyzer.analyze_ranking_proximity(
                candidate_1_id, candidate_2_id
            )

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
                    "proximity_weighted_affinity": round(
                        pair.proximity_weighted_affinity, 4
                    ),
                    "coalition_strength_score": round(pair.coalition_strength_score, 4),
                    "coalition_type": pair.coalition_type,
                },
                "proximity_analysis": proximity,
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


@app.get("/api/coalition/directional/{candidate_1_id}/{candidate_2_id}")
async def get_directional_analysis(candidate_1_id: int, candidate_2_id: int):
    """Get detailed directional analysis for a specific candidate pair using the 3 Core Questions Framework."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        analyzer = CoalitionAnalyzer(database)
        
        # Get detailed pair analysis with directional metrics
        pair = analyzer.get_detailed_pair_analysis(candidate_1_id, candidate_2_id)
        if not pair:
            raise HTTPException(
                status_code=404, 
                detail="Candidate pair not found or insufficient shared ballots"
            )

        # Return just the directional metrics with explanations
        result = {
            "candidate_1_id": pair.candidate_1,
            "candidate_1_name": pair.candidate_1_name,
            "candidate_2_id": pair.candidate_2,
            "candidate_2_name": pair.candidate_2_name,
            "directional_analysis": {
                "next_choice_rate_a_to_b": {
                    "value": round(pair.next_choice_rate_a_to_b, 2),
                    "explanation": f"Of ballots that ranked {pair.candidate_1_name} anywhere, {pair.next_choice_rate_a_to_b:.1f}% had {pair.candidate_2_name} immediately after",
                    "question": "Next Choice Rate (A → B)"
                },
                "next_choice_rate_b_to_a": {
                    "value": round(pair.next_choice_rate_b_to_a, 2),
                    "explanation": f"Of ballots that ranked {pair.candidate_2_name} anywhere, {pair.next_choice_rate_b_to_a:.1f}% had {pair.candidate_1_name} immediately after",
                    "question": "Next Choice Rate (B → A)"
                },
                "close_together_rate": {
                    "value": round(pair.close_together_rate, 2),
                    "explanation": f"{pair.close_together_rate:.1f}% of ballots that ranked both candidates had them both in the top 3 spots",
                    "question": "Close-Together Rate (A & B)"
                },
                "follow_through_a_to_b": {
                    "value": round(pair.follow_through_a_to_b, 2),
                    "explanation": f"When {pair.candidate_1_name} supporters' votes would transfer, {pair.follow_through_a_to_b:.1f}% actually went to {pair.candidate_2_name}",
                    "question": "Follow-Through (A → B reality)"
                },
                "follow_through_b_to_a": {
                    "value": round(pair.follow_through_b_to_a, 2),
                    "explanation": f"When {pair.candidate_2_name} supporters' votes would transfer, {pair.follow_through_b_to_a:.1f}% actually went to {pair.candidate_1_name}",
                    "question": "Follow-Through (B → A reality)"
                }
            },
            "summary_insights": {
                "bidirectional": bool(abs(pair.next_choice_rate_a_to_b - pair.next_choice_rate_b_to_a) <= 5.0),
                "strong_affinity": bool(pair.close_together_rate >= 50.0),
                "high_follow_through": bool(max(pair.follow_through_a_to_b, pair.follow_through_b_to_a) >= 20.0)
            }
        }
        
        return convert_numpy_types(result)

    except Exception as e:
        logger.error(f"Directional analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/coalition/network")
async def get_coalition_network_data(
    min_shared_ballots: int = 200, min_strength: float = 0.25
):
    """Get network graph data for coalition visualization."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        # Try to use precomputed data first (5-20x faster)
        if has_precomputed_data():
            logger.info(
                f"Using precomputed data for network graph (min_shared_ballots={min_shared_ballots}, min_strength={min_strength})"
            )

            # Get candidate metrics from precomputed table
            candidates = database.query_with_retry(
                """
                SELECT
                    candidate_id,
                    candidate_name,
                    weighted_score,
                    total_connections,
                    position_type
                FROM candidate_metrics
                ORDER BY candidate_name
            """
            )

            # Create nodes data using precomputed metrics
            nodes = []
            winners = [36, 46, 55]  # Portland winners
            for _, candidate in candidates.iterrows():
                candidate_id = candidate["candidate_id"]

                nodes.append(
                    {
                        "id": str(candidate_id),
                        "name": candidate["candidate_name"],
                        "votes": int(candidate["weighted_score"]),
                        "connections": int(candidate["total_connections"]),
                        "positionType": candidate["position_type"],
                        "isWinner": candidate_id in winners,
                        "group": "winner" if candidate_id in winners else "candidate",
                    }
                )

            # Get edges from precomputed adjacent pairs
            pairs_df = get_precomputed_pairs(min_shared_ballots)

            # Filter by coalition strength and create edges
            edges = []
            for _, pair in pairs_df.iterrows():
                if float(pair["coalition_strength_score"]) >= min_strength:
                    edges.append(
                        {
                            "source": str(pair["candidate_1"]),
                            "target": str(pair["candidate_2"]),
                            "strength": round(
                                float(pair["coalition_strength_score"]), 4
                            ),
                            "sharedBallots": int(pair["shared_ballots"]),
                            "avgDistance": round(
                                float(pair["avg_ranking_distance"]), 2
                            ),
                            "coalitionType": pair["coalition_type"],
                            "strongVotes": int(pair["strong_coalition_votes"]),
                            "weakVotes": int(pair["weak_coalition_votes"]),
                            "basicAffinity": round(
                                float(pair["basic_affinity_score"]), 4
                            ),
                            "proximityAffinity": round(
                                float(pair["proximity_weighted_affinity"]), 4
                            ),
                        }
                    )

            logger.info(
                f"Network: {len(nodes)} nodes, {len(edges)} edges from precomputed data"
            )

        else:
            # Fallback to live computation
            logger.warning(
                "Precomputed data not available, falling back to live computation for network data"
            )
            analyzer = CoalitionAnalyzer(database)

            # Get all candidates for nodes
            candidates = database.query_with_retry(
                "SELECT candidate_id, candidate_name FROM candidates ORDER BY candidate_name"
            )

            # Get ranking-weighted scores for each candidate (1st=6pts, 2nd=5pts, 3rd=4pts, etc.)
            candidate_weighted_scores = database.query_with_retry(
                """
                SELECT
                    candidate_id,
                    SUM(CASE
                        WHEN rank_position = 1 THEN 6
                        WHEN rank_position = 2 THEN 5
                        WHEN rank_position = 3 THEN 4
                        WHEN rank_position = 4 THEN 3
                        WHEN rank_position = 5 THEN 2
                        WHEN rank_position = 6 THEN 1
                        ELSE 0
                    END) as weighted_score
                FROM ballots_long
                GROUP BY candidate_id
            """
            )
            metrics_lookup = dict(
                zip(
                    candidate_weighted_scores["candidate_id"],
                    candidate_weighted_scores["weighted_score"],
                )
            )

            # Create nodes data
            nodes = []
            winners = [36, 46, 55]  # Portland winners
            for _, candidate in candidates.iterrows():
                candidate_id = candidate["candidate_id"]
                vote_count = metrics_lookup.get(candidate_id, 0)

                nodes.append(
                    {
                        "id": str(candidate_id),
                        "name": candidate["candidate_name"],
                        "votes": vote_count,
                        "isWinner": candidate_id in winners,
                        "group": "winner" if candidate_id in winners else "candidate",
                    }
                )

            # Get detailed pairs for edges
            detailed_pairs = analyzer.calculate_detailed_pairwise_analysis(
                min_shared_ballots=min_shared_ballots
            )

            # Create edges data
            edges = []
            for pair in detailed_pairs:
                if pair.coalition_strength_score >= min_strength:
                    edges.append(
                        {
                            "source": str(pair.candidate_1),
                            "target": str(pair.candidate_2),
                            "strength": round(pair.coalition_strength_score, 4),
                            "sharedBallots": pair.shared_ballots,
                            "avgDistance": round(pair.avg_ranking_distance, 2),
                            "coalitionType": pair.coalition_type,
                            "strongVotes": pair.strong_coalition_votes,
                            "weakVotes": pair.weak_coalition_votes,
                            "basicAffinity": round(pair.basic_affinity_score, 4),
                            "proximityAffinity": round(
                                pair.proximity_weighted_affinity, 4
                            ),
                        }
                    )

        # Calculate network statistics
        network_stats = {
            "totalNodes": len(nodes),
            "totalEdges": len(edges),
            "avgCoalitionStrength": (
                round(sum(e["strength"] for e in edges) / len(edges), 4) if edges else 0
            ),
            "strongCoalitions": len(
                [e for e in edges if e["coalitionType"] == "strong"]
            ),
            "moderateCoalitions": len(
                [e for e in edges if e["coalitionType"] == "moderate"]
            ),
            "weakCoalitions": len([e for e in edges if e["coalitionType"] == "weak"]),
            "strategicCoalitions": len(
                [e for e in edges if e["coalitionType"] == "strategic"]
            ),
        }

        result = {
            "nodes": nodes,
            "edges": edges,
            "stats": network_stats,
            "metadata": {
                "minSharedBallots": min_shared_ballots,
                "minStrength": min_strength,
                "generatedAt": pd.Timestamp.now().isoformat(),
            },
        }

        return convert_numpy_types(result)

    except Exception as e:
        logger.error(f"Coalition network data generation failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Network generation failed: {str(e)}"
        )


@app.get("/api/coalition/clusters")
async def get_coalition_clusters(min_strength: float = 0.2, min_group_size: int = 3):
    """Get automatically detected coalition clusters."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        analyzer = CoalitionAnalyzer(database)

        # Detect clusters
        clusters = analyzer.detect_coalition_clusters(
            min_strength=min_strength, min_group_size=min_group_size
        )

        # Get detailed analysis
        cluster_analysis = analyzer.get_cluster_analysis(clusters)

        return convert_numpy_types(cluster_analysis)

    except Exception as e:
        logger.error(f"Coalition clustering failed: {e}")
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


# Candidates Page and Enhanced API Endpoints
@app.get("/candidates")
async def candidates_page(request: Request):
    """Candidates exploration page."""
    return templates.TemplateResponse("candidates.html", {"request": request})


@app.get("/api/candidates/enhanced")
async def get_enhanced_candidates_list():
    """Get list of all candidates with enhanced summary metrics."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        metrics_analyzer = CandidateMetrics(database)
        candidates_summary = metrics_analyzer.get_all_candidates_summary()

        return convert_numpy_types(
            {"candidates": candidates_summary, "count": len(candidates_summary)}
        )
    except Exception as e:
        logger.error(f"Enhanced candidates list failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/candidates/{candidate_id}/profile")
async def get_candidate_profile(candidate_id: int):
    """Get comprehensive candidate profile with all advanced metrics."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        metrics_analyzer = CandidateMetrics(database)
        profile = metrics_analyzer.get_comprehensive_candidate_profile(candidate_id)

        if not profile:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Convert dataclass to dict for JSON serialization
        profile_dict = {
            "candidate_id": profile.candidate_id,
            "candidate_name": profile.candidate_name,
            "total_ballots": profile.total_ballots,
            "first_choice_votes": profile.first_choice_votes,
            "first_choice_percentage": profile.first_choice_percentage,
            "vote_strength_index": profile.vote_strength_index,
            "cross_camp_appeal": profile.cross_camp_appeal,
            "transfer_efficiency": profile.transfer_efficiency,
            "ranking_consistency": profile.ranking_consistency,
            "elimination_round": profile.elimination_round,
            "final_status": profile.final_status,
            "vote_progression": profile.vote_progression,
            "top_coalition_partners": profile.top_coalition_partners,
            "supporter_demographics": profile.supporter_demographics,
        }

        return convert_numpy_types(profile_dict)
    except Exception as e:
        logger.error(f"Candidate profile failed for {candidate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/candidates/{candidate_id}/supporters")
async def get_candidate_supporters_analysis(candidate_id: int):
    """Get detailed supporter analysis for a candidate."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        metrics_analyzer = CandidateMetrics(database)
        voter_behavior = metrics_analyzer.get_voter_behavior_analysis(candidate_id)

        if not voter_behavior:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Convert dataclass to dict
        behavior_dict = {
            "candidate_id": voter_behavior.candidate_id,
            "candidate_name": voter_behavior.candidate_name,
            "bullet_voters": voter_behavior.bullet_voters,
            "bullet_voter_percentage": voter_behavior.bullet_voter_percentage,
            "avg_ranking_position": voter_behavior.avg_ranking_position,
            "ranking_distribution": voter_behavior.ranking_distribution,
            "consistency_score": voter_behavior.consistency_score,
            "polarization_index": voter_behavior.polarization_index,
        }

        return convert_numpy_types(behavior_dict)
    except Exception as e:
        logger.error(f"Supporter analysis failed for {candidate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/candidates/{candidate_id}/transfers")
async def get_candidate_transfer_analysis(candidate_id: int):
    """Get detailed transfer efficiency analysis for a candidate."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        metrics_analyzer = CandidateMetrics(database)
        transfer_analysis = metrics_analyzer.get_transfer_efficiency_analysis(
            candidate_id
        )

        if not transfer_analysis:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Convert dataclass to dict
        transfer_dict = {
            "candidate_id": transfer_analysis.candidate_id,
            "candidate_name": transfer_analysis.candidate_name,
            "total_transferable_votes": transfer_analysis.total_transferable_votes,
            "successful_transfers": transfer_analysis.successful_transfers,
            "transfer_efficiency_rate": transfer_analysis.transfer_efficiency_rate,
            "avg_transfer_distance": transfer_analysis.avg_transfer_distance,
            "top_transfer_destinations": transfer_analysis.top_transfer_destinations,
            "transfer_pattern_type": transfer_analysis.transfer_pattern_type,
        }

        return convert_numpy_types(transfer_dict)
    except Exception as e:
        logger.error(f"Transfer analysis failed for {candidate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/candidates/{candidate_id}/comparison/{other_candidate_id}")
async def get_candidate_comparison(candidate_id: int, other_candidate_id: int):
    """Get head-to-head comparison between two candidates."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        metrics_analyzer = CandidateMetrics(database)

        # Get profiles for both candidates
        profile1 = metrics_analyzer.get_comprehensive_candidate_profile(candidate_id)
        profile2 = metrics_analyzer.get_comprehensive_candidate_profile(
            other_candidate_id
        )

        if not profile1 or not profile2:
            raise HTTPException(
                status_code=404, detail="One or both candidates not found"
            )

        # Get coalition analysis between the two
        coalition_analyzer = CoalitionAnalyzer(database)
        pair_analysis = coalition_analyzer.get_detailed_pair_analysis(
            candidate_id, other_candidate_id
        )

        comparison = {
            "candidate_1": {
                "candidate_id": profile1.candidate_id,
                "candidate_name": profile1.candidate_name,
                "first_choice_votes": profile1.first_choice_votes,
                "first_choice_percentage": profile1.first_choice_percentage,
                "vote_strength_index": profile1.vote_strength_index,
                "cross_camp_appeal": profile1.cross_camp_appeal,
                "transfer_efficiency": profile1.transfer_efficiency,
                "ranking_consistency": profile1.ranking_consistency,
            },
            "candidate_2": {
                "candidate_id": profile2.candidate_id,
                "candidate_name": profile2.candidate_name,
                "first_choice_votes": profile2.first_choice_votes,
                "first_choice_percentage": profile2.first_choice_percentage,
                "vote_strength_index": profile2.vote_strength_index,
                "cross_camp_appeal": profile2.cross_camp_appeal,
                "transfer_efficiency": profile2.transfer_efficiency,
                "ranking_consistency": profile2.ranking_consistency,
            },
            "coalition_analysis": (
                {
                    "shared_ballots": (
                        pair_analysis.shared_ballots if pair_analysis else 0
                    ),
                    "coalition_strength_score": (
                        pair_analysis.coalition_strength_score if pair_analysis else 0
                    ),
                    "coalition_type": (
                        pair_analysis.coalition_type
                        if pair_analysis
                        else "insufficient_data"
                    ),
                    "avg_ranking_distance": (
                        pair_analysis.avg_ranking_distance if pair_analysis else None
                    ),
                }
                if pair_analysis
                else None
            ),
        }

        return convert_numpy_types(comparison)
    except Exception as e:
        logger.error(
            f"Candidate comparison failed for {candidate_id} vs {other_candidate_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/candidates/{candidate_id}/ballot-journey")
async def get_candidate_ballot_journey(candidate_id: int):
    """Get detailed ballot journey analysis for a candidate."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        metrics_analyzer = CandidateMetrics(database)
        journey_data = metrics_analyzer.get_ballot_journey_analysis(candidate_id)

        if not journey_data:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Convert dataclass to dict for JSON serialization
        journey_dict = {
            "candidate_id": journey_data.candidate_id,
            "candidate_name": journey_data.candidate_name,
            "ballot_flows": journey_data.ballot_flows,
            "round_summaries": journey_data.round_summaries,
            "transfer_patterns": journey_data.transfer_patterns,
            "retention_analysis": journey_data.retention_analysis,
        }

        return convert_numpy_types(journey_dict)
    except Exception as e:
        logger.error(f"Ballot journey analysis failed for {candidate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/candidates/{candidate_id}/supporter-segments")
async def get_candidate_supporter_segments(candidate_id: int):
    """Get supporter segmentation analysis for a candidate."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        metrics_analyzer = CandidateMetrics(database)
        segmentation_data = metrics_analyzer.get_supporter_segmentation_analysis(
            candidate_id
        )

        if not segmentation_data:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Convert dataclass to dict for JSON serialization
        segmentation_dict = {
            "candidate_id": segmentation_data.candidate_id,
            "candidate_name": segmentation_data.candidate_name,
            "archetypes": [
                {
                    "archetype_name": archetype.archetype_name,
                    "ballot_count": archetype.ballot_count,
                    "percentage": archetype.percentage,
                    "characteristics": archetype.characteristics,
                    "sample_ballots": archetype.sample_ballots,
                }
                for archetype in segmentation_data.archetypes
            ],
            "clustering_analysis": segmentation_data.clustering_analysis,
            "preference_patterns": segmentation_data.preference_patterns,
        }

        return convert_numpy_types(segmentation_dict)
    except Exception as e:
        logger.error(f"Supporter segmentation failed for {candidate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/candidates/{candidate_id}/similarity")
async def get_candidate_similarity(candidate_id: int, limit: int = 10):
    """Find candidates with similar supporter profiles and ranking patterns."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        # Get the target candidate's supporter profile
        metrics_analyzer = CandidateMetrics(database)
        target_segmentation = metrics_analyzer.get_supporter_segmentation_analysis(
            candidate_id
        )

        if not target_segmentation:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Get all candidates for comparison
        candidates = database.query_with_retry(
            f"""
            SELECT candidate_id, candidate_name FROM candidates
            WHERE candidate_id != {candidate_id}
        """
        )

        similarity_scores = []

        for _, candidate in candidates.iterrows():
            other_id = candidate["candidate_id"]
            other_name = candidate["candidate_name"]

            # Calculate similarity based on supporter archetypes
            other_segmentation = metrics_analyzer.get_supporter_segmentation_analysis(
                other_id
            )

            if other_segmentation:
                # Simple similarity calculation based on archetype percentages
                target_archetypes = {
                    arch.archetype_name: arch.percentage
                    for arch in target_segmentation.archetypes
                }
                other_archetypes = {
                    arch.archetype_name: arch.percentage
                    for arch in other_segmentation.archetypes
                }

                # Calculate Euclidean distance between archetype distributions
                archetype_names = set(target_archetypes.keys()) | set(
                    other_archetypes.keys()
                )
                distance = 0
                for name in archetype_names:
                    target_pct = target_archetypes.get(name, 0)
                    other_pct = other_archetypes.get(name, 0)
                    distance += (target_pct - other_pct) ** 2

                similarity = max(
                    0, 100 - (distance**0.5)
                )  # Convert distance to similarity score

                similarity_scores.append(
                    {
                        "candidate_id": other_id,
                        "candidate_name": other_name,
                        "similarity_score": round(similarity, 2),
                        "shared_archetypes": list(
                            set(target_archetypes.keys()) & set(other_archetypes.keys())
                        ),
                        "archetype_comparison": {
                            "target": target_archetypes,
                            "other": other_archetypes,
                        },
                    }
                )

        # Sort by similarity score and limit results
        similarity_scores.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_similar = similarity_scores[:limit]

        return convert_numpy_types(
            {
                "candidate_id": candidate_id,
                "candidate_name": target_segmentation.candidate_name,
                "similar_candidates": top_similar,
                "analysis_method": "archetype_distribution_similarity",
            }
        )

    except Exception as e:
        logger.error(f"Candidate similarity analysis failed for {candidate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/candidates/{candidate_id}/round-progression")
async def get_candidate_round_progression(candidate_id: int, seats: int = 3):
    """Get detailed round-by-round progression for a candidate through STV."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        # Run STV with detailed tracking to get actual round progression
        tabulator = STVTabulator(database, seats=seats, detailed_tracking=True)
        rounds = tabulator.run_stv_tabulation()

        vote_flow = tabulator.get_vote_flow()
        if not vote_flow:
            raise HTTPException(status_code=500, detail="Vote flow tracking failed")

        # Extract progression data for the specific candidate
        candidate_progression = []

        for round_data in vote_flow.rounds:
            if candidate_id in round_data.vote_totals:
                round_info = {
                    "round_number": round_data.round_number,
                    "vote_total": round_data.vote_totals.get(candidate_id, 0),
                    "quota": round_data.quota,
                    "is_continuing": candidate_id in round_data.continuing_candidates,
                    "is_winner_this_round": candidate_id
                    in round_data.winners_this_round,
                    "is_eliminated_this_round": candidate_id
                    in round_data.eliminated_this_round,
                    "vote_change": 0,  # Will calculate below
                    "transfers_in": [],
                    "transfers_out": [],
                }

                # Calculate vote change from previous round
                if candidate_progression:
                    prev_votes = candidate_progression[-1]["vote_total"]
                    round_info["vote_change"] = round_info["vote_total"] - prev_votes

                candidate_progression.append(round_info)

        # Add transfer details
        for transfer in vote_flow.transfer_patterns:
            if transfer.to_candidate == candidate_id:
                # Find the corresponding round
                for round_info in candidate_progression:
                    if round_info["round_number"] == transfer.round_number:
                        round_info["transfers_in"].append(
                            {
                                "from_candidate": transfer.from_candidate,
                                "from_candidate_name": transfer.from_candidate_name,
                                "votes_transferred": transfer.votes_transferred,
                                "transfer_type": transfer.transfer_type,
                            }
                        )

            elif transfer.from_candidate == candidate_id:
                # Find the corresponding round
                for round_info in candidate_progression:
                    if round_info["round_number"] == transfer.round_number:
                        round_info["transfers_out"].append(
                            {
                                "to_candidate": transfer.to_candidate,
                                "to_candidate_name": transfer.to_candidate_name,
                                "votes_transferred": transfer.votes_transferred,
                                "transfer_type": transfer.transfer_type,
                            }
                        )

        # Get candidate name
        candidate_query = database.query_with_retry(
            f"""
            SELECT candidate_name FROM candidates WHERE candidate_id = {candidate_id}
        """
        )
        candidate_name = (
            candidate_query.iloc[0]["candidate_name"]
            if not candidate_query.empty
            else f"Candidate {candidate_id}"
        )

        return convert_numpy_types(
            {
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "round_progression": candidate_progression,
                "final_status": (
                    "winner"
                    if any(r["is_winner_this_round"] for r in candidate_progression)
                    else "eliminated"
                ),
                "elimination_round": next(
                    (
                        r["round_number"]
                        for r in candidate_progression
                        if r["is_eliminated_this_round"]
                    ),
                    None,
                ),
                "max_votes": max(
                    (r["vote_total"] for r in candidate_progression), default=0
                ),
                "total_rounds": len(candidate_progression),
            }
        )

    except Exception as e:
        logger.error(f"Round progression analysis failed for {candidate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/candidates/{candidate_id}/coalition-centrality")
async def get_candidate_coalition_centrality(candidate_id: int):
    """Get coalition network centrality analysis for a candidate."""
    database = get_database()
    if not database or not database.table_exists("ballots_long"):
        raise HTTPException(status_code=400, detail="No data loaded")

    try:
        metrics_analyzer = CandidateMetrics(database)
        centrality_data = metrics_analyzer.get_coalition_centrality_analysis(
            candidate_id
        )

        if "error" in centrality_data:
            raise HTTPException(status_code=404, detail=centrality_data["error"])

        return convert_numpy_types(centrality_data)
    except Exception as e:
        logger.error(f"Coalition centrality analysis failed for {candidate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
