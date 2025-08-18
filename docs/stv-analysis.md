# STV Analysis Guide

This guide covers how to run Single Transferable Vote (STV) tabulation and understand the results.

## Overview

The STV analysis engine implements multi-winner ranked-choice voting using the Droop quota method. It processes normalized ballot data and determines winners through multiple rounds of vote counting and redistribution.

## Prerequisites

- Processed CVR database (see [Data Processing Guide](data-processing.md))
- Understanding of STV/ranked-choice voting concepts

## Running STV Tabulation

### Basic STV Analysis

Run STV tabulation with default settings (3 seats):

```bash
python scripts/run_stv.py --db election_data.db
```

### Custom Number of Seats

Specify a different number of winners:

```bash
python scripts/run_stv.py --db election_data.db --seats 5
```

### Export Results

Save detailed results to CSV files:

```bash
python scripts/run_stv.py --db election_data.db --export results
```

This creates:
- `results.csv`: Final candidate results
- `results_rounds.csv`: Round-by-round vote totals

## Understanding STV Output

### Console Output Example

```
=== STV Tabulation (3 seats) ===
Total first preference votes: 78914
Droop quota: 19729
Seats to fill: 3

Round 1:
Quota: 19729.0
  🏆 Elana Pirtle-Guiney       : 21588.0 votes
  🏆 Dan Ryan                  : 22373.0 votes
     Sameer Kanal              : 10265.0 votes
     Tiffani Penson            :  7609.0 votes
     ...

Round 2:
Eliminating candidate 44 with 262.0 votes
  -> 97.0 votes to candidate 46
  -> 160.0 votes to candidate 55
  ...

=== Final Results ===
Elected (3 of 3 seats):
  1. Elana Pirtle-Guiney       : 19729.0 votes (Round 12)
  2. Dan Ryan                  : 19729.0 votes (Round 12)
  3. Sameer Kanal              : 19729.0 votes (Round 12)
```

### Key Concepts

**Droop Quota**: The minimum votes needed to guarantee election
- Formula: `floor(total_votes / (seats + 1)) + 1`
- Example: `floor(78914 / 4) + 1 = 19729`

**Rounds**: Each elimination or surplus transfer cycle
- Candidates meeting quota are elected
- Surplus votes are transferred proportionally
- Lowest candidate is eliminated and votes transferred

**Transfer Values**: Fractional vote weights for surplus transfers
- Surplus transfer value = `(candidate_votes - quota) / candidate_votes`
- Ensures exact quota distribution

## STV Algorithm Details

### Round Process

1. **Check for Winners**: Any candidates ≥ quota are elected
2. **Surplus Transfer**: Redistribute excess votes from winners
3. **Elimination**: Remove lowest candidate if no winners
4. **Vote Transfer**: Redistribute eliminated candidate's votes
5. **Repeat**: Until all seats filled

### Transfer Methodology

**Surplus Transfers** (when candidate exceeds quota):
```
transfer_value = (candidate_votes - quota) / candidate_votes
transferred_votes = ballot_count * transfer_value
```

**Elimination Transfers** (when candidate eliminated):
```
transfer_value = 1.0  (full value)
transferred_votes = ballot_count * 1.0
```

### Ballot Preferences

Transfers follow voter preferences:
- Find next continuing candidate on each ballot
- Group transfers by destination candidate
- Apply transfer value to vote totals

## Advanced Features

### Custom STV Parameters

Currently supported:
- Number of seats (default: 3)
- Droop quota calculation
- Sequential elimination of lowest candidates

### Export Options

**Final Results CSV**:
```csv
candidate_id,candidate_name,final_votes,status,election_round
46,Elana Pirtle-Guiney,19729.0,elected,12
55,Dan Ryan,19729.0,elected,12
36,Sameer Kanal,19729.0,elected,12
```

**Round Summary CSV**:
```csv
round,candidate_id,votes,quota,status,exhausted_votes
1,46,12533.0,19729.0,continuing,0.0
1,55,12189.0,19729.0,continuing,0.0
2,46,12630.0,19729.0,continuing,156.0
```

## Integration Options

### Web Interface

View results interactively:
```bash
python scripts/start_server.py --db election_data.db
# Visit: http://localhost:8000/api/stv-results
```

### Programmatic Access

Use the STV engine directly:
```python
from analysis.stv import STVTabulator
from data.database import CVRDatabase

with CVRDatabase("election_data.db") as db:
    tabulator = STVTabulator(db, seats=3)
    rounds = tabulator.run_stv_tabulation()
    results = tabulator.get_final_results()
```

## Troubleshooting

### Common Issues

1. **Database Not Found**
   ```
   Error: Database file required and must exist. Run process_data.py first.
   ```
   - Ensure you've processed CVR data first
   - Check database file path

2. **Missing Tables**
   ```
   Required table 'ballots_long' not found
   ```
   - Re-run data processing: `python scripts/process_data.py`
   - Verify data processing completed successfully

3. **Unexpected Winners**
   - Compare against official results using verification
   - Check if write-in candidates are included/excluded appropriately
   - Verify ballot filtering matches official methodology

### Validation Checks

**Data Integrity**:
- Total votes should remain constant across rounds
- Vote transfers should balance (votes out = votes in)
- Final elected candidates should meet quota

**Algorithm Verification**:
- Use verification script to compare against official results
- Check transfer calculations for accuracy
- Validate quota calculations

## Performance Notes

- **Small datasets** (<100k ballots): ~1-5 seconds
- **Large datasets** (>500k ballots): ~30-60 seconds
- **Memory usage**: Scales linearly with ballot count
- **Optimization**: DuckDB provides efficient querying for transfers

## Next Steps

After running STV analysis:

1. **Verify Results**: See [Verification Guide](verification.md)
2. **Explore Results**: See [Web Interface Guide](web-interface.md)
3. **Understand Mandate**: Analyze quota attribution and coalition patterns

## Mathematical Foundation

The implementation follows standard STV methodology:
- Droop quota for proportional representation
- Weighted inclusive Gregory method for surplus transfers
- Sequential elimination with full transfer values
- Exhaustive ballot preferences with no artificial cutoffs
