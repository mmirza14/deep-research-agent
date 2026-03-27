# Context Quality Improvements — Before/After Comparison

Session: `5f9219ae`
Graph: `/Users/mmirza/Desktop/research_agent/deep-research/data/graph.json`

---

## 1. Relevance-Ranked Truncation

Total findings: 115
Top-30 overlap between old/new: 20/30 (67%)
Findings promoted into top-30 by ranking: 10
Findings dropped from top-30 by ranking: 10

### Promoted (now in top-30, weren't before)
- [b0f7799ab6d7] **Biopolymers in Cosmetic Applications: Sustainable Future Inn** — score=0.652, conf=0.88, old position=#44
- [5e80dd04783a] **Carbomer Market Pricing 2024–2025** — score=0.642, conf=0.78, old position=#43
- [7ea1e143ce20] **Porphyra/Nori Macroalgae Bioactive Review (Journal of Food S** — score=0.618, conf=0.87, old position=#40
- [5004d3571c3d] **TEMPO-CNF: Electrolyte Sensitivity Limits Carbomer Parity** — score=0.610, conf=0.85, old position=#61
- [e10a1a420617] **Ulvan as Promising Marine Polysaccharide for Biomaterial Des** — score=0.600, conf=0.90, old position=#34
- [235d714caad2] **Agrobacterium Curdlan Genetic Engineering Microorganisms 202** — score=0.600, conf=0.90, old position=#39
- [9b0a10050479] **Extremophile-Derived Bioactives in Cosmeceuticals (Life 2025** — score=0.592, conf=0.88, old position=#50
- [375127f33805] **CelluForce CNC Commercial Supplier** — score=0.588, conf=0.87, old position=#52
- [d19923a0794a] **BASF Emulgade Verde Natural Emulsifier Launch (2024)** — score=0.580, conf=0.85, old position=#47
- [db0e55cdeefb] **LPMO Nanocellulose Biorefinery (FEBS Journal 2024)** — score=0.572, conf=0.83, old position=#36

### Demoted (were in top-30, now dropped)
- [0cb6fb54837a] **C16 Biosciences Palmless Fermentation Platform** — score=0.500, conf=0.80
- [597f9209d330] **Scleroglucan vs Xanthan Gum Rheology Comparison (PMC 2023)** — score=0.520, conf=0.85
- [f222fdba8498] **Saccharomyces cerevisiae Cosmetic Biosynthesis (ACS SynBio)** — score=0.520, conf=0.85
- [a784a5aaeea4] **PHA Biopolymer Production Cost Analysis (ScienceDirect 2025)** — score=0.520, conf=0.85
- [9c8bacd3a6b5] **BASF Biobased Cosmetic Polymers (Verdessence)** — score=0.522, conf=0.78
- [1a4180e8340e] **AI / ML in Cosmetics Formulation (ScienceDirect 2024)** — score=0.538, conf=0.82
- [7ff81bd9d373] **Precision Fermentation Cosmetic Polymers Market** — score=0.538, conf=0.82
- [14afbb5e0b96] **Cationic Guar Hair Electrokinetic Study (PMC 2022)** — score=0.540, conf=0.90
- [7bc26ddb6767] **Spider Silk Cosmetics ScienceDirect Review 2025** — score=0.552, conf=0.93
- [97e5747b1db0] **Givaudan PrimalHyal 50 Life Launch 2024** — score=0.568, conf=0.97

---

## 2. Semantic Graph Summary

Old summary length: 2138 chars
New summary length: 6375 chars (+4237)
Has thematic clusters: True
Number of themes: 7
Has gap detection: True

### Old summary (structural only)
```
Graph: 283 nodes, 329 edges.

Nodes by type:
  claim: 128
  source: 103
  concept: 38
  question: 7
  decision: 5
  direction: 2

Low-confidence nodes (6):
  - [65d0ed92cb76] Precision fermentation market projected at $36.3B by 2030 (conf=0.35)
  - [4f5b7e457a78] EU 2023/2055 forces reformulation of acrylate-based cosmetics by 2027-2035 (conf=0.35)
  - [49842c0076c9] Tara gum (Caesalpinia spinosa) commercially deployed COSMOS-approved thickener (conf=0.30)
  - [432b15b32680] EU 2024 Microplastics Ban Drives Bio-Polymer Adoption in Cosmetics (conf=0.35)
  - [80262aad5136] BASF Verdessence Maize: Biodegradable Synthetic Polymer Alternative for Styling (conf=0.30)

Recent nodes:
  - [0da69d7834eb] SYNTHESIS: Confidence Assessment — What We Know vs. Don't Know (concept)
  - [b664fb985803] SYNTHESIS: Key Tensions and Contradictions in the Evidence Base (concept)
  - [e9dd6acdaffb] SYNTHESIS: Precision Fermentation — Strongest Near-Term Pipeline with Market Projection Caveats (decision)
  - [c98443fa2c43] SYNTHESIS: Cost-in-Use Economics — Per-Kg Price is a Misleading Metric (decision)
  - [6c9e22020893] SYNTHESIS: Commercial Readiness Tiers for Bio-Based Polymer Alternatives (2026) (decision)
  - [9325df44e1fc] SYNTHESIS: EU Regulatory Driver — High Certainty for Nano/Insoluble Acrylates, Contested for Carbomer (decision)
  - [3f08b6544eb9] SYNTHESIS: Function-Specific Substitution Is the Only Viable Near-Term Strategy (decision)
  - [c15ae564b360] CP Kelco Keltrol Biodegradable X
```

### New summary (structural + thematic)
```
Graph: 283 nodes, 329 edges.

Nodes by type:
  claim: 128
  source: 103
  concept: 38
  question: 7
  decision: 5
  direction: 2

Low-confidence nodes (6):
  - [65d0ed92cb76] Precision fermentation market projected at $36.3B by 2030 (conf=0.35)
  - [4f5b7e457a78] EU 2023/2055 forces reformulation of acrylate-based cosmetics by 2027-2035 (conf=0.35)
  - [49842c0076c9] Tara gum (Caesalpinia spinosa) commercially deployed COSMOS-approved thickener (conf=0.30)
  - [432b15b32680] EU 2024 Microplastics Ban Drives Bio-Polymer Adoption in Cosmetics (conf=0.35)
  - [80262aad5136] BASF Verdessence Maize: Biodegradable Synthetic Polymer Alternative for Styling (conf=0.30)

Recent nodes:
  - [0da69d7834eb] SYNTHESIS: Confidence Assessment — What We Know vs. Don't Know (concept)
  - [b664fb985803] SYNTHESIS: Key Tensions and Contradictions in the Evidence Base (concept)
  - [e9dd6acdaffb] SYNTHESIS: Precision Fermentation — Strongest Near-Term Pipeline with Market Projection Caveats (decision)
  - [c98443fa2c43] SYNTHESIS: Cost-in-Use Economics — Per-Kg Price is a Misleading Metric (decision)
  - [6c9e22020893] SYNTHESIS: Commercial Readiness Tiers for Bio-Based Polymer Alternatives (2026) (decision)
  - [9325df44e1fc] SYNTHESIS: EU Regulatory Driver — High Certainty for Nano/Insoluble Acrylates, Contested for Carbomer (decision)
  - [3f08b6544eb9] SYNTHESIS: Function-Specific Substitution Is the Only Viable Near-Term Strategy (decision)
  - [c15ae564b360] CP Kelco Keltrol Biodegradable Xanthan: COSMOS + NATRUE Certified Commercial Product (claim)
  - [ea9e4556b9b9] Keratin Hydrolysate (Fermentation-Derived): MW-Dependent Film vs Penetration Dual Function (claim)
  - [5e5655f087cd] Cost Comparison: Bio-Based Alternatives vs Carbomer (2024) (claim)

Most connected nodes:
  - Bio-Based Acrylate Alternatives in Personal Care: 19 connections
  - Advanced Natural Polymer Modifications for Cosmetics: 16 connections
  - Precision Fermentation for Cosmetic Polymers: 16 connections
  - Biotech Platforms Challenging Acrylate Incumbents 2026-2031: 13 connections
  - Bio-Synthetic Hybrid Polymers for Cosmetics: 13 connections

## Research Themes

**Bio-Based Acrylate Alternatives in Personal Care** (127 nodes, 163 edges)
- "Cross-cutting assessment of bio-based polymer candidates vs. synthetic acrylates: rheological performance benchmarks,..." (conf=1.00)
- "What are the next-generation natural and bio-based polymers poised to replace synthetic acrylate chemistry in persona..." (conf=1.00)
- "Emerging biotechnology platforms enabling scalable, cost-competitive production of bio-based cosmetic polymers: preci..." (conf=1.00)

**Precision Fermentation for Cosmetic Polymers** (67 nodes, 96 edges)
- "Which emerging biotech platforms will enable scalable, cost-competitive production of bio-based cosmetic polymers abl..." (conf=1.00)
- "Fermentation-derived or biosynthetic biopolymers produced by engineered microorganisms as candidates to replace synth..." (conf=0.95)
- "Givau
```

---

## 3. MCP Tools for Socratic Critic

Existing transcript Critic turns: 0
Existing tool references in old transcript: 0 (expected: 0)
Total challenge outcomes: 122
Evidence-grounded challenges (heuristic): 33
Surface-level challenges (heuristic): 89

**Expected improvement**: After re-running with MCP access, the Critic should:
- Call get_neighborhood to verify source chains before challenging
- Call query_graph to find contradicting evidence
- Produce challenges that cite specific node IDs and graph relationships

**How to verify**: Re-run Socratic review on this session and compare transcripts.
Count tool_use blocks in the new transcript. Evidence-grounded ratio should increase.

---

## 4. Semantic Search for query_graph

Graph nodes available for search: 283

### Query: "cost reduction in large language models"
Keyword matches: 47
Top 3 keyword hits:
  - [ba7b1ec59075] Cationic Guar vs Polyquaternium-10 Hair Care Performance (Cosmetics &  (overlap=3)
  - [bd1ee5d9fa04] γ-PGA Bacillus Fermentation: Super-Humectant for Cosmetics (overlap=3)
  - [a784a5aaeea4] PHA Biopolymer Production Cost Analysis (ScienceDirect 2025) (overlap=2)
Semantic matches: 5
Top 3 semantic hits:
  - [a784a5aaeea4] PHA Biopolymer Production Cost Analysis (ScienceDirect 2025) (sim=0.228)
  - [c98443fa2c43] SYNTHESIS: Cost-in-Use Economics — Per-Kg Price is a Misleading Metric (sim=0.223)
  - [de10690da93f] PHA bio-based polymers cost 3-12x more than petrochemical equivalents (sim=0.212)
Novel semantic finds (not in keyword top-10): 4

### Query: "environmental impact of cosmetic ingredients"
Keyword matches: 122
Top 3 keyword hits:
  - [cdfb5fc89630] Biobased cosmetic polymer market driven by clean beauty 2024–2032 (overlap=3)
  - [e73072487c8a] EU Green Claims Directive 2024/825 tightens bio-based cosmetic claims (overlap=3)
  - [58de4ce50342] Mycelium/Fungal Fermentation Platforms (overlap=2)
Semantic matches: 5
Top 3 semantic hits:
  - [97c16997bbba] EcoBeautyScore Creates Market Pull for Bio-Based Polymers (sim=0.592)
  - [e18e2e051743] Regulatory Opportunity: Bio-Based Polymers Under EU Cosmetics 1223/200 (sim=0.562)
  - [cdfb5fc89630] Biobased cosmetic polymer market driven by clean beauty 2024–2032 (sim=0.543)
Novel semantic finds (not in keyword top-10): 3

### Query: "regulatory compliance timeline"
Keyword matches: 30
Top 3 keyword hits:
  - [edb61d8d0e29] Claim: EU Directive 2024/825 Restricts Generic "Biobased" Cosmetic Cla (overlap=2)
  - [e18e2e051743] Regulatory Opportunity: Bio-Based Polymers Under EU Cosmetics 1223/200 (overlap=2)
  - [ce53aeb2feae] Performance Parity, Regulatory Readiness & Commercial Scalability Asse (overlap=1)
Semantic matches: 5
Top 3 semantic hits:
  - [328c50815079] EU Biotech Act and Green Deal Bioeconomy Strategy (sim=0.414)
  - [8e027adda45d] EU REACH Microplastics Restriction (Regulation EU 2023/2055) (sim=0.409)
  - [5d0b5bec36d7] EU Regulation 2023/2055 - Microplastics Restriction in Cosmetics (sim=0.400)
Novel semantic finds (not in keyword top-10): 3

### Query: "alternative formulations for banned substances"
Keyword matches: 41
Top 3 keyword hits:
  - [5aaffceb6b13] Evonik Rhamnolipid Biosurfactant Plant Slovakia (overlap=2)
  - [93cd6394b8a7] EU Microplastics Phase-Out Timeline for Cosmetics (overlap=2)
  - [4d0215346eba] Claim: BASF Verdessence Maize Matches Synthetic PVP/VP-VA Styling Perf (overlap=2)
Semantic matches: 5
Top 3 semantic hits:
  - [f7d31f2409fd] EU bans nano acrylate copolymers from cosmetics 2025 (sim=0.450)
  - [93cd6394b8a7] EU Microplastics Phase-Out Timeline for Cosmetics (sim=0.431)
  - [7ee81d442b37] COSMOS v4.1: Polymers Not Allowed; Bio-Based Polysaccharides Permitted (sim=0.421)
Novel semantic finds (not in keyword top-10): 4

### Query: "consumer safety evidence"
Keyword matches: 14
Top 3 keyword hits:
  - [43686ecf3f17] ScienceDirect: Circular Economy Yeast - S. cerevisiae as Sustainable G (overlap=1)
  - [0c8b7cf4c508] Claim: Fungal beta-glucan (CM-beta-glucan from S. cerevisiae) is safe  (overlap=1)
  - [798d129eb435] Claim: Renewable Biopolymer Cosmetics Market to More Than Double to $3 (overlap=1)
Semantic matches: 5
Top 3 semantic hits:
  - [e73072487c8a] EU Green Claims Directive 2024/825 tightens bio-based cosmetic claims (sim=0.284)
  - [97c16997bbba] EcoBeautyScore Creates Market Pull for Bio-Based Polymers (sim=0.261)
  - [5905eb85d8ee] China CSAR Novel Cosmetic Ingredient Registration 2024-2025 (ChemLinke (sim=0.261)
Novel semantic finds (not in keyword top-10): 4


---

## 5. Researcher Cross-Awareness

Active nodes: 283
Existing corroborates edges (caught duplicates): 6
Potential missed duplicates (0.6-0.85 string similarity): 9

### Top potential duplicates the old method missed
- **0.68** similarity:
  A: [edb61d8d0e29] Claim: EU Directive 2024/825 Restricts Generic "Biobased" Co
  B: [e73072487c8a] EU Green Claims Directive 2024/825 tightens bio-based cosmet
- **0.68** similarity:
  A: [f6a28810108f] Cationic guar outperforms PQ-10 at lower concentration
  B: [dc2e8d02d071] Cationic Guar (Jaguar C500) Outperforms PQ-10 at 3x Lower Do
- **0.66** similarity:
  A: [5d6f98c85234] Hydroxypropyl starch phosphate: cold-gel thickener INCI list
  B: [619a0085a9c3] Hydroxypropyl Distarch Phosphate: Safe Thickener with Broad 
- **0.64** similarity:
  A: [69dc3e909aac] OSA starch DS controls Pickering emulsion stability
  B: [713cc4ae1f27] OSA Starch Pickering Emulsions: EAI 61.8 m²/g, 8-Year Stabil
- **0.63** similarity:
  A: [8ef5a4f11baf] S. cerevisiae as synthetic biology platform for cosmetic pol
  B: [621ef938b0b5] Arcaea $78M Series A: synthetic biology platform for petroch
- **0.62** similarity:
  A: [353f6682df1d] China Synthetic Biology Raised 2B+ RMB in 2024 for Cosmetics
  B: [8ef5a4f11baf] S. cerevisiae as synthetic biology platform for cosmetic pol
- **0.62** similarity:
  A: [bcd9ba2d7452] Precision Fermentation Ingredients Market 48.6% CAGR 2025-20
  B: [65d0ed92cb76] Precision fermentation market projected at $36.3B by 2030
- **0.61** similarity:
  A: [5d6f98c85234] Hydroxypropyl starch phosphate: cold-gel thickener INCI list
  B: [99287d4888a8] Hydroxypropyl Guar: Electrolyte-Tolerant Thickener for Ionic
- **0.60** similarity:
  A: [a6c01a8d3509] Claim: EU REACH microplastics restriction (2023/2055) is acc
  B: [432b15b32680] EU 2024 Microplastics Ban Drives Bio-Polymer Adoption in Cos

Graph density: 1.16 edges/node
**Expected improvement**: After re-running researchers with cross-awareness, expect fewer duplicates and higher density (more related_to edges).