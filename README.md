# Predicting M&A from Free News

**MFE 27, Term 2 - J.P. Morgan Industry Project, Group 2**
Dexin Fu · Ronald Liu · July 2026

Can free, public news flag a $1B+ acquisition target *before* the deal is announced? This
repository runs two pipelines over the same news and compares them head to head: a
classic-NLP one and an LLM one.

## Start here

| File | What it is |
|---|---|
| `code/nlp_vs_llm_pipeline.ipynb` | **The analysis** - runs both pipelines and compares them |
| `reports/MFE27_Term2_JPMorgan_2_MA_Prediction_Fu_Liu_slide_deck.pptx` | The presentation |
| `report.md` | The written report |
| `REPRODUCE.md` | How to re-run everything |

## Run it (no API key)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/jupyter lab code/nlp_vs_llm_pipeline.ipynb        # then Run All
```

The notebook loads the committed feature matrices in `data/interim/`, so it runs from a
fresh clone with no key. It builds both pipelines, compares them on identical rows and a
time-based split, and runs the validity checks. Re-scraping the news or regenerating the
LLM scores from scratch is optional and covered in `REPRODUCE.md`.

## The two pipelines

- **Pipeline A - classic NLP:** VADER + FinBERT sentiment, log-odds distinctive terms, NMF
  topics, EDGAR filing structure. `code/download_news_ma_events.py` collects the news.
- **Pipeline B - the LLM:** one structured call per news window scoring M&A-precursor
  signals. `code/extract_llm_features.py`.

Both feed the same three models and the same time-based split, so the comparison is fair.

## The result in one line

Free news gives at most a small edge over chance (best AUC 0.55, and the ranges still
include 0.50). The same pipeline detects deals the week they are announced at 0.79. So the
method works; the early signal simply is not in the free news. Full detail in the report
and slides.

## Layout

```
code/     the pipeline notebook + the news scraper and LLM extractor it uses
data/     the news cache, cleaned events, and parsed feature matrices
outputs/  exported figures from the notebook
reports/  the slide deck
report.md the written report
```
