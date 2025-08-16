# Web Interface Guide

This guide covers how to use the interactive web dashboard for exploring election results and data.

## Overview

The web interface provides an interactive dashboard for exploring STV election data, viewing results, and analyzing voting patterns. It's built with FastAPI and provides both a web UI and REST API.

## Getting Started

### 1. Start the Web Server

With a processed database:
```bash
python scripts/start_server.py --db election_data.db
```

With custom settings:
```bash
python scripts/start_server.py --db election_data.db --port 8080 --host 0.0.0.0
```

### 2. Access the Dashboard

Open your browser to:
```
http://localhost:8000
```

## Dashboard Overview

### Main Dashboard Features

**Summary Statistics**:
- Total ballots processed
- Number of candidates
- Average ranks per ballot
- Most common ballot length

**Interactive Charts**:
- First choice results bar chart
- Vote distribution by rank position
- Real-time STV tabulation

**Quick Actions**:
- Explore individual ballots
- Run STV analysis
- View candidate analysis
- Export data as CSV

## Key Features

### 1. First Choice Results

**What it shows**: Bar chart of first-preference vote totals for all candidates

**How to use**:
- Hover over bars for exact vote counts
- Chart shows top 10 candidates by default
- Interactive sorting and filtering

**Interpretation**:
- Identifies frontrunners and competitive candidates
- Shows baseline support before transfers
- Helps predict likely winners

### 2. STV Results Runner

**What it shows**: Complete STV tabulation with round-by-round results

**How to use**:
1. Click "Run STV Tabulation" button
2. View winners and round count
3. See eliminated candidates and vote flows
4. Export detailed results

**Example Output**:
```
STV Election Results
Elected Candidates:
1. Elana Pirtle-Guiney - 19729.0 votes (Round 12)
2. Dan Ryan - 19729.0 votes (Round 12)  
3. Sameer Kanal - 19729.0 votes (Round 12)

Total Rounds: 12
```

### 3. Ballot Explorer

**Access**: Navigate to `/ballots` (feature in development)

**What it does**:
- Search for specific ballots by ID
- View complete ranking sequences
- Find ballots that rank specific candidates
- Analyze ballot completion patterns

### 4. Candidate Analysis

**What it shows**: Detailed breakdown for individual candidates

**Features**:
- Vote totals by rank position
- Coalition analysis (who supporters also rank)
- Geographic patterns (when available)
- Transfer flow analysis

## API Endpoints

### Core Data Endpoints

**Summary Statistics**:
```
GET /api/summary
```
Returns basic election statistics.

**Candidate List**:
```
GET /api/candidates  
```
Returns all candidates with IDs and names.

**First Choice Results**:
```
GET /api/first-choice
```
Returns first-preference vote totals.

### Analysis Endpoints

**STV Tabulation**:
```
GET /api/stv-results?seats=3
```
Runs complete STV analysis and returns results.

**Individual Ballot**:
```
GET /api/ballot/{ballot_id}
```
Returns complete ranking for specific ballot.

**Ballot Search**:
```
GET /api/search-ballots?candidate=Laura%20Streib&rank=1&limit=10
```
Finds ballots ranking specific candidate at specific position.

**Candidate Analysis**:
```
GET /api/candidate-analysis/{candidate_name}
```
Returns detailed analysis for individual candidate.

**Results Verification**:
```
GET /api/verify-results?official_results_path=official.csv
```
Compares against official results.

### Export Endpoints

**Summary Export**:
```
GET /api/export/summary
```
Downloads summary statistics as CSV.

**First Choice Export**:
```
GET /api/export/first-choice  
```
Downloads first choice results as CSV.

## Interactive Features

### 1. Real-time Data Updates

The dashboard updates dynamically:
- Charts refresh when data changes
- Results appear without page reloads
- Error handling with user-friendly messages

### 2. Data Visualization

**Chart Types**:
- Bar charts for vote totals
- Interactive tables with sorting
- Hover tooltips for detailed information
- Responsive design for different screen sizes

### 3. Export Functionality

**Available Exports**:
- CSV files for all data tables
- Summary reports
- Detailed STV round data
- Individual candidate analysis

## Advanced Usage

### 1. API Integration

Use the REST API programmatically:

```python
import requests

# Get summary data
response = requests.get('http://localhost:8000/api/summary')
summary = response.json()

# Run STV analysis
response = requests.get('http://localhost:8000/api/stv-results')
results = response.json()
```

### 2. Custom Analysis

Combine multiple endpoints for custom analysis:

```javascript
// Fetch first choice results
fetch('/api/first-choice')
  .then(response => response.json())
  .then(data => {
    // Process and visualize data
    createCustomChart(data);
  });
```

### 3. Data Integration

Export data for use in other tools:
- Download CSV files for Excel/Google Sheets
- Use API endpoints for R/Python analysis
- Integrate with other visualization tools

## Troubleshooting

### Common Issues

1. **Server Won't Start**
   ```
   Error: Database file not found
   ```
   - Ensure database exists: `ls election_data.db`
   - Re-run data processing if needed

2. **No Data Loading**
   ```
   Error: No data loaded
   ```
   - Check that CVR data was processed successfully
   - Verify required tables exist in database

3. **STV Results Error**
   ```
   STV calculation failed
   ```
   - Check data quality and completeness
   - Ensure sufficient ballots for analysis
   - Review console logs for detailed error

### Performance Tips

**Large Datasets**:
- STV calculations may take 30-60 seconds
- Use browser developer tools to monitor API calls
- Consider pagination for very large result sets

**Browser Compatibility**:
- Modern browsers (Chrome, Firefox, Safari, Edge)
- JavaScript must be enabled
- Recommended: Latest browser versions

## Development Mode

For development and debugging:

```bash
python scripts/start_server.py --db election_data.db --reload
```

Features:
- Auto-reload on code changes
- Detailed error messages
- API documentation at `/docs`

## Security Notes

**Local Use**: The web interface is designed for local analysis
**Data Privacy**: All processing happens locally, no data transmitted externally
**File Access**: Server only accesses specified database file

## Next Steps

After exploring the web interface:

1. **Verify Results**: Use the verification endpoints to compare against official data
2. **Deep Analysis**: Use exported data for advanced statistical analysis
3. **Report Generation**: Combine insights for presentation or publication
4. **API Integration**: Build custom tools using the REST API