-- Extract candidate metadata from column headers
-- Creates a lookup table for all candidate voting columns

CREATE OR REPLACE TABLE candidate_columns AS
SELECT 
    column_name,
    -- Extract candidate ID (e.g., 36, 37, 38...)
    CAST(regexp_extract(column_name, 'Choice_(\d+)_1:', 1) AS INTEGER) as candidate_id,
    -- Extract rank position (1-6)
    CAST(regexp_extract(column_name, ':(\d+):Number of Winners', 1) AS INTEGER) as rank_position,
    -- Extract candidate name
    regexp_extract(column_name, 'Number of Winners \d+:([^:]+):NON', 1) as candidate_name
FROM information_schema.columns
WHERE table_name = 'rcv_data'
  AND column_name LIKE 'Choice_%'
  AND column_name NOT LIKE '%Uncertified%';  -- Exclude only uncertified write-ins

-- Create candidate lookup table (one row per candidate)
CREATE OR REPLACE TABLE candidates AS
SELECT DISTINCT 
    candidate_id, 
    candidate_name,
    COUNT(*) as rank_columns  -- Should be 6 (ranks 1-6)
FROM candidate_columns 
GROUP BY candidate_id, candidate_name
ORDER BY candidate_id;

-- Validation: Check we have expected number of candidates and ranks
SELECT 
    COUNT(*) as total_candidates,
    MIN(rank_columns) as min_ranks,
    MAX(rank_columns) as max_ranks,
    COUNT(*) * 6 as expected_total_columns,
    (SELECT COUNT(*) FROM candidate_columns) as actual_total_columns
FROM candidates;