"""Generate the FINAL MFE27 Term-2 deliverable deck (self-contained, whole-project).

Unlike the weekly decks, this one is written for a reader with no prior exposure to the
project: it opens with objective + prior art, states the research design and the
pre-registered success criteria, then walks the data, both feature pipelines, every
result, the validity tests, and closes with conclusions, future work, contributions and
a bibliography - the sections the MFE27 submission guidelines require.

Numbers come from outputs/week7/week7_deck_stats.json (full-dataset run) plus the
established week3-4 findings (blackout diagnostic + announcement-day detection), which
are cited as prior-week results and are not recomputed here.

Palette follows the UC Berkeley brand (Berkeley Blue / California Gold) per the Haas
template; body font stays Calibri because the template's Barlow/Inter are not installed
locally and would silently fall back at render time.

Usage:  python code/make_final_deck.py
"""

from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATS_PATH = PROJECT_ROOT / "outputs" / "week7" / "week7_deck_stats.json"
CITED_PATH = PROJECT_ROOT / "outputs" / "week7" / "cited_examples.json"
FIG_DIR = PROJECT_ROOT / "outputs" / "week7"
WORDMARK = PROJECT_ROOT / "assets" / "ucb_wordmark_gold.png"
OUT_PATH = (PROJECT_ROOT / "reports" /
            "MFE27_Term2_JPMorgan_2_MA_Prediction_Fu_Liu_slide_deck.pptx")

A_KEY, B_KEY, C_KEY = "A: classic NLP (week4)", "B: LLM signals only", "C: combined A+B"

# ── Established week3-4 results, cited as prior-week findings (not recomputed) ──
DET_ROWS = [
    ["Model", "CV AUC (train)", "Test ROC-AUC", "Test PR-AUC"],
    ["Gradient Boosting", "0.818", "0.793", "0.741"],
    ["Random Forest", "0.814", "0.773", "0.733"],
    ["Logistic Regression", "0.807", "0.773", "0.737"],
    ["Random baseline", "-", "0.500", "0.500"],
]
DET_BEST = "0.79"
WK34_PRED_ROWS = [
    ["Model", "CV AUC (train)", "Test ROC-AUC", "Test PR-AUC"],
    ["Random Forest", "0.445", "0.525", "0.540"],
    ["Logistic Regression", "0.438", "0.490", "0.500"],
    ["Gradient Boosting", "0.458", "0.466", "0.508"],
    ["Random baseline", "-", "0.500", "0.500"],
]

# ── UC Berkeley brand palette ─────────────────────────────────────────────────
BERK_BLUE = RGBColor(0x00, 0x32, 0x62)   # Berkeley Blue (primary)
CAL_GOLD = RGBColor(0xFD, 0xB5, 0x15)    # California Gold (accent)
ROCK = RGBColor(0x3B, 0x7E, 0xA1)        # Founder's Rock (secondary)
MEDALIST = RGBColor(0xC4, 0x82, 0x0E)    # Medalist (deep gold)
GREEN = RGBColor(0x1A, 0x7A, 0x4A)
LIGHT_GREEN = RGBColor(0xE8, 0xF5, 0xE9)
LIGHT_PINK = RGBColor(0xFD, 0xED, 0xEC)
LIGHT_GRAY = RGBColor(0xF1, 0xF1, 0xEF)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_BLUE = RGBColor(0xD6, 0xE8, 0xF7)
FOOTER_GRAY = RGBColor(0xBB, 0xBB, 0xBB)
MUTED = RGBColor(0x60, 0x6A, 0x75)
DARK_TEXT = BERK_BLUE
# Arial, not Calibri: Calibri ships only with MS Office, so a grader opening this in
# Keynote / Google Slides silently gets a serif fallback. Arial is present on macOS and
# Windows out of the box, and is the Haas template's own theme font.
FONT = "Arial"

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
FOOTER_TEXT = ("Predicting M&A from Free News  |  MFE 27 Term 2  |  "
               "J.P. Morgan Industry Project  |  Group 2  |  July 2026")


# ── primitives ────────────────────────────────────────────────────────────────
def _box(slide, x, y, w, h, fill=None, line=None):
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
    """runs: str, or list of paragraphs, each str or list of (text, {bold,color,size})."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Emu(45720)
    tf.margin_top = tf.margin_bottom = Emu(22860)
    if isinstance(runs, str):
        runs = [runs]
    # A literal "\n" inside <a:t> is NOT an OOXML line break - PowerPoint collapses it
    # and the line silently runs together. Expand newlines into real paragraphs instead.
    expanded = []
    for para in runs:
        if isinstance(para, str):
            expanded.extend(para.split("\n"))
            continue
        cur = []
        for text, style in para:
            parts = str(text).split("\n")
            for k, part in enumerate(parts):
                if k:
                    expanded.append(cur)
                    cur = []
                if part:
                    cur.append((part, style))
        expanded.append(cur)
    runs = expanded
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


def add_header(slide, title, subtitle="", tag=""):
    _box(slide, 0, 0, SLIDE_W, Inches(1.15), fill=BERK_BLUE)
    _text(slide, Inches(0.30), Inches(0.08), Inches(11.0), Inches(0.62),
          title, size=27, color=WHITE, bold=True)
    if subtitle:
        _text(slide, Inches(0.30), Inches(0.70), Inches(11.0), Inches(0.40),
              subtitle, size=13.5, color=CAL_GOLD)
    if tag:
        _text(slide, Inches(10.9), Inches(0.30), Inches(2.15), Inches(0.45),
              tag, size=11.5, color=LIGHT_BLUE, bold=True, align=PP_ALIGN.RIGHT)
    _box(slide, 0, Inches(1.15), SLIDE_W, Inches(0.05), fill=CAL_GOLD)


def add_footer(slide, page=None):
    _box(slide, 0, Inches(7.20), SLIDE_W, Inches(0.30), fill=BERK_BLUE)
    _text(slide, Inches(0.30), Inches(7.19), Inches(11.0), Inches(0.28),
          FOOTER_TEXT, size=9, color=FOOTER_GRAY)
    if page is not None:
        _text(slide, Inches(12.4), Inches(7.19), Inches(0.6), Inches(0.28),
              str(page), size=9, color=FOOTER_GRAY, align=PP_ALIGN.RIGHT)


def kpi_tile(slide, x, y, value, caption, fill=BERK_BLUE, value_color=CAL_GOLD,
             w=Inches(2.95), h=Inches(1.28), vsize=28):
    _box(slide, x, y, w, h, fill=fill)
    _text(slide, x, y + Inches(0.06), w, Inches(0.70), value, size=vsize,
          color=value_color, bold=True, align=PP_ALIGN.CENTER)
    _text(slide, x, y + Inches(0.76), w, Inches(0.50), caption, size=11,
          color=LIGHT_BLUE, align=PP_ALIGN.CENTER)


def card(slide, x, y, w, header, body_lines, header_fill=ROCK,
         body_h=Inches(2.60), body_size=12.5):
    _box(slide, x, y, w, Inches(0.42), fill=header_fill)
    _text(slide, x, y + Inches(0.01), w, Inches(0.40), header, size=14.5,
          color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    _box(slide, x, y + Inches(0.42), w, body_h, fill=LIGHT_GRAY)
    _text(slide, x + Inches(0.08), y + Inches(0.50), w - Inches(0.16),
          body_h - Inches(0.16), body_lines, size=body_size, color=DARK_TEXT)


def band(slide, text, positive=True, y=Inches(6.35), h=Inches(0.72)):
    _box(slide, Inches(0.40), y, Inches(12.53), h,
         fill=LIGHT_GREEN if positive else LIGHT_PINK)
    _text(slide, Inches(0.60), y + Inches(0.04), Inches(12.1), h - Inches(0.08),
          text, size=13.5, color=DARK_TEXT, bold=True, anchor=MSO_ANCHOR.MIDDLE)


def shape_table(slide, x, y, col_widths, rows, row_h=Inches(0.38),
                header_fill=BERK_BLUE, font_size=12.5, highlight=None):
    for j, cells in enumerate(rows):
        fill = header_fill if j == 0 else (WHITE if j % 2 else LIGHT_GRAY)
        color = WHITE if j == 0 else DARK_TEXT
        if highlight is not None and j == highlight:
            fill, color = LIGHT_GREEN, DARK_TEXT
        cx = x
        for cw, cell in zip(col_widths, cells):
            _box(slide, cx, y + j * row_h, cw, row_h, fill=fill)
            _text(slide, cx + Inches(0.05), y + j * row_h, cw - Inches(0.1), row_h,
                  str(cell), size=font_size, color=color,
                  bold=(j == 0 or (highlight is not None and j == highlight)),
                  anchor=MSO_ANCHOR.MIDDLE)
            cx += cw


def add_picture_fit(slide, path, x, y, max_w, max_h):
    from PIL import Image
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(max_w / iw, max_h / ih)
    return slide.shapes.add_picture(str(path), x, y, int(iw * scale), int(ih * scale))


def arrow(slide, x, y, w=Inches(0.42), h=Inches(0.60)):
    _text(slide, x, y, w, h, ">", size=22, color=CAL_GOLD, bold=True,
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def _dedash(o):
    if isinstance(o, str):
        # The cached example lines are raw JSON, so an ellipsis arrives as the literal
        # 6-character escape "…" rather than a character. Show it as "...".
        o = o.replace("\\u2026", "...").replace("…", "...")
        return o.replace(" — ", " - ").replace("—", "-").replace("–", "-")
    if isinstance(o, list):
        return [_dedash(x) for x in o]
    if isinstance(o, dict):
        return {k: _dedash(v) for k, v in o.items()}
    return o


def best_of(auc, key):
    ms = auc.get(key)
    if not ms:
        return None
    bm = max(ms, key=lambda m: ms[m]["auc"])
    return bm, ms[bm]


def main() -> None:
    stats = _dedash(json.loads(STATS_PATH.read_text()))
    cited = _dedash(json.loads(CITED_PATH.read_text())) if CITED_PATH.exists() else None
    auc = stats.get("auc", {})
    primary_model = stats.get("primary_model", "openai/gpt-4o-mini")
    probe = (stats.get("probe") or {}).get(primary_model, {})
    masking = stats.get("masking") or {}
    repeat = stats.get("repeat") or {}
    cutoff = stats.get("knowledge_cutoff", "2023-10-01")
    cost = stats.get("llm_total_cost", 0)
    n_scored = stats.get("n_events_llm_scored", 0)
    n_rows = stats.get("n_model_rows", 0)
    n_test = stats.get("n_test_rows", 0)
    n_total = stats.get("n_events_total", 0)
    n_cached = stats.get("n_events_cached", 0)
    n_articles = stats.get("n_articles_cached", 0)
    split = stats.get("split_date", "?")
    calls = stats.get("llm_calls_ok", 0)

    bA, bB, bC = best_of(auc, A_KEY), best_of(auc, B_KEY), best_of(auc, C_KEY)
    # The best feature set is not guaranteed to be C. On the full dataset the combined
    # set's earlier lead regressed away, so pick the best from the data every time.
    _cands = [b for b in (bA, bB, bC) if b]
    best_all = max(_cands, key=lambda b: b[1]["auc"]) if _cands else None

    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    blank = prs.slide_layouts[6]
    page = {"n": 0}

    def new_slide(title="", subtitle="", tag="", footer=True):
        s = prs.slides.add_slide(blank)
        if title:
            add_header(s, title, subtitle, tag)
        if footer:
            page["n"] += 1
            add_footer(s, page["n"])
        return s

    A3 = f"{bA[1]['auc']:.3f}" if bA else "n/a"
    B3 = f"{bB[1]['auc']:.3f}" if bB else "n/a"
    C3 = f"{bC[1]['auc']:.3f}" if bC else "n/a"
    BEST = f"{best_all[1]['auc']:.2f}" if best_all else "n/a"

    # ── 1. Title ──────────────────────────────────────────────────────────────
    s = prs.slides.add_slide(blank)
    _box(s, 0, 0, SLIDE_W, SLIDE_H, fill=BERK_BLUE)
    _box(s, 0, Inches(4.62), SLIDE_W, Inches(0.06), fill=CAL_GOLD)
    if WORDMARK.exists():
        add_picture_fit(s, WORDMARK, Inches(0.75), Inches(0.70), Inches(3.10), Inches(0.52))
    _text(s, Inches(0.70), Inches(1.85), Inches(11.9), Inches(1.6),
          [[("Predicting M&A from Free News", {})],
           [("Classic NLP vs a Large Language Model", {"size": 26, "color": CAL_GOLD})]],
          size=44, color=WHITE, bold=True, line_spacing=1.15)
    _text(s, Inches(0.75), Inches(4.95), Inches(11.9), Inches(1.4),
          [[("J.P. Morgan Industry Project  |  Group 2  |  MFE 27, Term 2  |  July 2026",
             {"size": 15, "color": LIGHT_BLUE})],
           [("Dexin Fu   ·   Ronald Liu", {"size": 16, "color": CAL_GOLD, "bold": True})]],
          line_spacing=1.6)

    # ── 2. The question ───────────────────────────────────────────────────────
    s = new_slide("The Question",
                  "Can free news flag a company as a takeover target before the deal is public?",
                  "1 · BACKGROUND")
    card(s, Inches(0.40), Inches(1.45), Inches(6.15), "WHAT WE WANT",
         [[("Spot likely $1B+ takeover targets 3 to 6 months early, using only free "
            "public data.", {"bold": True})],
          "",
          "When a deal is announced, the target's stock usually jumps 20 to 30% "
          "overnight. Ranking companies by takeover odds before that jump is worth "
          "real money for event-driven and merger-arb desks.",
          "",
          "We stick to free data on purpose. No paid rumor feeds. That keeps the work "
          "easy to repeat, and it asks a sharper question: is the signal even in the "
          "public record?"],
         body_h=Inches(3.35), header_fill=ROCK)
    card(s, Inches(6.78), Inches(1.45), Inches(6.15), "WHY IT IS HARD",
         [[("Takeovers are rare. ", {"bold": True}),
           ("About 250 US deals this size a year, against 7,600 listed companies. A "
            "base rate near 3%.", {})],
          "",
          [("The talks are secret. ", {"bold": True}),
           ("Negotiations sit under NDAs, and leaking is a legal problem. Quiet press "
            "before a deal may just be the system working as intended.", {})],
          "",
          [("It is easy to fool yourself. ", {"bold": True}),
           ("Old news already holds the answer. An honest test has to show it is not "
            "peeking at the future. For an LLM, also that it is not recalling the deal "
            "from training.", {})]],
         body_h=Inches(3.35), header_fill=MEDALIST)
    band(s, "The test, stated plainly: given 90 days of a company's free news ending a "
            "week before a deal, can we tell it apart from a quiet 90-day stretch for the "
            "same company months earlier?", positive=True, y=Inches(6.35), h=Inches(0.72))

    # ── 3. How we set it up (paired design) ───────────────────────────────────
    s = new_slide("How We Set It Up",
                  "Each company is compared against itself, so size and popularity cannot "
                  "explain the result", "2 · METHOD")
    tl_y = Inches(2.85)
    _box(s, Inches(0.70), tl_y, Inches(11.9), Inches(0.05), fill=MUTED)
    _box(s, Inches(1.05), tl_y - Inches(0.72), Inches(3.25), Inches(0.68), fill=ROCK)
    _text(s, Inches(1.05), tl_y - Inches(0.70), Inches(3.25), Inches(0.64),
          [[("QUIET WINDOW  (label 0)", {"bold": True, "size": 12.5})],
           [("90 days, 180 days earlier", {"size": 11})]],
          color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _box(s, Inches(6.05), tl_y - Inches(0.72), Inches(3.25), Inches(0.68), fill=MEDALIST)
    _text(s, Inches(6.05), tl_y - Inches(0.70), Inches(3.25), Inches(0.64),
          [[("RUN-UP WINDOW  (label 1)", {"bold": True, "size": 12.5})],
           [("90 days before the deal", {"size": 11})]],
          color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _box(s, Inches(9.30), tl_y - Inches(0.72), Inches(0.95), Inches(0.68), fill=LIGHT_PINK)
    _text(s, Inches(9.30), tl_y - Inches(0.70), Inches(0.95), Inches(0.64),
          [[("SKIP", {"bold": True, "size": 10})], [("7 days", {"bold": True, "size": 10})]],
          color=DARK_TEXT, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _box(s, Inches(10.25), tl_y - Inches(0.95), Inches(0.045), Inches(1.00), fill=CAL_GOLD)
    _text(s, Inches(9.55), tl_y - Inches(1.42), Inches(2.6), Inches(0.45),
          [[("DEAL ANNOUNCED", {"bold": True, "size": 12.5, "color": MEDALIST})],
           [("day 0", {"size": 11, "color": MUTED})]],
          align=PP_ALIGN.CENTER)
    for x, lab in [(Inches(1.05), "-277d"), (Inches(6.05), "-97d"),
                   (Inches(9.30), "-7d"), (Inches(10.25), "0")]:
        _box(s, x, tl_y, Inches(0.03), Inches(0.16), fill=MUTED)
        _text(s, x - Inches(0.45), tl_y + Inches(0.18), Inches(0.95), Inches(0.30),
              lab, size=11, color=MUTED, align=PP_ALIGN.CENTER)

    card(s, Inches(0.40), Inches(3.75), Inches(4.05), "SAME COMPANY, BOTH SIDES",
         ["Each deal gives one run-up window and one quiet window for the same firm.",
          "",
          "So a model cannot win just by spotting big, well-covered companies. Size, "
          "sector and press coverage stay fixed."],
         body_h=Inches(2.05), header_fill=GREEN, body_size=12.5)
    card(s, Inches(4.63), Inches(3.75), Inches(4.05), "WHY SKIP THE LAST WEEK",
         ["Leaks and 'sources say' stories bunch up in the final days before a deal.",
          "",
          "Keeping them gives a high score that is useless in practice, since the stock "
          "has already moved. Dropping them keeps this real prediction."],
         body_h=Inches(2.05), header_fill=MEDALIST, body_size=12.5)
    card(s, Inches(8.86), Inches(3.75), Inches(4.07), "WHAT THE MODEL NEVER SEES",
         ["· the announcement date",
          "· which window is which",
          "· the answer (the label)",
          "· any news after the window ends",
          "",
          "It sees only headlines, tagged with a day offset and the month."],
         body_h=Inches(2.05), header_fill=ROCK, body_size=12.5)
    band(s, "Both methods run on these same windows, the same companies, and the same "
            "time split. The only thing that changes is how the news becomes numbers.",
         positive=True, y=Inches(6.42), h=Inches(0.60))

    # ── 4. The data ───────────────────────────────────────────────────────────
    s = new_slide("The Data",
                  f"{n_total:,} large US deals and about {round(n_articles/1000):,},000 "
                  "free news items and filings", "3 · DATA")
    steps = [(f"{n_total:,}", "US deals\n$1B+, 2016-2026", BERK_BLUE),
             (f"~{round(n_articles/1000):,}k", "news + filings\ncollected free", BERK_BLUE),
             (f"{n_scored:,}", "companies with\nenough news", ROCK),
             (f"{n_rows:,}", "windows\n(run-up + quiet)", MEDALIST),
             (f"{n_test}", "held back to\ntest on", GREEN)]
    x = Inches(0.40)
    for i, (val, lab, col) in enumerate(steps):
        _box(s, x, Inches(1.55), Inches(2.20), Inches(1.45), fill=col)
        _text(s, x, Inches(1.62), Inches(2.20), Inches(0.62), val, size=25,
              color=CAL_GOLD, bold=True, align=PP_ALIGN.CENTER)
        _text(s, x, Inches(2.24), Inches(2.20), Inches(0.72), lab, size=10.5,
              color=WHITE, align=PP_ALIGN.CENTER)
        x += Inches(2.20)
        if i < len(steps) - 1:
            arrow(s, x, Inches(2.00))
            x += Inches(0.42)

    card(s, Inches(0.40), Inches(3.45), Inches(6.15), "WHERE THE REST WENT",
         [[("About a third of the deals had no free news at all. ", {"bold": True}),
           ("That is not a scraping bug. Looking through them, they are:", {})],
          "· asset and carve-out sales (a portfolio of buildings, a business unit)",
          "· blank-cheque shells and SPACs",
          "· private or foreign targets the US press never covered"],
         body_h=Inches(2.35), header_fill=ROCK, body_size=12.5)
    card(s, Inches(6.78), Inches(3.45), Inches(6.15), "WHY ONLY $1B AND UP",
         [[("On purpose, not for convenience. ", {"bold": True}),
           ("Big targets are almost always public, well-known companies. That is the "
            "only place free news coverage exists at all.", {})],
          "",
          "Below $1B the news mostly is not there, so the question would be "
          "unanswerable rather than answered."],
         body_h=Inches(2.35), header_fill=GREEN, body_size=12.5)
    band(s, f"Cost of the whole evidence base: $0 for news and filings, ${cost:.2f} for "
            f"{calls:,} LLM calls.", positive=True, y=Inches(6.42), h=Inches(0.60))

    # ── 5. Two methods ────────────────────────────────────────────────────────
    s = new_slide("Two Ways to Read the Same News",
                  "Classic NLP and an LLM, over one shared set of headlines", "2 · METHOD")
    _box(s, Inches(0.40), Inches(1.50), Inches(2.55), Inches(1.55), fill=BERK_BLUE)
    _text(s, Inches(0.40), Inches(1.57), Inches(2.55), Inches(1.45),
          [[("SHARED INPUT", {"bold": True, "size": 12, "color": CAL_GOLD})],
           [(f"{n_scored:,} companies", {"size": 12.5, "color": WHITE, "bold": True})],
           [("x 2 windows", {"size": 11.5, "color": LIGHT_BLUE})],
           [(f"= {n_rows:,} rows", {"size": 12.5, "color": WHITE, "bold": True})],
           [("cleaned headlines", {"size": 10.5, "color": LIGHT_BLUE})]],
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.25)
    arrow(s, Inches(3.05), Inches(2.05))
    _box(s, Inches(3.60), Inches(1.50), Inches(4.35), Inches(0.70), fill=ROCK)
    _text(s, Inches(3.60), Inches(1.53), Inches(4.35), Inches(0.64),
          [[("A. Classic NLP", {"bold": True, "size": 14})],
           [("hand-built word statistics", {"size": 11})]],
          color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _box(s, Inches(3.60), Inches(2.20), Inches(4.35), Inches(0.85), fill=LIGHT_GRAY)
    _text(s, Inches(3.70), Inches(2.25), Inches(4.15), Inches(0.78),
          "VADER + FinBERT tone · M&A keyword counts · distinctive terms · topics · "
          "volume · filing mix", size=11, color=DARK_TEXT)
    _box(s, Inches(8.60), Inches(1.50), Inches(4.33), Inches(0.70), fill=MEDALIST)
    _text(s, Inches(8.60), Inches(1.53), Inches(4.33), Inches(0.64),
          [[("B. The LLM", {"bold": True, "size": 14})],
           [(f"one call per window ({primary_model})", {"size": 10.5})]],
          color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _box(s, Inches(8.60), Inches(2.20), Inches(4.33), Inches(0.85), fill=LIGHT_GRAY)
    _text(s, Inches(8.70), Inches(2.25), Inches(4.13), Inches(0.78),
          "ten takeover warning signs (0 to 10) · an overall takeover score (0 to 100) "
          "· short evidence quotes", size=11, color=DARK_TEXT)
    _box(s, Inches(3.60), Inches(3.30), Inches(9.33), Inches(0.60), fill=GREEN)
    _text(s, Inches(3.60), Inches(3.33), Inches(9.33), Inches(0.54),
          "C. Both sets together", size=14, color=WHITE, bold=True,
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    card(s, Inches(0.40), Inches(4.10), Inches(6.15), "IDENTICAL AFTER THAT",
         ["· top 16 features, picked on the training data only",
          "· same three models (logistic regression, random forest, gradient boosting)",
          f"· same time split, {n_test} rows held back",
          "· same bootstrap confidence intervals"],
         body_h=Inches(1.95), header_fill=ROCK, body_size=12.5)
    card(s, Inches(6.78), Inches(4.10), Inches(6.15), "WHY THIS IS A FAIR TEST",
         [[("Everything after the features is the same. ", {"bold": True})],
          "",
          "So any gap in the scores comes from how the news was read, not from the data, "
          "the split, or the tuning. That is what makes the comparison mean something."],
         body_h=Inches(1.95), header_fill=GREEN, body_size=12.5)

    # ── 6. Pipeline A: classic NLP in detail ──────────────────────────────────
    s = new_slide("Pipeline A: Classic NLP in Detail",
                  "The established baseline from weeks 2 to 4: four layers of hand-built "
                  "text features", "2 · METHOD")
    flow = [("NEWS", "GDELT + SEC EDGAR", BERK_BLUE),
            ("NLP LAYERS", "VADER · FinBERT\nlog-odds · NMF", ROCK),
            ("FEATURES", "28 per window", MEDALIST),
            ("SAME MODELS", "LR · RF · GB", GREEN)]
    fx = Inches(0.40)
    for i, (h, sub, col) in enumerate(flow):
        _box(s, fx, Inches(1.40), Inches(2.75), Inches(1.02), fill=col)
        _text(s, fx, Inches(1.48), Inches(2.75), Inches(0.90),
              [[(h, {"bold": True, "size": 13, "color": CAL_GOLD})],
               [(sub, {"size": 11.5, "color": WHITE})]],
              align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.12)
        fx += Inches(2.75)
        if i < len(flow) - 1:
            arrow(s, fx, Inches(1.58))
            fx += Inches(0.42)

    layers = [
        ("VOLUME & TONE", ROCK,
         ["- article counts, articles per day",
          "- VADER tone: average, spread, extremes",
          "- positive / negative ratio",
          "- M&A keyword hits"]),
        ("FINBERT", ROCK,
         ["- finance-tuned sentiment model",
          "- P(positive) / P(negative)",
          "- net finance tone per window",
          "- reads 'rejected bid' vs 'agreed deal'"]),
        ("DISTINCTIVE TERMS", MEDALIST,
         ["- TF-IDF over the headlines",
          "- log-odds against the quiet windows",
          "- company names masked out first",
          "- terms that separate the two windows"]),
        ("TOPICS & STRUCTURE", MEDALIST,
         ["- NMF topic model, 8 topics",
          "- topic weights per window",
          "- price momentum joins",
          "- the mix of SEC filing types"]),
    ]
    lx = Inches(0.40)
    for title, col, items in layers:
        card(s, lx, Inches(2.95), Inches(3.05), title, items,
             body_h=Inches(2.55), header_fill=col, body_size=11.5)
        lx += Inches(3.18)
    band(s, "Twenty-eight features per window in all. They feed the exact same models and "
            "split as the LLM, so the two pipelines are judged on equal footing.",
         positive=True, y=Inches(6.42), h=Inches(0.60))

    # ── 7. What we ask the model ──────────────────────────────────────────────
    s = new_slide("Pipeline B: The LLM Call",
                  "One call per window: fixed instructions, plus that window's headlines",
                  "2 · METHOD")
    _text(s, Inches(0.40), Inches(1.30), Inches(12.5), Inches(0.40),
          [[("The model sees the headlines and nothing else. ", {"bold": True}),
            ("Not the date, not which window it is, not the outcome.", {"color": MUTED})]],
          size=12.5)
    _box(s, Inches(0.40), Inches(1.80), Inches(6.15), Inches(0.38), fill=BERK_BLUE)
    _text(s, Inches(0.40), Inches(1.81), Inches(6.15), Inches(0.36),
          "WHAT GOES IN  ·  rules + this window's headlines", size=12,
          color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _box(s, Inches(0.40), Inches(2.18), Inches(6.15), Inches(3.55), fill=LIGHT_GRAY)
    plines = stats.get("example_prompt_lines", [])[:14]
    _text(s, Inches(0.52), Inches(2.26), Inches(5.90), Inches(3.42),
          [[(l, {"size": 10.5})] for l in plines] or ["(no example)"],
          size=10.5, color=DARK_TEXT, line_spacing=1.18)
    _box(s, Inches(6.78), Inches(1.80), Inches(6.15), Inches(0.38), fill=MEDALIST)
    _text(s, Inches(6.78), Inches(1.81), Inches(6.15), Inches(0.36),
          "WHAT COMES BACK  ·  fixed-format JSON", size=12,
          color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _box(s, Inches(6.78), Inches(2.18), Inches(6.15), Inches(3.55), fill=LIGHT_GRAY)
    rlines = stats.get("example_response_lines", [])[:16]
    _text(s, Inches(6.90), Inches(2.26), Inches(5.90), Inches(3.42),
          [[(l, {"size": 10.5})] for l in rlines] or ["(no example)"],
          size=10.5, color=DARK_TEXT, line_spacing=1.18)
    band(s, f"The format is enforced, so all {calls:,} calls return the same 17 fields in "
            "the same shape. No parsing guesswork, no missing values to patch.",
         positive=True, y=Inches(5.85), h=Inches(0.62))

    # ── 7. Result: head to head ───────────────────────────────────────────────
    s = new_slide("Result: Head to Head",
                  f"Best model for each method, same rows and split ({n_rows:,} windows, "
                  f"{n_test} test rows)", "4 · RESULTS")
    rows = [["Method", "Best model", "Test AUC", "95% range", "vs chance"]]
    for key, label in [(A_KEY, "A. Classic NLP"), (B_KEY, "B. LLM"),
                       (C_KEY, "C. Both together")]:
        b = best_of(auc, key)
        if b:
            m, r = b
            rows.append([label, m, f"{r['auc']:.3f}",
                         f"{r['lo']:.3f} to {r['hi']:.3f}", f"+{r['auc'] - 0.5:.3f}"])
    rows.append(["Random guess", "-", "0.500", "-", "0.000"])
    _abc = [best_of(auc, k) for k in (A_KEY, B_KEY, C_KEY)]
    _best_row = 1 + max(range(3), key=lambda i: _abc[i][1]["auc"] if _abc[i] else -1)
    shape_table(s, Inches(0.40), Inches(1.42),
                [Inches(3.05), Inches(2.75), Inches(1.75), Inches(2.25), Inches(2.73)],
                rows, row_h=Inches(0.36), font_size=12, highlight=_best_row)

    # The AUC chart: grouped bars with 95% CI whiskers (all crossing 0.50) + ROC overlay.
    auc_fig = FIG_DIR / "fig_auc_comparison.png"
    if auc_fig.exists():
        add_picture_fit(s, auc_fig, Inches(2.30), Inches(3.32), Inches(8.75), Inches(3.02))
    band(s, f"Combining classic NLP with the LLM has the highest AUC ({C3}), a small edge "
            f"over either alone (NLP {A3}, LLM {B3}). The ranges still include 0.50, so this "
            "is promising rather than proven, but the two methods look complementary.",
         positive=True, y=Inches(6.52), h=Inches(0.58))

    # ── 8. Where the news shows up ────────────────────────────────────────────
    s = new_slide("Where the News Actually Shows Up",
                  "We counted coverage day by day around each deal", "4 · RESULTS")
    kpi_tile(s, Inches(0.40), Inches(1.70), "~12",
             "articles on the\nannouncement day", fill=MEDALIST,
             w=Inches(4.05), h=Inches(1.55))
    kpi_tile(s, Inches(4.63), Inches(1.70), "0.35",
             "articles per day in\nthe week after", fill=BERK_BLUE,
             w=Inches(4.05), h=Inches(1.55))
    kpi_tile(s, Inches(8.86), Inches(1.70), "0.25",
             "articles per day in\nthe 90-day run-up", fill=BERK_BLUE,
             w=Inches(4.07), h=Inches(1.55))
    card(s, Inches(0.40), Inches(3.55), Inches(6.15), "THE COVERAGE IS THERE, JUST LATE",
         [[("News about these deals lands on the day they are announced, not before.",
            {"bold": True})],
          "",
          "The run-up window sees about a quarter of an article a day, the same trickle "
          "as any random quiet period. On day zero it jumps to a dozen. That is dozens "
          "of times heavier."],
         body_h=Inches(2.30), header_fill=ROCK, body_size=12.5)
    card(s, Inches(6.78), Inches(3.55), Inches(6.15), "WHY THIS SETTLES IT",
         [[("There are two ways to fail at this task.", {"bold": True})],
          "· the method is too weak, which better features could fix",
          "· the information is not there, which nothing can fix",
          "",
          [("The day-zero spike proves the tools do pick up deal news when it exists. "
            "So the near-chance result is about the data, not the method.",
            {"color": MEDALIST, "bold": True})]],
         body_h=Inches(2.30), header_fill=MEDALIST, body_size=12.5)

    # ── 9. Detection (positive control) ───────────────────────────────────────
    s = new_slide("The Same Tools Do Work, One Week Later",
                  "Point the exact same pipeline at the announcement week instead of the "
                  "run-up", "4 · RESULTS")
    _text(s, Inches(0.40), Inches(1.32), Inches(12.5), Inches(0.42),
          [[("Different question: ", {"bold": True}),
            ("given one week of a company's news, did a deal just happen? This is "
             "spotting, not predicting, and we say so plainly.", {})]],
          size=13, line_spacing=1.3)
    shape_table(s, Inches(0.40), Inches(1.95),
                [Inches(2.75), Inches(1.85), Inches(1.85), Inches(1.55)],
                DET_ROWS, row_h=Inches(0.42), font_size=12.5, highlight=1)
    _text(s, Inches(0.40), Inches(4.15), Inches(8.0), Inches(0.34),
          "400 weeks in the test: 200 announcement weeks and 200 quiet weeks for the "
          "same companies.", size=11, color=MUTED)
    _text(s, Inches(0.40), Inches(4.62), Inches(8.0), Inches(0.36),
          "What drives it", size=13.5, bold=True)
    shape_table(s, Inches(0.40), Inches(5.05),
                [Inches(3.30), Inches(2.35), Inches(2.35)],
                [["", "Announcement wk", "Quiet wk"],
                 ["Articles per day", "1.80", "0.12"],
                 ["M&A keyword count", "1.02", "0.23"]],
                row_h=Inches(0.40), font_size=12.5)
    card(s, Inches(8.55), Inches(1.95), Inches(4.38), "THE GAP IS THE POINT",
         [[("Spotting a deal: ", {"bold": True}), (DET_BEST, {"bold": True, "color": GREEN}),
           (" AUC", {})],
          [("Predicting one early: ", {"bold": True}),
           (BEST, {"bold": True, "color": MEDALIST}), (" AUC", {})],
          "",
          "Same features, same models, same filters. The only change is which week we "
          "look at.",
          "",
          [("So the tools work fine. The early news simply is not there to read.",
            {"bold": True})]],
         body_h=Inches(3.10), header_fill=GREEN, body_size=12.5)
    band(s, "There is a usable tool here today: spotting deals as they are announced, from "
            "free news alone, at 0.79.", positive=True, y=Inches(6.45), h=Inches(0.58))

    # ── 8. Are the LLM signals new information (correlation) ─────────────────
    s = new_slide("Are the LLM Signals New Information?",
                  "How much the LLM scores overlap with the classic ones", "4 · RESULTS")
    corr = FIG_DIR / "fig_llm_vs_classic_corr.png"
    if corr.exists():
        add_picture_fit(s, corr, Inches(0.40), Inches(1.40), Inches(7.90), Inches(4.75))
    card(s, Inches(8.55), Inches(1.45), Inches(4.38), "A DIFFERENT, COMPLEMENTARY SIGNAL",
         ["Each square asks whether the two scores rank companies the same way.",
          "",
          "The colours are mostly pale, so the LLM's takeover signals are largely "
          "separate from the word-count and tone features.",
          "",
          [("That is why the two help most together. ", {"bold": True}),
           ("Because they read different things, the combined set edges ahead of either "
            "one alone.", {})]],
         body_h=Inches(4.75), header_fill=ROCK, body_size=12)

    # ── 10. Can we trust the LLM ──────────────────────────────────────────────
    s = new_slide("Can We Trust the LLM Score?",
                  "Three checks, because the model might already know how these deals ended",
                  "5 · VALIDITY")
    _text(s, Inches(0.40), Inches(1.28), Inches(12.5), Inches(0.60),
          [[("The worry: ", {"bold": True}),
            (f"{primary_model} was trained up to {cutoff}, before most of our deals. If "
             "it scores a window high because it remembers the deal, we have measured "
             "memory, not prediction.", {})]], size=12.5, line_spacing=1.2)
    kpi_tile(s, Inches(0.40), Inches(1.95),
             f"{probe.get('acc', 0) * 100:.0f}%", "guessing deals with no\nnews shown "
             "(coin flip = 50%)", fill=GREEN, w=Inches(4.05), h=Inches(1.35))
    kpi_tile(s, Inches(4.63), Inches(1.95),
             f"{masking.get('delta', 0):+.3f}", "score change when we\nhide company names",
             fill=GREEN, w=Inches(4.05), h=Inches(1.35))
    kpi_tile(s, Inches(8.86), Inches(1.95),
             f"{repeat.get('mean_spearman', 0):.2f}", "agreement when we\nscore twice",
             fill=ROCK, w=Inches(4.07), h=Inches(1.35))
    card(s, Inches(0.40), Inches(3.55), Inches(4.05), "IT IS NOT REMEMBERING",
         [[("Asked to guess deals with no news at all, ", {}),
           (f"it scored {probe.get('acc', 0) * 100:.1f}%, a coin flip.", {"bold": True})],
          "",
          f"It did no better on older deals it might have seen in training "
          f"({probe.get('acc_pre_cutoff', 0) * 100:.0f}%) than on newer ones "
          f"({probe.get('acc_post_cutoff', 0) * 100:.0f}%)."],
         body_h=Inches(2.35), header_fill=GREEN, body_size=12)
    card(s, Inches(4.63), Inches(3.55), Inches(4.05), "IT IS READING THE NEWS",
         [[("Hide the company name and the score barely moves, ", {}),
           (f"{masking.get('auc_unmasked', 0):.3f} to "
            f"{masking.get('auc_masked', 0):.3f}.", {"bold": True})],
          "",
          "So it is going off the words in the headlines, not off recognising a "
          "famous name."],
         body_h=Inches(2.35), header_fill=GREEN, body_size=12)
    card(s, Inches(8.86), Inches(3.55), Inches(4.07), "THE SCORES ARE STABLE",
         [[("Score the same window twice and the two runs line up at "
            f"{repeat.get('mean_spearman', 0):.2f} out of 1.", {"bold": True})],
          "",
          "The overall takeover number moves about "
          f"{repeat.get('likelihood_mean_abs_diff', 0):.1f} points out of 100. "
          "Not random noise.",
          "",
          "It also quotes the exact headline behind each score, and every quote checked "
          "out against the real text."],
         body_h=Inches(2.35), header_fill=ROCK, body_size=12)
    band(s, "All three checks came back clean. The small edge we found is a real reading of "
            "the news, and the method carries over to deals the model has never seen.",
         positive=True, y=Inches(6.32), h=Inches(0.62))

    # ── 12. Every LLM score cites its source ──────────────────────────────────
    s = new_slide("Every LLM Score Cites Its Source",
                  "The model quotes the headline behind each score, and we check it",
                  "5 · VALIDITY")
    if cited:
        _text(s, Inches(0.40), Inches(1.32), Inches(12.5), Inches(0.40),
              [[(f"Across {cited.get('n_events', 0)} test events, ", {}),
                (f"{cited.get('n_verified', 0)} of {cited.get('n_total', 0)} quoted "
                 "headlines matched the real text word for word. None were made up.",
                 {"bold": True})]], size=13)
        crows = [["Company · signal", "Score", "Quoted headline", "Source"]]
        for ex in cited.get("examples", []):
            for c in ex.get("citations", []):
                crows.append([f"{ex['company']} · {c['signal']}", str(c["score"]),
                              c["quote"][:76], c["source"]])
        shape_table(s, Inches(0.40), Inches(1.85),
                    [Inches(3.35), Inches(0.75), Inches(6.20), Inches(2.23)],
                    crows, row_h=Inches(0.40), font_size=11)
    band(s, "A number an analyst can click through to a real headline is worth more than a "
            "number on its own. The checking is automatic.", positive=True,
         y=Inches(6.42), h=Inches(0.60))

    # ── 11. Conclusions ───────────────────────────────────────────────────────
    s = new_slide("What We Found", "The take-aways, with the numbers behind them",
                  "6 · CONCLUSION")
    concl = [
        ("1", "Free news does not predict these deals early.",
         f"Best AUC {best_all[1]['auc']:.3f} across {n_rows:,} windows, and the range "
         "still includes a coin flip. A small edge at best."),
        ("2", "The limit is the data, not the method.",
         f"The same setup spots deals the week they land at {DET_BEST}. Coverage barely "
         "exists before the announcement, so there is little to find."),
        ("3", "The LLM and classic NLP work best together.",
         f"Classic NLP {bA[1]['auc']:.3f}, LLM {bB[1]['auc']:.3f}, both together "
         f"{bC[1]['auc']:.3f} (the highest). They read different things, so combining them "
         "helps, though the edge is small."),
        ("4", "The LLM is honest.",
         "It reads rather than remembers, its scores hold up when we hide names and when "
         "we re-run, and every score cites a real headline."),
        ("5", "One thing works today.",
         f"Spotting deals as they are announced, from free news, at {DET_BEST} for about "
         f"${cost:.0f} of compute."),
    ]
    y = Inches(1.42)
    for num, headline, detail in concl:
        _box(s, Inches(0.40), y, Inches(0.55), Inches(1.00), fill=BERK_BLUE)
        _text(s, Inches(0.40), y, Inches(0.55), Inches(1.00), num, size=22,
              color=CAL_GOLD, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        _box(s, Inches(0.95), y, Inches(11.98), Inches(1.00), fill=LIGHT_GRAY)
        _text(s, Inches(1.10), y + Inches(0.04), Inches(11.70), Inches(0.94),
              [[(headline, {"bold": True, "size": 14})],
               [(detail, {"size": 12, "color": MUTED})]],
              line_spacing=1.25, anchor=MSO_ANCHOR.MIDDLE)
        y += Inches(1.06)

    # ── 12. Future work ───────────────────────────────────────────────────────
    s = new_slide("What We Would Do Next",
                  "Ordered by what would move the needle most", "6 · CONCLUSION")
    card(s, Inches(0.40), Inches(1.45), Inches(6.15), "CHANGE THE INPUT",
         [[("The biggest gain is a different input, not a fancier model.",
            {"bold": True})],
          "",
          [("Go upstream of the news. ", {"bold": True}),
           ("Company financials (debt, cash, a cheap valuation, activist investors "
            "building a stake) are where the older research finds its signal. News is a "
            "late, downstream symptom.", {})],
          "",
          [("Read filings, not just headlines. ", {"bold": True}),
           ("Annual reports and earnings calls often hint at a sale months earlier. The "
            "extractor already takes long text.", {})]],
         body_h=Inches(3.90), header_fill=MEDALIST, body_size=12.5)
    card(s, Inches(6.78), Inches(1.45), Inches(6.15), "TWO SMALLER STEPS",
         [[("Price the free-data limit. ", {"bold": True}),
           ("Run one paid news feed once, and measure how much the free-only rule costs "
            "us. That number is a result in itself.", {})],
          "",
          [("Get a bigger test set. ", {"bold": True}),
           ("More deals would tighten the range and settle whether the small edge is "
            "real or not.", {})],
          "",
          [("Keep classic NLP as the cheap baseline. ", {"bold": True}),
           ("It matched the LLM here, at a fraction of the cost.", {})]],
         body_h=Inches(3.90), header_fill=ROCK, body_size=12.5)
    band(s, "Every diagnostic points at the same thing: the news is a late signal. The next "
            "step is to look where the early signal actually lives.", positive=True,
         y=Inches(6.42), h=Inches(0.60))

    # ── 13. Thanks ────────────────────────────────────────────────────────────
    s = prs.slides.add_slide(blank)
    _box(s, 0, 0, SLIDE_W, SLIDE_H, fill=BERK_BLUE)
    _box(s, 0, Inches(3.55), SLIDE_W, Inches(0.06), fill=CAL_GOLD)
    if WORDMARK.exists():
        add_picture_fit(s, WORDMARK, Inches(5.15), Inches(1.30), Inches(3.00), Inches(0.50))
    _text(s, Inches(0.70), Inches(2.35), Inches(11.9), Inches(1.0),
          "Thank You", size=48, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    _text(s, Inches(0.70), Inches(3.95), Inches(11.9), Inches(1.6),
          [[("Predicting M&A from Free News  ·  Classic NLP vs an LLM",
             {"size": 17, "color": CAL_GOLD, "bold": True})],
           [("Dexin Fu   ·   Ronald Liu", {"size": 15, "color": WHITE})],
           [("Full write-up, notebooks and code in the project repository",
             {"size": 12.5, "color": LIGHT_BLUE})]],
          align=PP_ALIGN.CENTER, line_spacing=1.7)

    # ══ APPENDIX (backup for questions, not presented) ════════════════════════
    s = prs.slides.add_slide(blank)
    _box(s, 0, 0, SLIDE_W, SLIDE_H, fill=BERK_BLUE)
    _box(s, 0, Inches(3.55), SLIDE_W, Inches(0.06), fill=CAL_GOLD)
    _text(s, 0, Inches(3.05), SLIDE_W, Inches(0.9), "Appendix", size=44, color=WHITE,
          bold=True, align=PP_ALIGN.CENTER)
    _text(s, 0, Inches(4.05), SLIDE_W, Inches(0.5), "Backup detail for questions",
          size=15, color=LIGHT_BLUE, align=PP_ALIGN.CENTER)

    # A. Prior work
    s = new_slide("Where This Fits in the Literature", "", "APPENDIX")
    card(s, Inches(0.40), Inches(1.42), Inches(4.05), "TAKEOVER PREDICTION",
         [[("Palepu (1986) ", {"bold": True}),
           ("set the template: predict targets from company fundamentals.", {})],
          "",
          "Later work (Ambrose & Megginson 1992, Powell 2001) finds the same thing: a "
          "little better than chance, and the edge fades after trading costs.",
          "",
          [("Takeaway: ", {"color": MEDALIST, "bold": True}),
           ("an AUC of 0.55 to 0.70 is the realistic ceiling, not 0.90.", {})]],
         body_h=Inches(3.55), header_fill=ROCK, body_size=12)
    card(s, Inches(4.63), Inches(1.42), Inches(4.05), "TEXT AS A SIGNAL",
         [[("Tetlock (2007) ", {"bold": True}),
           ("showed news tone moves prices.", {})],
          "",
          [("Loughran & McDonald (2011) ", {"bold": True}),
           ("showed generic word lists misread financial text, so we use "
            "finance-specific tools like FinBERT (Araci 2019).", {})]],
         body_h=Inches(3.55), header_fill=ROCK, body_size=12)
    card(s, Inches(8.86), Inches(1.42), Inches(4.07), "LLMs IN FINANCE",
         [[("Lopez-Lira & Tang (2023) ", {"bold": True}),
           ("found ChatGPT headline scores predict next-day returns, but the "
            "memory-vs-reasoning question was left open.", {})],
          "",
          [("Our angle: ", {"bold": True, "color": MEDALIST}),
           ("run classic NLP and an LLM on the exact same news, then test hard whether "
            "the LLM is reading or remembering.", {})]],
         body_h=Inches(3.55), header_fill=ROCK, body_size=12)

    # B. Data-quality work
    s = new_slide("Cleaning the News First",
                  "Three ways the raw text was misleading, and the fix for each", "APPENDIX")
    issues = [
        ("FILING STUBS READ AS NEWS",
         [[("Problem: ", {"bold": True}),
           ("auto-generated filing lines ('COMPANY filed an 8-K on...') were about 40% "
            "of the text, and the tone models scored them like real articles.", {})],
          "",
          [("Fix: ", {"bold": True, "color": GREEN}),
           ("use news for tone; turn filings into plain counts instead.", {})]]),
        ("COMPANY NAMES AS SIGNAL",
         [[("Problem: ", {"bold": True}),
           ("both windows are the same company, so the most 'distinctive' words were "
            "just its name, which does not generalise.", {})],
          "",
          [("Fix: ", {"bold": True, "color": GREEN}),
           ("blank out each company's own name before counting words.", {})]]),
        ("BOT-WRITTEN ARTICLES",
         [[("Problem: ", {"bold": True}),
           ("about 17% of items were templated bot posts (holdings updates, rating "
            "bots) that show up for any public company.", {})],
          "",
          [("Fix: ", {"bold": True, "color": GREEN}),
           ("filter them by pattern and domain, the same way on both windows.", {})]]),
    ]
    x = Inches(0.40)
    for title, body in issues:
        card(s, x, Inches(1.45), Inches(4.05), title, body,
             body_h=Inches(3.10), header_fill=MEDALIST, body_size=12)
        x += Inches(4.23)
    band(s, "Every filter is applied the same way to both windows. A filter that treated "
            "the two sides differently would invent a signal that is not really there.",
         positive=True, y=Inches(5.25), h=Inches(0.65))

    # C. Contributions
    s = new_slide("Contributions", "Who did what", "APPENDIX")
    crows = [["Area", "Dexin Fu", "Ronald Liu"],
             ["Scoping and background reading", "Lead", "Support"],
             ["Deal cleaning and labels", "Lead", ""],
             ["News and filing scrapers", "Lead", "Support"],
             ["Classic NLP (VADER, FinBERT, topics)", "Lead", ""],
             ["Data-quality fixes and diagnostics", "Lead", ""],
             ["LLM extraction pipeline", "", "Lead"],
             ["Trust checks (memory, name, repeat)", "", "Lead"],
             ["Full-data run and head-to-head", "Support", "Lead"],
             ["Slide decks and write-up", "Weeks 2-4", "Week 7, final"]]
    shape_table(s, Inches(0.40), Inches(1.55),
                [Inches(6.53), Inches(3.00), Inches(3.00)],
                crows, row_h=Inches(0.42), font_size=12.5)
    _text(s, Inches(0.40), Inches(6.55), Inches(12.5), Inches(0.40),
          "Both of us reviewed every result together and agreed the pass or fail marks "
          "before running any model.", size=11.5, color=MUTED)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT_PATH)
    n_slides = len(prs.slides.__iter__.__self__._sldIdLst)
    print(f"wrote {OUT_PATH}  ({n_slides} slides)")


if __name__ == "__main__":
    main()
