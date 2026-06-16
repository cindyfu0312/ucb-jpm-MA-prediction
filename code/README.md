# M&A Prediction - Industry Project Proposal

**Dexin Fu, Ronald Liu**



## Project Objective

Develop a multi-signal predictive model to identify, before public announcement, which companies are likely to:

- Be acquired (target identification)
- Act as acquirers (acquirer identification)
-  Form strategically compatible acquisition pairs 

The resulting model supports event-driven trading strategies including merger arbitrage, risk trading, and institutional market intelligence workflows.



## Research Questions

- Can public market data and corporate disclosures predict M&A activity prior to announcement?
- Do unusual options trading patterns contain early signals of acquisitions?
- Can Generative AI extract strategic intent from filings and earnings transcripts at scale?
- What structural industry consolidation patterns reliably precede acquisitions?



## Data Sources

| **Category**              | **Sources**                                                  |
| ------------------------- | ------------------------------------------------------------ |
| **Corporate Disclosures** | SEC filings (10-K, 10-Q, 8-K), earnings call transcripts, investor  presentations, press releases |
| **Market Data**           | Stock prices & returns, volatility, liquidity metrics, options  trading activity |
| **External Information**  | News articles, analyst reports, industry M&A databases       |
| **Fund Disclosures**      | ETF daily/periodic holdings, mutual fund N-PORT/N-CEN schedules,  historical holdings time-series |



## Current Local Data Pipeline

The current prototype links three local datasets by ticker:

| **File** | **Role** | **Key Columns** |
| -------- | -------- | --------------- |
| `data/raw/index/us_listed_companies_sec.csv` | US-listed company universe from the SEC ticker master | `ticker`, `company_name`, `exchange`, `cik` |
| `data/raw/market/daily_prices.csv` | Daily OHLCV market history | `date`, `ticker`, `open`, `high`, `low`, `close`, `volume`, `ret` |
| `data/raw/events/ma_events.csv` | Cleaned M&A ground-truth events | `announcement_date`, `target_ticker`, `acquirer_ticker`, `deal_status`, `close_date`, `deal_value_usd` |

### 1. Universe Construction

The project now uses a broad US-listed universe instead of only Russell 1000 constituents.

```bash
python3 code/download_us_listed_companies.py
```

This writes `data/raw/index/us_listed_companies_sec.csv`, which is used as the ticker and company-name master for matching M&A targets. A broad universe is important because M&A target events are rare; limiting the sample to Russell 1000 creates too few positive labels for machine learning.

### 2. M&A Event Cleaning

The raw S&P Global transaction spreadsheet is cleaned into the Week 1 event schema with:

```bash
python3 code/clean_ma_events.py
```

The cleaner keeps US transactions where the target can be mapped to a listed ticker. The buyer can be public, private, foreign, PE-backed, or unknown; therefore `acquirer_ticker` is allowed to be blank. The output is:

- `data/raw/events/ma_events.csv`: compact event label file used by analysis notebooks
- `data/raw/events/ma_events_match_audit.csv`: audit file with original target/buyer names and ticker-match details

For target prediction, `target_ticker` and `announcement_date` are the most important fields. `acquirer_ticker` is useful for acquirer prediction and pair modeling, but it should not be required because many buyers are not public US-listed companies.

### 3. Linking OHLCV to M&A Labels

The main modeling table should be a ticker-date panel. For each company and each prediction date (`as_of_date`), features must be built only from OHLCV data available on or before that date:

| **Feature Group** | **Examples from OHLCV** |
| ----------------- | ----------------------- |
| Return momentum | 5-day, 20-day, 60-day cumulative return |
| Volatility | rolling 20-day and 60-day return volatility |
| Liquidity | average dollar volume, volume z-score, turnover proxy |
| Price pressure | abnormal return vs. market/sector, drawdown, gap moves |
| Pre-event drift | cumulative return in windows before the prediction date |

Labels are then assigned from `ma_events.csv` using future announcement dates:

```text
label_target_within_6m = 1
if target_ticker == ticker
and announcement_date > as_of_date
and announcement_date <= as_of_date + 6 months
```

The same pattern can be used for acquirer labels when `acquirer_ticker` is available:

```text
label_acquirer_within_6m = 1
if acquirer_ticker == ticker
and announcement_date > as_of_date
and announcement_date <= as_of_date + 6 months
```

This alignment is the core connection between market data and M&A prediction: OHLCV data provides pre-announcement signals, while cleaned M&A events provide future labels. The strict rule is that no feature may use price, volume, filing, or news information after `as_of_date`.

### 4. Modeling Dataset Shape

A supervised-learning dataset should have one row per `(ticker, as_of_date)`:

| **Column Type** | **Examples** |
| --------------- | ------------ |
| Entity keys | `ticker`, `cik`, `company_name`, `exchange` |
| Time key | `as_of_date` |
| Market features | `ret_20d`, `ret_60d`, `vol_20d`, `volume_zscore_20d`, `avg_dollar_volume_20d` |
| Event history features | prior target count, prior acquirer count, days since last event |
| Forward labels | `label_target_within_6m`, `label_acquirer_within_6m` |

For machine learning, the most practical first target is `label_target_within_6m`, because target tickers are cleaner and more consistently observable than acquirer tickers. Once this baseline works, the project can add acquirer prediction and target-acquirer pair scoring.

### 5. Important Week 1 Caveat

`code/week1_russell1000_analysis.ipynb` still uses `data/raw/index/russell1000_membership.csv` as its universe. If the notebook is run unchanged, it will drop M&A events whose targets are outside the Russell 1000. To train on all listed companies, the analysis notebook should be updated to use `data/raw/index/us_listed_companies_sec.csv`, and OHLCV data should be downloaded for that broader ticker set.



## Methodologies

### 1. **Merger-Arb Fund Scoring**

Quantify the ex-ante probability that individual announced M&A deals will close, and attribute outcomes to fund-specific selection and sizing decisions.

**Goals:**

- Rank merger-arb ETFs and mutual funds by skill using calibration and outcome-based metrics (Brier score, log loss, hit rate, realized spread capture)
- Detect and act on rebalance signals from high-skill providers to predict spread compression/expansion
- Identify short-term P&L drivers around deal milestones

**Key Metrics:**

- Hit rate: proportion of predicted completions that close
- Brier score / log loss: probabilistic calibration quality
- Realized spread capture: actual vs. theoretical arbitrage spread earned
- Entry timing relative to announcement

### 2. **Generative AI Signal Extraction**

Deploy large language models (LLMs) to extract strategic and structural signals from unstructured corporate documents at scale. 

**Target Signals:**

- "Strategic alternatives": signals board-level review of corporate structure
- "Portfolio optimization": indicates potential divestitures or consolidation
- "Capital allocation flexibility": signals financial readiness for transactions
- "Exploring partnerships": early indicator of strategic deal interest
- Sentiment trajectory across consecutive quarterly filings

**Methodology:**

- Summarize corporate strategy sections across 10-K/10-Q/8-K filings
- Identify language indicating strategic review or potential transactions
- Convert qualitative signals into quantitative time-series indicators
- Sentiment analysis over earnings call transcripts (management tone shifts)

### 3. **Market Microstructure Detection**

Identify abnormal trading behavior that historically precedes M&A announcements, capturing informed trading or market anticipation of corporate events.

**Signals Monitored:**

- Unusual options activity: abnormal call option buying volumes
- Volatility skew changes: implied vol surface distortions pre-announcement
- Abnormal stock price drift: sustained upward pressure without news catalyst
- Large institutional block trades: dark pool and lit market accumulation
- Put/call ratio divergence from sector norms



## Evaluation Framework 

M&A events are relatively rare (low base rate), performance will be measured using ranking-based metrics rather than simple classification accuracy.

| **Metric**             | **Description**                                              | **Target** |
| ---------------------- | ------------------------------------------------------------ | ---------- |
| **Precision@50**       | Acquisitions correctly identified in top 50 predictions      | 10–15 hits |
| **Hit Rate**           | Proportion of top-N predictions that are actual targets      | > 20%      |
| **ROC-AUC**            | Area under the ROC curve across the full universe            | > 0.70     |
| **Event Capture Rate** | % of actual M&A events captured within top-ranked tier       | > 30%      |
| **Brier Score**        | Probabilistic calibration quality of deal-completion estimates | < 0.15     |



## Planned Timeline

### Week 1: **Scoping, Data Access & Infrastructure Setup**

- Finalize project scope, KPIs, and success criteria with stakeholders
- Establish data pipelines: SEC EDGAR API, market data feeds (Bloomberg/Refinitiv/WRDS), options data
- Set up cloud infrastructure, version control, and experiment tracking (MLflow/W&B)
- Conduct literature review on M&A prediction, merger arbitrage, and informed trading detection
- Define target universe (e.g., Russell 1000 or S&P 500 constituents) and historical training window

### Week 2: **Data Collection & Feature Engineering (Market)**

- Pull historical stock returns, volume, liquidity, and volatility data for universe
- Download options chain data: open interest, IV, put/call ratios, skew metrics
- Construct baseline market features: abnormal returns (CAPM-adjusted), volume z-scores,  IV percentile rank 
- Build  options signal layer: call OI anomaly scores, skew change detectors, block  trade flags
- Verify data quality, handle survivorship bias, and align fiscal calendars 

### Week 3:  **GenAI Pipeline**

- Ingest and parse SEC filings (10-K, 10-Q, 8-K) via EDGAR full-text search
- Design prompt templates for strategic intent detection, sentiment scoring, and language pattern extraction
- Run LLM inference over filings to generate per-company, per-period signal scores
- Process earnings call transcripts: management tone analysis, forward-looking language flags
- Validate extracted signals against known M&A announcement dates (historical ground truth)

### Week 4: **Fund Scoring**

- Collect ETF/mutual fund holdings data (N-PORT, N-CEN, daily ETF disclosures)
- Normalize holdings schema: identifiers, weights, hedge legs, entry/exit dates
- Compute deal-level features: spread at entry, time-weighted spread, deal type dummies, financing indicators
- Implement fund skill metrics: hit rate, Brier score, log loss, realized spread capture
- Rank providers; detect rebalance signals from top-quartile funds

### Week 5: **Model Integration & Probability Scoring** 

- Combine market signals, NLP signals, and fund rebalance signals into unified feature store
- Train baseline models: logistic regression, gradient boosting (XGBoost/LightGBM), ensemble
- Implement label construction: binary (acquired within 6 months) and time-to-event (survival model)
- Run cross-validation with time-series splits; prevent look-ahead bias
- Produce per-company probability scores and calibrate outputs (Platt scaling / isotonic regression)

### Week 6:  Backtesting, Evaluation & Strategy Simulation

- Run full historical backtest across defined test window (e.g., 2018–2024)
- Compute all evaluation metrics: Precision@50, Hit Rate, ROC-AUC, Event Capture Rate, Brier Score
- Simulate merger arbitrage strategy: long top-N predicted targets, measure realized P&L and Sharpe
- Compare against naive and benchmark strategies (random, sector-avg, published M&A predictors)
- Conduct feature importance and SHAP analysis; identify top predictive drivers per signal category

### Week 7:  Refinement, Documentation & Delivery

- Incorporate feedback from Week 6 review; tune models and rebalance signal weights
- Finalize scoring pipeline for prospective use (inference-ready, scheduled refresh)
- Produce live predictions for current universe with ranked probability scores
- Write full technical documentation: data dictionaries, model cards, API specs
- Deliver final presentation


