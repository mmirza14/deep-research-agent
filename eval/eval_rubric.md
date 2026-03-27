# Context Quality — Manual Evaluation Rubric

Use this rubric to score research outputs before and after the context quality improvements. Score each dimension 1–5 for a given session's outputs. Compare totals across runs.

---

## How to use

1. Run a research session (or re-run Socratic review + report generation on an existing graph)
2. Open the literature review, insights report, and Socratic transcripts
3. Score each dimension below
4. Record scores in the table at the bottom

---

## Dimension 1: Evidence Centrality

*Does the report lead with the strongest, most well-supported findings?*

| Score | Description |
|-------|-------------|
| 1 | Report buries key findings. High-confidence, well-connected claims are absent or mentioned in passing. |
| 2 | Some strong findings appear but are mixed with weak or peripheral ones with no prioritisation. |
| 3 | Most important findings are present. A few high-value claims are missing or underweighted. |
| 4 | Report clearly prioritises strong evidence. Key findings are prominent and supported by citations. |
| 5 | The most central, well-reviewed findings dominate the report. Evidence hierarchy is clear and justified. |

**What to check:**
- Are the top-scored findings (from `proxy_metrics.py` truncation analysis) covered in the report?
- Are low-confidence or withdrawn findings correctly excluded or caveated?
- Does the thematic overview in the lit review reflect the actual graph clusters?

---

## Dimension 2: Challenge Depth

*Are Socratic challenges evidence-grounded rather than surface-level?*

| Score | Description |
|-------|-------------|
| 1 | Challenges are generic ("this seems unsupported") with no reference to graph evidence. |
| 2 | Some challenges reference specific nodes but most are surface-level. |
| 3 | Most challenges identify specific issues. A few cite graph evidence (source chains, contradictions). |
| 4 | Challenges consistently reference specific nodes, source credibility, and evidence chains. |
| 5 | Every challenge is grounded in graph evidence. Critic uses neighborhood/query tools to find contradictions and verify source chains before challenging. |

**What to check:**
- Read `transcript_findings.md` — does the Critic mention node IDs, sources, or graph relationships?
- Does the Critic distinguish well-sourced claims from unsourced ones?
- Are `get_neighborhood` or `query_graph` results referenced in challenges?
- Compare `critic_tool_usage` metrics before/after

---

## Dimension 3: Gap Identification

*Does the system identify real knowledge gaps vs just restating what's missing?*

| Score | Description |
|-------|-------------|
| 1 | No gap identification. Report only summarises what was found. |
| 2 | Gaps are mentioned generically ("more research needed") with no specifics. |
| 3 | Some genuine gaps identified (e.g. specific unanswered questions, missing perspectives). |
| 4 | Gaps are specific and actionable. The system identifies disconnected clusters and unanswered questions. |
| 5 | Gaps are precise, referencing graph structure (unlinked questions, disconnected themes, unsupported claims). The direction-finding phase produces targeted follow-ups. |

**What to check:**
- Does the graph summary show a "Gaps" section with specific items?
- Does the lit review's "Gaps & Limitations" section reference specific graph gaps?
- Do direction nodes from Phase 5 target genuine structural gaps (vs generic suggestions)?

---

## Dimension 4: Redundancy

*How much duplication exists in the graph and reports?*

| Score | Description |
|-------|-------------|
| 1 | Obvious duplicates throughout — same claims from different researchers, repeated in report. |
| 2 | Some duplicates caught but several near-duplicates survive. Report has noticeable repetition. |
| 3 | Most exact duplicates caught. A few semantic duplicates remain. Report has minor repetition. |
| 4 | Near-zero duplicates. Related findings are linked rather than duplicated. Report is tight. |
| 5 | No duplicates survive. Semantic dedup catches paraphrased versions. Graph is dense with cross-links. Report is non-repetitive and every source appears once. |

**What to check:**
- Run `proxy_metrics.py` — check `duplicate_metrics.potential_missed_duplicates`
- Scan the source table in the lit review for duplicate or near-duplicate entries
- Check `related_to` edge count — higher means researchers are linking to existing nodes
- Compare `edges_per_node` before and after

---

## Dimension 5: Thematic Coherence

*Does the system understand what the research is about, not just how much data it has?*

| Score | Description |
|-------|-------------|
| 1 | Summary is purely structural (node counts, edge counts). No thematic awareness. |
| 2 | Some thematic grouping but clusters are poorly labelled or miss key themes. |
| 3 | Themes are identified and mostly correspond to the actual research topics. |
| 4 | Themes are well-labelled, descriptions are informative, and gaps between themes are identified. |
| 5 | Thematic summary is a reliable map of the research landscape. Lead agent uses it to avoid redundant decomposition. Cross-session themes emerge naturally. |

**What to check:**
- Read the graph summary `## Research Themes` section
- Compare theme labels to the actual sub-topics the lead agent decomposed
- Does the Lead Agent's decomposition avoid re-researching covered themes? (Check agent output)
- Are disconnected cluster pairs flagged?

---

## Scoring Sheet

Copy this table for each evaluation run:

```
Session ID:     _______________
Date:           _______________
Version:        [ ] Before improvements  [ ] After improvements
Notes:          _______________

| Dimension              | Score (1-5) | Notes |
|------------------------|-------------|-------|
| Evidence Centrality    |             |       |
| Challenge Depth        |             |       |
| Gap Identification     |             |       |
| Redundancy             |             |       |
| Thematic Coherence     |             |       |
| **Total**              |    /25      |       |
```

---

## Interpreting Results

| Total | Interpretation |
|-------|---------------|
| 5-10  | System is operating with minimal context awareness. Outputs are noisy. |
| 11-15 | Partial improvements. Some dimensions working, others still baseline. |
| 16-20 | Solid improvement. Most context quality issues addressed. |
| 21-25 | Strong context management. Reports are evidence-driven, non-redundant, and thematically coherent. |

**Minimum bar for "improvements validated":** Total >= 18, with no individual dimension below 3.
