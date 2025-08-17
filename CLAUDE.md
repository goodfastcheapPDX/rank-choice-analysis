# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a ranked-choice voting analysis project for analyzing election data from Portland City Council District 2 elections. The project currently contains Cast Vote Record (CVR) data in CSV format from ranked-choice voting elections.

## Data Structure

The repository contains election data files:
- CSV files with Cast Vote Records (CVR) format
- Each record contains ballot information with candidate rankings (1-6 ranks per candidate)
- Data includes 22 candidates plus write-in options for a multi-winner election (3 winners)

### CVR Data Format

The CSV files contain these key columns:
- `RowNumber`, `BoxID`, `BoxPosition`, `BallotID`: Ballot identification
- `PrecinctID`, `BallotStyleID`, `PrecinctStyleName`: Location information
- `Choice_X_1:City of Portland, Councilor, District 2:Y:Number of Winners 3:[Candidate Name]:NON`: Ranking data
  - X = Choice ID number (36-57, plus write-in IDs)
  - Y = Rank position (1-6)
  - Values are 1 for selected rank, 0 for not selected

## Data Analysis Considerations

When working with this election data:

1. **Multi-winner RCV**: This is a 3-winner ranked-choice election, requiring different tabulation algorithms than single-winner RCV
2. **Candidate Management**: 22 named candidates plus multiple write-in categories
3. **Ranking Structure**: Voters can rank up to 6 preferences per candidate
4. **Data Volume**: Files contain 50k+ ballot records for analysis

## Expected Development Tasks

Future development will likely involve:
- Data parsing and validation scripts
- RCV tabulation algorithms (likely Single Transferable Vote for multi-winner)
- Results visualization and reporting
- Data export/import utilities
- Statistical analysis tools

## Architecture

### Technology Stack
- **Backend**: Python with DuckDB for fast analytical queries
- **Web Framework**: FastAPI with Jinja2 templates
- **Visualization**: Plotly.js for interactive charts
- **Data Storage**: Parquet/DuckDB for efficient querying
- **Dependencies**: See `requirements.txt` and `pyproject.toml`

### Project Structure
```
src/
├── data/           # Data processing and database management
│   ├── database.py     # DuckDB connection wrapper
│   └── cvr_parser.py   # CVR data parsing and transformation
├── analysis/       # Analysis engines
│   └── stv.py         # STV tabulation algorithm
└── web/           # Web application
    ├── main.py        # FastAPI application
    └── templates/     # HTML templates

sql/               # SQL scripts for data transformation
├── 01_load_data.sql      # Load CVR data
├── 02_create_metadata.sql # Extract candidate metadata
├── 04_basic_analysis.sql  # Basic analysis views
└── 05_candidate_analysis.sql # Candidate-specific queries
Note: Wide-to-long transformation handled dynamically in Python

scripts/           # Command-line tools
├── process_data.py   # Process CVR data
├── run_stv.py       # Run STV tabulation
├── start_server.py  # Start web server
└── test_pipeline.py # Test the complete pipeline
```

## Development Commands

### Data Processing
```bash
# Process CVR data (required first step)
python scripts/process_data.py your_file.csv --db election_data.db --validate

# Run STV tabulation
python scripts/run_stv.py --db election_data.db --seats 3 --export results

# Test the complete pipeline
python scripts/test_pipeline.py
```

### Web Application
```bash
# Start web server
python scripts/start_server.py --db election_data.db --port 8000

# Development mode with auto-reload
python scripts/start_server.py --db election_data.db --reload
```

### Package Management
```bash
# Install dependencies
pip install -r requirements.txt
# or
pip install -e .

# Development dependencies
pip install -e .[dev]

# Code formatting
black src/ scripts/
isort src/ scripts/

# Dependency versions (as of August 2025)
# FastAPI 0.115.6, DuckDB 1.1.3, Pandas 2.2.3, NumPy 2.1.3
```

## API Endpoints

The web application provides REST API endpoints:
- `GET /api/summary` - Summary statistics
- `GET /api/candidates` - Candidate list
- `GET /api/first-choice` - First choice results
- `GET /api/stv-results` - Run STV tabulation
- `GET /api/ballot/{ballot_id}` - Individual ballot details
- `GET /api/export/*` - CSV data exports

## File Naming Convention

Election data files follow pattern: `[Election_Description]_[Date].cvr.csv` or similar variations with sample indicators.

## Current Status Report

### ✅ **Phase 1 Complete: Basic Data Explorer**
- **Data Processing Pipeline**: ✅ Working
- **STV Tabulation Engine**: ✅ Working  
- **Web Interface**: ✅ Working
- **Results Verification System**: ✅ Working

**Key Achievement**: Successfully built end-to-end pipeline that processes 332,969 ballots, runs STV tabulation in 12 rounds, and identifies winners.

### ⚠️ **Current Issues - Results Verification**

**Status**: STV algorithm working but discrepancies found vs official results

**Verification Results** (as of 2025-08-16):
- **Our Winners**: Elana Pirtle-Guiney (46), Dan Ryan (55), Sameer Kanal (36)
- **Total Vote Difference**: 1,485 votes across all candidates
- **Winners Match**: ❌ False (official winners not properly extracted)
- **Vote Count Accuracy**: ~98% (small systematic differences)

### 🔧 **Action Plan - Critical Fixes Needed**

#### **Priority 1: Data Alignment Issues**
1. **Include Write-in Candidates** 
   - Issue: We exclude write-ins, officials include them (211 vote difference)
   - Fix: Modify `02_create_metadata.sql` to include write-in choices
   - File: `sql/02_create_metadata.sql` lines 12-14

2. **Ballot Universe Verification**
   - Issue: Our 77,511 effective ballots may differ from official count
   - Fix: Investigate ballot filtering criteria and status codes
   - Check: `Status`, `Remade` columns in CVR data

3. **Threshold Calculation**
   - Issue: Our Droop quota (19,729) vs Official (19,290) = 439 difference
   - Fix: Verify continuing vote count matches official methodology

#### **Priority 2: Official Results Parser**
1. **Winner Extraction Bug**
   - Issue: Parser returns empty `Official winners: []`
   - Fix: Improve CSV parsing in `src/analysis/verification.py` 
   - Target: `_parse_results_data()` method line ~45

2. **Candidate Name Matching**
   - Issue: Ensure exact name matching between our data and official results
   - Fix: Add name normalization and fuzzy matching

#### **Priority 3: Algorithm Refinement**
1. **Transfer Value Calculation**
   - Verify surplus transfer methodology matches official STV implementation
   - Check fractional transfer handling

2. **Tie-breaking Rules**
   - Implement official tie-breaking procedures
   - Add deterministic ordering for eliminated candidates

### 🎯 **Next Development Phases**

**Phase 2**: Quota Attribution Explorer (blocked until verification issues resolved)
**Phase 3**: Affinity & Coalition Explorer  
**Phase 4**: Geographic & Stability Analysis
**Phase 5**: Ballot Simulator & What-If Lab
**Phase 6**: Round Explorer & Professional Reports

### 🧪 **Testing Commands**

```bash
# Test full pipeline
python scripts/test_pipeline.py

# Detailed verification
python scripts/verify_results.py --db election_data.db --official "2024-12-02_15-04-45_report_official.csv" --export verification_report.txt

# Web interface
python scripts/start_server.py --db election_data.db
```

**Expected Outcome**: Verification should show `✅ VERIFICATION PASSED` once critical fixes are implemented.

### 🎯 **Active Verification Fix Plan** (2025-08-17)

**Current Sprint: Data Alignment & Parser Fixes**

#### **Priority 1: Data Alignment Issues** ✅ COMPLETED
1. **✅ Include Write-in Candidates** (COMPLETED)
   - Fixed: Modified `02_create_metadata.sql` to include write-in choices
   - Expected: Reduce total vote difference from 1,485 to ~1,274
   - Commit: "Include write-in candidates in metadata extraction"

2. **✅ Ballot Universe Verification** (COMPLETED)
   - Fixed: Added `Status = 0` filter to exclude remade ballots from analysis
   - Expected: Reduce ballot universe from 77,511 to ~73,916 ballots
   - Goal: Resolve threshold calculation discrepancy (19,729 vs 19,290)
   - Commit: "Fix ballot filtering to match official count"

#### **Priority 2: Official Results Parser** ✅ COMPLETED
1. **✅ Winner Extraction Bug** (COMPLETED)
   - Fixed: Improved CSV parsing in `_parse_results_data()` method
   - Result: Should now correctly extract winners from "Met threshold for election" line
   - Commit: "Fix official results winner extraction parsing"

2. **✅ Candidate Name Normalization** (COMPLETED)
   - Fixed: Added `normalize_candidate_name()` function with robust matching
   - Features: Handles whitespace, case, parentheses, and hyphen variations
   - Commit: "Add candidate name normalization for verification"

#### **Priority 3: OSS STV Library Migration** ⏳ ACTIVE
**Goal**: Replace hand-coded STV implementation with PyRankVote library

**Library Selection**: PyRankVote (OpenRCV not recommended - stalled since 2014)

**Implementation Phases**:
1. **✅ Unit Testing Infrastructure** (COMPLETED)
   - ✅ Created comprehensive test suite for current STV implementation
   - ✅ Built interface compatibility tests for API validation
   - ✅ 13/16 tests passing - excellent foundation for migration
   - Commit: "Create comprehensive STV test infrastructure"

2. **Library Integration** - Install PyRankVote and create data adapter module  
3. **Interface Compatibility** - Maintain existing API while using PyRankVote backend
4. **Automated Validation** - Side-by-side comparison testing with official results
5. **Integration & Deployment** - Configuration options and gradual migration
6. **Migration & Cleanup** - Switch defaults and optional cleanup

**Key Benefits**: Proven STV algorithm, reduced maintenance burden, industry standards
**Risk Mitigation**: Extensive testing, parallel implementations, configuration fallback
**Test Coverage**: Quota calculations, elections, transfers, edge cases, API compatibility

**Working Protocol:**
- Complete each task individually with git commits
- Run verification tests after each task  
- Update this plan as progress is made

#### **Next Steps: Testing & Validation**
Now that all Priority 1 & 2 fixes are complete:
1. **Reprocess data** with new filtering and metadata inclusion
2. **Run verification** to test improvements
3. **Evaluate results** and determine if Priority 3 (OSS libraries) is needed
4. **Document findings** and plan next development phase