"""Map tickers -> Capital IQ companyid using WRDS ciq_common identifier tables.

The CIQ transcript tables key on companyid, not ticker. This builds a
ticker -> companyid crosswalk so transcripts (and other CIQ data) can be pulled
precisely for the project's universe, instead of fuzzy company-name matching.

  python code/build_ciq_crosswalk.py --discover            # inspect the id schema
  python code/build_ciq_crosswalk.py --only-priced         # map the 999 priced tickers
  python code/build_ciq_crosswalk.py                       # map the full universe

Output: data/raw/index/ticker_to_ciq_companyid.csv
Then:   python code/download_transcripts_wrds.py --companyids-file data/raw/index/ticker_to_ciq_companyid.csv

Standard CIQ chain: ciqtradingitem (ticker) -> ciqsecurity (companyid) -> ciqcompany.
Confirm column names with --discover if the query errors.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIVERSE = PROJECT_ROOT / "data" / "raw" / "index" / "us_listed_companies_sec.csv"
DEFAULT_PRICES = PROJECT_ROOT / "data" / "raw" / "market" / "daily_prices.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "index" / "ticker_to_ciq_companyid.csv"
LIB = "ciq_common"


def connect(username: str | None):
    try:
        import wrds
    except ImportError:
        sys.exit("The 'wrds' package is required:  pip install wrds")
    return wrds.Connection(wrds_username=username) if username else wrds.Connection()


def discover(db) -> None:
    tbls = [t for t in db.list_tables(library=LIB) if any(k in t for k in ("security", "tradingitem", "company"))]
    print(f"[{LIB}] identifier tables:\n  {tbls}")
    for t in ("ciqcompany", "ciqsecurity", "ciqtradingitem"):
        try:
            print(f"\nColumns of {LIB}.{t}:")
            print(db.describe_table(library=LIB, table=t).to_string(index=False))
        except Exception as exc:  # noqa: BLE001
            print(f"(could not describe {LIB}.{t}: {exc})")


def load_tickers(args) -> list[str]:
    uni = pd.read_csv(args.universe)
    tickers = uni["ticker"].dropna().astype(str).str.upper()
    if args.only_priced:
        priced = set(pd.read_csv(args.prices)["ticker"].astype(str).str.upper())
        tickers = tickers[tickers.isin(priced)]
    return sorted(tickers.unique())


def fetch_crosswalk(db, tickers: list[str]) -> pd.DataFrame:
    sql = f"""
        SELECT upper(ti.tickersymbol) AS ticker,
               s.companyid            AS companyid,
               c.companyname          AS companyname,
               s.securityid           AS securityid,
               ti.tradingitemid       AS tradingitemid
        FROM {LIB}.ciqtradingitem ti
        JOIN {LIB}.ciqsecurity s ON s.securityid = ti.securityid
        JOIN {LIB}.ciqcompany  c ON c.companyid  = s.companyid
        WHERE upper(ti.tickersymbol) = ANY(%(tickers)s)
          -- Disambiguate the ~75% of tickers that map to many companyids: keep the company's
          -- PRIMARY security only. Confirm the exact flag column with --discover first.
          -- Do NOT filter on active/listing status: M&A targets get acquired and delisted,
          -- and dropping them would remove exactly the companies this project predicts.
          AND s.primaryflag = 1    -- company's primary security (common stock)
          AND ti.primaryflag = 1   -- primary trading item (primary exchange listing)
    """
    return db.raw_sql(sql, params={"tickers": tickers})


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Map tickers -> CIQ companyid via WRDS ciq_common.")
    p.add_argument("--discover", action="store_true", help="Inspect the ciq_common identifier schema and exit.")
    p.add_argument("--wrds-username", default=os.environ.get("WRDS_USERNAME"))
    p.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    p.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    p.add_argument("--only-priced", action="store_true", help="Restrict to tickers present in the price file.")
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    db = connect(args.wrds_username)

    if args.discover:
        discover(db)
        return

    tickers = load_tickers(args)
    print(f"Mapping {len(tickers):,} tickers via {LIB} ...")
    df = fetch_crosswalk(db, tickers)
    if df.empty:
        print("No matches -- confirm ciq_common table/column names with --discover.")
        return

    df = df.dropna(subset=["companyid"]).copy()
    df["companyid"] = df["companyid"].astype(int)
    # One row per (ticker, companyid); if a ticker maps to several companies, keep all
    # but flag ambiguity so the transcript pull can be reviewed.
    counts = df.groupby("ticker")["companyid"].nunique()
    crosswalk = (
        df.sort_values(["ticker", "companyid"])
        .drop_duplicates(subset=["ticker", "companyid"])
        .assign(ambiguous=lambda x: x["ticker"].map(counts > 1))
        .reset_index(drop=True)
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    crosswalk.to_csv(args.output, index=False)

    matched = crosswalk["ticker"].nunique()
    ambiguous = int((counts > 1).sum())
    print(f"\nMapped {matched:,}/{len(tickers):,} tickers ({ambiguous} ambiguous) -> {os.path.relpath(args.output, PROJECT_ROOT)}")
    print(f"  {len(crosswalk):,} ticker-companyid rows; unique companyids: {crosswalk['companyid'].nunique():,}")


if __name__ == "__main__":
    main()
