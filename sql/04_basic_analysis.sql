-- Basic analysis queries for exploring the voting data

-- Analysis 1: First choice vote totals for all candidates
CREATE OR REPLACE VIEW first_choice_totals AS
SELECT
    candidate_id,
    candidate_name,
    COUNT(*) as first_choice_votes,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(DISTINCT BallotID) FROM ballots_long), 2) as percentage
FROM ballots_long
WHERE rank_position = 1
GROUP BY candidate_id, candidate_name
ORDER BY first_choice_votes DESC;

-- Analysis 2: Vote totals by rank position (who dominates each rank)
CREATE OR REPLACE VIEW votes_by_rank AS
WITH rank_totals AS (
    SELECT
        rank_position,
        candidate_name,
        COUNT(*) as total_votes
    FROM ballots_long
    GROUP BY rank_position, candidate_name
),
ranked AS (
    SELECT
        rank_position,
        candidate_name,
        total_votes,
        ROW_NUMBER() OVER (PARTITION BY rank_position ORDER BY total_votes DESC) as rank_order
    FROM rank_totals
)
SELECT
    rank_position,
    candidate_name,
    total_votes,
    ROUND(100.0 * total_votes / (SELECT COUNT(DISTINCT BallotID) FROM ballots_long), 2) as percentage,
    rank_order
FROM ranked
ORDER BY rank_position, rank_order;

-- Analysis 3: Ballot completion patterns (how many ranks did voters use)
CREATE OR REPLACE VIEW ballot_completion AS
SELECT
    BallotID,
    COUNT(*) as ranks_used,
    MAX(rank_position) as highest_rank_used,
    STRING_AGG(candidate_name, ' -> ' ORDER BY rank_position) as ranking_sequence
FROM ballots_long
GROUP BY BallotID
ORDER BY ranks_used DESC, BallotID;

-- Analysis 4: Summary statistics
CREATE OR REPLACE VIEW summary_stats AS
SELECT
    'Total Ballots' as metric,
    COUNT(DISTINCT BallotID)::VARCHAR as value
FROM ballots_long
UNION ALL
SELECT
    'Total Candidates',
    COUNT(DISTINCT candidate_id)::VARCHAR
FROM ballots_long
UNION ALL
SELECT
    'Average Ranks Per Ballot',
    ROUND(AVG(ranks_used), 2)::VARCHAR
FROM ballot_completion
UNION ALL
SELECT
    'Most Common Ballot Length',
    MODE(ranks_used)::VARCHAR || ' ranks'
FROM ballot_completion;
