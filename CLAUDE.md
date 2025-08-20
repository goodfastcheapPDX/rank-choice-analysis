# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

This is a ranked-choice voting analysis project. See `README.md` for project overview and `ARCHITECTURE.md` for detailed technical documentation.

**Key Context for Development:**
- Multi-winner RCV election analysis (3 winners from 22+ candidates)
- 332,969+ ballot records with 1-6 ranking preferences
- PyRankVote STV implementation with 100% verified winner accuracy
- Comprehensive web interface with interactive visualizations

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

# Multiple instances (now supported without database locks)
python scripts/start_server.py --db election_data.db --port 8001 &
python scripts/start_server.py --db election_data.db --port 8002 &
python scripts/start_server.py --db election_data.db --port 8003 &
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

## Testing Commands

```bash
# Test full pipeline
python scripts/test_pipeline.py

# Detailed verification
python scripts/verify_results.py --db election_data.db --official "2024-12-02_15-04-45_report_official.csv" --export verification_report.txt

# Web interface
python scripts/start_server.py --db election_data.db

# Run full test suite
pytest tests/
make test

# Run with coverage
pytest --cov=src tests/
make test-coverage
```

## Web Application Features

### ✅ **Implemented Pages**
- **Dashboard** (`/`) - Working main page with summary stats and quick actions
- **Vote Flow** (`/vote-flow`) - Complete interactive STV vote transfer visualization
- **Coalition Analysis** (`/coalition`) - Comprehensive candidate coalition analysis

### 🚧 **Navigation Items To Be Implemented**

#### **Candidates Page** (`/candidates`)
**Purpose**: Candidate-centered exploration for users who want comprehensive information about specific candidates
**Intended Features**:
- Individual candidate profiles with detailed statistics
- Vote progression analysis across all rounds
- Coalition partners and opposition patterns
- Supporter demographics and voting patterns
- Transfer flow visualization focused on single candidate
- Comparison tools between candidates
- "Everything about your favorite candidate" approach

#### **Ballot Explorer** (`/ballots`)
**Purpose**: Individual ballot examination and pattern discovery
**Intended Features**:
- Search ballots by candidate preferences
- Ballot completion pattern analysis
- Individual ballot journey visualization through STV rounds
- Ballot similarity clustering and grouping
- Export capabilities for research purposes
- Educational examples of different voting patterns

#### **STV Results** (`/stv-results`)
**Purpose**: Comprehensive STV tabulation results and analysis
**Intended Features**:
- Detailed round-by-round results table
- Winner analysis with quota achievement visualization
- Elimination order and reasoning
- Counterfactual "what-if" scenario analysis
- Export detailed results for verification
- Comparison with other STV implementations

## API Endpoints Reference

See `ARCHITECTURE.md` for complete API documentation. Key endpoints:
- Core Analysis: `/api/summary`, `/api/stv-results`, `/api/candidates`
- Vote Flow: `/api/stv-flow-data`, `/api/vote-transfers/round/{round_number}`
- Coalition: `/api/coalition/pairs/all`, `/api/coalition/network`
- Advanced Analytics: `/api/candidates/{id}/supporter-segments`, `/api/candidates/{id}/similarity`

## Current Status

### ✅ **Mission Accomplished: Production-Ready Election Analysis Platform**

**Major Achievements Complete:**
1. ✅ **STV Implementation & Verification**: 100% winner accuracy against official Portland results
2. ✅ **Advanced Coalition Analysis**: Network visualization, clustering, mathematical analysis
3. ✅ **Vote Flow Visualization**: Interactive Sankey diagrams with round-by-round tracking
4. ✅ **Database Architecture**: Production-ready with multiple instance support
5. ✅ **Candidate Deep-Dive Analytics**: Supporter segmentation, similarity matching
6. ✅ **Testing Infrastructure**: Comprehensive test coverage with golden datasets
7. ✅ **User Experience**: Educational interface with comprehensive guidance

**Quality Metrics:**
- **Results Verification**: ✅ EXACT winner matches (100% accuracy)
- **Test Coverage**: Comprehensive unit, integration, and golden dataset tests
- **Code Quality**: All lint errors resolved, pre-commit hooks passing
- **Performance**: Sub-second response times, multiple instance support
- **User Experience**: Interactive visualizations, educational explanations

## File Naming Convention

Election data files follow pattern: `[Election_Description]_[Date].cvr.csv` or similar variations with sample indicators.

## Git Workflow Guidelines

**CRITICAL RULES:**
- Never use `--no-verify` with git commit without explicit consent
- Never make changes to commit hooks or lint rules without explicit permission for every change
- Write a git commit every time you complete a todo
- All pre-commit hooks must pass before committing

**Pre-commit Hook System:**
- **Code Quality**: Black formatting, isort imports, flake8 linting
- **Security**: Bandit security scanning
- **Testing**: Unit tests and smoke tests
- **Election-Specific**: Mathematical invariants and golden dataset verification

## Claude-Specific Development Guidance

**When Working on This Project:**

1. **Always Check Existing Implementations**: This project has comprehensive existing code. Check for existing patterns, utilities, and conventions before creating new code.

2. **Follow Testing Patterns**: Add tests for new functionality using the established testing infrastructure (unit tests, golden datasets, invariant tests).

3. **Use Existing Database Patterns**: The `CVRDatabase` class handles connections, retries, and pooling. Use `db.query()` or `db.query_with_retry()` methods.

4. **API Development**: Follow the established FastAPI patterns in `src/web/main.py`. Use proper error handling and JSON serialization.

5. **Mathematical Accuracy**: This is electoral analysis - mathematical correctness is critical. Use existing validation patterns and add appropriate tests.

6. **User Experience**: This platform serves researchers, campaigns, and citizens. Maintain the educational approach with clear explanations and interactive guidance.

7. **Performance Considerations**: Use read-only database connections where possible, implement caching for expensive operations, and consider memory usage for large datasets.

8. **Documentation**: Update relevant documentation (README.md, ARCHITECTURE.md) when adding significant features.

## Important Instruction Reminders

- Never use `--no-verify` flag without explicit consent from user
- Write a git commit every time you complete a todo
- Always prefer editing existing files over creating new ones
- Never proactively create documentation files unless explicitly requested
- Keep responses concise and direct
- Focus on the specific task at hand
