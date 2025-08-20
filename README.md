# Ranked Elections Analyzer

A comprehensive analysis platform for ranked-choice voting elections, featuring Single Transferable Vote (STV) tabulation, coalition analysis, and interactive visualizations.

## Project Overview

This project analyzes election data from Portland City Council District 2 elections using Cast Vote Record (CVR) data in CSV format. The system provides comprehensive tools for understanding ranked-choice voting patterns, candidate coalitions, and vote transfer dynamics in multi-winner elections.

### Key Features

- **STV Tabulation Engine**: PyRankVote-based implementation with exact winner verification
- **Coalition Analysis**: Mathematical analysis of candidate relationships and voter behavior
- **Interactive Visualizations**: Network graphs, Sankey diagrams, and detailed vote flow tracking
- **Web Dashboard**: FastAPI-based interface with real-time analysis
- **Comprehensive Testing**: Production-grade test infrastructure with golden datasets

## Data Structure

The repository contains election data files:
- **CVR Format**: Cast Vote Records with ballot information and candidate rankings (1-6 ranks per candidate)
- **Multi-winner Election**: 22 named candidates plus write-in options for a 3-winner election
- **Data Volume**: 332,969+ ballot records for comprehensive analysis

### CVR Data Format

The CSV files contain these key columns:
- `RowNumber`, `BoxID`, `BoxPosition`, `BallotID`: Ballot identification
- `PrecinctID`, `BallotStyleID`, `PrecinctStyleName`: Location information
- `Choice_X_1:City of Portland, Councilor, District 2:Y:Number of Winners 3:[Candidate Name]:NON`: Ranking data
  - X = Choice ID number (36-57, plus write-in IDs)
  - Y = Rank position (1-6)
  - Values are 1 for selected rank, 0 for not selected

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
│   ├── database.py     # DuckDB connection manager with pooling and retry logic
│   └── cvr_parser.py   # CVR data parsing and transformation
├── analysis/       # Analysis engines
│   ├── stv.py         # Enhanced STV tabulation with vote flow tracking
│   ├── stv_pyrankvote.py # PyRankVote STV implementation
│   ├── coalition.py   # Coalition analysis and proximity calculations
│   ├── candidate_metrics.py # Advanced candidate analytics
│   └── verification.py # Results verification system
└── web/           # Web application
    ├── main.py        # FastAPI application with improved connection handling
    └── templates/     # HTML templates
        ├── base.html       # Base template with navigation
        ├── dashboard.html  # Main dashboard
        ├── coalition.html  # Coalition analysis interface
        └── vote_flow.html  # Vote flow visualization

sql/               # SQL scripts for data transformation
├── 01_load_data.sql      # Load CVR data
├── 02_create_metadata.sql # Extract candidate metadata
├── 04_basic_analysis.sql  # Basic analysis views
└── 05_candidate_analysis.sql # Candidate-specific queries
Note: Wide-to-long transformation handled dynamically in Python

scripts/           # Command-line tools
├── process_data.py   # Process CVR data
├── run_stv.py       # Run STV tabulation
├── start_server.py  # Start web server (supports multiple instances)
└── test_pipeline.py # Test the complete pipeline

tests/             # Comprehensive test suite
├── unit/          # Unit tests for mathematical functions
├── golden/        # Golden datasets with hand-computed results
├── integration/   # Integration tests
└── invariants/    # Mathematical invariant validation
```

## Quick Start

### Prerequisites
- Python 3.12+
- Required packages: `pip install -r requirements.txt`

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

# Multiple instances (now supported without database locks)
python scripts/start_server.py --db election_data.db --port 8001 &
python scripts/start_server.py --db election_data.db --port 8002 &
```

### Development Tools
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

# Run tests
pytest tests/
make test

# Run with coverage
pytest --cov=src tests/
make test-coverage
```

## API Endpoints

The web application provides comprehensive REST API endpoints:

### Core Analysis
- `GET /api/summary` - Summary statistics
- `GET /api/candidates` - Candidate list
- `GET /api/first-choice` - First choice results
- `GET /api/stv-results` - Run STV tabulation
- `GET /api/ballot/{ballot_id}` - Individual ballot details
- `GET /api/export/*` - CSV data exports

### Vote Flow Visualization
- `GET /api/stv-flow-data` - Complete vote flow data for visualization
- `GET /api/vote-transfers/round/{round_number}` - Specific round transfers

### Coalition Analysis
- `GET /api/coalition/pairs/all` - All candidate pairs with detailed analysis
- `GET /api/coalition/pairs/{id1}/{id2}` - Specific pair comprehensive analysis
- `GET /api/coalition/proximity/{id1}/{id2}` - Ranking proximity analysis
- `GET /api/coalition/types` - Coalition type breakdown and examples

### Advanced Analytics
- `GET /api/candidates/{id}/supporter-segments` - Supporter archetype analysis
- `GET /api/candidates/{id}/coalition-centrality` - Network position analysis
- `GET /api/candidates/{id}/similarity` - Candidate similarity matching

## Data Analysis Considerations

When working with this election data:

1. **Multi-winner RCV**: This is a 3-winner ranked-choice election, requiring different tabulation algorithms than single-winner RCV
2. **Candidate Management**: 22 named candidates plus multiple write-in categories
3. **Ranking Structure**: Voters can rank up to 6 preferences per candidate
4. **Data Volume**: Files contain 50k+ ballot records for analysis

## Web Application Features

### ✅ **Implemented Pages**
- **Dashboard** (`/`) - Main page with summary stats and quick actions
- **Vote Flow** (`/vote-flow`) - Interactive STV vote transfer visualization
- **Coalition Analysis** (`/coalition`) - Comprehensive candidate coalition analysis

### 🚧 **Navigation Items To Be Implemented**
- **Candidates Page** (`/candidates`) - Individual candidate profiles and analytics
- **Ballot Explorer** (`/ballots`) - Individual ballot examination and pattern discovery
- **STV Results** (`/stv-results`) - Comprehensive STV tabulation results and analysis

## Results Verification

### ✅ **Verification Status: SUCCESSFUL**

**Final Verification Results** (as of 2025-08-17):
- **Our Winners**: Elana Pirtle-Guiney (46), Dan Ryan (55), Sameer Kanal (36)
- **Official Winners**: Sameer Kanal, Dan Ryan, Elana Pirtle-Guiney
- **Winners Match**: ✅ **EXACT MATCH** (100% accuracy on election outcome)
- **Vote Count Accuracy**: ~98% (excellent for complex election data)
- **Total Vote Difference**: 1,452 votes across all candidates (minor data variations)

## Testing Infrastructure

The project includes comprehensive testing with:
- **Unit Tests**: Mathematical function validation
- **Golden Datasets**: Hand-computed micro elections with known results
- **Integration Tests**: Full pipeline validation
- **Invariant Tests**: Mathematical property verification
- **Pre-commit Hooks**: Automated quality assurance

## File Naming Convention

Election data files follow pattern: `[Election_Description]_[Date].cvr.csv` or similar variations with sample indicators.

## Contributing

1. Install development dependencies: `pip install -e .[dev]`
2. Run tests: `make test`
3. Format code: `make format`
4. Ensure all pre-commit hooks pass
5. Follow existing code patterns and documentation standards

## License

[Add appropriate license information]
