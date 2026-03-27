# Evaluation Scores — Context Quality Improvements

## Baseline: Session 5f9219ae (pre-improvement run)

| Dimension              | Score (1-5) | Notes |
|------------------------|-------------|-------|
| Evidence Centrality    | 3           | Positional truncation meant top-30 missed 10 high-scoring findings. Reports covered available context but couldn't see promoted findings. |
| Challenge Depth        | 2           | 27% evidence-grounded. Critic had no tool access — challenges were text-review only, no source chain verification. 0 tool-intent phrases. |
| Gap Identification     | 2           | Old summary was purely structural (node counts). No thematic gaps, no unanswered question detection. Direction finding had structural analysis but summary didn't surface it. |
| Redundancy             | 3           | String dedup caught 4 duplicates. 9 near-duplicates missed (0.6-0.85 range). No researcher cross-awareness. |
| Thematic Coherence     | 1           | Summary showed counts and "most connected nodes" only. No clustering, no theme descriptions. Lead Agent had to re-discover themes each time. |
| **Total**              | **11/25**   | Below the improvement validation bar of 18. |

---

## Improved: Session eval_8af56c (all improvements active)

| Dimension              | Score (1-5) | Notes |
|------------------------|-------------|-------|
| Evidence Centrality    | 4           | Ranked truncation reordered 73% of top-30 (only 26.7% overlap with positional). Lit review cites graph node labels, references confidence scores, notes Socratic modifications. High-confidence, well-connected findings lead. |
| Challenge Depth        | 4           | Critic shows 15 tool-intent phrases ("let me examine", "check their neighborhoods"). 2.5x more graph-evidence language (124 vs 48 in Critic sections). Challenges cite specific URLs, cross-reference node IDs, identify regulatory inaccuracies by checking source text vs claim. More selective: 86 unchallenged (vs 65) because well-sourced claims verified before challenging. |
| Gap Identification     | 4           | Thematic summary includes "## Gaps" section with unanswered questions and disconnected cluster pairs. Lit review identifies specific data gaps (levan/γ-PGA pricing, Lubrizol pricing). Direction-finding benefits from better summary. |
| Redundancy             | 3           | Caught 13 duplicates (up from 4), but 14 missed. Semantic dedup active but threshold may need tuning. Researcher cross-awareness prompt in place but researchers didn't consistently call query_graph before adding. Graph density improved (1.25 vs 1.16 edges/node, 22 related_to edges vs 8). |
| Thematic Coherence     | 4           | Summary shows 7 research themes with top descriptions and confidence scores. Gap detection identifies disconnected clusters. Lead Agent used the thematic summary to note existing coverage before decomposing ("rich technical data but lacks deep focus on cost barriers"). |
| **Total**              | **19/25**   | Above the validation bar of 18. |

---

## Summary

| Metric | Baseline | Improved | Change |
|--------|----------|----------|--------|
| Rubric total | 11/25 | 19/25 | **+8 points** |
| Truncation overlap (lower=better) | 66.7% | 26.7% | Ranking reorders 73% of top-30 |
| Critic graph-evidence language | 48 | 124 | **+158%** |
| Critic tool-intent phrases | 0 | 15 | Tools being used |
| Caught duplicates | 4 | 13 | **+225%** |
| Edges per node | 1.16 | 1.25 | **+8%** denser graph |
| related_to edges | 8 | 22 | **+175%** more cross-links |
| Thematic clusters in summary | 0 | 7 | From none to full thematic map |
| Gap detection | No | Yes | Unanswered Qs + disconnected pairs |

## Remaining Gaps

1. **Researcher cross-awareness (#5)** is the weakest improvement. Prompt change alone isn't driving consistent query_graph calls before add_node. May need to enforce this at the SDK level or make it a mandatory tool call in the agent definition.

2. **Semantic dedup threshold** (0.85 cosine similarity) may be too conservative — 14 near-duplicates still slipped through. Consider lowering to 0.80 or adding a secondary label-similarity check.

3. **Critic tool usage measurement** is hampered by the SDK consuming tool_use blocks before transcript capture. The transcript module should be updated to capture tool calls explicitly for better observability.

4. **Evidence-grounded % metric** (heuristic-based) is unreliable — it shows 14% for the improved session despite qualitatively better challenges. The heuristic needs refinement (checking for node ID patterns, URL references, and cross-references rather than simple keyword matching).
