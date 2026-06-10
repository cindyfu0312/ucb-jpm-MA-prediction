# Predicting Corporate M&A Activity Using Market Signals and Generative AI

*Merger-Arbitrage Prediction · Event-Driven Strategy · GenAI Signal Extraction*

A data-driven framework to identify, **before public announcement**, which companies are likely to participate in M&A over a 3–6 month horizon — as targets, acquirers, or strategically compatible pairs. The system fuses quantitative market signals, structured fund disclosures, and LLM-based text analysis into per-company probability scores for event-driven and merger-arbitrage workflows.

## Objective

Produce a probability score for each company in the target universe (e.g., S&P 500 / Russell 1000) indicating its likelihood of an M&A event within 3–6 months, to:

- Detect potential **acquisition targets**
- Detect likely **acquirers**
- Identify strategically compatible **acquisition pairs**

## Research Questions

- Can public market data and corporate disclosures predict M&A before announcement?
- Do unusual options patterns contain early signals of acquisitions?
- Can GenAI extract strategic intent from filings and transcripts at scale?
- What industry-consolidation patterns reliably precede deals?

## Data Sources

| Category | Sources |
|---|---|
| Corporate disclosures | 10-K, 10-Q, 8-K; earnings transcripts; investor presentations; press releases |
| Market data | Prices/returns; volatility; liquidity; options activity |
| External | News; analyst reports; industry M&A databases |
| Fund disclosures | ETF holdings; mutual-fund N-PORT/N-CEN; historical holdings time-series |

## Methodology — Three-Component Framework

### Component 1 — Merger-Arb Fund Scoring
Quantify the **ex-ante probability that announced deals close** and rank merger-arb funds by skill.
- **Inputs:** ETF/MF holdings, N-PORT/N-CEN, historical holdings time-series, merger-arb benchmarks.
- **Method:** normalize holdings to a common schema (incl. hedge legs: long target / short acquirer); engineer deal-level features (spread, deal type, financing, days-to-close, regulatory intensity) and fund-level features (entry timing, sizing, turnover); fit a calibrated completion model; score funds via **hit rate, Brier, log loss, realized spread capture**; detect rebalance signals from top-quartile funds; backtest.

### Component 2 — GenAI Signal Extraction
Use LLMs to convert unstructured text into quantitative strategic-intent indicators.
- **Target signals:** "strategic alternatives," "portfolio optimization," "capital allocation flexibility," "exploring partnerships"; sentiment trajectory across consecutive filings.
- **Method:** prompt-based extraction over 10-K/10-Q/8-K, transcripts, and press releases; per-company per-period time-series; validate against historical announcement dates.

### Component 3 — Market Microstructure Detection
Detect abnormal trading that historically precedes announcements.
- **Signals:** unusual options / abnormal call buying, volatility-skew shifts, abnormal price drift, large block trades, put/call divergence.
- **Method:** CAPM-adjusted abnormal returns, volume z-scores, IV percentile rank, skew-change detectors.

## Evaluation Framework

M&A is a rare event, so performance is measured with **ranking-based** metrics, not raw accuracy.

| Metric | Description | Target |
|---|---|---|
| Precision@50 | Acquisitions correctly identified in the top-50 predictions | 10–15 hits |
| Hit rate | Share of top-*N* predictions that are actual targets | > 20% |
| ROC-AUC | Area under ROC across the universe | > 0.70 |
| Event capture | Share of actual events in the top-ranked tier | > 30% |
| Brier score | Calibration quality of completion estimates | < 0.15 |

## Weekly Plan (7 Weeks)

| Wk | Phase | Key activities | Deliverables |
|:--:|---|---|---|
| 1 | Foundation | Scope, KPIs, success criteria; stand up data pipelines (EDGAR, market/options); cloud, version control, experiment tracking; define universe & training window | Scoping doc, data-access confirmation, infra checklist |
| 2 | Market data | Pull returns/volume/volatility/liquidity and options chains (OI, IV, put/call, skew); build abnormal-return, volume z-score, IV-rank, skew/block-trade features; QA & survivorship handling | Market feature matrix, options signal set, QA report |
| 3 | AI / NLP | Parse filings; design strategic-intent & sentiment prompts; LLM inference → per-company signals; transcript tone analysis; validate vs. announcement dates | NLP signal dataset, prompt library, validation report |
| 4 | Fund analytics | Collect ETF/MF holdings; normalize schema incl. hedge legs; deal- & fund-level features; skill metrics (hit rate, Brier, log loss, spread capture); rank funds; rebalance signals | Fund-skill ranking, rebalance-signal feed, deal feature set |
| 5 | Modeling | Merge market + NLP + fund signals into a feature store; train logistic / GBM / ensemble; labels (6-mo binary + survival); time-series CV; calibrate (Platt / isotonic) | Model artifacts, probability scores, CV & calibration results |
| 6 | Validation | Backtest (e.g., 2018–2024); compute all metrics; simulate long top-*N* strategy (P&L, Sharpe); benchmark vs. naive/published; SHAP / feature importance | Backtest report, strategy P&L, importance dashboard |
| 7 | Delivery | Incorporate feedback; finalize inference-ready pipeline with scheduled refresh; produce live ranked predictions; technical docs + model cards; final presentation | Live predictions, documentation, final deck, Phase-2 roadmap |

*Weekly status report every Friday.*

## Assumptions & Risks

| Risk | Mitigation |
|---|---|
| Data-access delays (market/options feeds) | Identify backups (Yahoo Finance, FRED, WRDS) in Week 1 |
| Low M&A base rate in test window | Use rank-based metrics (Precision@K, AUC); augment if needed |
| LLM inference cost / latency | Batch offline; cache embeddings; consider distilled models |
| Look-ahead bias in features | Strict point-in-time discipline; time-series CV splits |

**Assumptions:** access to ≥ 5 years of historical M&A ground truth; SEC EDGAR, market, and options data procurable in Week 1; LLM API access available; weekly stakeholder review (Fridays).

## Phase 2 (Preview)

Real-time monitoring & alerts · pair-level target–acquirer matching · portfolio-system integration for position sizing · expanded mid-cap and international coverage.
