from __future__ import annotations

import argparse
import difflib
import os
import re
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "data" / "raw" / "events" / "SPGlobal_TransactionsStatistics_10-Jun-2026.xlsx"
DEFAULT_UNIVERSE = PROJECT_ROOT / "data" / "raw" / "index" / "us_listed_companies_sec.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "events" / "ma_events.csv"
DEFAULT_AUDIT = PROJECT_ROOT / "data" / "raw" / "events" / "ma_events_match_audit.csv"

LEGAL_SUFFIXES = {
    "THE",
    "INC",
    "INCORPORATED",
    "CORP",
    "CORPORATION",
    "CO",
    "COMPANY",
    "COS",
    "COMPANIES",
    "LTD",
    "LIMITED",
    "PLC",
    "LLC",
    "LP",
    "L",
    "P",
    "SA",
    "AG",
    "NV",
    "HOLDING",
    "HOLDINGS",
    "GROUP",
    "DE",
    "NEW",
    "OLD",
    "MA",
    "VA",
    "TX",
    "NY",
    "CA",
    "DELAWARE",
    "ADR",
    "ADS",
}


def normalize_company_name(value: object) -> str:
    if pd.isna(value):
        return ""

    text = str(value).upper().replace("&", " AND ")
    text = text.replace("*", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"/[A-Z]{2,}(?:/[A-Z]{2,})*/?", " ", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    tokens = [token for token in text.split() if token not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def ticker_priority(ticker: object, sec_rank: object = pd.NA) -> tuple[int, int, int, str]:
    ticker_text = str(ticker).strip().upper()
    rank = pd.to_numeric(sec_rank, errors="coerce")
    rank_value = int(rank) if pd.notna(rank) else 1_000_000
    non_common_penalty = 0
    if ".P" in ticker_text or ticker_text.endswith((".U", ".W", ".R")):
        non_common_penalty += 100_000
    if "." not in ticker_text and len(ticker_text) > 4 and ticker_text.endswith(("U", "W", "R")):
        non_common_penalty += 100_000
    return non_common_penalty, rank_value, len(ticker_text), ticker_text


def build_name_map(universe: pd.DataFrame) -> dict[str, str]:
    candidates: dict[str, list[tuple[tuple[int, int, int, str], str]]] = {}

    for _, row in universe.dropna(subset=["ticker", "company_name"]).iterrows():
        ticker = str(row["ticker"]).strip().upper()
        normalized = normalize_company_name(row["company_name"])
        if len(normalized) < 3:
            continue
        candidates.setdefault(normalized, []).append((ticker_priority(ticker, row.get("sec_rank", pd.NA)), ticker))

    return {normalized: sorted(options)[0][1] for normalized, options in candidates.items()}


def match_company_name(
    value: object,
    name_to_ticker: dict[str, str],
    match_keys: list[str],
    fuzzy_cutoff: float | None,
) -> tuple[str | pd.NA, str, str | pd.NA]:
    normalized = normalize_company_name(value)
    if normalized in name_to_ticker:
        return name_to_ticker[normalized], "normalized_exact", normalized

    if fuzzy_cutoff is None or len(normalized) < 6:
        return pd.NA, "no_match", normalized or pd.NA

    closest = difflib.get_close_matches(normalized, match_keys, n=1, cutoff=fuzzy_cutoff)
    if closest:
        return name_to_ticker[closest[0]], "fuzzy", closest[0]

    return pd.NA, "no_match", normalized


def clean_events(
    source_path: Path,
    universe_path: Path,
    fuzzy_cutoff: float | None = None,
    require_target_ticker: bool = False,
    require_acquirer_ticker: bool = False,
    company_level_only: bool = False,
    include_spinoff: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if source_path.suffix.lower() == ".csv":
        raw = pd.read_csv(source_path)
    else:
        raw = pd.read_excel(source_path, sheet_name="Transactions Statistics")
    universe = pd.read_csv(universe_path)
    name_to_ticker = build_name_map(universe)
    match_keys = list(name_to_ticker)

    events = raw.copy()
    events["Announcement Date"] = pd.to_datetime(events["Announcement Date"], errors="coerce")
    events["Completion Date"] = pd.to_datetime(events["Completion Date"], errors="coerce")

    is_usa = events["Country/Region"].astype(str).str.strip().str.upper().eq("USA")
    events = events.loc[is_usa].copy()
    if not include_spinoff:
        events = events.loc[events["Transaction Type"].astype(str).str.contains("Acquisition", case=False, na=False)].copy()
    if company_level_only:
        transaction_type = events["Transaction Type"].astype(str)
        is_company_level_deal = transaction_type.str.contains(
            "Acquisition of Whole Company|Acquisition of Minority Stake",
            case=False,
            na=False,
            regex=True,
        )
        events = events.loc[is_company_level_deal].copy()

    target_matches = events["Target or Issuer"].apply(
        lambda value: match_company_name(value, name_to_ticker, match_keys, fuzzy_cutoff)
    )
    acquirer_matches = events["Buyer"].apply(
        lambda value: match_company_name(value, name_to_ticker, match_keys, fuzzy_cutoff)
    )

    events[["target_ticker", "target_match_method", "target_matched_name"]] = pd.DataFrame(
        target_matches.tolist(), index=events.index
    )
    events[["acquirer_ticker", "acquirer_match_method", "acquirer_matched_name"]] = pd.DataFrame(
        acquirer_matches.tolist(), index=events.index
    )

    if require_acquirer_ticker:
        cleaned = events.dropna(subset=["target_ticker", "acquirer_ticker"]).copy()
    elif require_target_ticker:
        cleaned = events.dropna(subset=["target_ticker"]).copy()
    else:
        cleaned = events.copy()

    deal_value_m = cleaned["Deal Value ($M)"].combine_first(cleaned["Transaction Value ($M)"])
    cleaned["deal_value_usd"] = (pd.to_numeric(deal_value_m, errors="coerce") * 1_000_000).round().astype("Int64")

    output = pd.DataFrame(
        {
            "transaction_id": cleaned["Transaction ID"],
            "announcement_date": cleaned["Announcement Date"].dt.date,
            "target_name": cleaned["Target or Issuer"],
            "target_ticker": cleaned["target_ticker"].astype("string").str.upper(),
            "acquirer_name": cleaned["Buyer"],
            "acquirer_ticker": cleaned["acquirer_ticker"].astype("string").str.upper(),
            "seller_name": cleaned["Seller"],
            "transaction_type": cleaned["Transaction Type"],
            "deal_status": cleaned["Status"],
            "close_date": cleaned["Completion Date"].dt.date,
            "deal_value_usd": cleaned["deal_value_usd"],
            "primary_industry": cleaned["Primary Industry (MI)"],
            "country_region": cleaned["Country/Region"],
        }
    )
    output = output.sort_values(["announcement_date", "transaction_id"], ascending=[False, True]).reset_index(drop=True)

    audit_columns = [
        "Transaction ID",
        "Announcement Date",
        "Completion Date",
        "Target or Issuer",
        "target_ticker",
        "target_match_method",
        "target_matched_name",
        "Buyer",
        "acquirer_ticker",
        "acquirer_match_method",
        "acquirer_matched_name",
        "Seller",
        "Transaction Type",
        "Transaction Value ($M)",
        "Deal Value ($M)",
        "Status",
        "Primary Industry (MI)",
        "Country/Region",
    ]
    audit = cleaned[audit_columns].sort_values(["Announcement Date", "Target or Issuer"], ascending=[False, True])
    return output, audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean SPGlobal M&A transactions into the Week 1 event schema.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument(
        "--fuzzy-cutoff",
        type=float,
        default=None,
        help="Optional fuzzy matching cutoff. Omit for safer exact normalized name matching only.",
    )
    parser.add_argument(
        "--require-target-ticker",
        action="store_true",
        help="Keep only deals where the target can be mapped to the selected ticker universe.",
    )
    parser.add_argument(
        "--require-acquirer-ticker",
        action="store_true",
        help="Keep only deals where the buyer can also be mapped to the selected ticker universe.",
    )
    parser.add_argument(
        "--company-level-only",
        action="store_true",
        help="Exclude asset/branch acquisitions and spinoff/splitoff transactions.",
    )
    parser.add_argument(
        "--include-spinoff",
        action="store_true",
        help="Also keep spinoff/splitoff events. By default only acquisition-style M&A events are kept.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output, audit = clean_events(
        source_path=args.source,
        universe_path=args.universe,
        fuzzy_cutoff=args.fuzzy_cutoff,
        require_target_ticker=args.require_target_ticker,
        require_acquirer_ticker=args.require_acquirer_ticker,
        company_level_only=args.company_level_only,
        include_spinoff=args.include_spinoff,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    audit.to_csv(args.audit, index=False)

    print(f"Wrote {len(output):,} cleaned M&A events to {os.path.relpath(args.output, PROJECT_ROOT)}")
    print(f"Wrote {len(audit):,} matched event audit rows to {os.path.relpath(args.audit, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
