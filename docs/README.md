# Ranked Elections Analyzer - User Guide

This document provides instructions for using the Portland STV Election Analysis Platform.

## Overview

The Ranked Elections Analyzer is a complete toolkit for analyzing ranked-choice voting (STV) election data from Portland City Council elections. It provides data processing, STV tabulation, results verification, and interactive web-based exploration tools.

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Process Election Data**
   ```bash
   python scripts/process_data.py "your_cvr_file.csv" --db election_data.db --validate
   ```

3. **Start Web Interface**
   ```bash
   python scripts/start_server.py --db election_data.db
   ```

4. **Open Browser**
   ```
   http://localhost:8000
   ```

## Detailed Guides

- [**Data Processing Guide**](data-processing.md) - How to load and transform CVR data
- [**STV Analysis Guide**](stv-analysis.md) - Running STV tabulation and understanding results
- [**Web Interface Guide**](web-interface.md) - Using the interactive dashboard
- [**Verification Guide**](verification.md) - Comparing results against official data
- [**API Reference**](api-reference.md) - REST API endpoints and usage

## Key Features

### ✅ **Currently Working**
- **Data Processing**: Transform CVR files into normalized database format
- **STV Tabulation**: Multi-winner ranked-choice voting algorithm implementation
- **Interactive Dashboard**: Web-based exploration of results and candidate data
- **Results Verification**: Compare against official election results
- **Data Export**: CSV downloads of all analysis data

### 🔧 **In Development**
- Coalition analysis and voter affinity mapping
- Geographic voting pattern analysis
- Ballot simulation and "what-if" scenarios
- Advanced reporting and mandate attribution

## File Structure

```
docs/
├── README.md              # This overview guide
├── data-processing.md     # CVR data processing instructions
├── stv-analysis.md        # STV tabulation guide
├── web-interface.md       # Dashboard usage guide
├── verification.md        # Results verification guide
└── api-reference.md       # API documentation
```

## Support

For issues or questions:
1. Check the relevant guide in this docs/ directory
2. Review the troubleshooting section in each guide
3. Examine the verification report if results seem incorrect
4. Check CLAUDE.md for current status and known issues