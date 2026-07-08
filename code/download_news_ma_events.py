"""Pull pre-/post-announcement news for large (>=$1B) M&A events and cache it locally.

For each event in `data/raw/events/ma_events.csv` this samples two 90-day windows around
the target company's M&A announcement:
  - `pre`      (label=1): [announcement-97d, announcement-7d]  -- the run-up, minus a 7-day
               blackout so deal-leak headlines right before the announcement don't count.
  - `baseline` (label=0): the same window shifted back 180 days -- a "quiet period" for the
               same company, used as the negative class.

Two free, date-filterable sources are queried per window:
  - GDELT DOC 2.0 (global news, ~2017-> present; degrades before that)
  - SEC EDGAR full-text search (8-K/SC-TO/SC-13D/SC-13G/DEFM14A mentioning the company)
Google News RSS is intentionally excluded -- it has no historical date filter, so it is
useless for events before ~today and would only burn request budget.4

Output is a persistent, append-only local cache (`data/raw/news/ma_event_news.csv`,
gitignored/regenerable per DATA.md). Re-running the script is always safe: any
(transaction_id, window) pair already present in the cache is skipped, so a run can be
stopped and resumed, or repeated later to top up additional events, without re-fetching
anything or re-hitting rate limits for work already done.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote as url_quote

import pandas as pd

from _sec_http import http_get

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENTS = PROJECT_ROOT / "data" / "raw" / "events" / "ma_events.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "news" / "ma_event_news.csv"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "raw" / "news" / "ma_event_news_manifest.csv"

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
EDGAR_FTS_URL = "https://efts.sec.gov/LATEST/search-index"
GDELT_UA = "UCB JPM M&A research ronaldliubc@gmail.com"

LEGAL_NOISE = re.compile(
    r"\b(Inc|Corp|LLC|Ltd|LP|Co|Group|Holdings|International|Technologies?|"
    r"Solutions?|Services?|Systems?|Financial|Capital|Partners?|Global|"
    r"Enterprises?|Industries|Incorporated|Corporation|Limited)\b\.?",
    re.IGNORECASE,
)

CACHE_COLUMNS = [
    "transaction_id",
    "window",
    "label",
    "company_name",
    "title",
    "date",
    "domain",
    "source",
    "url",
]


def clean_name(name: object) -> str:
    if not name or pd.isna(name):
        return ""
    s = re.sub(r"\*", "", str(name))
    s = re.sub(r"\([^)]*\)", "", s)
    s = LEGAL_NOISE.sub("", s)
    s = re.sub(r"[^A-Za-z0-9 &]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class RateLimiter:
    """Enforces a minimum spacing between GDELT calls so we stay under its rate limit
    instead of tripping 429s and paying for it with long exponential-backoff retries."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.monotonic()


def _gdelt_raw(
    limiter: RateLimiter,
    query: str,
    start_date: str,
    end_date: str,
    max_records: int,
    retries: int = 2,
) -> list[dict]:
    import requests

    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": min(max_records, 250),
        "format": "json",
        "startdatetime": start_date.replace("-", "") + "000000",
        "enddatetime": end_date.replace("-", "") + "235959",
        "sort": "DateDesc",
    }
    for attempt in range(retries):
        limiter.wait()
        try:
            resp = requests.get(
                GDELT_URL, params=params, headers={"User-Agent": GDELT_UA}, timeout=10
            )
            if resp.status_code == 200:
                articles = (resp.json() or {}).get("articles", []) or []
                return [
                    {
                        "title": a.get("title", ""),
                        "date": (a.get("seendate", "") or "")[:8],
                        "domain": a.get("domain", ""),
                        "source": "gdelt",
                        "url": a.get("url", ""),
                    }
                    for a in articles
                    if a.get("title")
                ]
            if resp.status_code == 429 and attempt < retries - 1:
                time.sleep(3.0 * (attempt + 1))
                continue
            return []
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            if attempt < retries - 1:
                time.sleep(2.0)
                continue
            return []
    return []


def fetch_gdelt(
    limiter: RateLimiter,
    company_name: str,
    start_date: str,
    end_date: str,
    max_records: int = 50,
) -> list[dict]:
    """Exact-phrase English query first; fall back to any-language, then a keyword query."""
    name = clean_name(company_name)
    if not name or len(name) < 3:
        return []
    for q in [f'"{name}" sourcelang:English', f'"{name}"']:
        arts = _gdelt_raw(limiter, q, start_date, end_date, max_records)
        if arts:
            return arts
    return []


def fetch_edgar(
    company_name: str,
    start_date: str,
    end_date: str,
    forms: str = "8-K,SC-TO,SC-13D,SC-13G,DEFM14A",
) -> list[dict]:
    name = clean_name(company_name)
    if not name or len(name) < 3:
        return []
    try:
        raw = http_get(
            EDGAR_FTS_URL
            + "?"
            + "&".join(
                [
                    f"q={url_quote(chr(34) + name + chr(34))}",
                    "dateRange=custom",
                    f"startdt={start_date}",
                    f"enddt={end_date}",
                    f"forms={url_quote(forms)}",
                ]
            ),
            timeout=20,
            retries=3,
        )
        hits = (json.loads(raw.decode("utf-8")).get("hits", {}) or {}).get(
            "hits", []
        ) or []
        out = []
        for h in hits:
            src = h.get("_source") or {}
            file_date = src.get("file_date", "")
            if not file_date:
                continue
            out.append(
                {
                    "title": f"[{src.get('root_forms', ['SEC'])[0]}] {(src.get('display_names') or [''])[0]} filed {file_date}",
                    "date": file_date.replace("-", ""),
                    "domain": "sec.gov",
                    "source": "edgar",
                    "url": "",
                }
            )
        return out
    except Exception:
        return []


def get_window_dates(
    announcement_date,
    window: str,
    lookback_days: int,
    blackout_days: int,
    negative_shift: int,
) -> tuple[str, str]:
    ann = pd.Timestamp(announcement_date)
    if window == "pre":
        end = ann - timedelta(days=blackout_days)
        start = ann - timedelta(days=lookback_days + blackout_days)
    else:
        end = ann - timedelta(days=blackout_days + negative_shift)
        start = ann - timedelta(days=lookback_days + blackout_days + negative_shift)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def load_cache(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, dtype=str).fillna("")
    return pd.DataFrame(columns=CACHE_COLUMNS)


def select_events(
    events: pd.DataFrame, n_events: int, seed: int, min_deal_value_usd: float | None
) -> pd.DataFrame:
    pool = events[
        events["target_name"].notna()
        & events["deal_status"].isin(["Completed", "Announced"])
    ].copy()
    if min_deal_value_usd is not None:
        pool = pool[pool["deal_value_usd"] >= min_deal_value_usd]
    if n_events and n_events < len(pool):
        pool = pool.sample(n=n_events, random_state=seed)
    return pool


def run(
    events_path: Path,
    output_path: Path,
    manifest_path: Path,
    n_events: int,
    seed: int,
    min_deal_value_usd: float | None,
    lookback_days: int,
    blackout_days: int,
    negative_shift: int,
    gdelt_min_interval: float,
    flush_every: int,
    verbose: bool,
) -> None:
    events = pd.read_csv(events_path, parse_dates=["announcement_date"])
    sample = select_events(events, n_events, seed, min_deal_value_usd)

    cache = load_cache(output_path)
    done = set(zip(cache["transaction_id"], cache["window"]))
    limiter = RateLimiter(gdelt_min_interval)

    print(
        f"Event pool: {len(sample):,} events (of {len(events):,} total) | "
        f"already cached: {cache['transaction_id'].nunique() if not cache.empty else 0} events"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    new_rows: list[dict] = []
    n_scraped = 0
    for i, (_, row) in enumerate(sample.iterrows(), start=1):
        txn_id = str(row["transaction_id"])
        company = row["target_name"]

        for window, label in [("pre", "1"), ("baseline", "0")]:
            if (txn_id, window) in done:
                continue
            start_d, end_d = get_window_dates(
                row["announcement_date"],
                window,
                lookback_days,
                blackout_days,
                negative_shift,
            )
            articles = fetch_gdelt(limiter, company, start_d, end_d) + fetch_edgar(
                company, start_d, end_d
            )
            seen_titles: set[str] = set()
            deduped = []
            for a in articles:
                if a["title"] and a["title"] not in seen_titles:
                    seen_titles.add(a["title"])
                    deduped.append(a)
            if deduped:
                for a in deduped:
                    new_rows.append(
                        {
                            "transaction_id": txn_id,
                            "window": window,
                            "label": label,
                            "company_name": company,
                            **a,
                        }
                    )
            else:
                new_rows.append(
                    {
                        "transaction_id": txn_id,
                        "window": window,
                        "label": label,
                        "company_name": company,
                        "title": "",
                        "date": "",
                        "domain": "",
                        "source": "",
                        "url": "",
                    }
                )
            done.add((txn_id, window))
            n_scraped += 1

        if verbose:
            print(
                f"  [{i}/{len(sample)}] {company!r} -> {sum(1 for r in new_rows if r['transaction_id'] == txn_id and r['title'])} articles"
            )

        if len(new_rows) >= flush_every * 2:
            cache = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
            cache.to_csv(output_path, index=False)
            new_rows = []
            print(
                f"  ... checkpoint: {cache['transaction_id'].nunique()} events cached, {len(cache):,} rows"
            )

    if new_rows:
        cache = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
        cache.to_csv(output_path, index=False)

    articles_only = cache[cache["title"] != ""]
    manifest = pd.DataFrame(
        [
            {
                "run_at": pd.Timestamp.utcnow().isoformat(),
                "events_targeted": len(sample),
                "events_cached_total": cache["transaction_id"].nunique(),
                "rows_total": len(cache),
                "articles_total": len(articles_only),
                "events_with_articles": articles_only["transaction_id"].nunique(),
            }
        ]
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    header = not manifest_path.exists()
    manifest.to_csv(manifest_path, mode="a", header=header, index=False)

    try:
        display_path = output_path.relative_to(PROJECT_ROOT)
    except ValueError:
        display_path = output_path
    print(
        f"\nDone. Cache: {len(cache):,} rows across {cache['transaction_id'].nunique()} events "
        f"-> {display_path}"
    )
    print(
        f"  Articles with text: {len(articles_only):,} | events with >=1 article: {articles_only['transaction_id'].nunique()}"
    )
    if not articles_only.empty:
        print(articles_only["source"].value_counts().to_string())


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Cache GDELT + SEC EDGAR news for large M&A events, locally and resumably."
    )
    p.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument(
        "--n-events",
        type=int,
        default=300,
        help="Number of events to sample this run (0 = all).",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--min-deal-value-usd",
        type=float,
        default=None,
        help="Extra filter on top of ma_events.csv (which is already >=$1B by default).",
    )
    p.add_argument("--lookback-days", type=int, default=90)
    p.add_argument("--blackout-days", type=int, default=7)
    p.add_argument("--negative-shift", type=int, default=180)
    p.add_argument(
        "--gdelt-min-interval",
        type=float,
        default=1.2,
        help="Minimum seconds between GDELT requests (avoids tripping 429 rate limits).",
    )
    p.add_argument(
        "--flush-every",
        type=int,
        default=25,
        help="Checkpoint the cache to disk every N events.",
    )
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run(
        args.events,
        args.output,
        args.manifest,
        args.n_events,
        args.seed,
        args.min_deal_value_usd,
        args.lookback_days,
        args.blackout_days,
        args.negative_shift,
        args.gdelt_min_interval,
        args.flush_every,
        args.verbose,
    )


if __name__ == "__main__":
    main()
