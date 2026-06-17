# M&A Prediction

Predicting corporate M&A activity from market signals and GenAI, before public announcement.

📖 **The full project README lives at [`code/README.md`](code/README.md)** — objective, data pipeline, modeling approach, evaluation framework, and the weekly plan.

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
python code/download_us_listed_companies.py
python code/clean_ma_events.py --source data/raw/events/<your-S&P-export>.csv --company-level-only
python code/build_ma_prediction_dataset.py
```
