# Data Processing Guide

This guide covers how to process Cast Vote Record (CVR) data for analysis.

## Overview

The data processing pipeline transforms wide-format CVR files into a normalized database optimized for STV analysis and visualization.

## Prerequisites

- CVR data file in CSV format (e.g., `City_of_Portland__Councilor__District_2_2024_11_29_17_26_12.cvr copy.csv`)
- Python environment with dependencies installed (`pip install -r requirements.txt`)

## Step-by-Step Process

### 1. Basic Data Processing

Process a CVR file and create a database:

```bash
python scripts/process_data.py "your_cvr_file.csv" --db election_data.db
```

**Example:**
```bash
python scripts/process_data.py "City_of_Portland__Councilor__District_2_2024_11_29_17_26_12.cvr copy.csv" --db election_data.db
```

### 2. Data Processing with Validation

Add validation checks to ensure data quality:

```bash
python scripts/process_data.py "your_cvr_file.csv" --db election_data.db --validate
```

This will:
- ✅ Load and parse the CVR file
- ✅ Extract candidate metadata from column headers
- ✅ Transform data from wide to long format
- ✅ Generate summary statistics
- ✅ Run validation checks on data quality

### 3. Understanding the Output

The script will display:

```
✓ Loaded 332969 ballots
✓ Found 22 candidates
✓ Created 362492 vote records
✓ Processing 77511 ballots with votes

Summary:
  Total Ballots: 77511
  Total Candidates: 22
  Average Ranks Per Ballot: 4.68
  Most Common Ballot Length: 6 ranks

Top 10 First Choice Results:
  Elana Pirtle-Guiney      : 12533 votes ( 16.2%)
  Dan Ryan                 : 12189 votes ( 15.7%)
  Sameer Kanal             : 10054 votes ( 13.0%)
  ...
```

## Expected Data Format

### Input: CVR CSV File

Your CSV file should contain:

- **Ballot Identification**: `RowNumber`, `BoxID`, `BoxPosition`, `BallotID`
- **Location Data**: `PrecinctID`, `BallotStyleID`, `PrecinctStyleName`
- **Vote Columns**: Pattern like `Choice_36_1:City of Portland, Councilor, District 2:1:Number of Winners 3:Sameer Kanal:NON`
  - `36` = Candidate ID
  - `1` = Rank position (1-6)
  - `Sameer Kanal` = Candidate name
  - Values: `1` = vote cast, `0` = no vote

### Output: DuckDB Database

The processing creates these tables:

- **`rcv_data`**: Raw loaded data
- **`candidate_columns`**: Metadata extracted from headers
- **`candidates`**: Candidate ID to name mapping
- **`ballots_long`**: Normalized vote records (ballot_id, candidate_id, rank_position)
- **Analysis views**: `first_choice_totals`, `votes_by_rank`, `ballot_completion`, etc.

## Advanced Options

### Custom Database Location

```bash
python scripts/process_data.py "file.csv" --db /path/to/custom/location.db
```

### Processing Multiple Files

Process each file into separate databases:

```bash
python scripts/process_data.py "file1.csv" --db election1.db
python scripts/process_data.py "file2.csv" --db election2.db
```

## Troubleshooting

### Common Issues

1. **File Not Found**
   ```
   Error: CSV file not found: your_file.csv
   ```
   - Check file path and ensure file exists
   - Use quotes around filenames with spaces

2. **Column Format Issues**
   ```
   Error: No matching columns found that match regex "Choice_%"
   ```
   - Verify CVR file has expected column format
   - Check that file contains actual ballot data (not summary reports)

3. **Memory Issues with Large Files**
   - DuckDB handles large files efficiently
   - For extremely large files (>1M ballots), consider processing in chunks

### Data Quality Validation

The `--validate` flag checks:
- ✅ Ballot ID uniqueness
- ✅ Expected number of candidates found
- ✅ Reasonable vote distribution
- ✅ Rank participation rates

**Warning Signs:**
- Very low rank 1 participation (<80%)
- Unexpected number of candidates
- Large numbers of duplicate ballot IDs

## Next Steps

After successful data processing:

1. **Run STV Analysis**: See [STV Analysis Guide](stv-analysis.md)
2. **Start Web Interface**: See [Web Interface Guide](web-interface.md)
3. **Verify Results**: See [Verification Guide](verification.md)

## File Outputs

- **`election_data.db`**: DuckDB database with processed data
- **Console output**: Summary statistics and validation results
- **Log files**: Detailed processing information (if logging enabled)

The database file can be used with:
- STV tabulation scripts
- Web interface
- Direct SQL queries via DuckDB CLI
- Verification against official results
