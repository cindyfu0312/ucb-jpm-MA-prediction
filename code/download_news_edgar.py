"""Build a structured 8-K corporate-news event feed from SEC EDGAR.

For every company in the universe, query the SEC submissions API and extract one row per
8-K filing: date + item codes. 8-K items are the news signal:
  - LEADING (predictive): 1.01 entry into a material agreement, 1.02 termination.
  - COMPLETION (outcome): 2.01 completion of acquisition -- this fires the day a deal CLOSES,
    so it is the event being predicted. It is emitted in a SEPARATE column (is_completion) and
    must NOT be used as an as-of feature, to avoid label leakage.
Joins to the panel by (ticker, filing_date) -> (ticker, as_of_date), point-in-time.

Unlike code/download.py (full filing text for one ticker), this is a compact event TABLE
across the whole universe -- features, not blobs.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd

from _sec_http import http_get


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIVERSE = PROJECT_ROOT / "data" / "raw" / "index" / "us_listed_companies_sec.csv"
DEFAULT_PRICES = PROJECT_ROOT / "data" / "raw" / "market" / "daily_prices.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "news" / "edgar_8k_events.csv"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SHARD_URL = "https://data.sec.gov/submissions/{name}"

# 8-K item codes. Leading = predictive (before outcome); completion = the deal-closing OUTCOME.
MNA_LEADING_ITEMS = {"1.01", "1.02"}
COMPLETION_ITEMS = {"2.01"}


def _rows_from(block: dict) -> list[tuple]:
    return list(zip(block.get("form", []), block.get("filingDate", []), block.get("items", []),
                    block.get("accessionNumber", []), block.get("primaryDocument", [])))


def fetch_company_8ks(cik: int, sleep: float) -> list[dict]:
    """Return all 8-K filings for one CIK, following submissions pagination shards (full history)."""
    base = json.loads(http_get(SUBMISSIONS_URL.format(cik=int(cik))).decode("utf-8"))
    filings = base.get("filings", {})
    rows = _rows_from(filings.get("recent", {}))
    for shard in filings.get("files", []):          # older filings are paged into separate shards
        name = shard.get("name") if isinstance(shard, dict) else shard
        if not name:
            continue
        time.sleep(sleep)
        try:
            rows += _rows_from(json.loads(http_get(SHARD_URL.format(name=name)).decode("utf-8")))
        except Exception:  # noqa: BLE001 - a bad shard shouldn't kill the company
            continue
    return [{"filing_date": d, "items": it or "", "accession": acc or "", "primary_doc": doc or ""}
            for form, d, it, acc, doc in rows if form == "8-K"]


def build_event_feed(universe_path, prices_path, only_priced, limit_tickers, sleep, verbose) -> pd.DataFrame:
    universe = pd.read_csv(universe_path).dropna(subset=["cik", "ticker"]).drop_duplicates("ticker")
    universe["ticker"] = universe["ticker"].astype(str).str.upper()
    if only_priced:
        priced = set(pd.read_csv(prices_path)["ticker"].astype(str).str.upper())
        universe = universe[universe["ticker"].isin(priced)]
    if limit_tickers:
        universe = universe.head(limit_tickers)

    cache: dict[int, list[dict]] = {}
    records: list[dict] = []
    errors = 0
    total = len(universe)
    for n, (_, row) in enumerate(universe.iterrows(), start=1):
        cik = int(row["cik"])
        ticker = row["ticker"]
        try:
            if cik not in cache:
                cache[cik] = fetch_company_8ks(cik, sleep)
                time.sleep(sleep)
            filings = cache[cik]
        except Exception as exc:  # noqa: BLE001
            errors += 1
            if verbose:
                print(f"  ! {ticker} (CIK {cik}): {exc}")
            continue
        for f in filings:
            items = {x.strip() for x in str(f["items"]).split(",") if x.strip()}
            acc_nodash = f["accession"].replace("-", "")
            doc_url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{f['primary_doc']}"
                       if f["primary_doc"] else "")
            records.append({
                "cik": cik, "ticker": ticker, "filing_date": f["filing_date"], "items": f["items"],
                "is_mna_leading": int(bool(items & MNA_LEADING_ITEMS)),
                "is_completion": int(bool(items & COMPLETION_ITEMS)),
                "accession": f["accession"], "doc_url": doc_url,
            })
        if n % 100 == 0 or n == total:
            print(f"  {n}/{total} companies  ({len(records):,} 8-Ks, {errors} errors)")

    events = pd.DataFrame.from_records(records)
    if not events.empty:
        events["filing_date"] = pd.to_datetime(events["filing_date"], errors="coerce")
        events = events.dropna(subset=["filing_date"]).sort_values(["ticker", "filing_date"]).reset_index(drop=True)
    return events


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a structured 8-K event feed from SEC EDGAR.")
    p.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    p.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--only-priced", action="store_true", help="Restrict to tickers present in the price file.")
    p.add_argument("--limit-tickers", type=int, default=0, help="Cap the number of companies (for testing).")
    p.add_argument("--sleep", type=float, default=0.1, help="Seconds between SEC requests (<= 10 req/s).")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    events = build_event_feed(args.universe, args.prices, args.only_priced, args.limit_tickers, args.sleep, args.verbose)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.output, index=False)
    companies = events["ticker"].nunique() if not events.empty else 0
    print(f"\nWrote {len(events):,} 8-K events for {companies} companies to {os.path.relpath(args.output, PROJECT_ROOT)}")
    if not events.empty:
        print(f"  date range : {events['filing_date'].min().date()} -> {events['filing_date'].max().date()}")
        print(f"  leading M&A (1.01/1.02): {int(events['is_mna_leading'].sum()):,}"
              f" | completions (2.01, OUTCOME): {int(events['is_completion'].sum()):,}")


if __name__ == "__main__":
    main()
