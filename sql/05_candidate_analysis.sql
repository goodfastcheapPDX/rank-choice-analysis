-- Candidate-specific analysis queries
-- Reusable patterns for analyzing individual candidates and their supporters

-- Create a macro for analyzing candidate partners (who their supporters also rank)
CREATE OR REPLACE MACRO analyze_candidate_partners(target_candidate VARCHAR) AS TABLE
WITH target_first_ballots AS (
    SELECT DISTINCT BallotID
    FROM ballots_long
    WHERE candidate_name = target_candidate
      AND rank_position = 1
),
partner_analysis AS (
    SELECT
        rank_position,
        candidate_name,
        COUNT(*) as votes,
        ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM target_first_ballots), 2) as percentage
    FROM ballots_long bl
    WHERE bl.BallotID IN (SELECT BallotID FROM target_first_ballots)
      AND bl.candidate_name != target_candidate
      AND bl.rank_position IN (2, 3, 4, 5, 6)
    GROUP BY rank_position, candidate_name
)
SELECT
    rank_position,
    candidate_name,
    votes,
    percentage,
    ROW_NUMBER() OVER (PARTITION BY rank_position ORDER BY votes DESC) as rank_within_position
FROM partner_analysis
ORDER BY rank_position, votes DESC;

-- Create a macro for reverse analysis (who ranks this candidate but not first)
CREATE OR REPLACE MACRO analyze_candidate_supporters(target_candidate VARCHAR) AS TABLE
WITH target_non_first_ballots AS (
    SELECT DISTINCT bl1.BallotID, bl1.rank_position as target_rank
    FROM ballots_long bl1
    WHERE bl1.candidate_name = target_candidate
      AND bl1.rank_position > 1
      AND NOT EXISTS (
          SELECT 1
          FROM ballots_long bl2
          WHERE bl2.BallotID = bl1.BallotID
            AND bl2.candidate_name = target_candidate
            AND bl2.rank_position = 1
      )
)
SELECT
    'First choice of voters who rank ' || target_candidate || ' at rank ' || target_rank as analysis,
    bl.candidate_name as first_choice_candidate,
    COUNT(*) as votes,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM target_non_first_ballots WHERE target_rank = bl.rank_position), 2) as percentage
FROM ballots_long bl
JOIN target_non_first_ballots tnf ON bl.BallotID = tnf.BallotID
WHERE bl.rank_position = 1
GROUP BY target_rank, bl.candidate_name
ORDER BY target_rank, votes DESC;

-- Analysis: Most popular 2nd and 3rd choices for each candidate's first-choice voters
CREATE OR REPLACE VIEW candidate_coalition_patterns AS
WITH all_candidates AS (
    SELECT DISTINCT candidate_name FROM ballots_long WHERE rank_position = 1
),
coalition_data AS (
    SELECT
        ac.candidate_name as first_choice,
        bl.rank_position,
        bl.candidate_name as other_choice,
        COUNT(*) as votes
    FROM all_candidates ac
    JOIN ballots_long fc ON fc.candidate_name = ac.candidate_name AND fc.rank_position = 1
    JOIN ballots_long bl ON bl.BallotID = fc.BallotID
    WHERE bl.rank_position IN (2, 3)
      AND bl.candidate_name != ac.candidate_name
    GROUP BY ac.candidate_name, bl.rank_position, bl.candidate_name
),
ranked_coalitions AS (
    SELECT
        first_choice,
        rank_position,
        other_choice,
        votes,
        ROW_NUMBER() OVER (PARTITION BY first_choice, rank_position ORDER BY votes DESC) as choice_rank
    FROM coalition_data
)
SELECT
    first_choice,
    rank_position,
    other_choice,
    votes,
    choice_rank
FROM ranked_coalitions
WHERE choice_rank <= 3  -- Top 3 choices for each rank
ORDER BY first_choice, rank_position, choice_rank;
