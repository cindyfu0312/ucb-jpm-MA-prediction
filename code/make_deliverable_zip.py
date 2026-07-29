"""Assemble the MFE27 Term-2 submission bundle into a single zip.

Copies the deck, the executed notebooks, the pipeline scripts, and the parsed feature
matrices (so the notebooks run end-to-end with no API key), writes a grader-facing
README, and zips the result under the program's required filename convention.

Deliberately EXCLUDED: .env and any credential, data/raw/text (5.9 GB of article bodies),
data/raw/llm (regenerable per-call API cache), logs, caches, and personal scratch notes.

The news cache is copied only if it parses cleanly - the scraper rewrites that file in
place, so a mid-flush copy can be truncated.

Usage:  python code/make_deliverable_zip.py
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STEM = "MFE27_Term2_JPMorgan_2_MA_Prediction_Fu_Liu"
BUILD_DIR = PROJECT_ROOT / "build"
STAGE = BUILD_DIR / STEM
ZIP_PATH = BUILD_DIR / f"{STEM}.zip"

DECK = PROJECT_ROOT / "reports" / f"{STEM}_slide_deck.pptx"

# (source, destination-inside-bundle). Notebooks are renumbered into reading order.
NOTEBOOKS = [
    ("code/week1_russell1000_analysis.ipynb", "1_market_data_and_universe.ipynb"),
    ("code/week2_news_ma_prediction.ipynb", "2_news_nlp_baseline.ipynb"),
    ("code/week3_news_ma_prediction.ipynb", "3_news_nlp_data_quality.ipynb"),
    ("code/week4_news_ma_prediction.ipynb", "4_news_nlp_full_stack.ipynb"),
    ("code/week7_llm_ma_prediction.ipynb", "5_llm_vs_classic_nlp_head_to_head.ipynb"),
]

SCRIPTS = [
    "code/_sec_http.py",
    "code/download_us_listed_companies.py",
    "code/clean_ma_events.py",
    "code/build_ma_prediction_dataset.py",
    "code/download_news_ma_events.py",
    "code/enrich_article_text.py",
    "code/diagnose_blackout_signal.py",
    "code/extract_llm_features.py",
    "code/make_final_deck.py",
    "code/make_week7_deck.py",
    "code/make_deliverable_zip.py",
]

# Parsed matrices the notebooks consume - these are what make the bundle runnable keyless.
DATA = [
    "data/interim/ma_news_features.csv",
    "data/interim/ma_news_features_week7.csv",
    "data/interim/ma_llm_features.csv",
    "data/interim/ma_prediction_panel.csv",
    "data/raw/events/ma_events.csv",
]
NEWS_CACHE = "data/raw/news/ma_event_news.csv"   # copied only if it parses cleanly

DOCS = ["requirements.txt", "DATA.md", "code/README.md"]

README = """# Predicting M&A from Free News - MFE27 Term 2 Submission

**Group 2 | J.P. Morgan Industry Project | Dexin Fu, Ronald Liu | July 2026**

Can free, public news predict a $1B+ acquisition *before* it is announced? This bundle
contains everything behind that question: the deck, the executed notebooks, the pipeline
scripts, and the parsed feature matrices.

## Start here

| # | File | What it is |
|---|---|---|
| 1 | `{stem}_report.md` | **The written report.** The whole project in plain language: question, data, method, results, conclusion, future work, contributions, references. |
| 2 | `{stem}_slide_deck.pptx` | **The deck.** 24 slides, self-contained: intro and prior art, research design, data, both pipelines, results, validity tests, conclusions, future work, contributions, references. |
| 3 | `notebooks/5_llm_vs_classic_nlp_head_to_head.ipynb` | The headline result: classic NLP vs LLM on identical rows and split. |
| 4 | `notebooks/4_news_nlp_full_stack.ipynb` | The classic-NLP baseline, the data-quality fixes, and the diagnostic that explains the null. |

## The headline numbers

| Result | Value |
|---|---|
| Advance prediction, best AUC (combined features) | **0.551**, 95% CI [0.495, 0.606] |
| Classic NLP alone / LLM alone | 0.525 / 0.518 |
| Announcement-day *detection*, same pipeline | **0.79** |
| LLM memorization probe (chance = 50%) | 50.4% |
| Company-name masking, AUC delta | 0.017 |
| Total LLM API spend | $2.10 |

The gap between 0.55 (prediction) and 0.79 (detection) is the project's central finding:
the method works, but free news covers these deals **on announcement day, not before it**.

## Layout

```
{stem}/
  {stem}_report.md
  {stem}_slide_deck.pptx
  notebooks/    5 executed notebooks, in reading order
  code/         the pipeline scripts (scrapers, cleaners, LLM extractor, deck builders)
  data/         parsed feature matrices + cleaned event labels
  docs/         requirements.txt, DATA.md, pipeline README
```

## Reproducing the results

```bash
pip install -r docs/requirements.txt
```

This zip is a **read-only submission snapshot** (files are renamed and reorganised for
review). To actually re-run anything, use the git repository, where the folder layout the
scripts expect is intact. There, from the repo root:

- **Regenerate the slide deck** (no API key, seconds):
  `python code/make_final_deck.py` reads the committed stats and figures in
  `outputs/week7/` and rebuilds the deck. This is the one-command reproduction of the
  headline deliverable.
- **Re-run the classic-NLP pipeline** (Pipeline A): the weeks 2-4 notebooks build their
  features from the committed news cache. No key needed.
- **Re-run the LLM pipeline** (Pipeline B): `python code/extract_llm_features.py` needs an
  `OPENROUTER_API_KEY` in a local `.env` and costs about $2. Its parsed output is already
  committed (`data/interim/ma_llm_features.csv`), so you only need this to regenerate it
  from scratch.

The numbers you see are the initial 1,156-event run. The committed matrices and stats
reflect that run, so the deck regenerates to exactly what is shown here.

## What is not in here, and why

- **API keys** - never bundled. The extractor reads `OPENROUTER_API_KEY` from a local
  `.env` that is gitignored.
- **`data/raw/text/`** (5.9 GB of full article bodies) and **`data/raw/llm/`** (the raw
  per-call API cache) - both regenerable, and the parsed matrices that the notebooks
  actually consume are included instead.
- The full news cache is included only when it can be verified consistent; see the note in
  `data/` if it is absent.

## Contributions

| Workstream | Dexin Fu | Ronald Liu |
|---|---|---|
| Scoping, KPIs, literature review | Lead | Support |
| Event cleaning, ticker matching, market panel | Lead | - |
| GDELT + EDGAR scrapers | Lead | Support |
| Classic-NLP stack (VADER, FinBERT, log-odds, NMF) | Lead | - |
| Data-quality fixes; blackout and detection diagnostics | Lead | - |
| LLM extraction pipeline (OpenRouter, strict JSON) | - | Lead |
| Validity suite (memorization probe, masking, repeats) | - | Lead |
| Full-dataset A/B/C head-to-head | Support | Lead |
| Decks | Wk 2, Wk 3-4 | Wk 7, final |

Both authors reviewed all results jointly and agreed the pre-registered success criteria
before any model was run.
"""


def main() -> None:
    if not DECK.exists():
        raise SystemExit(f"deck not found: {DECK}\nRun: python code/make_final_deck.py")

    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    for sub in ("notebooks", "code", "data", "docs"):
        (STAGE / sub).mkdir(parents=True, exist_ok=True)

    shutil.copy2(DECK, STAGE / DECK.name)

    report = PROJECT_ROOT / "report.md"
    if report.exists():
        shutil.copy2(report, STAGE / f"{STEM}_report.md")

    for src, dst in NOTEBOOKS:
        p = PROJECT_ROOT / src
        if p.exists():
            shutil.copy2(p, STAGE / "notebooks" / dst)
        else:
            print(f"  skip (missing): {src}")

    for src in SCRIPTS:
        p = PROJECT_ROOT / src
        if p.exists():
            shutil.copy2(p, STAGE / "code" / p.name)

    for src in DATA:
        p = PROJECT_ROOT / src
        if p.exists():
            shutil.copy2(p, STAGE / "data" / p.name)
        else:
            print(f"  skip (missing): {src}")

    # The scraper rewrites the news cache in place, so only ship a copy we can verify.
    news = PROJECT_ROOT / NEWS_CACHE
    if news.exists():
        dest = STAGE / "data" / news.name
        shutil.copy2(news, dest)
        try:
            import pandas as pd
            df = pd.read_csv(dest, dtype=str)
            need = {"transaction_id", "window", "title"}
            if not need.issubset(df.columns) or df.empty:
                raise ValueError("unexpected columns/empty")
            print(f"  news cache OK: {len(df):,} rows, "
                  f"{df.transaction_id.nunique():,} events")
        except Exception as exc:
            dest.unlink(missing_ok=True)
            (STAGE / "data" / "NOTE_news_cache_omitted.txt").write_text(
                "The raw news cache was being rewritten by the scraper when this bundle\n"
                "was built, so it was omitted rather than shipped truncated.\n"
                f"Reason: {type(exc).__name__}: {exc}\n\n"
                "It is fully regenerable:\n"
                "  python code/download_news_ma_events.py --n-events 0 "
                "--gdelt-min-interval 10\n"
                "The parsed feature matrices in this folder are unaffected and are what\n"
                "the notebooks actually consume.\n")
            print(f"  news cache OMITTED (unstable copy): {exc}")

    for src in DOCS:
        p = PROJECT_ROOT / src
        if p.exists():
            shutil.copy2(p, STAGE / "docs" / p.name)

    figs = PROJECT_ROOT / "outputs" / "week7"
    if figs.exists():
        out = STAGE / "outputs"
        out.mkdir(exist_ok=True)
        for f in sorted(figs.iterdir()):
            if f.suffix in (".png", ".json"):
                shutil.copy2(f, out / f.name)

    (STAGE / "README.md").write_text(README.format(stem=STEM))

    # Final guard: nothing credential-shaped may enter the zip.
    # Real keys are a long unbroken base62/hex run after the prefix. A looser "sk-..."
    # pattern false-positives on ~90 news URL slugs ("risk-when-markets-go-nuts"),
    # so require 24+ consecutive alphanumerics, which hyphenated slugs never have.
    import re
    pat = re.compile(rb"(?:sk-or-v1-[A-Za-z0-9]{32,}"
                     rb"|sk-proj-[A-Za-z0-9_\-]{24,}"
                     rb"|sk-[A-Za-z0-9]{24,})")
    for f in STAGE.rglob("*"):
        if f.name == ".env":
            raise SystemExit(f"ABORT - .env staged at {f}")
        if f.is_file() and pat.search(f.read_bytes()):
            raise SystemExit(f"ABORT - key-like string found in {f}")

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(STAGE.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(BUILD_DIR))

    n = sum(1 for f in STAGE.rglob("*") if f.is_file())
    print(f"\n{ZIP_PATH}")
    print(f"  {n} files, {ZIP_PATH.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
