# Reproducing this project

Two pipelines read the same free news and try to flag M&A targets before announcement:
**Pipeline A** (classic NLP) and **Pipeline B** (an LLM). Both run in
`code/nlp_vs_llm_pipeline.ipynb` and are compared head to head.

## 1. Environment

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Python 3.11 to 3.13. FinBERT runs on CPU, so no GPU is needed.

## 2. Run the analysis (no API key)

```bash
.venv/bin/jupyter lab code/nlp_vs_llm_pipeline.ipynb
```

Run it once, top to bottom. It loads the committed feature matrices in `data/interim/`
(`ma_news_features_week7.csv` for Pipeline A, `ma_llm_features.csv` for Pipeline B), builds
the A / B / C models on identical rows and a time-based split, and runs the three validity
checks. No key or download needed.

The appendix at the end rebuilds Pipeline A's features from the news cache with FinBERT
(slow, and only needed to regenerate that matrix from scratch).

## 3. Regenerate the inputs from raw data (optional)

- **News (Pipeline A input), no key:**
  ```bash
  python code/download_news_ma_events.py --n-events 0 --gdelt-min-interval 10
  ```
  scrapes GDELT + SEC EDGAR headlines into `data/raw/news/ma_event_news.csv` (resumable).

- **LLM scores (Pipeline B), needs a key:** put `OPENROUTER_API_KEY=...` in a local `.env`,
  then
  ```bash
  python code/extract_llm_features.py --model openai/gpt-4o-mini \
    --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
    --reasoning-effort "" --max-cost 5
  ```
  (about $2). The parsed output is already committed at `data/interim/ma_llm_features.csv`.

## What is committed vs regenerable

| Committed | Not committed (regenerable) |
|---|---|
| News cache, cleaned events, parsed feature matrices | Raw per-call LLM cache (~$2 to rebuild) |
| Executed notebook, deck, report | Full article bodies (several GB) |
| | Anything under a paid data licence (S&P, CIQ) |

## A note on the numbers

The presented results are the initial 1,156-event run; the committed matrices reflect it,
so the notebook reproduces exactly what the deck and report show.
