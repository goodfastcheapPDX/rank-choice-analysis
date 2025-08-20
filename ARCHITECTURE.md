# Architecture Documentation

This document provides detailed technical architecture information for the Ranked Elections Analyzer project.

## System Architecture

### High-Level Overview

The system follows a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Interface Layer                      │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────┐ │
│  │   Dashboard     │  │   Coalition      │  │ Vote Flow   │ │
│  │     (HTML)      │  │   Analysis       │  │    Viz      │ │
│  └─────────────────┘  └──────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                     │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐  │
│  │ Core Results │ │   Coalition  │ │  Advanced Analytics │  │
│  │     APIs     │ │     APIs     │ │        APIs        │  │
│  └──────────────┘ └──────────────┘ └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   Analysis Engine Layer                     │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐  │
│  │ STV Tabulator│ │   Coalition  │ │  Candidate Metrics  │  │
│  │  (PyRankVote)│ │   Analyzer   │ │     & Network       │  │
│  └──────────────┘ └──────────────┘ └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                  Data Processing Layer                      │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐  │
│  │  CVR Parser  │ │  Database    │ │    Verification     │  │
│  │              │ │   Manager    │ │      System         │  │
│  └──────────────┘ └──────────────┘ └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                     Data Storage Layer                      │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────┐  │
│  │   DuckDB     │ │   Parquet    │ │     Golden          │  │
│  │  Database    │ │    Files     │ │    Datasets         │  │
│  └──────────────┘ └──────────────┘ └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Data Processing Layer

#### CVR Parser (`src/data/cvr_parser.py`)
- **Purpose**: Parse Cast Vote Record CSV files into normalized database format
- **Key Features**:
  - Wide-to-long transformation of ballot data
  - Candidate metadata extraction
  - Data validation and integrity checks
  - Ballot completion pattern analysis

#### Database Manager (`src/data/database.py`)
- **Purpose**: Centralized database connection management with reliability features
- **Key Features**:
  - Connection pooling with automatic retry logic
  - Read-only vs read-write connection optimization
  - Exponential backoff for connection conflicts
  - Multiple instance support without locking issues
  - Comprehensive error handling and logging

### 2. Analysis Engine Layer

#### STV Tabulator (`src/analysis/stv.py` & `src/analysis/stv_pyrankvote.py`)
- **Purpose**: Single Transferable Vote election tabulation
- **Implementation**: Dual implementation approach
  - **Custom STV Engine**: Detailed round-by-round tracking
  - **PyRankVote Integration**: Industry-standard library for verification
- **Key Features**:
  - Droop quota calculation
  - Vote transfer algorithms
  - Surplus redistribution
  - Detailed ballot journey tracking
  - Round-by-round result generation

#### Coalition Analyzer (`src/analysis/coalition.py`)
- **Purpose**: Mathematical analysis of candidate relationships
- **Key Features**:
  - Proximity-weighted coalition strength calculation
  - Coalition type classification (Strong/Moderate/Weak/Strategic)
  - Network centrality analysis
  - Bidirectional vote transfer analysis
  - Graph-based clustering algorithms

#### Candidate Metrics (`src/analysis/candidate_metrics.py`)
- **Purpose**: Advanced candidate-centered analytics
- **Key Features**:
  - Supporter archetype segmentation
  - Behavioral pattern analysis
  - Transfer efficiency scoring
  - Similarity matching algorithms
  - Network position assessment

#### Verification System (`src/analysis/verification.py`)
- **Purpose**: Results validation against official election data
- **Key Features**:
  - Official results parsing
  - Winner comparison validation
  - Vote count accuracy assessment
  - Discrepancy analysis and reporting

### 3. Web Application Layer

#### FastAPI Application (`src/web/main.py`)
- **Purpose**: RESTful API server with HTML template rendering
- **Key Features**:
  - Comprehensive API endpoint coverage
  - Real-time data analysis
  - JSON serialization handling
  - Database connection management
  - Error handling and logging

#### Templates (`src/web/templates/`)
- **Base Template**: Common navigation and styling
- **Dashboard**: Summary statistics and quick actions
- **Coalition Analysis**: Interactive candidate relationship exploration
- **Vote Flow**: Sankey diagram visualization of vote transfers

### 4. Visualization Components

#### Interactive Network Graphs
- **Technology**: D3.js force-directed networks
- **Features**:
  - Real-time candidate relationship visualization
  - Weighted node sizing based on voter preference
  - Dynamic edge styling for coalition strength
  - Zoom, pan, and interaction controls

#### Vote Flow Diagrams
- **Technology**: Plotly.js Sankey diagrams
- **Features**:
  - Round-by-round vote transfer visualization
  - Interactive filtering and navigation
  - Transfer pattern analysis
  - Educational round progression

## Database Schema

### Core Tables

#### `ballots_long`
- **Purpose**: Normalized ballot data in long format
- **Key Columns**:
  - `BallotID`: Unique ballot identifier
  - `candidate_id`: Candidate identifier
  - `rank_position`: Voter's ranking (1-6)
  - Ballot metadata (precinct, style, etc.)

#### `candidates`
- **Purpose**: Candidate metadata and information
- **Key Columns**:
  - `candidate_id`: Unique candidate identifier
  - `candidate_name`: Full candidate name
  - Choice column mappings

#### `coalition_pairs` (Precomputed)
- **Purpose**: Candidate pair analysis results
- **Key Columns**:
  - Candidate pair identifiers
  - Coalition strength metrics
  - Proximity calculations
  - Co-ranking statistics

#### Views and Analysis Tables
- `first_choice_totals`: First preference vote counts
- `ballot_completion_stats`: Ranking pattern analysis
- `adjacent_pairs`: Ranking proximity data

## Data Flow

### 1. Data Ingestion
```
CSV File → CVR Parser → Database Normalization → DuckDB Storage
```

### 2. Analysis Pipeline
```
Raw Data → STV Tabulation → Coalition Analysis → Candidate Metrics → Web API
```

### 3. Visualization Pipeline
```
Database → API Endpoints → JavaScript Visualization → Interactive Interface
```

## Performance Optimizations

### Database Level
- **Read-only connections** for most operations to prevent locking
- **Connection pooling** with automatic retry logic
- **Efficient SQL queries** with proper indexing
- **Parquet storage** for fast analytical queries

### Application Level
- **Lazy loading** of expensive computations
- **Caching strategies** for frequently accessed data
- **Asynchronous processing** where appropriate
- **Memory-efficient algorithms** for large datasets

### Frontend Level
- **Progressive data loading** for large visualizations
- **Client-side filtering** to reduce server requests
- **Optimized JavaScript libraries** (D3.js, Plotly.js)
- **Responsive design** for multiple device types

## Security Considerations

### Data Protection
- **Read-only database access** for web interface
- **Input validation** for all API endpoints
- **SQL injection protection** through parameterized queries
- **File path validation** for CSV uploads

### Application Security
- **Dependency scanning** with bandit security linter
- **Code quality enforcement** through pre-commit hooks
- **Error handling** without information disclosure
- **Secure random number generation** where required

## Testing Architecture

### Test Categories

#### Unit Tests (`tests/unit/`)
- Mathematical function validation
- Algorithm correctness verification
- Individual component testing
- Edge case handling

#### Golden Datasets (`tests/golden/`)
- Hand-computed micro elections
- Known correct results for regression testing
- Mathematical invariant validation
- Algorithm verification benchmarks

#### Integration Tests (`tests/integration/`)
- Full pipeline validation
- Database interaction testing
- API endpoint verification
- End-to-end workflow testing

#### Invariant Tests
- Mathematical property verification
- Data consistency checks
- Algorithm correctness validation
- Conservation law verification

### Quality Assurance

#### Pre-commit Hooks
- **Code formatting**: Black, isort
- **Linting**: flake8 with custom rules
- **Security scanning**: bandit
- **Test execution**: Automated test running
- **Custom validation**: Election-specific checks

#### Continuous Validation
- **Golden dataset verification**: Regression prevention
- **Mathematical invariant checks**: Algorithm correctness
- **Import validation**: Dependency verification
- **Performance benchmarks**: Speed regression detection

## Deployment Considerations

### Development Environment
- **Python 3.12+** for latest features and performance
- **Virtual environment** for dependency isolation
- **Development dependencies** for testing and quality assurance
- **Hot reloading** for rapid development iteration

### Production Environment
- **Multiple instance support** through read-only database connections
- **Port flexibility** with automatic port detection
- **Resource optimization** through connection pooling
- **Error resilience** with comprehensive exception handling

### Monitoring and Logging
- **Structured logging** throughout the application
- **Performance metrics** for database operations
- **Error tracking** with detailed stack traces
- **Usage analytics** for optimization insights

## Extension Points

### Adding New Analysis Types
1. Create new module in `src/analysis/`
2. Implement analysis class with standard interface
3. Add API endpoints in `src/web/main.py`
4. Create corresponding tests
5. Update documentation

### Adding New Visualizations
1. Create HTML template in `src/web/templates/`
2. Implement JavaScript visualization logic
3. Add supporting API endpoints
4. Integrate with navigation system
5. Add responsive design considerations

### Database Schema Extensions
1. Define new tables/views in SQL scripts
2. Update CVR parser if needed
3. Add migration scripts for existing data
4. Update API endpoints for new data
5. Create comprehensive tests

This architecture provides a solid foundation for electoral analysis while maintaining flexibility for future enhancements and extensions.
