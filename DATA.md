# Data

Git holds the code and the small derived data needed to run the analysis. Large raw data
and anything under a paid data licence are not committed.

## What is in the repo

| File | What it is |
|---|---|
| `data/raw/news/ma_event_news.csv` | GDELT + SEC EDGAR headlines for two 90-day windows per M&A event (the run-up and a quiet baseline). Regenerate with `code/download_news_ma_events.py`. |
| `data/raw/events/ma_events.csv` | Cleaned M&A labels: US company-level deals >= $1B, 2016-2026. Derived from a licensed S&P Capital IQ export; the raw export itself is not shared. |
| `data/interim/ma_news_features_week7.csv` | Pipeline A features (classic NLP) per event-window. |
| `data/interim/ma_llm_features.csv` | Pipeline B features (LLM signals) per event-window. Regenerate with `code/extract_llm_features.py` (needs a key). |
| `data/interim/ma_news_features.csv` | An earlier classic-NLP feature matrix, kept for a cross-check in the notebook. |

## Not committed (regenerable)

- **Raw per-call LLM cache** (`data/raw/llm/`): the prompt/response cache. Rebuild with
  `extract_llm_features.py` and an OpenRouter key (about $2). The parsed matrix above is the
  committed derivative, so the notebook runs without it.
- **Full article bodies**: several GB, not needed for the headline pipeline.
- **Proprietary data**: the S&P Capital IQ export and any Capital IQ / WRDS licensed files
  are never committed.
- **Secrets**: the API key lives only in a local `.env` (gitignored).
