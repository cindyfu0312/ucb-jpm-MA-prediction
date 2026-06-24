"""Bulk-download Capital IQ earnings-call transcripts from WRDS.

S&P licenses Capital IQ Transcripts to WRDS as a queryable database, so the way to
"mass download from Capital IQ" is to query WRDS (the CIQ web terminal only exports
one call at a time). This pulls full earnings-call transcripts -- speaker/section
level text -- for a set of companies over a date range, and writes:

  data/raw/text/transcripts/transcript_components.csv   # one row per speaker turn
  data/raw/text/transcripts/transcript_manifest.csv     # one row per call (panel join)

Requirements:
  - the `wrds` package + a WRDS account with the Capital IQ Transcripts subscription
  - WRDS prompts for credentials on first run (offers to save ~/.pgpass)

Schema confirmed against ciq.* on WRDS via `--discover`:
  - ciq.wrds_transcript_detail   : header (companyid, companyname, date, event type)  -- NO gvkey
  - ciq.ciqtranscriptcomponent   : the text (componenttext), keyed by transcriptcomponentid
  - ciq.wrds_transcript_person   : per-component speaker + section + word count

NOTE: this table has companyid/companyname but no ticker. Filter by company name
(--companies) or companyid (--companyids). Bulk pull by ticker needs a
ticker->companyid crosswalk (ciq_common security tables) -- a follow-up step.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "text" / "transcripts"
LIBRARY = "ciq"


def connect(username: str | None):
    try:
        import wrds
    except ImportError:
        sys.exit("The 'wrds' package is required:  pip install wrds")
    return wrds.Connection(wrds_username=username) if username else wrds.Connection()


def discover(db) -> None:
    """Print CIQ transcript libraries/tables/columns so the schema can be confirmed."""
    libs = [l for l in db.list_libraries() if "ciq" in l.lower() or "transcript" in l.lower()]
    print("Libraries matching ciq/transcript:\n ", libs)
    for tbl in ("wrds_transcript_detail", "ciqtranscriptcomponent", "wrds_transcript_person"):
        try:
            print(f"\nColumns of {LIBRARY}.{tbl}:")
            print(db.describe_table(library=LIBRARY, table=tbl).to_string(index=False))
        except Exception as exc:  # noqa: BLE001
            print(f"(could not describe {LIBRARY}.{tbl}: {exc})")


def resolve_company_filter(args) -> tuple[str, dict]:
    """Build the SQL WHERE fragment that selects companies, plus its bind params."""
    if getattr(args, "companyids_file", None):
        ids = pd.read_csv(args.companyids_file)["companyid"].dropna().astype(int).unique().tolist()
        print(f"  filtering to {len(ids)} companyids from {Path(args.companyids_file).name}")
        return "AND d.companyid = ANY(%(companyids)s)", {"companyids": ids}
    if args.companyids:
        ids = [int(x) for x in args.companyids.split(",") if x.strip()]
        return "AND d.companyid = ANY(%(companyids)s)", {"companyids": ids}
    if args.companies:
        names = [n.strip() for n in args.companies.split(",") if n.strip()]
        clauses = " OR ".join(f"d.companyname ILIKE %(name{i})s" for i in range(len(names)))
        params = {f"name{i}": f"{n}%" for i, n in enumerate(names)}
        return f"AND ({clauses})", params
    if not args.all:
        sys.exit("Refusing to pull ALL transcripts. Pass --companies, --companyids, or --all.")
    return "", {}


def fetch(db, args) -> pd.DataFrame:
    company_filter, company_params = resolve_company_filter(args)
    sql = f"""
        SELECT d.companyid                    AS companyid,
               d.companyname                  AS company_name,
               d.mostimportantdateutc         AS call_date,
               d.keydeveventtypename          AS event_type,
               d.transcriptid                 AS transcriptid,
               c.componentorder               AS component_order,
               p.transcriptcomponenttypename  AS section,
               p.transcriptpersonname         AS speaker,
               p.speakertypename              AS speaker_type,
               COALESCE(p.word_count, 0)      AS word_count,
               c.componenttext                AS text
        FROM {LIBRARY}.wrds_transcript_detail d
        JOIN {LIBRARY}.ciqtranscriptcomponent c
              ON c.transcriptid = d.transcriptid
        LEFT JOIN {LIBRARY}.wrds_transcript_person p
              ON p.transcriptcomponentid = c.transcriptcomponentid
        WHERE d.keydeveventtypename ILIKE %(event)s
          AND d.mostimportantdateutc BETWEEN %(start)s AND %(end)s
          {company_filter}
        ORDER BY d.transcriptid, c.componentorder
    """
    params = {"event": args.event, "start": args.start, "end": args.end, **company_params}
    print("Running WRDS query (this can take a while for large pulls)...")
    return db.raw_sql(sql, params=params)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bulk-download CIQ earnings-call transcripts from WRDS.")
    p.add_argument("--discover", action="store_true", help="Inspect the CIQ transcript schema and exit.")
    p.add_argument("--wrds-username", default=os.environ.get("WRDS_USERNAME"))
    p.add_argument("--start", default="2018-01-01", help="Earliest call date (YYYY-MM-DD).")
    p.add_argument("--end", default="2026-12-31", help="Latest call date (YYYY-MM-DD).")
    p.add_argument("--event", default="Earnings Call%", help="keydeveventtypename filter (ILIKE).")
    # company selection (choose one)
    p.add_argument("--companies", help="Comma-separated company-name prefixes (ILIKE).")
    p.add_argument("--companyids", help="Comma-separated CIQ companyids.")
    p.add_argument("--companyids-file", type=Path, help="CSV with a 'companyid' column (e.g. the ticker crosswalk).")
    p.add_argument("--all", action="store_true", help="Pull every company in the date range (large!).")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    db = connect(args.wrds_username)

    if args.discover:
        discover(db)
        return

    df = fetch(db, args)
    if df.empty:
        print("No transcripts returned -- check the date range / company filter / --event value.")
        return

    df = df.assign(call_date=pd.to_datetime(df["call_date"], errors="coerce"))
    args.output_dir.mkdir(parents=True, exist_ok=True)

    components_path = args.output_dir / "transcript_components.csv"
    manifest_path = args.output_dir / "transcript_manifest.csv"
    df.to_csv(components_path, index=False)

    manifest = (
        df.groupby(["transcriptid", "companyid", "company_name", "call_date"], dropna=False)
        .agg(n_components=("component_order", "size"), total_words=("word_count", "sum"))
        .reset_index()
        .sort_values("call_date")
    )
    manifest.to_csv(manifest_path, index=False)

    print(f"\nWrote {len(df):,} speaker turns across {manifest['transcriptid'].nunique():,} transcripts")
    print(f"  companies : {df['company_name'].nunique():,}")
    print(f"  date range: {df['call_date'].min().date()} -> {df['call_date'].max().date()}")
    print(f"  -> {os.path.relpath(components_path, PROJECT_ROOT)}")
    print(f"  -> {os.path.relpath(manifest_path, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
