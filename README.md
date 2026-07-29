# Predicting M&A from Free News

**MFE 27, Term 2 — J.P. Morgan Industry Project, Group 2**
Dexin Fu · Ronald Liu · July 2026

Can free, public news flag a $1B+ acquisition target *before* the deal is announced? This
repository is the final deliverable. It runs two parallel pipelines over the same news, a
classic-NLP one and an LLM one, and compares them head to head on identical data.

## Start here

| File | What it is |
|---|---|
| [`reports/MFE27_Term2_JPMorgan_2_MA_Prediction_Fu_Liu_slide_deck.pptx`](reports/) | The 16-slide presentation |
| [`report.md`](report.md) | The written report: intro, method, results, conclusion, references |
| [`REPRODUCE.md`](REPRODUCE.md) | Full instructions to re-run either pipeline |

## Run it (no API key, about a minute)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python code/make_final_deck.py
```

That rebuilds the slide deck from the committed results in `outputs/week7/`, with no data
download and no API key. It is the quickest way to confirm the numbers reproduce.

To re-run the analysis notebooks (classic NLP in weeks 2 to 4, the head-to-head in
week 7), see [`REPRODUCE.md`](REPRODUCE.md). The classic-NLP side runs from the committed
news cache with no key; the LLM side needs an OpenRouter key (about $2) only if you want to
regenerate its scores, which are already committed.

## The result in one line

Free news gives at most a small edge over chance (best AUC 0.55, and the confidence ranges
still include 0.50). The very same pipeline detects deals the week they are announced at
0.79 AUC. So the method works; the early signal simply is not in the free news. The report
and slides have the full story.

## What is in here

```
reports/     the slide deck and the head-to-head comparison deck
report.md    the written report
code/        pipeline scripts (scrapers, feature extractors, deck builders) + notebooks
data/        the news cache, cleaned events, and parsed feature matrices
outputs/     exported stats and figures the deck is built from
```

Large raw data (full article bodies, per-call LLM cache) and anything under a paid data
licence are left out on purpose; everything needed to reproduce the presented results is
here. See [`DATA.md`](DATA.md) for the data sources.
