# Code

The two-pipeline analysis lives in `nlp_vs_llm_pipeline.ipynb`. It runs both pipelines end
to end from the committed feature matrices, so it needs no API key. The scripts below are the
data-collection and feature-building steps behind it, plus the exploratory data tracks we
tried along the way.

## The news pipelines (behind the final result)

| Script | What it does | Needs |
|---|---|---|
| `download_news_ma_events.py` | Main news scraper: GDELT + EDGAR headlines for each event window. Feeds Pipeline A. | none |
| `download_news_gdelt.py` | GDELT DOC 2.0 headline puller. | none |
| `download_news_edgar.py` | 8-K event feed from SEC EDGAR. | none |
| `enrich_article_text.py` | Optional full article-body fetch for cached headlines. | none |
| `extract_llm_features.py` | Pipeline B: one structured LLM call per news window. | OpenRouter key |
| `_sec_http.py` | Shared SEC HTTP helper (rate limit + retry). | none |

## Event labels and universe

| Script | What it does | Needs |
|---|---|---|
| `download_us_listed_companies.py` | US-listed universe from the SEC ticker file. | none |
| `clean_ma_events.py` | Turns the licensed S&P Capital IQ deal export into the cleaned `ma_events.csv` labels. | the S&P export (local) |
| `build_ma_prediction_dataset.py` | Joins universe, prices, and events into a point-in-time panel. | price file (local) |
| `diagnose_blackout_signal.py` | Diagnostic: does deal-rumor news cluster in the pre-announcement blackout? | none |

## Exploratory tracks (tried, not in the final news-only result)

Kept for reference. The transcript track needs licensed WRDS / Capital IQ access; the
fund-holdings track is free SEC data.

| Script | What it does | Needs |
|---|---|---|
| `build_ciq_crosswalk.py` | Maps tickers to Capital IQ company ids. | WRDS account |
| `download_transcripts_wrds.py` | Bulk-downloads earnings-call transcripts. | WRDS + CIQ Transcripts |
| `build_transcript_features.py` | Collapses transcripts to one row per call (local, no WRDS). | crosswalk output |
| `download_fund_holdings.py` | Merger-arb fund holdings from SEC N-PORT. | none |
| `download.py` | Early single-ticker SEC filing prototype, superseded by `download_news_edgar.py`. | none |

None of these scripts contain licensed data or credentials. WRDS access reads a
`WRDS_USERNAME` environment variable and a local `~/.pgpass`, never anything in the repo.
