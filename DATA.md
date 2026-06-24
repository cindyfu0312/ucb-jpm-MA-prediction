# Data & scripts

**Git holds code + config only.** Data lives locally / on Drive — see `.gitignore`. Run everything from the repo root with the project venv (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`).

## Pipelines

### Free — no credentials
| Script | Output | Notes |
|---|---|---|
| `download_us_listed_companies.py` | `data/raw/index/us_listed_companies_sec.csv` | SEC universe (~7.6k cos) |
| `download_news_edgar.py --only-priced` | `data/raw/news/edgar_8k_events.csv` | 8-K event feed; `is_mna_leading` (1.01/1.02) vs `is_completion` (2.01 = outcome, do not use as a feature) |
| `download_news_gdelt.py --companies "..."` | `data/raw/news/gdelt_articles.csv` | headlines + Reuters/wire flags; rate-limited → spot-checks only |
| `download_fund_holdings.py` | `data/raw/funds/` | N-PORT merger-arb fund holdings (long/short legs) |
| `build_ma_prediction_dataset.py` | `data/interim/ma_prediction_panel.csv` | the modeling panel |

### Needs a WRDS account (Capital IQ Transcripts subscription)
| Script | Output | Notes |
|---|---|---|
| `build_ciq_crosswalk.py --only-priced` | `data/raw/index/ticker_to_ciq_companyid.csv` | ticker → CIQ companyid (run `--discover` first to confirm columns) |
| `download_transcripts_wrds.py --companyids-file <crosswalk>` | `data/raw/text/transcripts/` | earnings-call transcripts (large — multi-GB) |
| `build_transcript_features.py` | `data/raw/text/transcripts/transcript_calls.csv` | dedup + attach ticker (local, no WRDS) |

### Needs the proprietary S&P Capital IQ export
| Script | Output | Notes |
|---|---|---|
| `clean_ma_events.py --source <S&P export>.csv --company-level-only` | `data/raw/events/ma_events.csv` | M&A labels (reads `.csv` or `.xlsx`) |

## Not in git (gitignored)
- **Proprietary** — S&P export, CIQ transcripts, ticker→companyid crosswalk. Share via Drive, or pull from your own WRDS/CIQ.
- **Large regenerable** — `data/raw/news/`, `data/raw/funds/`. Re-create by running the scripts.

## Point-in-time joins
Every source joins to the panel by `(ticker, date)` using a **knowable-as-of** date — never a period-end:
- 8-K → `filing_date`
- fund holdings → `available_date` (NOT `report_date`; N-PORT is public ~57 days after period-end)
- transcripts → `call_date` (use calls strictly *before* `as_of_date`)
