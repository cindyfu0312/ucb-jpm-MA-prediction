"""Best-effort full-article-text enrichment for already-cached GDELT headlines.

`download_news_ma_events.py` only stores GDELT's headline + URL, not the article body --
headlines alone carry much less signal than the article text. This is a separate, additive,
resumable script (does not touch download_news_ma_events.py) that visits each cached GDELT
URL once, does best-effort boilerplate-stripped text extraction, and appends the result to a
local persistent cache (`data/raw/news/ma_event_article_text.csv`, gitignored like the other
news caches). Re-running is safe: any URL already present (success OR permanent failure) is
skipped, so a run can be stopped/resumed/topped up without re-fetching.

Expected yield is well under 100% -- paywalls, dead links, JS-only pages, and anti-bot blocks
are all normal outcomes here; `fetched=0` rows just mean "no usable text," not a bug.
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NEWS_CACHE = PROJECT_ROOT / "data" / "raw" / "news" / "ma_event_news.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "news" / "ma_event_article_text.csv"

UA = ("Mozilla/5.0 (compatible; UCB-JPM-MA-research/1.0; "
      "contact ronaldliubc@gmail.com)")
MAX_CHARS = 4000
CACHE_COLUMNS = ["url", "transaction_id", "window", "fetched", "char_count", "text", "error"]


def extract_text(html: bytes) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
        tag.decompose()
    container = soup.find("article") or soup.find(attrs={"role": "main"}) or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if len(p) > 40]  # drop nav/caption fragments
    text = " ".join(paragraphs)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_CHARS]


def load_cache(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, dtype=str).fillna("")
    return pd.DataFrame(columns=CACHE_COLUMNS)


def run(news_cache_path: Path, output_path: Path, limit: int, min_interval: float,
        timeout: int, flush_every: int, verbose: bool) -> None:
    news = pd.read_csv(news_cache_path, dtype=str).fillna("")
    targets = news[
        (news["source"] == "gdelt") & (news["url"].str.strip() != "")
    ][["url", "transaction_id", "window"]].drop_duplicates(subset=["url"])

    existing = load_cache(output_path)
    done_urls = set(existing["url"]) if not existing.empty else set()
    todo = targets[~targets["url"].isin(done_urls)]
    if limit:
        todo = todo.head(limit)

    print(f"{len(targets):,} unique GDELT URLs total, {len(done_urls):,} already attempted, "
          f"{len(todo):,} to fetch this run")

    rows: list[dict] = list(existing.to_dict("records"))
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    last_call = 0.0
    n_ok = 0
    for i, (_, row) in enumerate(todo.iterrows(), start=1):
        elapsed = time.monotonic() - last_call
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        last_call = time.monotonic()

        url = row["url"]
        rec = {"url": url, "transaction_id": row["transaction_id"], "window": row["window"],
               "fetched": "0", "char_count": "0", "text": "", "error": ""}
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            ctype = resp.headers.get("Content-Type", "")
            if resp.status_code == 200 and "html" in ctype:
                text = extract_text(resp.content)
                if len(text) > 200:
                    rec.update(fetched="1", char_count=str(len(text)), text=text)
                    n_ok += 1
                else:
                    rec["error"] = "too_short"
            else:
                rec["error"] = f"status_{resp.status_code}_or_non_html"
        except Exception as exc:  # noqa: BLE001 -- best-effort scraping, log and move on
            rec["error"] = type(exc).__name__

        rows.append(rec)
        if verbose or i % 50 == 0:
            print(f"  [{i}/{len(todo)}] ok={n_ok} last={'OK' if rec['fetched']=='1' else rec['error']:<28s} {url[:70]}")

        if i % flush_every == 0:
            pd.DataFrame(rows, columns=CACHE_COLUMNS).to_csv(output_path, index=False)

    pd.DataFrame(rows, columns=CACHE_COLUMNS).to_csv(output_path, index=False)
    print(f"Done. {n_ok:,}/{len(todo):,} fetched this run "
          f"({n_ok/len(todo):.1%} yield)." if len(todo) else "Nothing to do.")
    print(f"Total cache: {len(rows):,} rows -> {output_path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Best-effort full-text enrichment for cached GDELT URLs.")
    p.add_argument("--news-cache", type=Path, default=DEFAULT_NEWS_CACHE)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--limit", type=int, default=0, help="Max new URLs to fetch this run (0 = all remaining).")
    p.add_argument("--min-interval", type=float, default=0.4, help="Minimum seconds between requests.")
    p.add_argument("--timeout", type=int, default=8)
    p.add_argument("--flush-every", type=int, default=50)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.news_cache, args.output, args.limit, args.min_interval, args.timeout,
        args.flush_every, args.verbose)
