# Data & scripts

**Git holds code + config only.** Data lives locally / on Drive — see `.gitignore`. Run everything from the repo root with the project venv (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`).

## Pipelines

### Free — no credentials
| Script | Output | Notes |
|---|---|---|
| `download_us_listed_companies.py` | `data/raw/index/us_listed_companies_sec.csv` | SEC universe (~7.6k cos) |
| `download_news_edgar.py --only-priced` | `data/raw/news/edgar_8k_events.csv` | 8-K event feed; `is_mna_leading` (1.01/1.02) vs `is_completion` (2.01 = outcome, do not use as a feature) |
| `download_news_gdelt.py --companies "..."` | `data/raw/news/gdelt_articles.csv` | universe-wide headlines + Reuters/wire flags; rate-limited → spot-checks only |
| `download_news_ma_events.py --n-events 300` | `data/raw/news/ma_event_news.csv` | GDELT + SEC EDGAR full-text-search headlines for pre-/post-announcement windows of large M&A events; **persistent, resumable local cache** — re-running only fetches (transaction_id, window) pairs not already cached |
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
| `clean_ma_events.py --source <2016-2021.xlsx> <2021-2026.xlsx> --company-level-only --min-deal-value-usd 1e9` | `data/raw/events/ma_events.csv` | M&A labels, US company-level deals >= $1B, 2016-2026 (reads `.csv` or `.xlsx`, multiple `--source` files are concatenated + deduped by Transaction ID) |

### Needs an OpenAI API key (`OPENAI_API_KEY` in gitignored `.env`)
| Script | Output | Notes |
|---|---|---|
| `extract_llm_features.py` | `data/raw/llm/ma_event_llm_scores.csv` (+ `_probe.csv`, `_manifest.csv`) | One structured-JSON LLM call per cached (event, window): 17 M&A-precursor signals. **Resumable + `--max-cost`-capped** — re-running skips keys already scored; ~$3 for a full gpt-5-mini pass. Variants: `--mask-names`, `--task probe` (memorization test, never a model feature), `--task day0`, `--model gpt-5 --limit-events 100`. The parsed numeric matrix is committed as `data/interim/ma_llm_features.csv` so the week-6 notebook runs **without** a key. |

## Not in git (gitignored)
- **Proprietary** — S&P export, CIQ transcripts, ticker→companyid crosswalk. Share via Drive, or pull from your own WRDS/CIQ.
- **Large regenerable** — `data/raw/news/`, `data/raw/funds/`. Re-create by running the scripts.
- **Paid regenerable** — `data/raw/llm/` (raw per-call LLM cache incl. prompts' JSON). Re-create with `extract_llm_features.py` + an OpenAI key; the derived feature matrix lives in `data/interim/ma_llm_features.csv` (committed).
- **Secrets** — `.env` (OpenAI key). Never commit; each teammate keeps their own.

## Point-in-time joins
Every source joins to the panel by `(ticker, date)` using a **knowable-as-of** date — never a period-end:
- 8-K → `filing_date`
- fund holdings → `available_date` (NOT `report_date`; N-PORT is public ~57 days after period-end)
- transcripts → `call_date` (use calls strictly *before* `as_of_date`)
