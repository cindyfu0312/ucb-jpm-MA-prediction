# Reproducing this project

Two pipelines read the same free news and try to flag M&A targets before announcement:
**Pipeline A** (classic NLP) and **Pipeline B** (an LLM). This file is the short version of
how to re-run them. Longer notes on the data live in `DATA.md` and `code/README.md`.

## 1. Environment

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Python 3.11 to 3.13. FinBERT runs on CPU, so no GPU is needed. The only credential anything
needs is an LLM key, and only for Pipeline B (see step 4).

## 2. Fastest check: regenerate the deck (no key, seconds)

```bash
python code/make_final_deck.py
```

This reads the committed stats and figures in `outputs/week7/` and rebuilds
`reports/MFE27_Term2_JPMorgan_2_MA_Prediction_Fu_Liu_slide_deck.pptx`. It reproduces the
exact numbers in the presentation, with no data download and no API key. The report
(`report.md`) is plain Markdown and needs nothing.

## 3. Pipeline A: classic NLP (no key)

The classic-NLP features are built from the committed news cache
(`data/raw/news/ma_event_news.csv`, GDELT + SEC EDGAR headlines). The weeks 2 to 4
notebooks build and model them:

```bash
jupyter lab code/week4_news_ma_prediction.ipynb    # VADER, FinBERT, log-odds, NMF
```

To re-scrape the news from scratch instead (slow, rate-limited, resumable):

```bash
python code/download_news_ma_events.py --n-events 0 --gdelt-min-interval 10
```

## 4. Pipeline B: the LLM (needs a key)

Put a key in a local `.env` (never commit it):

```
OPENROUTER_API_KEY=sk-or-...
```

Then extract the LLM features (about $2, resumable, cost-capped):

```bash
python code/extract_llm_features.py \
  --model openai/gpt-4o-mini --base-url https://openrouter.ai/api/v1 \
  --api-key-env OPENROUTER_API_KEY --reasoning-effort "" --max-cost 5
```

The parsed output is already committed at `data/interim/ma_llm_features.csv`, so you only
need this step if you want to regenerate it yourself.

## 5. The head-to-head notebook

```bash
jupyter lab code/week7_llm_ma_prediction.ipynb
```

This is where Pipeline A and Pipeline B are compared on identical rows and split. It runs
from a fresh clone with no API key: the LLM scores load from the raw cache if present, and
otherwise from the committed `data/interim/ma_llm_features.csv`.

Run it once, top to bottom. The head-to-head results (the numbers in the deck) come from the
committed feature matrices in the first two thirds of the notebook. The appendix at the end
rebuilds Feature Set A from the news cache with FinBERT (slow, and only needed to regenerate
that matrix from scratch).

## What is committed vs regenerable

| Committed (in the repo) | Not committed (regenerable) |
|---|---|
| Cleaned events, news cache, parsed feature matrices | Raw per-call LLM cache (`data/raw/llm/`, ~$2 to rebuild) |
| Exported stats + figures (`outputs/week7/`) | Full article bodies (`data/raw/text/`, several GB) |
| Executed notebooks, deck, report | Anything under a paid data licence (S&P, CIQ) |
| The generators (`make_final_deck.py`, etc.) | API keys (live only in a local `.env`) |

## A note on the numbers

The presented results are the **initial 1,156-event run**. A later run on a larger news
scrape is preserved in the git history; the committed matrices and stats here reflect the
1,156-event run, so everything regenerates to exactly what the deck shows.
