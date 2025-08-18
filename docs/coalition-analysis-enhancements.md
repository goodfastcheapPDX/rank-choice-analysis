# Coalition Analysis Enhancements - Technical Design Document

## Summary of Inquiry

This document summarizes a deep dive into the current coalition analysis capabilities and identifies opportunities to enhance the system to provide more nuanced political insights from ranked-choice voting data.

## Current State Analysis

### What We Have
- **Basic Affinity Analysis**: Counts ballots where candidates appear together (regardless of ranking)
- **Vote Transfer Analysis**: Shows where votes would go if candidates were eliminated (ranking matters)
- **Simple Coalition Detection**: Identifies candidate pairs with high co-occurrence

### What We're Missing
- **Ranking Proximity Analysis**: Understanding the political significance of ranking distance
- **Coalition Type Classification**: Distinguishing between strong alliances vs. strategic fallbacks
- **Comprehensive Pair Exploration**: Detailed analysis of every candidate relationship

## Key Insight: Ranking Proximity Matters

### Current Gap
The system treats "A ranked 1st, B ranked 2nd" the same as "A ranked 1st, B ranked 6th" for affinity purposes, but these represent fundamentally different political relationships:

- **A(1) + B(2)**: Strong political alliance - voters see them as representing similar values
- **A(1) + B(6)**: Weak acceptance - voters would take B as a last resort, but don't see ideological alignment

### Political Significance
- **Close rankings (1-2, 2-3)**: Suggest ideological similarity and strong coalition potential
- **Distant rankings (1-6, 2-7)**: Suggest strategic voting and weak coalition bonds
- **Transfer patterns**: Reveal how voters think about candidates relative to each other

## Proposed Architecture Enhancements

### 1. Enhanced Data Models

```python
@dataclass
class DetailedCandidatePair:
    """Comprehensive analysis of a candidate pair relationship."""
    candidate_1: int
    candidate_1_name: str
    candidate_2: int
    candidate_2_name: str

    # Basic co-occurrence
    shared_ballots: int
    total_ballots_1: int
    total_ballots_2: int

    # Ranking proximity analysis
    ranking_distances: List[int]  # All observed distances between rankings
    avg_ranking_distance: float
    min_ranking_distance: int
    max_ranking_distance: int

    # Proximity-weighted metrics
    strong_coalition_votes: int  # Ballots with candidates ranked 1-2, 2-3, etc.
    weak_coalition_votes: int   # Ballots with candidates ranked far apart

    # Transfer analysis
    transfer_votes_1_to_2: int  # If 1 eliminated, how many go to 2
    transfer_votes_2_to_1: int  # If 2 eliminated, how many go to 1

    # Affinity scores
    basic_affinity_score: float  # Current Jaccard similarity
    proximity_weighted_affinity: float  # New proximity-weighted score
    coalition_strength_score: float  # Combined metric
```

### 2. New Analysis Methods

```python
def calculate_detailed_pairwise_analysis(self, min_shared_ballots: int = 10) -> List[DetailedCandidatePair]:
    """Calculate comprehensive analysis for all candidate pairs."""

def analyze_ranking_proximity(self, candidate_1: int, candidate_2: int) -> Dict:
    """Analyze how close candidates typically appear in rankings."""

def calculate_proximity_weighted_affinity(self, candidate_1: int, candidate_2: int) -> float:
    """Calculate affinity score weighted by ranking proximity."""

def identify_coalition_types(self, candidate_1: int, candidate_2: int) -> Dict:
    """Classify the type of coalition: strong, weak, strategic, etc."""
```

### 3. New API Endpoints

```python
@app.get("/api/coalition/pairs/{candidate_1_id}/{candidate_2_id}")
async def get_detailed_pair_analysis(candidate_1_id: int, candidate_2_id: int):
    """Get comprehensive analysis of a specific candidate pair."""

@app.get("/api/coalition/pairs/all")
async def get_all_candidate_pairs_analysis(min_shared_ballots: int = 10):
    """Get analysis for all candidate pairs meeting minimum threshold."""

@app.get("/api/coalition/pairs/proximity")
async def get_proximity_analysis(proximity_threshold: int = 3):
    """Get pairs with specific ranking proximity characteristics."""

@app.get("/api/coalition/pairs/coalition-types")
async def get_coalition_type_breakdown():
    """Get breakdown of different coalition types across all pairs."""
```

### 4. Database Schema Enhancements

```sql
-- Materialized view for ranking proximity analysis
CREATE VIEW candidate_pair_proximity AS
SELECT
    b1.candidate_id as candidate_1,
    b2.candidate_id as candidate_2,
    b1.BallotID,
    ABS(b1.rank_position - b2.rank_position) as ranking_distance,
    b1.rank_position as rank_1,
    b2.rank_position as rank_2
FROM ballots_long b1
JOIN ballots_long b2 ON b1.BallotID = b2.BallotID
    AND b1.candidate_id < b2.candidate_id;

-- Index for performance
CREATE INDEX idx_pair_proximity ON candidate_pair_proximity(candidate_1, candidate_2);
```

### 5. Frontend Components

- **Pair Explorer**: Interactive grid showing all candidate pairs
- **Proximity Filter**: Filter pairs by ranking distance ranges
- **Coalition Type Breakdown**: Charts showing distribution of coalition types
- **Detailed Pair View**: Drill-down into specific candidate relationships
- **Export Functionality**: Download comprehensive pair analysis data

### 6. Performance Considerations

```python
# Cache detailed analysis results
@lru_cache(maxsize=1000)
def get_cached_pair_analysis(self, candidate_1: int, candidate_2: int) -> DetailedCandidatePair:

# Batch processing for large datasets
def calculate_all_pairs_batch(self, batch_size: int = 100) -> List[DetailedCandidatePair]:
```

### 7. Configuration Options

```python
class AnalysisConfig:
    proximity_weights: Dict[int, float]  # Weight for each ranking distance
    strong_coalition_threshold: int = 3   # Max distance for "strong" coalition
    weak_coalition_threshold: int = 6     # Min distance for "weak" coalition
    min_shared_ballots: int = 10          # Minimum ballots for analysis
```

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- Add ranking proximity analysis to existing affinity calculation
- Create new data models for detailed pair analysis
- Implement basic proximity-weighted affinity scoring

### Phase 2: Core Analysis (Week 3-4)
- Build comprehensive pairwise analysis engine
- Add coalition type classification
- Implement transfer pattern analysis integration

### Phase 3: API Layer (Week 5-6)
- Create new endpoints for detailed pair exploration
- Add filtering and pagination for large datasets
- Implement caching for performance

### Phase 4: Frontend (Week 7-8)
- Build interactive pair exploration interface
- Add visualization components for coalition types
- Implement export and reporting features

### Phase 5: Optimization (Week 9-10)
- Performance tuning and database optimization
- Add batch processing capabilities
- Implement advanced caching strategies

## Expected Outcomes

### Enhanced Political Insights
- **Strong Coalitions**: Identify candidates with genuine ideological alignment
- **Weak Coalitions**: Spot strategic voting patterns and fallback preferences
- **Voter Segmentation**: Understand different voter groups and their preferences
- **Strategic Positioning**: See how candidates position themselves relative to others

### Better Decision Support
- **Campaign Strategy**: Help candidates understand their coalition potential
- **Voter Education**: Show voters how their preferences relate to others
- **Policy Analysis**: Understand the political landscape and coalition dynamics
- **Election Reform**: Provide data for improving ranked-choice systems

## Technical Considerations

### Data Volume
- Current Portland election: ~50,000 ballots, ~60 candidates = 1,770 candidate pairs
- Each pair requires detailed analysis of ranking patterns
- Consider materialized views and caching for performance

### Scalability
- Design for elections with 100+ candidates and 100,000+ ballots
- Implement batch processing for large datasets
- Use async processing for long-running analyses

### Maintainability
- Keep existing API endpoints working
- Add new functionality incrementally
- Maintain clear separation between basic and advanced analysis

## Conclusion

This enhancement would transform the coalition analysis from a simple "who appears together" tool into a sophisticated political intelligence platform that reveals the nuanced relationships between candidates based on how voters actually think about and prioritize them. The ranking proximity analysis would provide insights that are currently invisible but politically crucial for understanding coalition dynamics in ranked-choice elections.
