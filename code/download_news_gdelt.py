"""Pull company news headlines from GDELT (free, no API key).

GDELT's DOC 2.0 API indexes global online news (~2017->present), including Reuters, AP,
Bloomberg, CNBC, etc. Article-level rows (date, source domain, title, country, url) aggregate
to per-(ticker, date) news features -- the article-text complement to the 8-K event feed.

Reuters has no free article API, so this is the practical way to get Reuters-sourced news:
filter on the is_reuters / is_major_wire flags (exact-domain matching, no lookalike false positives).

Caveat: free-text company-name recall is uneven and GDELT rate-limits, so this is best for
targeted spot-checks, not a sweep of the whole universe (http_get retries the 429/5xx it throws).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

from _sec_http import http_get


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIVERSE = PROJECT_ROOT / "data" / "raw" / "index" / "us_listed_companies_sec.csv"
DEFAULT_PRICES = PROJECT_ROOT / "data" / "raw" / "market" / "daily_prices.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "news" / "gdelt_articles.csv"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

MAJOR_WIRES = ("reuters.com", "apnews.com", "bloomberg.com", "cnbc.com", "ft.com", "wsj.com")
MNA_TERMS = '(acquisition OR merger OR takeover OR acquire OR "strategic alternatives")'

SUFFIX_RE = re.compile(
    r",?\s+(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|LLC|LP|HOLDINGS|GROUP|SA|AG|NV)\.?$",
    re.IGNORECASE,
)


def clean_name(name: str) -> str:
    n = str(name).strip()
    prev = None
    while n != prev:
        prev = n
        n = SUFFIX_RE.sub("", n).strip().rstrip(",")
    return n


def _domain_match(domain: str, wire: str) -> bool:
    """Exact host match (so 'notreuters.com' does NOT match 'reuters.com')."""
    return domain == wire or domain.endswith("." + wire)


def fetch_gdelt(query: str, start: str, end: str, maxrecords: int) -> list[dict]:
    params = {"query": query, "mode": "ArtList", "maxrecords": maxrecords,
              "format": "json", "sort": "datedesc", "startdatetime": start, "enddatetime": end}
    raw = http_get(f"{GDELT_URL}?{urlencode(params)}").decode("utf-8", "replace")
    if not raw.strip().startswith("{"):
        return []  # GDELT returns plain text on rate-limit / empty / malformed query
    return json.loads(raw).get("articles", [])


def load_companies(args) -> list[tuple[str | None, str]]:
    if args.companies:
        return [(None, c.strip()) for c in args.companies.split(",") if c.strip()]
    uni = pd.read_csv(args.universe).dropna(subset=["ticker", "company_name"]).drop_duplicates("ticker")
    if args.only_priced:
        priced = set(pd.read_csv(args.prices)["ticker"].astype(str).str.upper())
        uni = uni[uni["ticker"].astype(str).str.upper().isin(priced)]
    if args.limit_companies:
        uni = uni.head(args.limit_companies)
    return [(str(t).upper(), clean_name(n)) for t, n in zip(uni["ticker"], uni["company_name"])]


def build_feed(args) -> pd.DataFrame:
    companies = load_companies(args)
    records: list[dict] = []
    total = len(companies)
    for i, (ticker, name) in enumerate(companies, start=1):
        query = f'"{name}"' + (f" {MNA_TERMS}" if args.mna_only else "")
        try:
            articles = fetch_gdelt(query, args.start, args.end, args.maxrecords)
        except Exception as exc:  # noqa: BLE001
            if args.verbose:
                print(f"  ! {name}: {exc}")
            articles = []
        for a in articles:
            domain = (a.get("domain") or "").lower()
            records.append({
                "ticker": ticker, "company": name, "seen_date": a.get("seendate"),
                "title": a.get("title"), "domain": domain, "sourcecountry": a.get("sourcecountry"),
                "language": a.get("language"),
                "is_reuters": int(_domain_match(domain, "reuters.com")),
                "is_major_wire": int(any(_domain_match(domain, w) for w in MAJOR_WIRES)),
                "url": a.get("url"),
            })
        if i % 25 == 0 or i == total:
            print(f"  {i}/{total} companies  ({len(records):,} articles)")
        time.sleep(args.sleep)

    df = pd.DataFrame.from_records(records)
    if not df.empty:
        df["seen_date"] = pd.to_datetime(df["seen_date"], errors="coerce")
        df = df.dropna(subset=["seen_date"]).sort_values(["company", "seen_date"]).reset_index(drop=True)
    return df


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pull company news headlines from GDELT (free, no key).")
    p.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    p.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--companies", help="Comma-separated company names (overrides the universe).")
    p.add_argument("--only-priced", action="store_true")
    p.add_argument("--limit-companies", type=int, default=0)
    p.add_argument("--mna-only", action="store_true", help="Add M&A keywords to each query.")
    p.add_argument("--start", default="20170101000000", help="Start datetime, YYYYMMDDHHMMSS.")
    p.add_argument("--end", default="20261231000000", help="End datetime, YYYYMMDDHHMMSS.")
    p.add_argument("--maxrecords", type=int, default=250)
    p.add_argument("--sleep", type=float, default=1.5)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    df = build_feed(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"\nWrote {len(df):,} articles for {df['company'].nunique() if not df.empty else 0} companies "
          f"to {os.path.relpath(args.output, PROJECT_ROOT)}")
    if not df.empty:
        print(f"  date range : {df['seen_date'].min().date()} -> {df['seen_date'].max().date()}")
        print(f"  Reuters    : {int(df['is_reuters'].sum()):,} | major wires: {int(df['is_major_wire'].sum()):,}")


if __name__ == "__main__":
    main()
