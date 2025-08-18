# Phase 2 Performance Issues: Performance Enhancement (Weeks 3-4)
*Smart Caching and Query Optimization*

## Issue #6: Implement LRU Caching Layer for Coalition Data

**Title**: Add intelligent caching layer for frequently accessed coalition analysis data

**Priority**: P1 (High)
**Estimated Effort**: 3-4 days
**Labels**: `performance`, `caching`, `backend`

**Description**:
Implement a smart caching layer to reduce repeated database queries for coalition analysis operations that are frequently accessed with the same parameters.

**Acceptance Criteria**:
- [ ] Implement LRU cache for coalition pairs queries
- [ ] Add parameter-based cache keys (min_shared_ballots, min_strength)
- [ ] Create cache warming scripts for common parameter combinations
- [ ] Implement cache invalidation on data updates
- [ ] Add cache hit/miss ratio monitoring
- [ ] Include memory usage limits and eviction policies
- [ ] Support for distributed caching (Redis) as optional enhancement

**Technical Implementation**:
```python
from functools import lru_cache
from typing import Dict, Any
import hashlib

class CoalitionCache:
    def __init__(self, max_size: int = 128):
        self.max_size = max_size
        self._cache = {}

    def get_cache_key(self, params: Dict[str, Any]) -> str:
        """Generate deterministic cache key from parameters"""
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()

    @lru_cache(maxsize=128)
    def get_coalition_pairs(self, min_shared_ballots: int, min_strength: float):
        """Cached coalition pairs retrieval"""
        pass
```

**Cache Targets**:
- Coalition pairs with different parameter combinations
- Network data generation results
- Candidate centrality calculations
- Supporter segmentation results
- Coalition cluster detection results

**Performance Expectations**:
- Cache hit rate: >80% for common queries
- Cache miss penalty: <10% performance overhead
- Memory usage: 100-200MB for cache layer

---

## Issue #7: Add Query Pattern Optimizations for Centrality Calculations

**Title**: Optimize network centrality and candidate metrics calculations

**Priority**: P1 (High)
**Estimated Effort**: 2-3 days
**Labels**: `performance`, `coalition-analysis`, `optimization`

**Description**:
Optimize expensive network analysis calculations by precomputing centrality metrics and improving SQL query patterns.

**Acceptance Criteria**:
- [ ] Precompute degree centrality for all candidates
- [ ] Precompute strength centrality (weighted by coalition scores)
- [ ] Calculate bridge scores for cross-coalition connectivity
- [ ] Optimize supporter segmentation queries
- [ ] Create materialized views for complex aggregations
- [ ] Add indexed lookup tables for frequent joins
- [ ] Eliminate unnecessary SQL JOINs where possible

**Precomputed Centrality Metrics**:
```sql
CREATE TABLE candidate_centrality (
    candidate_id INTEGER PRIMARY KEY,
    candidate_name VARCHAR,
    degree_centrality DECIMAL(6,4),        -- Number of connections / max possible
    strength_centrality DECIMAL(6,4),      -- Sum of coalition strengths
    bridge_score DECIMAL(6,4),             -- Cross-group connectivity
    cluster_membership VARCHAR(50),         -- Which coalition cluster
    centrality_rank INTEGER,               -- Overall ranking by centrality
    connection_count INTEGER,              -- Total meaningful connections
    avg_coalition_strength DECIMAL(6,4),   -- Average strength of connections
    position_type VARCHAR(20)              -- Hub, Bridge, Peripheral, Isolated
);
```

**Query Optimizations**:
- Replace real-time centrality calculations with table lookups
- Use indexed materialized views for supporter archetypes
- Optimize coalition strength distribution queries
- Add compound indexes for common filter patterns

**Performance Targets**:
- Network centrality API: 1-3s → 200-500ms
- Candidate coalition summary: 500ms-1s → 100-200ms
- Supporter segmentation: 1-2s → 300-600ms

---

## Issue #8: Implement API Response Optimizations

**Title**: Add pagination, compression, and streaming for large API responses

**Priority**: P1 (High)
**Estimated Effort**: 2-3 days
**Labels**: `performance`, `api`, `user-experience`

**Description**:
Optimize API response handling for large datasets through pagination, compression, and progressive loading techniques.

**Acceptance Criteria**:
- [ ] Add pagination to `/api/coalition/pairs/all` endpoint
- [ ] Implement gzip compression for JSON responses
- [ ] Add streaming responses for large datasets
- [ ] Create partial data loading with continuation tokens
- [ ] Implement response size limits with overflow handling
- [ ] Add response time monitoring and alerting
- [ ] Support client-side caching headers

**API Pagination Implementation**:
```python
@app.get("/api/coalition/pairs/all")
async def get_all_candidate_pairs_analysis(
    min_shared_ballots: int = 50,
    min_strength: float = 0.1,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "coalition_strength_score",
    sort_order: str = "desc"
):
    """Paginated coalition pairs with sorting and filtering"""
    pass
```

**Response Format**:
```json
{
    "data": [...],
    "pagination": {
        "page": 1,
        "page_size": 50,
        "total_pages": 12,
        "total_items": 600,
        "has_next": true,
        "has_previous": false
    },
    "metadata": {
        "query_time_ms": 45,
        "cache_hit": true,
        "data_version": "2024-08-18T10:30:00Z"
    }
}
```

**Compression & Streaming**:
- Enable gzip compression for responses >1KB
- Implement streaming for coalition network data
- Add progressive loading for candidate lists
- Support partial content requests (HTTP 206)

---

## Issue #9: Create Performance Monitoring and Benchmarking Suite

**Title**: Implement comprehensive performance monitoring and automated benchmarking

**Priority**: P1 (High)
**Estimated Effort**: 2-3 days
**Labels**: `performance`, `monitoring`, `testing`

**Description**:
Create a comprehensive performance monitoring system to track optimization effectiveness and prevent regressions.

**Acceptance Criteria**:
- [ ] Add response time monitoring for all API endpoints
- [ ] Implement cache hit/miss ratio tracking
- [ ] Create memory and CPU usage monitoring
- [ ] Add automated performance benchmarking suite
- [ ] Implement alerting for performance regressions
- [ ] Create performance dashboard/reporting
- [ ] Add load testing capabilities for concurrent users

**Monitoring Implementation**:
```python
import time
import logging
from functools import wraps

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
        self.logger = logging.getLogger('performance')

    def track_endpoint(self, endpoint_name: str):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    self._record_success(endpoint_name, duration)
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self._record_error(endpoint_name, duration, str(e))
                    raise
            return wrapper
        return decorator
```

**Benchmark Test Suite**:
- API response time benchmarks for all endpoints
- Memory usage profiling for large datasets
- Cache performance validation
- Concurrent user simulation (1, 5, 10, 20 users)
- Data size scaling tests

**Performance Thresholds**:
- API response time: <500ms (95th percentile)
- Cache hit rate: >80% for common queries
- Memory usage: <1GB for full application
- Concurrent users: Support 10+ without degradation

---

## Issue #10: Add Cache Warming and Invalidation Strategies

**Title**: Implement intelligent cache warming and data invalidation mechanisms

**Priority**: P2 (Medium)
**Estimated Effort**: 2 days
**Labels**: `performance`, `caching`, `automation`

**Description**:
Create automated cache warming strategies and intelligent invalidation to maintain optimal cache performance and data freshness.

**Acceptance Criteria**:
- [ ] Implement cache warming script for common parameter combinations
- [ ] Add automatic cache invalidation on data updates
- [ ] Create cache preloading for application startup
- [ ] Implement intelligent cache eviction based on usage patterns
- [ ] Add cache statistics and health monitoring
- [ ] Create cache warming job scheduling
- [ ] Implement cache validation and consistency checks

**Cache Warming Strategy**:
```python
class CacheWarmer:
    def __init__(self, cache_manager):
        self.cache = cache_manager
        self.common_parameters = [
            {'min_shared_ballots': 50, 'min_strength': 0.1},
            {'min_shared_ballots': 100, 'min_strength': 0.15},
            {'min_shared_ballots': 200, 'min_strength': 0.25},
            # Additional common combinations
        ]

    async def warm_coalition_cache(self):
        """Pre-populate cache with common queries"""
        for params in self.common_parameters:
            await self.cache.get_coalition_pairs(**params)

    async def warm_network_cache(self):
        """Pre-populate network analysis cache"""
        pass
```

**Invalidation Triggers**:
- New CVR data loaded
- Precomputed tables updated
- Configuration changes affecting calculations
- Manual cache clear requests
- Data integrity issues detected

**Cache Health Monitoring**:
- Hit/miss ratios by endpoint
- Cache size and memory usage
- Eviction frequency and patterns
- Data staleness tracking
- Performance impact measurement

---

## Phase 2 Milestone Definition

**Milestone**: "Smart Caching and Query Optimization"

**Success Criteria**:
- [ ] All 5 issues (#6-#10) completed and tested
- [ ] 95% of API requests respond in <500ms
- [ ] Cache hit rate >80% for common queries
- [ ] Memory usage optimized and monitored
- [ ] Performance monitoring dashboard operational
- [ ] Automated benchmarking suite operational
- [ ] Load testing validates concurrent user support

**Performance Validation**:
```python
# Benchmark targets after Phase 2
PERFORMANCE_TARGETS = {
    'coalition_pairs_all': 200,      # ms (vs 2000-5000ms baseline)
    'coalition_network': 300,        # ms (vs 3000-8000ms baseline)
    'candidate_centrality': 150,     # ms (vs 1000-3000ms baseline)
    'supporter_segments': 400,       # ms (vs 1000-2000ms baseline)
    'cache_hit_rate': 80,           # percentage
    'memory_usage_mb': 800,         # MB total application
    'concurrent_users': 10          # simultaneous users supported
}
```

**Validation Process**:
1. Execute automated benchmark suite
2. Validate cache performance under load
3. Test concurrent user scenarios (1, 5, 10, 20 users)
4. Verify memory usage stays within targets
5. Confirm all performance monitoring systems operational
6. Validate data accuracy with caching enabled

**Risk Mitigation**:
- Maintain ability to disable caching if issues arise
- Implement cache bypass mechanisms for debugging
- Add comprehensive cache validation to prevent stale data issues
- Create rollback procedures for performance optimizations
- Monitor for memory leaks and cache bloat
