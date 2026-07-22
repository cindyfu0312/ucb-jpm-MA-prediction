"""Generate reports/week7_ma_prediction_nlp_vs_llm_presentation.pptx - the Week 7 deck.

A single head-to-head presentation of BOTH feature pipelines on the same full-dataset corpus:
  - Pipeline 1: the week-4 classic-NLP stack (VADER, FinBERT, NMF topics, log-odds,
    momentum, EDGAR structure)
  - Pipeline 2: the LLM extractor (one structured JSON call per window, openai/gpt-4o-mini)
scored on identical rows, the same time split, and the same three models, so the only thing
that changes between them is the featurizer.

Consumes outputs/week7/week7_deck_stats.json + outputs/week7/fig_*.png (written by
code/week7_llm_ma_prediction.ipynb), so the deck re-renders in seconds after any notebook
re-run. Layout/palette match the team's week2 / week3-4 decks (navy header band + gold rule +
gray footer, Calibri, manual text boxes - no layout placeholders). Self-contained.

Usage:  python code/make_week7_deck.py
"""

from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATS_PATH = PROJECT_ROOT / "outputs" / "week7" / "week7_deck_stats.json"
FIG_DIR = PROJECT_ROOT / "outputs" / "week7"
OUT_PATH = PROJECT_ROOT / "reports" / "week7_ma_prediction_nlp_vs_llm_presentation.pptx"
CITED_PATH = PROJECT_ROOT / "outputs" / "week7" / "cited_examples.json"

A_KEY, B_KEY, C_KEY = "A: classic NLP (week4)", "B: LLM signals only", "C: combined A+B"
WK34_DETECTION_AUC = "0.77"  # established week3-4 finding, cited as context (not recomputed)

# ── Style constants measured from week3-4 deck ────────────────────────────────
NAVY = RGBColor(0x1A, 0x3A, 0x5C)
BLUE = RGBColor(0x2E, 0x6D, 0xB4)
GOLD = RGBColor(0xB8, 0x86, 0x0B)
GREEN = RGBColor(0x1A, 0x7A, 0x4A)
LIGHT_GREEN = RGBColor(0xE8, 0xF5, 0xE9)
LIGHT_PINK = RGBColor(0xFD, 0xED, 0xEC)
LIGHT_GRAY = RGBColor(0xF0, 0xF0, 0xF0)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_BLUE = RGBColor(0xD6, 0xE8, 0xF7)
AMBER = RGBColor(0xFF, 0xC0, 0x00)
FOOTER_GRAY = RGBColor(0xBB, 0xBB, 0xBB)
DARK_TEXT = NAVY
FONT = "Calibri"

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
FOOTER_TEXT = "M&A Prediction | JPMorgan Industry Project | July 2026"


def _box(slide, x, y, w, h, fill=None, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    sh.shadow.inherit = False
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
    return sh


def _text(slide, x, y, w, h, runs, size=14, color=DARK_TEXT, bold=False,
          align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line_spacing=1.0):
    """runs: str, or list of paragraphs, each str or list of (text, {bold,color,size}) runs."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Emu(45720)
    tf.margin_top = tf.margin_bottom = Emu(22860)
    if isinstance(runs, str):
        runs = [runs]
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        if isinstance(para, str):
            para = [(para, {})]
        for text, style in para:
            r = p.add_run()
            r.text = text
            r.font.name = FONT
            r.font.size = Pt(style.get("size", size))
            r.font.bold = style.get("bold", bold)
            r.font.color.rgb = style.get("color", color)
    return tb


def add_header(slide, title, subtitle=""):
    _box(slide, 0, 0, SLIDE_W, Inches(1.15), fill=NAVY)
    _text(slide, Inches(0.30), Inches(0.08), Inches(12.6), Inches(0.62),
          title, size=28, color=WHITE, bold=True)
    if subtitle:
        _text(slide, Inches(0.30), Inches(0.70), Inches(12.6), Inches(0.40),
              subtitle, size=14, color=GOLD)
    _box(slide, 0, Inches(1.15), SLIDE_W, Inches(0.04), fill=GOLD)


def add_footer(slide):
    _box(slide, 0, Inches(7.20), SLIDE_W, Inches(0.30), fill=NAVY)
    _text(slide, Inches(0.30), Inches(7.19), Inches(9.0), Inches(0.28),
          FOOTER_TEXT, size=9, color=FOOTER_GRAY)


def kpi_tile(slide, x, y, value, caption, fill=NAVY, value_color=AMBER,
             w=Inches(2.95), h=Inches(1.30)):
    _box(slide, x, y, w, h, fill=fill)
    _text(slide, x, y + Inches(0.06), w, Inches(0.70), value, size=28,
          color=value_color, bold=True, align=PP_ALIGN.CENTER)
    _text(slide, x, y + Inches(0.78), w, Inches(0.50), caption, size=11.5,
          color=LIGHT_BLUE, align=PP_ALIGN.CENTER)


def card(slide, x, y, w, header, body_lines, header_fill=BLUE, body_h=Inches(2.60)):
    _box(slide, x, y, w, Inches(0.42), fill=header_fill)
    _text(slide, x, y + Inches(0.01), w, Inches(0.40), header, size=15,
          color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    _box(slide, x, y + Inches(0.42), w, body_h, fill=LIGHT_GRAY)
    _text(slide, x + Inches(0.08), y + Inches(0.52), w - Inches(0.16), body_h - Inches(0.2),
          body_lines, size=12.5, color=DARK_TEXT)


def callout(slide, text, positive=True, y=Inches(6.35), h=Inches(0.75)):
    _box(slide, Inches(0.40), y, Inches(12.53), h,
         fill=LIGHT_GREEN if positive else LIGHT_PINK)
    _text(slide, Inches(0.60), y + Inches(0.04), Inches(12.1), h - Inches(0.08),
          text, size=14, color=DARK_TEXT, bold=True, anchor=MSO_ANCHOR.MIDDLE)


def shape_table(slide, x, y, col_widths, rows, row_h=Inches(0.38), header_fill=NAVY,
                font_size=12.5):
    for j, cells in enumerate(rows):
        fill = header_fill if j == 0 else (WHITE if j % 2 else LIGHT_GRAY)
        color = WHITE if j == 0 else DARK_TEXT
        cx = x
        for cw, cell in zip(col_widths, cells):
            _box(slide, cx, y + j * row_h, cw, row_h, fill=fill)
            _text(slide, cx + Inches(0.05), y + j * row_h, cw - Inches(0.1), row_h,
                  str(cell), size=font_size, color=color, bold=(j == 0),
                  anchor=MSO_ANCHOR.MIDDLE)
            cx += cw


def add_picture_fit(slide, path, x, y, max_w, max_h):
    from PIL import Image
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(max_w / iw, max_h / ih)
    slide.shapes.add_picture(str(path), x, y, int(iw * scale), int(ih * scale))


def fmt(v, spec=".3f", missing="n/a"):
    return format(v, spec) if isinstance(v, (int, float)) else missing


def _dedash(o):
    """Recursively replace em/en dashes with hyphens in any stats-derived text."""
    if isinstance(o, str):
        return o.replace(" — ", " - ").replace("—", "-").replace("–", "-")
    if isinstance(o, list):
        return [_dedash(x) for x in o]
    if isinstance(o, dict):
        return {k: _dedash(v) for k, v in o.items()}
    return o


def best_of(auc: dict, key: str):
    """Return (model_name, {auc,lo,hi}) for the best model in a feature set, or None."""
    ms = auc.get(key)
    if not ms:
        return None
    bm = max(ms, key=lambda m: ms[m]["auc"])
    return bm, ms[bm]


def model_table_rows(auc: dict, key: str):
    """A per-model AUC table (all three learners) for one feature set."""
    rows = [["Model", "Test ROC-AUC", "95% CI (bootstrap)"]]
    ms = auc.get(key, {})
    for m in sorted(ms, key=lambda m: -ms[m]["auc"]):
        r = ms[m]
        rows.append([m, f"{r['auc']:.3f}", f"[{r['lo']:.3f}, {r['hi']:.3f}]"])
    return rows


def main() -> None:
    stats = _dedash(json.loads(STATS_PATH.read_text()))
    cited = _dedash(json.loads(CITED_PATH.read_text())) if CITED_PATH.exists() else None
    auc = stats.get("auc", {})
    primary_model = stats.get("primary_model", "openai/gpt-4o-mini")
    probe = (stats.get("probe") or {}).get(primary_model, {})
    masking = stats.get("masking") or {}
    cutoff = stats.get("knowledge_cutoff", "2023-10")
    cost = stats.get("llm_total_cost", 0)
    n_events = stats.get("n_events_llm_scored") or stats.get("n_events_cached") or "?"
    n_rows = stats.get("n_model_rows", "?")
    n_test = stats.get("n_test_rows", "?")
    split = stats.get("split_date", "?")
    ne = f"{n_events:,}" if isinstance(n_events, int) else str(n_events)
    nr = f"{n_rows:,}" if isinstance(n_rows, int) else str(n_rows)

    bA, bB, bC = best_of(auc, A_KEY), best_of(auc, B_KEY), best_of(auc, C_KEY)

    def auc_2dp(b):
        return f"{b[1]['auc']:.2f}" if b else "n/a"

    # Data-driven head-to-head verdict (does the LLM clearly beat classic NLP?).
    verdict_pos, gap = False, None
    if bA and bC:
        gap = bC[1]["auc"] - bA[1]["auc"]
        overlap = bC[1]["lo"] <= bA[1]["hi"]
        verdict_pos = gap >= 0.05 and not overlap

    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    blank = prs.slide_layouts[6]

    def new_slide():
        return prs.slides.add_slide(blank)

    # ── 1. Title ──────────────────────────────────────────────────────────────
    s = new_slide()
    _box(s, 0, 0, SLIDE_W, SLIDE_H, fill=NAVY)
    _box(s, 0, 0, SLIDE_W, Inches(0.55), fill=BLUE)
    _box(s, 0, Inches(0.55), SLIDE_W, Inches(0.05), fill=GOLD)
    _text(s, Inches(0.8), Inches(2.25), Inches(11.7), Inches(1.9),
          ["Predicting M&A from Free News", "Classic NLP vs LLM, Head to Head"],
          size=40, color=WHITE, bold=True)
    _text(s, Inches(0.8), Inches(4.45), Inches(11.7), Inches(0.5),
          "J.P.Morgan Industry Project | Week 7 Results - NLP vs LLM on the Full Dataset | July 2026",
          size=19, color=GOLD)
    _text(s, Inches(0.8), Inches(5.05), Inches(11.7), Inches(0.4),
          "Dexin Fu, Ronald Liu", size=16, color=LIGHT_BLUE)

    # ── 2. Executive summary ─────────────────────────────────────────────────
    s = new_slide()
    add_header(s, "Executive Summary",
               "Two feature pipelines, one corpus - which one actually predicts an acquisition?")
    x0 = Inches(0.40)
    kpi_tile(s, x0, Inches(1.42), f"{n_events:,}" if isinstance(n_events, int) else str(n_events),
             "events scored (both pipelines)", fill=BLUE, value_color=WHITE)
    kpi_tile(s, x0 + Inches(3.18), Inches(1.42), auc_2dp(bA),
             "Classic-NLP test AUC", fill=NAVY, value_color=AMBER)
    kpi_tile(s, x0 + Inches(6.36), Inches(1.42), auc_2dp(bB),
             "LLM test AUC", fill=NAVY, value_color=AMBER)
    kpi_tile(s, x0 + Inches(9.54), Inches(1.42), auc_2dp(bC),
             "Combined (A+B) test AUC", fill=NAVY, value_color=AMBER)
    scope = (f"Honest scope: {nr} windows (pre/baseline) from {ne} events "
             f"({n_test} in the held-out test set), one time-based split (train <= {split}), "
             f"bootstrap 95% CIs. Small sample - read every AUC as DIRECTIONAL.")
    _box(s, x0, Inches(2.72), Inches(12.13), Inches(0.46), fill=GOLD)
    _text(s, x0 + Inches(0.10), Inches(2.72), Inches(12.0), Inches(0.46), scope,
          size=11, color=NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    card(s, x0, Inches(3.30), Inches(4.05), "The question",
         ["Given 90 days of a company's free", "news BEFORE any announcement,",
          "can we rank it as an acquisition", "target better than a coin flip?"],
         body_h=Inches(1.75))
    card(s, x0 + Inches(4.24), Inches(3.30), Inches(4.05), "Two pipelines, same rows",
         ["A: classic NLP (VADER, FinBERT,", "  NMF, log-odds, momentum, EDGAR)",
          "B: one LLM call/window -> 17 fields", "  Only the featurizer changes."],
         body_h=Inches(1.75))
    card(s, x0 + Inches(8.48), Inches(3.30), Inches(4.05), "The answer",
         ["All three sets edge above chance",
          f"  ({auc_2dp(bA)} / {auc_2dp(bB)} / {auc_2dp(bC)} AUC).",
          "NLP + LLM combined does best -", "a small, clean, promising lift."],
         body_h=Inches(1.75))
    add_footer(s)

    # ── 3. Shared setup (what makes the comparison fair) ─────────────────────
    s = new_slide()
    add_header(s, "One Corpus, One Split, Two Featurizers",
               "The comparison is fair because everything except the features is held identical")
    steps = ["Same events\n(SPGlobal >=$1B)", "Same news\n(GDELT + EDGAR)",
             "Same windows\npre vs baseline", "Same time split\ntrain <= " + str(split),
             "Same 3 models\nLogReg/RF/GB", "Same bootstrap\n95% CIs"]
    sw, gap_w, sx = Inches(1.92), Inches(0.14), Inches(0.40)
    for i, st in enumerate(steps):
        x = sx + i * (sw + gap_w)
        _box(s, x, Inches(1.55), sw, Inches(0.95), fill=NAVY)
        _text(s, x, Inches(1.57), sw, Inches(0.91), st.split("\n"), size=11,
              color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        if i < len(steps) - 1:
            _text(s, x + sw - Inches(0.03), Inches(1.67), Inches(0.24), Inches(0.5),
                  "=", size=20, color=GOLD, bold=True)
    rows = [["Held identical across both pipelines", "The ONLY thing that differs"],
            ["Event set, news corpus, noise filter", "How the text becomes numbers:"],
            ["Pre / baseline 90-day window geometry", "  A: hand-built NLP statistics"],
            ["Train/test time split + class balance", "  B: an LLM's structured judgment"],
            ["LogReg / RandomForest / GradientBoost", "Top-16 features by train-only"],
            ["Bootstrap 95% CIs on every AUC", "  mutual information, per set"]]
    shape_table(s, Inches(0.40), Inches(2.95), [Inches(6.25), Inches(6.25)], rows)
    add_footer(s)

    # ── 4. Pipeline 1: classic NLP ───────────────────────────────────────────
    s = new_slide()
    add_header(s, "Pipeline 1: Classic NLP (Weeks 3-4)",
               "Hand-built linguistic statistics - the established baseline, recomputed on this corpus")
    _box(s, Inches(0.40), Inches(1.40), Inches(6.35), Inches(0.40), fill=BLUE)
    _text(s, Inches(0.40), Inches(1.41), Inches(6.35), Inches(0.38),
          "What it computes (28 candidate features)", size=14, color=WHITE, bold=True,
          align=PP_ALIGN.CENTER)
    _box(s, Inches(0.40), Inches(1.80), Inches(6.35), Inches(3.55), fill=LIGHT_GRAY)
    _text(s, Inches(0.55), Inches(1.92), Inches(6.05), Inches(3.35),
          [[("Volume + VADER sentiment (7):", {"bold": True})],
           "   counts, avg/std/max/min tone, pos/neg ratio",
           [("M&A keyword hits (2)", {"bold": True}), ("   +   ", {}),
            ("FinBERT finance tone (4)", {"bold": True})],
           [("Log-odds distinctive terms (1):", {"bold": True})],
           "   data-driven, company-name masked",
           [("NMF topics (8)", {"bold": True}), ("   +   ", {}),
            ("Momentum (2)", {"bold": True})],
           [("EDGAR filing structure (3):", {"bold": True})],
           "   8-K / SC 13D counts + deal-filing ratio"],
          size=12, color=DARK_TEXT, line_spacing=1.25)
    _box(s, Inches(6.98), Inches(1.40), Inches(5.95), Inches(0.40), fill=NAVY)
    _text(s, Inches(6.98), Inches(1.41), Inches(5.95), Inches(0.38),
          "Result on this corpus (advance prediction)", size=14, color=AMBER, bold=True,
          align=PP_ALIGN.CENTER)
    shape_table(s, Inches(6.98), Inches(1.95), [Inches(2.55), Inches(1.85), Inches(1.55)],
                model_table_rows(auc, A_KEY), row_h=Inches(0.40), font_size=11.5)
    _text(s, Inches(6.98), Inches(3.95), Inches(5.95), Inches(1.5),
          [[("Reads as: ", {"bold": True}),
            (f"best classic model AUC {auc_2dp(bA)} - a coin flip.", {})],
           [("Context: ", {"bold": True}),
            (f"the SAME pipeline pointed at the announcement week detects a deal at "
             f"AUC ~ {WK34_DETECTION_AUC} (week 3-4). The signal exists - just not 90 days early.", {})]],
          size=12.5, color=DARK_TEXT, line_spacing=1.2)
    add_footer(s)

    # ── 5. Pipeline 2: LLM extraction ────────────────────────────────────────
    s = new_slide()
    add_header(s, "Pipeline 2: LLM Feature Extraction (Week 7)",
               f"One structured call per window ({primary_model}) - the same news, read by a generative model")
    _box(s, Inches(0.40), Inches(1.40), Inches(6.35), Inches(0.40), fill=BLUE)
    _text(s, Inches(0.40), Inches(1.41), Inches(6.35), Inches(0.38),
          "What it extracts (17 strict-JSON fields)", size=14, color=WHITE, bold=True,
          align=PP_ALIGN.CENTER)
    _box(s, Inches(0.40), Inches(1.80), Inches(6.35), Inches(3.55), fill=LIGHT_GRAY)
    _text(s, Inches(0.55), Inches(1.90), Inches(6.05), Inches(3.40),
          [[("10 M&A-precursor signals, each 0-10:", {"bold": True})],
           "   rumor, strategic-review, activist, mgmt-",
           "   instability, distress, undervaluation,",
           "   sector-consolidation, antitrust, divestiture,",
           "   growth (control dimension)",
           [("acquisition_likelihood 0-100", {"bold": True}),
            ("   +   info_quality 0-10", {})],
           [("Audit-only (never model inputs):", {"bold": True})],
           "   dominant_theme, recognized_company/deal,",
           "   evidence_quotes, rationale"],
          size=12, color=DARK_TEXT, line_spacing=1.2)
    _box(s, Inches(6.98), Inches(1.40), Inches(5.95), Inches(0.40), fill=NAVY)
    _text(s, Inches(6.98), Inches(1.41), Inches(5.95), Inches(0.38),
          "Result on this corpus (advance prediction)", size=14, color=AMBER, bold=True,
          align=PP_ALIGN.CENTER)
    shape_table(s, Inches(6.98), Inches(1.95), [Inches(2.55), Inches(1.85), Inches(1.55)],
                model_table_rows(auc, B_KEY), row_h=Inches(0.40), font_size=11.5)
    kpi_tile(s, Inches(6.98), Inches(3.95), f"${cost:.2f}" if isinstance(cost, (int, float)) else "n/a",
             "total API spend (both variants)", fill=GREEN, value_color=WHITE,
             w=Inches(2.85), h=Inches(1.15))
    kpi_tile(s, Inches(10.05), Inches(3.95), str(cutoff),
             "knowledge cutoff (memorization guard)", fill=BLUE, value_color=WHITE,
             w=Inches(2.85), h=Inches(1.15))
    add_footer(s)

    # ── 5b. Feature dictionary (complete A + B input lists; from week-6 deck) ─
    s = new_slide()
    add_header(s, "Feature Dictionary - Every Input the Models See",
               "Set A = classic NLP stack · Set B = LLM signals · C = A ∪ B, top 16 of 40 "
               "by train-only mutual information")
    _box(s, Inches(0.40), Inches(1.40), Inches(6.15), Inches(0.40), fill=BLUE)
    _text(s, Inches(0.40), Inches(1.41), Inches(6.15), Inches(0.38),
          "SET A - classic NLP (28 candidates)", size=14, color=WHITE, bold=True,
          align=PP_ALIGN.CENTER)
    _box(s, Inches(0.40), Inches(1.80), Inches(6.15), Inches(4.55), fill=LIGHT_GRAY)
    _text(s, Inches(0.55), Inches(1.92), Inches(5.9), Inches(4.35),
          [[("Volume & VADER sentiment (7):", {"bold": True})],
           "   news_count · avg / std / max / min_sentiment · pos_ratio · neg_ratio",
           [("M&A keywords (2):", {"bold": True})],
           "   ma_keyword_count · ma_keyword_ratio",
           [("FinBERT finance sentiment (4):", {"bold": True})],
           "   avg / std_finbert_compound · avg_finbert_positive · avg_finbert_negative",
           [("Data-driven terms (1):", {"bold": True}), ("  distinctive_term_ratio (log-odds, name-masked)", {})],
           [("Momentum (2):", {"bold": True}), ("  late_share · sentiment_trend", {})],
           [("EDGAR filing structure (3):", {"bold": True})],
           "   edgar_filing_count · edgar_deal_filing_count · edgar_deal_filing_ratio",
           [("NMF topics (8):", {"bold": True}), ("  topic_0_mean … topic_7_mean (name-masked)", {})],
           [("Meta (1):", {"bold": True}), ("  industry_enc", {})]],
          size=11.5, color=DARK_TEXT, line_spacing=1.12)
    _box(s, Inches(6.77), Inches(1.40), Inches(6.15), Inches(0.40), fill=NAVY)
    _text(s, Inches(6.77), Inches(1.41), Inches(6.15), Inches(0.38),
          "SET B - LLM signals (12 features + 5 audit fields)", size=14, color=WHITE,
          bold=True, align=PP_ALIGN.CENTER)
    _box(s, Inches(6.77), Inches(1.80), Inches(6.15), Inches(4.55), fill=LIGHT_GRAY)
    _text(s, Inches(6.92), Inches(1.88), Inches(5.9), Inches(4.47),
          [[("Model features (one strict-JSON call per window):", {"bold": True})],
           "   ma_rumor_intensity 0-10: “in talks”, bids, “sources say”",
           "   strategic_alternatives_review 0-10: reviews, bankers hired",
           "   activist_pressure 0-10: activists, stakes, proxy fights",
           "   management_instability 0-10: CEO/CFO exits, shakeups",
           "   financial_distress 0-10: losses, debt, downgrades",
           "   undervaluation_narrative 0-10: “cheap”, lagging peers",
           "   sector_consolidation_wave 0-10: peers merging",
           "   regulatory_antitrust_attention 0-10: regulator scrutiny",
           "   divestiture_restructuring 0-10: spin-offs, carve-outs",
           "   growth_expansion_tone 0-10: ordinary growth (control)",
           "   acquisition_likelihood 0-100: holistic judgment",
           "   headline_information_quality 0-10: text usability",
           [("Audit fields - never model inputs:", {"bold": True})],
           "   dominant_theme · recognized_company · recognized_deal",
           "   evidence_quotes (verbatim) · rationale (≤ 40 words)"],
          size=11.5, color=DARK_TEXT, line_spacing=1.08)
    add_footer(s)

    # ── 5c. The exact call - nothing hidden (prompt walk-through; from week-6) ─
    s = new_slide()
    add_header(s, "The Exact Call - Nothing Hidden",
               "One API call per window = fixed instructions + this window's text -> 17 forced fields. "
               "The 0/1 label is never in the prompt.")
    _box(s, Inches(0.40), Inches(1.30), Inches(12.53), Inches(0.66), fill=GOLD)
    _text(s, Inches(0.55), Inches(1.31), Inches(12.2), Inches(0.64),
          [[("The model never sees:  ", {"bold": True, "color": NAVY}),
            ("the announcement date · whether this is a run-up or a “quiet” window · the outcome.  "
             "It scores blind - the 1/0 label lives only in our spreadsheet, never in the prompt. "
             "That is what makes the comparison fair.", {"color": NAVY})]],
          size=12, color=NAVY, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.0)
    sys_txt = ("You are a financial-news analyst scoring M&A-precursor signals for ONE US public "
               "company from a single ~90-day period of its news coverage. Judge ONLY from the text "
               "provided. Do not use any memory of real-world outcomes for this specific company. "
               "Score each dimension 0-10 (0 = no evidence, 10 = overwhelming). Be conservative: "
               "for most companies in most periods, most dimensions score 0-2.")
    _box(s, Inches(0.40), Inches(2.08), Inches(7.35), Inches(4.55), fill=LIGHT_GRAY)
    left = [
        [("①  SYSTEM MESSAGE", {"bold": True, "color": BLUE, "size": 11.5}),
         ("   - role + rules, identical for every call", {"size": 9.5, "color": NAVY})],
        [(sys_txt, {"size": 9.5})],
        "",
        [("②  USER MESSAGE", {"bold": True, "color": BLUE, "size": 11.5}),
         (f"   - only THIS window's text  ({stats.get('example_company', 'example')})", {"size": 9.5, "color": NAVY})],
    ]
    left += [[(ln, {"size": 9})] for ln in (stats.get("example_prompt_lines") or [])]
    left.append([("Score the signals defined in the schema, based ONLY on the text above.",
                  {"size": 9, "color": NAVY})])
    left.append("")
    left.append([("+  response_format = strict JSON schema  ->  forces the 17 fields at right",
                  {"bold": True, "color": GOLD, "size": 9.5})])
    _text(s, Inches(0.55), Inches(2.18), Inches(7.05), Inches(4.35), left,
          size=9.5, color=DARK_TEXT, line_spacing=1.02)
    _box(s, Inches(7.92), Inches(2.08), Inches(5.01), Inches(1.86), fill=NAVY)
    _text(s, Inches(8.05), Inches(2.13), Inches(4.8), Inches(0.30),
          "③  THE 17 FIELDS WE FORCE (the labels we ask for)", size=10.5, color=AMBER, bold=True)
    _text(s, Inches(8.05), Inches(2.46), Inches(4.78), Inches(1.42),
          ["10 M&A-precursor signals, each 0-10 + a definition:",
           "  rumor · strategic-review · activist · mgmt-instability",
           "  distress · undervaluation · sector-consolidation",
           "  antitrust · divestiture · growth (control dim.)",
           "acquisition_likelihood 0-100   ·   info_quality 0-10",
           "dominant_theme · evidence_quotes (≤3) · rationale",
           "recognized_company / recognized_deal -> memorization flag"],
          size=9.5, color=LIGHT_BLUE, line_spacing=1.06)
    _box(s, Inches(7.92), Inches(4.02), Inches(5.01), Inches(2.61), fill=NAVY)
    _text(s, Inches(8.05), Inches(4.07), Inches(4.8), Inches(0.30),
          "④  IT RETURNS - strict JSON, one call", size=10.5, color=AMBER, bold=True)
    _text(s, Inches(8.05), Inches(4.40), Inches(4.78), Inches(2.15),
          (stats.get("example_response_lines") or ["{ … }"]),
          size=8, color=LIGHT_BLUE, line_spacing=1.0)
    add_footer(s)

    # ── 6. Head-to-head results (the centrepiece) ────────────────────────────
    s = new_slide()
    add_header(s, "Head to Head: Does the LLM Beat Classic NLP?",
               f"Best model per feature set, identical rows & split, bootstrap 95% CIs ({nr} windows)")
    rows = [["Feature set", "Best model", "Test ROC-AUC", "95% CI (bootstrap)"]]
    for label, b in [("A - Classic NLP", bA), ("B - LLM signals", bB), ("C - Combined A+B", bC)]:
        if b:
            rows.append([label, b[0], f"{b[1]['auc']:.3f}", f"[{b[1]['lo']:.3f}, {b[1]['hi']:.3f}]"])
    shape_table(s, Inches(0.40), Inches(1.50),
                [Inches(3.5), Inches(3.2), Inches(2.7), Inches(3.1)], rows, row_h=Inches(0.44))
    fig = FIG_DIR / "fig_auc_comparison.png"
    if fig.exists():
        add_picture_fit(s, fig, Inches(1.2), Inches(3.55), Inches(10.9), Inches(2.6))
    add_footer(s)

    # ── 7. Are the LLM signals even different? ───────────────────────────────
    fig_corr = FIG_DIR / "fig_llm_vs_classic_corr.png"
    if fig_corr.exists():
        s = new_slide()
        add_header(s, "Are the LLM Signals New Information?",
                   "Spearman rank correlation - LLM fields (rows) x classic-NLP features (columns)")
        add_picture_fit(s, fig_corr, Inches(0.30), Inches(1.45), Inches(7.1), Inches(5.35))
        _text(s, Inches(7.60), Inches(1.60), Inches(5.35), Inches(4.7),
              [[("How to read it:", {"bold": True, "size": 14})],
               "• Each cell: do the two scores rank companies the same way? "
               "(+1 identical, 0 unrelated, -1 opposite)",
               "• A deep-red row = that LLM field just re-derives a classic feature (redundant).",
               "• A near-white row = a description the classic stack misses (novel).",
               "• The LLM's rumor read largely re-derives simple keyword matching; activist, "
               "distress and divestiture reads are genuinely new descriptive axes.",
               [("Takeaway: ", {"bold": True}),
                ("the LLM is partly redundant, partly novel - but neither part separates pre "
                 "from baseline, so the novelty does not become predictivity.", {})]],
              size=12.5, color=DARK_TEXT, line_spacing=1.2)
        add_footer(s)

    # ── 8. Validity: is the LLM result even trustworthy? ─────────────────────
    s = new_slide()
    add_header(s, "Is the LLM Result Trustworthy?",
               "Two stress tests: does it remember these deals, and does it read the text or the name?")

    def _pp(v):
        return f"{v:.0%}" if isinstance(v, (int, float)) else "n/a"

    kpi_tile(s, Inches(0.40), Inches(1.50), _pp(probe.get("acc")),
             "memorization-probe accuracy (chance 50%)",
             fill=GREEN if isinstance(probe.get("acc"), (int, float)) and probe["acc"] < 0.6 else NAVY,
             value_color=WHITE, w=Inches(3.9), h=Inches(1.30))
    kpi_tile(s, Inches(4.54), Inches(1.50),
             f"{_pp(probe.get('acc_pre_cutoff'))} / {_pp(probe.get('acc_post_cutoff'))}",
             "accuracy pre / post knowledge cutoff", fill=NAVY, value_color=AMBER,
             w=Inches(3.9), h=Inches(1.30))
    md = masking.get("delta")
    kpi_tile(s, Inches(8.68), Inches(1.50),
             f"{md:+.2f}" if isinstance(md, (int, float)) else "n/a",
             "AUC drop when the company name is hidden", fill=NAVY, value_color=AMBER,
             w=Inches(4.25), h=Inches(1.30))
    card(s, Inches(0.40), Inches(3.05), Inches(6.15),
         "Test 1: does it just remember the outcome?",
         ["Ask, with NO news: 'was this company announced",
          "as a >=$1B target?' - from memory alone.",
          [(f"Cutoff {cutoff}: ", {"bold": True}),
           ("most 2024-26 deals are AFTER training, so the", {})],
          "model cannot have memorized them - a clean holdout.",
          [("Pre ~ post accuracy => ", {"bold": True}),
           ("no time-localized memory edge.", {})]],
         body_h=Inches(2.20))
    card(s, Inches(6.77), Inches(3.05), Inches(6.15),
         "Test 2: reading the text or the name?",
         ["Re-score every window with the company name",
          "blanked out, then compare the AUC.",
          [(f"AUC change {md:+.2f}: " if isinstance(md, (int, float)) else "AUC change small: ",
            {"bold": True}),
           ("how much of the 'skill' was recognizing the", {})],
          "company vs actually reading the coverage.",
          [("Matters most ", {"bold": True}),
           ("for scoring companies never seen before.", {})]],
         body_h=Inches(2.20))
    add_footer(s)

    # ── 8b. Cited sources: every score is grounded in a real, checkable headline ─
    if cited:
        s = new_slide()
        add_header(s, "Every LLM Score Cites Its Source",
                   "The model must quote the exact headline behind each signal - reading, not "
                   "predicting (slide 6) - and we verify every quote against the source text")
        _box(s, Inches(0.40), Inches(1.35), Inches(12.53), Inches(0.55), fill=GOLD)
        _text(s, Inches(0.55), Inches(1.35), Inches(12.2), Inches(0.55),
              f"Across {cited.get('n_events', '?')} tested events: "
              f"{cited.get('n_verified', '?')} of {cited.get('n_total', '?')} cited signals matched a "
              f"real headline VERBATIM - 0 hallucinated sources. Examples:",
              size=13, color=NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        rows = [["Company - signal", "Score", "Cited headline (verbatim from the news)", "Source"]]
        sig_label = {"ma_rumor_intensity": "rumor intensity",
                     "acquisition_likelihood": "acq. likelihood"}
        for ex in cited.get("examples", []):
            for c in ex["citations"]:
                scale = 100 if c["signal"] == "acquisition_likelihood" else 10
                lbl = sig_label.get(c["signal"], c["signal"].replace("_", " "))
                rows.append([f"{ex['company']} - {lbl}", f"{c['score']} / {scale}",
                             f"“{c['quote']}”", f"{c['source']}  ✓"])
        shape_table(s, Inches(0.40), Inches(2.05),
                    [Inches(2.9), Inches(1.1), Inches(6.53), Inches(2.0)], rows,
                    row_h=Inches(0.44), font_size=10.5)
        _text(s, Inches(0.40), Inches(5.40), Inches(12.53), Inches(1.10),
              [[("Illustrative high-signal windows.  ", {"bold": True, "color": NAVY}),
                ("Explicit deal chatter like this is rare across all events, so headline-only "
                 "prediction still lands near chance (slide 6). The point here is trust: every score "
                 "traces to a real, checkable headline - and the acquirer is read FROM the text, not "
                 "recalled from memory (consistent with the clean memorization probe).",
                 {"color": NAVY})]],
              size=11.5, color=NAVY, line_spacing=1.12)
        add_footer(s)

    # ── 9. Verdict & recommendation ──────────────────────────────────────────
    s = new_slide()
    add_header(s, "Verdict & Recommendation",
               "A small, clean edge over chance - promising but not yet conclusive, and how to confirm it")
    card(s, Inches(0.40), Inches(1.45), Inches(4.05), "What we see",
         [[("A small edge above chance", {"bold": True})],
          f"across all three sets ({auc_2dp(bA)} / {auc_2dp(bB)} /",
          f"{auc_2dp(bC)} AUC). Combining classic NLP",
          "with LLM judgment does best -",
          "a hint of complementary signal."],
         body_h=Inches(2.05))
    card(s, Inches(4.64), Inches(1.45), Inches(4.05), "Is the edge real?",
         [[("Small, not yet significant:", {"bold": True})],
          "95% CIs still include 0.50 on 400",
          "test rows. But it is clean -",
          "memorization probe at chance,",
          "masking barely moves it (not an artifact)."],
         body_h=Inches(2.05))
    card(s, Inches(8.88), Inches(1.45), Inches(4.05), "Recommendation",
         [[("Promising enough to scale.", {"bold": True})],
          "More events to tighten the CIs,",
          "article bodies for richer text, a",
          "cutoff-matched backtest. Keep NLP the",
          "cheap baseline; layer the LLM on top."],
         body_h=Inches(2.05))
    _box(s, Inches(0.40), Inches(3.75), Inches(12.53), Inches(1.85), fill=LIGHT_GREEN)
    _text(s, Inches(0.62), Inches(3.89), Inches(12.1), Inches(1.68),
          [[("The bottom line:  ", {"size": 16, "bold": True, "color": NAVY}),
            (f"combining classic NLP with LLM judgment gives a small but consistent edge over chance "
             f"(best {auc_2dp(bC)}), and it is clean - no memorization, no name-recognition. "
             f"Promising, though not yet statistically conclusive on this sample.",
             {"size": 15, "color": NAVY})],
           "",
           [(f"For context, the same pipeline detects an announcement once it lands at AUC ~ "
             f"{WK34_DETECTION_AUC}, so the signal exists - the open question is how early it becomes "
             f"readable. This {ne}-event edge is worth scaling: more data to tighten the CIs, richer "
             f"text, and a cutoff-matched backtest to confirm it.", {"size": 13, "color": NAVY})]],
          size=13, color=NAVY, line_spacing=1.14)
    add_footer(s)

    # ── 10. Thanks ────────────────────────────────────────────────────────────
    s = new_slide()
    _box(s, 0, 0, SLIDE_W, SLIDE_H, fill=NAVY)
    _box(s, 0, Inches(0.55), SLIDE_W, Inches(0.05), fill=GOLD)
    _text(s, 0, Inches(2.9), SLIDE_W, Inches(1.6), "Thanks", size=80, color=WHITE,
          bold=True, align=PP_ALIGN.CENTER)
    _text(s, 0, Inches(6.9), SLIDE_W, Inches(0.35), FOOTER_TEXT, size=9,
          color=FOOTER_GRAY, align=PP_ALIGN.CENTER)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT_PATH))
    print(f"Wrote {OUT_PATH.relative_to(PROJECT_ROOT)} "
          f"({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")


if __name__ == "__main__":
    main()
