# Enhanced Coalition Analysis: Statistical Rigor & Toggle-Driven Implementation

## Executive Summary

Your philosophical feedback identifies critical gaps in our current coalition analysis approach. The core issue: we're currently analyzing "interesting correlations" rather than "rigorous electoral intelligence." This plan transforms our methodology through **toggle-driven implementation** that allows users to see the impact of each statistical control while maintaining pipeline efficiency.

## Current State Analysis

### Existing Pipeline Dependencies
**Current Data Flow**: `CVR → ballots_long → analysis views → coalition calculations`
- ✅ **Smart Caching**: `_is_ballots_long_current()` prevents unnecessary recomputation
- ✅ **Real-time Computation**: All coalition analysis computed on-demand from `ballots_long`
- ✅ **SQL Views**: Basic analysis precomputed (first_choice_totals, votes_by_rank, etc.)
- ✅ **No Heavy Precomputation**: Current approach avoids pipeline complexity

### Key Insight: Most Enhancements Require **Zero Pipeline Changes**
The sophisticated statistical controls you've outlined can be implemented as **runtime toggles** without any changes to the data pipeline, making this a low-risk, high-impact enhancement.

## Implementation Strategy: Toggle-First Architecture

### Phase 1: Methodology Toggles (Zero Pipeline Impact)

**Real-time API Parameter Toggles**:
```javascript
// Example: /api/coalition/pairs?method=proximity_weighted&normalize=lift&ci=bootstrap
{
  "method": "basic" | "proximity_weighted" | "directional",
  "normalize": "raw" | "conditional" | "lift",
  "confidence_intervals": false | "bootstrap" | "analytical",
  "min_shared_ballots": 200,
  "ballot_length_filter": false | true,
  "popularity_control": false | true
}
```

**Core Statistical Enhancements (Runtime Implementation)**:

1. **Normalization Against Baselines** ⚡ *Zero pipeline impact*
   - Toggle between raw co-occurrence vs conditional probability vs lift
   - Implement `P(B∈top-k | A∈top-k)` calculations
   - Add `lift = P(A∧B)/[P(A)P(B)]` option
   - "Excess proximity" = observed - expected under independence

2. **Directional & Local Proximity** ⚡ *Zero pipeline impact*
   - Track `A→B` vs `B→A` as distinct relationships
   - Implement proximity kernel: `S_A,B = Σ w(d) * P(B at r+d | A at r)`
   - Distance-specific analysis: "A at rank r, B at r+1" vs "A at rank r, B at r+2"

3. **Ballot Length Controls** ⚡ *Zero pipeline impact*
   - Filter analysis to ballots where `len(ballot) ≥ max(rankA, rankB)`
   - Toggle to control for truncation bias
   - Exhaustion bias detection warnings

4. **Bootstrap Confidence Intervals** ⚡ *Zero pipeline impact*
   - On-demand bootstrap sampling for CIs
   - Stability thresholds for "strong coalition" labels
   - User-configurable confidence levels

### Phase 2: Enhanced Views (One-Time Pipeline Addition)

**New SQL Views** (add to `04_basic_analysis.sql`):
```sql
-- Ballot metadata for truncation controls
CREATE OR REPLACE VIEW ballot_metadata AS
SELECT BallotID, COUNT(*) as ballot_length,
       MAX(rank_position) as max_rank
FROM ballots_long GROUP BY BallotID;

-- Rank transition pairs for directional analysis
CREATE OR REPLACE VIEW rank_transitions AS
SELECT b1.BallotID, b1.candidate_id as from_candidate,
       b2.candidate_id as to_candidate,
       b1.rank_position as from_rank,
       b2.rank_position as to_rank
FROM ballots_long b1
JOIN ballots_long b2 ON b1.BallotID = b2.BallotID
                    AND b2.rank_position = b1.rank_position + 1;
```

**Pipeline Trigger**: Only when these views are added (one-time schema enhancement).

### Phase 3: Advanced Precomputation (Optional Performance Tier)

**Power User Optimization** (new `06_coalition_cache.sql`):
```sql
-- Heavy lifting for sub-second response times
CREATE OR REPLACE TABLE coalition_proximity_cache AS ...
CREATE OR REPLACE TABLE coalition_bootstrap_cache AS ...
```

**Pipeline Trigger**: Optional for users wanting <50ms response times.

## The 3 Core Questions Framework

Transform complex coalition analysis into **3 intuitive questions**:

### 1. "Next Choice Rate" (A → B)
```
Of ballots that ranked A anywhere, what % had B immediately after A?
Reads like: "A's people usually go to B."
```

### 2. "Close-Together Rate" (A & B)
```
% of ballots that list both A and B within the top 3 spots (in any order).
Reads like: "same lane / similar vibe."
```

### 3. "Follow-Through" (A → B reality)
```
When A was eliminated (or had surplus), what share actually landed on B?
Reads like: "did the affection turn into action?"
```

## Advanced Metrics Implementation

### Interpretable Metrics (Runtime Calculation)
- **Immediate-follow index**: `P(B immediately after A)` for "ticket" behavior
- **Top-k mutuality**: Share with both in top-k and `|rankA-rankB|≤1`
- **Fallbackiness score**: Share of A-first ballots where B appears at lower rank
- **Excess transfer**: Realized A→B / proximity-predicted transfer

### Visual Grammar Enhancements
- **Rank-Lag Impulse Heatmaps**: 6×6 matrix showing `P(B at r+Δ | A at r)`
- **Order-aware Chord Diagrams**: Adjacent rank relations with directional arrows
- **Transfer vs Proximity Quadrants**: Scatter revealing latent vs actual alliances
- **Stability Ribbons**: Show confidence intervals on all metrics

## Automation Strategy

### File-Based Pipeline Triggers
```bash
# Git hooks detect when re-runs needed
PIPELINE_FILES="sql/04_basic_analysis.sql sql/05_candidate_analysis.sql"
CACHE_FILES="sql/06_coalition_cache.sql src/analysis/coalition.py"

if git diff --name-only HEAD | grep -E "(${PIPELINE_FILES})"; then
  echo "⚠️  Pipeline files changed - recommend: python scripts/process_data.py --refresh-analysis"
fi
```

### Schema Version Tracking
```sql
CREATE OR REPLACE TABLE schema_versions AS
SELECT 'coalition_analysis_v2' as feature,
       'proximity_weighted_directional' as version,
       CURRENT_TIMESTAMP as installed_at;
```

## Implementation Roadmap

### Week 1: Toggle Architecture Foundation
- ✅ Add methodology toggles to existing `/api/coalition/*` endpoints
- ✅ Implement conditional probability calculations (runtime)
- ✅ Add lift calculation toggles with popularity bias controls
- ✅ Bootstrap CI toggle (computed on-demand)
- **Zero pipeline changes required**

### Week 2: Enhanced Views & Directional Analysis
- Add `ballot_metadata` and `rank_transitions` views to `04_basic_analysis.sql`
- Implement directional proximity analysis with A→B vs B→A tracking
- Add proximity kernel scoring with distance weighting
- **Pipeline trigger**: One-time view addition

### Week 3: Advanced Statistical Controls
- "Excess proximity" calculations with independence baselines
- Ballot length conditioning and truncation bias warnings
- Geographic stratification toggle (if precinct data available)
- Statistical significance gating for coalition labels

### Week 4: User Experience & Documentation
- Simplified UI with 3-question framework
- Advanced toggle explanations and educational content
- Pipeline trigger documentation and automation
- Performance tier options (basic/advanced/power user)

## User Experience Benefits

### Educational Value Through Toggles
Users can experiment and see immediate impact:
- **Raw vs Normalized**: See how popularity bias affects results
- **Basic vs Directional**: Understand A→B vs B→A differences
- **With/Without CI**: Learn about statistical uncertainty
- **Ballot Length Filtering**: Observe truncation bias effects

### Performance Tiers
- **Basic Tier**: Real-time toggles (200-500ms response)
- **Enhanced Tier**: Light precomputation (50-200ms response)
- **Power User**: Full cache (sub-50ms response)

### Zero-Surprise Pipeline Management
- Clear documentation of when re-runs needed
- Automated detection and warnings
- Git hooks for change detection
- Schema versioning for feature tracking

## Migration Strategy

### Backward Compatibility
- All existing endpoints remain functional
- New parameters are optional with sensible defaults
- Progressive enhancement approach
- Existing UI continues working during development

### Risk Mitigation
- Phase 1 has zero breaking changes
- Toggle approach allows A/B testing
- Incremental rollout with user feedback
- Fallback to existing methods if issues arise

## Expected Outcomes

### For Researchers & Analysts
- **Rigorous Statistics**: Move from correlations to causal insights
- **Methodological Transparency**: See impact of each analytical choice
- **Confidence Intervals**: Understand uncertainty in all metrics
- **Publication Quality**: Statistical rigor suitable for academic work

### For General Users
- **Simplified Interface**: 3-question framework makes analysis accessible
- **Educational Journey**: Learn RCV dynamics through interactive exploration
- **Confidence Building**: Understand what metrics mean and when to trust them
- **Progressive Disclosure**: Start simple, dig deeper as needed

### For Developers
- **Clean Architecture**: Toggle system scales to future enhancements
- **Performance Options**: Choose appropriate tier for use case
- **Pipeline Clarity**: Know exactly when re-runs are needed
- **Future-Proof**: Framework supports advanced statistical methods

## Success Metrics

1. **Statistical Rigor**: All coalition metrics include confidence intervals
2. **User Education**: Users understand methodology choices through toggles
3. **Performance**: Maintain sub-500ms response times for basic analysis
4. **Adoption**: Increased usage of advanced analytical features
5. **Pipeline Efficiency**: Clear triggers prevent unnecessary recomputation

This plan transforms coalition analysis from "interesting patterns" to "rigorous electoral intelligence" while maintaining the system's performance and usability through intelligent architecture design.
