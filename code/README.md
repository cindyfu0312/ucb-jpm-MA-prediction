# M&A Prediction — Market Signals & Generative AI

**Dexin Fu, Ronald Liu**

*Merger-arbitrage prediction · event-driven strategy · GenAI signal extraction*

A data-driven framework to identify, **before public announcement**, which US-listed companies are likely to participate in M&A over a 3–6 month horizon — as **targets**, **acquirers**, or strategically compatible **pairs**. It fuses point-in-time market signals, structured fund disclosures, and LLM-based text analysis into per-company probability scores for event-driven and merger-arbitrage workflows.

## Objective

Produce a probability score for each company in the universe indicating its likelihood of an M&A event within 3–6 months, to detect potential **acquisition targets**, likely **acquirers**, and compatible **pairs**.

## Research Questions

- Can public market data and corporate disclosures predict M&A before announcement?
- Can GenAI extract strategic intent from filings and transcripts at scale?
- What industry-consolidation patterns reliably precede deals?

## Data Sources

| Category | Sources |
|---|---|
| Corporate disclosures | 10-K, 10-Q, 8-K; earnings transcripts; investor presentations; press releases |
| Market data | Daily prices/returns; realized volatility; liquidity (dollar volume, turnover) |
| External | News; analyst reports; industry M&A databases (S&P Capital IQ) |
| Fund disclosures | ETF holdings; mutual-fund N-PORT/N-CEN; historical holdings time-series |

## Quickstart

```bash
# one-time environment setup
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# run the pipeline (from repo root)
python code/download_us_listed_companies.py                  # 1. company universe (SEC, free)
python code/clean_ma_events.py \                             # 2. clean S&P deals ($1B+) -> labels
    --source data/raw/events/SPGlobal_TransactionsStatistics_2016-2021.xlsx \
             data/raw/events/SPGlobal_TransactionsStatistics_2021-2026.xlsx \
    --company-level-only --min-deal-value-usd 1e9
python code/build_ma_prediction_dataset.py                   # 3. build the modeling panel

# optional: news-NLP track (code/week2_news_ma_prediction.ipynb)
python code/download_news_ma_events.py --n-events 300        # 4. cache GDELT+EDGAR news, resumable
```

Produces `data/interim/ma_prediction_panel.csv` (one row per company-month, features + labels) and a coverage report under `reports/week1/`.

## Pipeline (current implementation)

Three scripts turn raw market + M&A data into a supervised, point-in-time modeling table, linked by ticker.

| File | Role | Key columns |
|---|---|---|
| `data/raw/index/us_listed_companies_sec.csv` | US-listed universe (SEC ticker master) | `ticker, company_name, exchange, cik` |
| `data/raw/market/daily_prices.csv` | Daily OHLCV history | `date, ticker, open, high, low, close, volume, ret` |
| `data/raw/events/ma_events.csv` | Cleaned M&A ground-truth events, $1B+ deals, 2016-2026 | `announcement_date, target_ticker, acquirer_ticker, deal_status, close_date, deal_value_usd` |

### 1. Universe — `download_us_listed_companies.py`
Downloads the SEC ticker master (NYSE / Nasdaq / NYSE American) → ~7,600 companies. A broad universe matters because M&A targets are rare; restricting to Russell 1000 yields too few positive labels.

### 2. Events → labels — `clean_ma_events.py`
Cleans raw **S&P Capital IQ** transactions exports into the event schema. Accepts multiple `--source` files (concatenated + deduped by Transaction ID) and an optional `--min-deal-value-usd` floor — the default sources are two exports pre-filtered to deals **>= $1B**, giving ~2,029 US company-level events spanning 2016-2026. Name normalization maps target/buyer → ticker where possible (`--company-level-only` drops asset/branch and spinoff deals); `acquirer_ticker` may be blank — many buyers are private, PE-backed, or foreign. Reads `.csv` or `.xlsx`. Also writes `ma_events_match_audit.csv` for match QA.

Restricting to $1B+ deals is deliberate: large targets are overwhelmingly public, name-recognizable companies, which is the regime where the free news-NLP track below actually has recall.

### News-NLP track — `download_news_ma_events.py` + `week2_news_ma_prediction.ipynb`
`download_news_ma_events.py` samples events from `ma_events.csv` and caches GDELT + SEC EDGAR full-text-search headlines for two 90-day windows per target (`pre` = run-up to announcement, `baseline` = a quiet period 180 days earlier) into `data/raw/news/ma_event_news.csv`. The cache is **local, gitignored, and resumable** — re-running only fetches `(transaction_id, window)` pairs not already cached, so the GDELT-rate-limited scraping cost is paid once and can be topped up over multiple runs (`--n-events N`). `week2_news_ma_prediction.ipynb` loads that cache and builds NLP features across four layers: VADER sentiment, FinBERT (finance-tuned BERT) sentiment, TF-IDF + log-odds data-driven distinctive terms, and NMF topic modeling — then trains logistic regression / random forest classifiers on the resulting feature matrix.

### GenAI track (week 7) — `extract_llm_features.py` + `week7_llm_ma_prediction.ipynb`
`extract_llm_features.py` sends **one structured-JSON LLM call per cached (event, window)** — the window's noise-filtered headlines plus an SEC-filing summary — and receives 17 M&A-precursor fields (rumor intensity, strategic-alternatives language, activist pressure, management instability, distress, an overall 0-100 acquisition likelihood, verbatim evidence quotes...). Parallel, resumable, and `--max-cost`-capped, with the same cache discipline as the scrapers; needs `OPENROUTER_API_KEY` (or `OPENAI_API_KEY`) in the gitignored `.env` (~$1/full pass at `openai/gpt-4o-mini` via OpenRouter). `week7_llm_ma_prediction.ipynb` compares three feature sets on identical rows and split — **A** (the week-4 classic-NLP stack recomputed on the same corpus), **B** (LLM signals only), **C** (combined) — with bootstrap CIs, and stress-tests validity three ways before trusting any lift: a **memorization probe** (no news shown — does the model already *know* these deals from training?), a **company-name-masking A/B** (is it reading the text or recognizing the company?), and **repeat-consistency** re-scoring (how arbitrary are the numbers?). Announcements after the model's knowledge cutoff serve as a memorization-free holdout. `make_week7_deck.py` renders the results deck from the notebook's exported stats. Recommended next step: cutoff-matched backtesting via OpenRouter (score each window with a model trained only on data from before it).

### 3. Modeling panel — `build_ma_prediction_dataset.py`
Builds one row per `(ticker, as_of_date)` (monthly by default). For each row:
- **Features (past only):** `ret_5d/20d/60d`, `vol_20d/60d`, `avg_dollar_volume_20d`, `volume_zscore_20d`, `drawdown_60d`, plus event history (`prior_*_event_count`, `days_since_prior_*_event`).
- **Labels (future only):** `label_target_within_6m`, `label_acquirer_within_6m` = 1 if the company is announced in that role within the next *H* months.

The strict past/future split is the core discipline — **no feature may use information after `as_of_date`.** A coverage report (`reports/week1/ma_prediction_data_coverage.csv`) tracks join rates and positive-label counts.

> **Current data status.** The committed `daily_prices.csv` is a 2-month, ~1,000-large-cap sample, so only a fraction of matched targets have price history (most positives are censored). Dropping in **multi-year, full-universe** OHLCV (same WRDS/CRSP source) makes the panel trainable with no code changes.

## Modeling approach

The first and most reliable target is `label_target_within_6m` (target tickers are cleaner than acquirer tickers). Once the market-signal baseline works, add acquirer prediction and target–acquirer pair scoring. Two extension tracks layer additional signals onto the same panel:

### Track A — Merger-Arb Fund Scoring
Quantify the **ex-ante probability that announced deals close** and rank merger-arb funds by skill. Normalize ETF/MF holdings (incl. hedge legs: long target / short acquirer); engineer deal-level features (spread, deal type, financing, days-to-close) and fund-level features (entry timing, sizing, turnover); fit a calibrated completion model; score funds via **hit rate, Brier, log loss, realized spread capture**; detect rebalance signals from top-quartile funds.

### Track B — GenAI Signal Extraction
Use LLMs to convert unstructured text into quantitative strategic-intent indicators — "strategic alternatives," "portfolio optimization," "capital allocation flexibility," "exploring partnerships," and sentiment trajectory across consecutive filings. Prompt-based extraction over 10-K/10-Q/8-K, transcripts, and press releases; per-company per-period time-series; validate against historical announcement dates. (`code/download.py` fetches the underlying SEC filings.)

> Market-microstructure / options-based detection (unusual options activity, IV skew, block trades) is intentionally **out of scope** for this project.

## Evaluation Framework

M&A is a rare event, so performance is measured with **ranking-based** metrics, not raw accuracy.

| Metric | Description | Target |
|---|---|---|
| Precision@50 | Acquisitions correctly identified in the top-50 predictions | 10–15 hits |
| Hit rate | Share of top-*N* predictions that are actual targets | > 20% |
| ROC-AUC | Area under ROC across the universe | > 0.70 |
| Event capture | Share of actual events in the top-ranked tier | > 30% |
| Brier score | Calibration quality of completion estimates (fund track) | < 0.15 |

## Weekly Plan (7 Weeks)

| Wk | Phase | Key activities | Deliverables |
|:--:|---|---|---|
| 1 | Foundation | Scope, KPIs; stand up data pipelines (SEC, market); env & version control; define universe & window | Scoping doc, data-access confirmation, infra checklist |
| 2 | Market data ✅ | Pull returns/volume/volatility/liquidity; build momentum, volatility, volume-z, drawdown features; QA & survivorship handling | **Market feature panel (done)**, QA report |
| 3 | AI / NLP | Parse filings; strategic-intent & sentiment prompts; LLM inference → per-company signals; validate vs. announcement dates | NLP signal dataset, prompt library, validation report |
| 4 | Fund analytics | Collect ETF/MF holdings; normalize schema incl. hedge legs; deal- & fund-level features; skill metrics; rank funds | Fund-skill ranking, rebalance-signal feed |
| 5 | Modeling | Merge market + NLP + fund signals; train logistic / GBM / ensemble; time-series CV; calibrate | Model artifacts, probability scores, CV results |
| 6 | Validation | Backtest; compute metrics; simulate long top-*N* strategy (P&L, Sharpe); benchmark; SHAP | Backtest report, strategy P&L, importance dashboard |
| 7 | Delivery | Finalize inference-ready pipeline; live ranked predictions; docs + model cards; final deck | Live predictions, documentation, final deck |

*Weekly status report every Friday.*

## Assumptions & Risks

| Risk | Mitigation |
|---|---|
| Data-access delays (market feeds) | Backups (Yahoo Finance, Stooq, WRDS) identified early |
| Low M&A base rate in test window | Rank-based metrics (Precision@K, AUC); broaden the universe |
| LLM inference cost / latency | Batch offline; cache; consider distilled models |
| Look-ahead bias in features | Strict point-in-time discipline; time-series CV |

## Phase 2 (preview)

Real-time monitoring & alerts · pair-level target–acquirer matching · portfolio integration for position sizing · expanded mid-cap and international coverage.
