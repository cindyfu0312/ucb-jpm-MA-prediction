"""Collapse CIQ transcripts to one row per (ticker, earnings call) for panel joins.

The raw WRDS pull (transcript_manifest.csv) is keyed on (transcriptid, companyid), has CIQ
revision duplicates (multiple transcriptids per call), and carries NO ticker. This script,
run locally (no WRDS), turns it into a panel-joinable table:

  1. attaches ticker via the ticker->companyid crosswalk. An INNER join also drops companyids
     that are not in the (de-duplicated) crosswalk -- i.e. the wrong matches from an ambiguous
     crosswalk -- so rebuild the crosswalk with the primaryflag filter first for best results.
  2. de-duplicates revisions to ONE transcript per (companyid, call_date), keeping the most
     complete version (max components, then max words) -- avoids near-empty audio-stub revisions.
  3. writes one row per (ticker, call).

Point-in-time join to the panel: for each (ticker, as_of_date), take the most recent call with
call_date STRICTLY BEFORE as_of_date (no look-ahead).

  data/raw/text/transcripts/transcript_calls.csv
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "raw" / "text" / "transcripts" / "transcript_manifest.csv"
DEFAULT_CROSSWALK = PROJECT_ROOT / "data" / "raw" / "index" / "ticker_to_ciq_companyid.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "text" / "transcripts" / "transcript_calls.csv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dedup CIQ transcripts into a (ticker, call) table.")
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--crosswalk", type=Path, default=DEFAULT_CROSSWALK)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    manifest = pd.read_csv(args.manifest)
    cross = pd.read_csv(args.crosswalk).dropna(subset=["companyid", "ticker"]).copy()
    cross["companyid"] = cross["companyid"].astype("int64")
    # Prefer unambiguous crosswalk rows, then one ticker per companyid.
    if "ambiguous" in cross.columns:
        cross = cross.sort_values("ambiguous")
    cmap = cross.drop_duplicates("companyid")[["companyid", "ticker"]]

    m = manifest.copy()
    m["companyid"] = pd.to_numeric(m["companyid"], errors="coerce").astype("Int64")
    m["call_date"] = pd.to_datetime(m["call_date"], errors="coerce")
    m = m.dropna(subset=["companyid", "call_date"])
    m = m.merge(cmap, on="companyid", how="inner")  # attach ticker; drop off-crosswalk companyids

    # De-dup revisions: one transcript per call, most complete first.
    sort_cols = [c for c in ["n_components", "total_words"] if c in m.columns]
    m = m.sort_values(["companyid", "call_date"] + sort_cols,
                      ascending=[True, True] + [False] * len(sort_cols))
    calls = m.drop_duplicates(subset=["companyid", "call_date"], keep="first")

    keep = [c for c in ["ticker", "companyid", "company_name", "call_date", "transcriptid",
                        "n_components", "total_words"] if c in calls.columns]
    calls = calls[keep].sort_values(["ticker", "call_date"]).reset_index(drop=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    calls.to_csv(args.output, index=False)

    print(f"Wrote {len(calls):,} calls for {calls['ticker'].nunique():,} tickers "
          f"-> {os.path.relpath(args.output, PROJECT_ROOT)}")
    print(f"  collapsed from {len(manifest):,} raw transcripts "
          f"(revision dupes + off-crosswalk companyids dropped)")


if __name__ == "__main__":
    main()
