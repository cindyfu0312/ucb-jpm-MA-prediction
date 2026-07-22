# Russell 1000 Week 1 Data Request

This project does not require Bloomberg for the Week 1 analysis. Use either WRDS exports or Databento/API exports, then save files into the paths below. The notebook also includes an optional Databento API downloader for daily OHLCV bars.

## Minimum Viable Dataset

### 1. Russell 1000 membership

Save as:

`data/raw/index/russell1000_membership.csv`

Required columns:

| column | description |
|---|---|
| `ticker` | Company ticker |
| `company_name` | Company name |
| `sector` | Sector or GICS sector, if available |
| `start_date` | First date in Russell 1000 universe, if point-in-time membership is available |
| `end_date` | Last date in universe; blank if current member |
| `permno` | Optional WRDS/CRSP identifier |
| `gvkey` | Optional Compustat identifier |
| `cik` | Optional SEC identifier |

Best source:

- WRDS: Russell index constituent data if your WRDS account has index membership access.
- Fallback: current Russell 1000 constituent list from FTSE Russell/iShares export, marked as current-only and not point-in-time.
- Databento note: Databento can provide market data and reference data, but you should still provide this Russell 1000 membership file separately.

### 2. Daily prices and volume

Save as:

`data/raw/market/daily_prices.csv`

Required columns:

| column | description |
|---|---|
| `date` | Trading date |
| `ticker` | Ticker matching membership file |
| `open` | Daily open price, adjusted preferred |
| `high` | Daily high price, adjusted preferred |
| `low` | Daily low price, adjusted preferred |
| `close` | Daily close price, adjusted preferred |
| `volume` | Daily share volume |
| `ret` | Optional daily return; notebook computes it if absent |
| `shares_out` | Optional shares outstanding |
| `market_cap` | Optional market capitalization |
| `permno` | Optional WRDS/CRSP identifier |
| `gvkey` | Optional Compustat identifier |

Recommended time window:

- Prototype: `2018-01-01` to `2024-12-31`
- If export size is an issue: start with `2022-01-01` to `2024-12-31`

WRDS option:

- CRSP daily stock file for `date`, `permno`, `ticker/ncusip` mapping, `prc`, `vol`, `ret`, `shrout`.
- Add CRSP/Compustat linking table if you want `gvkey` and accounting features later.

Databento option:

- Use the Databento API cell in `code/week1_russell1000_analysis.ipynb`.
- Set `DATABENTO_API_KEY` as an environment variable rather than hardcoding it in the notebook.
- Populate `data/raw/index/russell1000_membership.csv` first, then set `RUN_DATABENTO_DOWNLOAD = True`.
- Default notebook settings use `dataset="XNAS.ITCH"`, `schema="ohlcv-1d"`, `stype_in="raw_symbol"`, and a short date range/symbol limit for cost control. Change these to match your Databento subscription.
- Export security master or corporate-action data later if ticker history, listings/delistings, or adjustment factors become important.

Install client if needed:

```bash
python3 -m pip install databento
```

### 3. M&A event labels, optional for Week 1

Save as:

`data/raw/events/ma_events.csv`

Required columns:

| column | description |
|---|---|
| `announcement_date` | Deal announcement date |
| `target_ticker` | Target ticker |
| `acquirer_ticker` | Acquirer ticker, if known |
| `deal_status` | announced, completed, withdrawn, pending |
| `close_date` | Close date, if completed |
| `deal_value_usd` | Optional deal value |

Best source:

- WRDS/Refinitiv SDC, Capital IQ, FactSet, or manually curated sample for Week 1.

## Not Needed for Week 1

These are useful later but should not block the first analysis:

- Historical options chains / OPRA data
- TAQ intraday trades and quotes
- News and analyst reports
- Full SEC filing text
- Fund N-PORT/N-CEN holdings

## Week 1 Analysis Output

The notebook `code/week1_russell1000_analysis.ipynb` will produce:

- Universe coverage summary
- Sector distribution
- Price history coverage by ticker
- Missingness report
- Daily return, rolling volatility, dollar volume, and liquidity summaries
- Optional M&A event-rate summary if labels are provided
