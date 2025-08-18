# Phase 1 Performance Issues: Foundation (Weeks 1-2)
*High-Impact Quick Wins for Coalition Analysis Performance*

## Issue #1: Create Precomputation Batch Processor

**Title**: Implement batch data precomputation pipeline for performance optimization

**Priority**: P0 (Critical)
**Estimated Effort**: 3-4 days
**Labels**: `performance`, `architecture`, `backend`

**Description**:
Create a comprehensive batch processing pipeline to precompute expensive analytical operations that currently run on-demand.

**Acceptance Criteria**:
- [ ] Create `scripts/precompute_data.py` with CLI interface
- [ ] Support `--election-id` parameter for multiple elections
- [ ] Add `--force-refresh` flag to rebuild all precomputed data
- [ ] Include progress reporting and logging
- [ ] Generate data validation reports
- [ ] Add error handling and rollback capabilities
- [ ] Integration with existing data processing pipeline

**Technical Requirements**:
- Use existing DuckDB connection management
- Implement incremental processing where possible
- Add data versioning and timestamps
- Include memory usage optimization
- Support parallel processing for independent computations

**Definition of Done**:
- Script successfully precomputes all target data tables
- Documentation updated with usage instructions
- Integration tests pass for precomputed data accuracy
- Performance benchmarks show expected improvements

---

## Issue #2: Implement Adjacent Pairs Precomputation

**Title**: Precompute candidate pairwise relationships and coalition metrics

**Priority**: P0 (Critical)
**Estimated Effort**: 2-3 days
**Labels**: `performance`, `coalition-analysis`, `backend`

**Description**:
Replace expensive real-time self-joins on `ballots_long` with precomputed pairwise candidate relationship data.

**Acceptance Criteria**:
- [ ] Create `adjacent_pairs` table with all candidate pair combinations
- [ ] Precompute ranking distance calculations and distributions
- [ ] Calculate strong/weak coalition vote counts
- [ ] Generate proximity-weighted affinity scores
- [ ] Include transfer vote estimations
- [ ] Add coalition type classifications
- [ ] Optimize for storage efficiency (use appropriate data types)

**Technical Details**:
```sql
-- Target table structure
CREATE TABLE adjacent_pairs (
    candidate_1 INTEGER,
    candidate_2 INTEGER,
    candidate_1_name VARCHAR,
    candidate_2_name VARCHAR,
    shared_ballots INTEGER,
    total_ballots_1 INTEGER,
    total_ballots_2 INTEGER,
    avg_ranking_distance DECIMAL(4,2),
    min_ranking_distance INTEGER,
    max_ranking_distance INTEGER,
    strong_coalition_votes INTEGER,  -- distance <= 2
    weak_coalition_votes INTEGER,    -- distance >= 4
    basic_affinity_score DECIMAL(6,4),
    proximity_weighted_affinity DECIMAL(6,4),
    coalition_strength_score DECIMAL(6,4),
    coalition_type VARCHAR(20),
    transfer_votes_1_to_2 INTEGER,
    transfer_votes_2_to_1 INTEGER
);
```

**Performance Target**:
- Coalition pairs API response time: 2-5s → 50-200ms
- Network data generation: 3-8s → 200-500ms

---

## Issue #3: Update Coalition APIs to Use Precomputed Data

**Title**: Refactor coalition analysis APIs to query precomputed tables

**Priority**: P0 (Critical)
**Estimated Effort**: 2-3 days
**Labels**: `performance`, `api`, `coalition-analysis`

**Description**:
Modify all coalition analysis endpoints to use precomputed data instead of real-time calculations.

**Acceptance Criteria**:
- [ ] Update `/api/coalition/pairs/all` to query `adjacent_pairs` table
- [ ] Modify `/api/coalition/pairs/{id1}/{id2}` for single pair lookups
- [ ] Update `/api/coalition/network` to use precomputed centrality metrics
- [ ] Modify `/api/coalition/clusters` to use precomputed relationships
- [ ] Add fallback to live computation if precomputed data unavailable
- [ ] Maintain backward compatibility with existing API contracts
- [ ] Update response schemas if needed for additional data

**API Endpoints to Update**:
- `/api/coalition/pairs/all`
- `/api/coalition/pairs/{candidate_1_id}/{candidate_2_id}`
- `/api/coalition/proximity/{candidate_1_id}/{candidate_2_id}`
- `/api/coalition/network`
- `/api/coalition/clusters`
- `/api/coalition/types`

**Testing Requirements**:
- Response accuracy validation against current implementation
- Performance benchmarking for all endpoints
- Error handling for missing precomputed data
- API contract compatibility testing

---

## Issue #4: Add Optimized Data Types and Dictionary Encoding

**Title**: Implement memory-efficient data types and dictionary encoding

**Priority**: P1 (High)
**Estimated Effort**: 2 days
**Labels**: `performance`, `storage`, `optimization`

**Description**:
Optimize data storage and memory usage through appropriate data types and dictionary encoding for categorical variables.

**Acceptance Criteria**:
- [ ] Dictionary-encode `candidate_id` (22 candidates + write-ins)
- [ ] Use INT8 for `rank_position` (values 1-6)
- [ ] Use INT16 for `BallotID` where possible
- [ ] Implement VARCHAR length optimization for candidate names
- [ ] Add Parquet export capability for precomputed data
- [ ] Include compression options for storage efficiency
- [ ] Validate data integrity after type conversions

**Implementation Details**:
```python
# Data type optimization mapping
OPTIMIZED_TYPES = {
    'candidate_id': 'INT8',      # 22 candidates + write-ins
    'rank_position': 'INT8',     # 1-6 ranks
    'BallotID': 'INT32',         # 332K ballots
    'PrecinctID': 'INT16',       # Reasonable precinct count
    'ranking_distance': 'INT8',   # 0-5 max distance
    'shared_ballots': 'INT32',    # Up to total ballot count
    'coalition_strength_score': 'DECIMAL(6,4)'  # 0.0000-1.0000
}
```

**Expected Benefits**:
- Memory usage: 50-70% reduction
- I/O performance: 30-50% improvement
- Storage size: 40-60% reduction

---

## Issue #5: Eliminate Dynamic Wide→Long Transformations

**Title**: Persist ballots_long table and eliminate startup UNPIVOT operations

**Priority**: P1 (High)
**Estimated Effort**: 2-3 days
**Labels**: `performance`, `data-loading`, `startup`

**Description**:
Remove expensive dynamic wide-to-long transformations that run on every application startup by persisting the normalized data.

**Acceptance Criteria**:
- [ ] Modify CVR parser to persist `ballots_long` permanently
- [ ] Add incremental data loading for new CVR files
- [ ] Implement data versioning and change detection
- [ ] Create data integrity validation checks
- [ ] Add rollback capability for data corruption scenarios
- [ ] Update startup process to validate existing data instead of rebuilding
- [ ] Maintain compatibility with existing data loading workflows

**Technical Implementation**:
```python
# New data loading workflow
def load_cvr_data(csv_path, force_rebuild=False):
    if not force_rebuild and table_exists('ballots_long'):
        # Validate existing data
        if validate_data_integrity():
            logger.info("Using existing ballots_long table")
            return get_data_stats()
    
    # Rebuild only if necessary
    return rebuild_ballots_long(csv_path)
```

**Performance Target**:
- Application startup: 15-30s → 2-5s
- Data reload operations: 80% faster
- Eliminate repeated UNPIVOT operations

**Testing Requirements**:
- Data integrity validation after persistence
- Incremental loading accuracy testing
- Startup time benchmarking
- Rollback mechanism testing

---

## Phase 1 Milestone Definition

**Milestone**: "Precomputation Pipeline MVP"

**Success Criteria**:
- [ ] All 5 issues completed and tested
- [ ] Coalition analysis response time < 200ms (vs current 2-5s)
- [ ] Application startup time < 5 seconds (vs current 15-30s)
- [ ] All existing functionality preserved and tested
- [ ] Performance benchmarking completed with documented improvements
- [ ] Documentation updated for new precomputation workflow

**Validation Process**:
1. Run comprehensive performance benchmarks
2. Execute full test suite to ensure no regressions
3. Validate API response accuracy against baseline
4. Test concurrent user scenarios
5. Verify memory usage improvements

**Risk Mitigation**:
- Maintain fallback to live computation for all precomputed operations
- Implement comprehensive data validation and integrity checks
- Create rollback procedures for each optimization
- Add monitoring and alerting for performance regressions