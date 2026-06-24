# Data Sources


## 1. Daily market data — `data/raw/market/daily_prices.csv`

| | |
|---|---|
| **Origin** | WRDS / CRSP daily stock file (manual export, no script) |
| **Access** | WRDS account |
| **Frequency** | Daily (one row per ticker per trading day) |
| **Range / size** | 2026-01-02 → 2026-02-27 · ~38.9k rows, 999 tickers |

OHLCV (`date, ticker, open, high, low, close, volume, ret`) plus `shares_out, market_cap, permno, gvkey` (the `permno`/`gvkey` columns confirm CRSP/Compustat-via-WRDS). `build_ma_prediction_dataset.py` standardizes tickers, drops rows without `close`, sets `dollar_volume = |close| × volume`, and computes all rolling features past-only per ticker.

> **Limitation.** Only a 2-month, ~1,000-large-cap sample, so most matched targets have no overlapping price history (labels censored). Dropping in multi-year, full-universe OHLCV from the same source makes the panel trainable with no code changes.

---

## 2. M&A events (labels) — `data/raw/events/ma_events.csv`

| | |
|---|---|
| **Origin** | S&P Capital IQ — Transactions Statistics export (raw: `SPGlobal_transactions_2022-2026.csv`, ~66k rows) |
| **Access** | Proprietary (S&P Capital IQ) |
| **Producer** | `code/clean_ma_events.py` |
| **Frequency** | Event-driven (one row per deal); export is a periodic snapshot |
| **Range / size** | Announced 2022-06-27 → 2026-06-15 · ~318 cleaned events |

Cleaned schema: `announcement_date, target_ticker, acquirer_ticker, deal_status, close_date, deal_value_usd`. `acquirer_ticker` is often blank (private/PE/foreign buyers).

**Processing:** keep USA deals; `--company-level-only` keeps whole-company / minority-stake deals (drops asset and spinoff deals); map target & buyer names → tickers via a normalized-name map from the SEC ticker master (exact by default, optional `--fuzzy-cutoff`); keep rows whose target maps; `deal_value_usd = (Deal Value $M ⟶ Transaction Value $M) × 1e6`. Also writes `ma_events_match_audit.csv` for match QA.

---

## 3. 8-K corporate-event feed — `data/raw/news/edgar_8k_events.csv`

| | |
|---|---|
| **Origin** | SEC EDGAR submissions API (`data.sec.gov/submissions/CIK{cik}.json` + shards) |
| **Access** | Free |
| **Producer** | `code/download_news_edgar.py` |
| **Frequency** | Event-driven (filed ~4 business days after a material event) |
| **Range / size** | 1994-01-05 → 2026-06-16 · ~252k filings |

One row per 8-K: `cik, ticker, filing_date, items, is_mna_leading, is_completion, accession, doc_url`.
- `is_mna_leading` = items **1.01** (material agreement) or **1.02** (termination) — **leading/predictive**, usable as features.
- `is_completion` = item **2.01** (deal closes) — the **outcome**; **never use as a feature** (leakage). Joins point-in-time on `filing_date`.

---

## 4. News headlines — GDELT — `data/raw/news/gdelt_articles.csv` (on demand)

| | |
|---|---|
| **Origin** | GDELT DOC 2.0 API (`api.gdeltproject.org/api/v2/doc/doc`) |
| **Access** | Free (no key) |
| **Producer** | `code/download_news_gdelt.py` |
| **Frequency** | Near-real-time (~15-min updates); pulled per query |
| **Range / size** | ~2017 → present · generated on demand, not committed |

Article rows: `ticker, company, seen_date, title, domain, sourcecountry, language, is_reuters, is_major_wire, url`. Wire flags use exact host matching against `reuters/apnews/bloomberg/cnbc/ft/wsj`; `--mna-only` appends M&A keywords. Recall is uneven and the endpoint rate-limits — best for targeted spot-checks, not a full-universe sweep.

---

## 5. Merger-arb fund holdings — `data/raw/funds/`

| | |
|---|---|
| **Origin** | SEC EDGAR — NPORT-P filings (full-text search `efts.sec.gov` + archive) |
| **Access** | Free |
| **Producer** | `code/download_fund_holdings.py` |
| **Frequency** | Each filing = one month-end snapshot; publicly ~quarterly, ~60 days after period-end (SEC phasing in monthly/30-day over 2025–26) |
| **Range / size** | `report_date` 2024-07 → 2026-03 · ~1,464 holdings, 7 filings |

Funds: IQ/NYLI Merger Arbitrage (MNA), ProShares Merger (MRGR), AltShares Merger Arbitrage (ARB) / Event-Driven, The Merger Fund / VL (MERFX), Gabelli — each anchored to its own registrant CIK to exclude funds-of-funds.
- `fund_holdings.csv` — one row per holding; `payoffProfile` marks long vs short (long target / short acquirer hedge legs).
- `fund_manifest.csv` — one row per filing (`report_date, available_date, total_assets, n_holdings`).

**`available_date` (EDGAR filing date) ≠ `report_date` (period-end).** NPORT-P is public ~60 days after period-end, so panel joins must use `available_date`.

---

## 6. Earnings-call transcripts — `data/raw/text/transcripts/`

| | |
|---|---|
| **Origin** | S&P Capital IQ Transcripts via WRDS (`ciq.*` tables) |
| **Access** | WRDS account + Capital IQ Transcripts subscription |
| **Producer** | `download_transcripts_wrds.py` → `build_transcript_features.py` |
| **Frequency** | Per earnings call (~quarterly per company) |
| **Range / size** | 2018-01-01 → 2026-06-12 · ~117.7k raw → ~36.9k calls; text ≈ 5.9 GB |

Pulled from `wrds_transcript_detail` (header), `ciqtranscriptcomponent` (text), `wrds_transcript_person` (speaker/section/words), filtered to earnings calls. Outputs: `transcript_components.csv` (one row per speaker turn, ~5.9 GB, not committed), `transcript_manifest.csv` (one row per raw transcript). `build_transcript_features.py` attaches ticker via the `ciq_common` crosswalk (`build_ciq_crosswalk.py`), de-dups revisions to one transcript per (companyid, call_date), and writes `transcript_calls.csv`. Join point-in-time on `call_date` (strictly before `as_of_date`).

---

## Point-in-time join keys

Every source joins by `(ticker, date)` using a **knowable-as-of** date, never a period-end:

| Source | Join date | Note |
|---|---|---|
| 8-K events | `filing_date` | use `is_mna_leading`; never `is_completion` |
| Fund holdings | `available_date` | not `report_date` (public ~60 days later) |
| Transcripts | `call_date` | calls strictly before `as_of_date` |
| Market features | windows ending ≤ `as_of_date` | past prices only |

## Access tiers

| Tier | Sources |
|---|---|
| **Free** | 8-K events (§3), GDELT news (§4), fund holdings (§5) |
| **WRDS account** | Daily prices/CRSP (§1), transcripts (§6) |
| **Proprietary S&P export** | M&A event labels (§2) |

Git holds code + config only; data lives locally / on Drive (see `.gitignore`). Proprietary and multi-GB files aren't committed — regenerate via the scripts or share via Drive.
