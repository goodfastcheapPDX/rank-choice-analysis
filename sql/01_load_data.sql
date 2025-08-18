-- Load CVR data from CSV file
-- This script loads the raw Cast Vote Record data into DuckDB

CREATE OR REPLACE TABLE rcv_data AS
SELECT * FROM read_csv_auto(?, header=true);

-- Add basic validation
SELECT
    COUNT(*) as total_ballots,
    COUNT(DISTINCT BallotID) as unique_ballots,
    COUNT(*) - COUNT(DISTINCT BallotID) as duplicate_ballots
FROM rcv_data;
