"""Diagnostic-only: does deal-rumor news actually cluster in the 7-day blackout period?

The main pipeline (download_news_ma_events.py) deliberately excludes the last `blackout_days`
before announcement from the `pre` window, to avoid training on same-day leak/rumor coverage.
Every robustness check run so far (paired Wilcoxon on headlines, on full article text, at
various *retroactive* blackout lengths using already-fetched dates) has found no significant
pre-vs-baseline gap. One explanation: real "deal talks" / "sources say" news is concentrated in
exactly the days we're excluding, so the pre window (announcement-97d to announcement-7d) never
had much signal in it to find in the first place.

This script fetches GDELT coverage for the blackout period itself
([announcement-blackout_days, announcement]) for a sample of already-cached events, purely to
compare its volume/sentiment against the pre/baseline windows already in the main cache. It is
NOT wired into the modeling pipeline and must never be merged into ma_news_features.csv --
training on it would be exactly the leakage the blackout exists to prevent. Output goes to a
separate file, `ma_event_news_blackout.csv`.

Resumable like the other scripts: re-running skips transaction_ids already fetched.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from download_news_ma_events import RateLimiter, fetch_gdelt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENTS = PROJECT_ROOT / "data" / "raw" / "events" / "ma_events.csv"
DEFAULT_NEWS_CACHE = PROJECT_ROOT / "data" / "raw" / "news" / "ma_event_news.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "news" / "ma_event_news_blackout.csv"

CACHE_COLUMNS = ["transaction_id", "company_name", "title", "date", "domain", "source", "url"]


def run(events_path: Path, news_cache_path: Path, output_path: Path, blackout_days: int,
        n_events: int, seed: int, gdelt_min_interval: float, flush_every: int, verbose: bool) -> None:
    events = pd.read_csv(events_path, parse_dates=["announcement_date"])
    cached = pd.read_csv(news_cache_path, dtype=str)
    covered_ids = set(cached.loc[cached["title"].fillna("") != "", "transaction_id"])

    pool = events[events["transaction_id"].isin(covered_ids)].copy()
    if n_events and n_events < len(pool):
        pool = pool.sample(n=n_events, random_state=seed)

    if output_path.exists():
        existing = pd.read_csv(output_path, dtype=str).fillna("")
    else:
        existing = pd.DataFrame(columns=CACHE_COLUMNS)
    done_ids = set(existing["transaction_id"]) if not existing.empty else set()

    todo = pool[~pool["transaction_id"].isin(done_ids)]
    print(f"{len(pool)} covered events sampled, {len(done_ids)} already fetched, "
          f"{len(todo)} to fetch this run (blackout_days={blackout_days})")

    limiter = RateLimiter(gdelt_min_interval)
    rows: list[dict] = list(existing.to_dict("records"))
    n_with_articles = 0

    for i, (_, ev) in enumerate(todo.iterrows(), start=1):
        ann = pd.Timestamp(ev["announcement_date"])
        start = (ann - pd.Timedelta(days=blackout_days)).strftime("%Y-%m-%d")
        end = ann.strftime("%Y-%m-%d")
        arts = fetch_gdelt(limiter, ev["target_name"], start, end)
        if arts:
            n_with_articles += 1
        if not arts:
            rows.append({"transaction_id": ev["transaction_id"], "company_name": ev["target_name"],
                         "title": "", "date": "", "domain": "", "source": "gdelt", "url": ""})
        for a in arts:
            rows.append({"transaction_id": ev["transaction_id"], "company_name": ev["target_name"],
                         "title": a["title"], "date": a["date"], "domain": a["domain"],
                         "source": "gdelt", "url": a["url"]})

        if verbose or i % 20 == 0:
            print(f"  [{i}/{len(todo)}] {ev['target_name'][:40]:40s} window={start}..{end} "
                  f"-> {len(arts)} articles")
        if i % flush_every == 0:
            pd.DataFrame(rows, columns=CACHE_COLUMNS).to_csv(output_path, index=False)

    pd.DataFrame(rows, columns=CACHE_COLUMNS).to_csv(output_path, index=False)
    print(f"Done. {n_with_articles}/{len(todo)} events had >=1 article this run "
          f"({n_with_articles/len(todo):.1%})." if len(todo) else "Nothing to do.")
    print(f"Total cache: {len(rows):,} rows -> {output_path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    p.add_argument("--news-cache", type=Path, default=DEFAULT_NEWS_CACHE)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--blackout-days", type=int, default=7)
    p.add_argument("--n-events", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--gdelt-min-interval", type=float, default=1.2)
    p.add_argument("--flush-every", type=int, default=20)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.events, args.news_cache, args.output, args.blackout_days, args.n_events,
        args.seed, args.gdelt_min_interval, args.flush_every, args.verbose)
