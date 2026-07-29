# Speaker Notes: Predicting M&A from Free News

**15-minute talk, 16 slides. Two presenters.**

Suggested split (follows who built what):
- **Dexin:** slides 1 to 6 (the problem, the setup, the data, and the classic-NLP pipeline)
- **Ronald:** slides 7 to 16 (the LLM pipeline, the results, the checks, the wrap-up)

These are prompts, not a word-for-word script. Say them in your own words. Sixteen slides
in fifteen minutes is tight, so keep each one moving; there's a "what to cut" list at the
end if you fall behind.

---

## 1. Title  ·  ~15s  ·  (Dexin opens)

- Hi, we're Dexin and Ronald.
- Our project asks a simple question: can you predict a big acquisition from free news, before it's announced?
- We built two pipelines to do it, one classic text-analysis, one LLM, and we spent a lot of the time keeping ourselves honest about the answer.

## 2. The Question  ·  ~65s  ·  (Dexin)

- When a company gets bought, its stock usually jumps 20 to 30% the day the deal is announced. So spotting a target early is worth real money.
- We gave ourselves one rule: free data only, no paid rumor feeds. That keeps it reproducible, and it asks a sharper question. Is the signal even in the public record?
- Three things make it hard. The deals are rare, about a 3% base rate. The talks are secret, under NDAs. And it's easy to fool yourself, because old news already contains the answer.
- So here's the exact test (point at the band): 90 days of a company's news ending a week before the deal, against a quiet 90 days for the same company months earlier. Can we tell them apart?

## 3. How We Set It Up  ·  ~75s  ·  (Dexin)

- This is the design, and it's the part that makes the result trustworthy.
- For every deal we take two windows of the same company. A run-up window right before the deal, and a quiet window 180 days earlier.
- Same company on both sides is the trick. A model can't win just by learning that big, well-covered companies get bought, because size and press coverage are the same on both sides.
- We drop the last 7 days on purpose. That's where leaks cluster. Keeping them would give a great-looking number that's useless in practice, because the stock has already moved.
- And the model only ever sees headlines tagged with a day offset and the month. Not the date, not which window it is, not the answer.

## 4. The Data  ·  ~50s  ·  (Dexin)

- Quick walk across the funnel. We started with 2,673 US deals over a billion dollars, and pulled about 40,000 free news items and filings.
- 1,156 companies had enough news to score, which gave us about 2,000 windows, with 400 held back to test on.
- About a third of the deals had no free news at all. That's not a scraping bug. Those are asset sales, blank-cheque shells, and private or foreign targets the press just never covered.

## 5. Two Ways to Read the Same News  ·  ~55s  ·  (Dexin)

- Same headlines go into both pipelines. Method A is classic NLP: word counts, sentiment, keyword hits, topics. Method B is the LLM: one call per window. C is just both sets together.
- Everything after the features is identical: same features picked the same way, same three models, same split.
- That's what makes this a fair test. If the scores differ, it's because of how the news was read, not the data or the tuning.
- Let me show you each pipeline in a bit more detail, starting with the classic one.

## 6. Pipeline A: Classic NLP  ·  ~65s  ·  (Dexin, then hand off)

- This is the classic side, the pipeline we built over weeks 2 to 4. Same news in, turned into numbers four ways.
- VADER and FinBERT give us tone. FinBERT is finance-tuned, so it knows a "rejected bid" reads differently from an "agreed deal."
- Log-odds pulls out the words that separate a run-up window from a quiet one, with company names masked first so it can't just memorize names.
- And NMF pulls out topics. Altogether that's 28 features per window.
- The point of the slide: all of this feeds the exact same models and split as the LLM. So when we compare them, it's a fair fight. I'll hand to Ronald for the LLM side.

## 7. Pipeline B: The LLM Call  ·  ~55s  ·  (Ronald)

- Here's the other pipeline. On the left is exactly what the model sees: a company, a time period, and the headlines. On the right is what it sends back.
- Same as before, it doesn't see the date, or which window this is, or the outcome.
- The answer comes back in a fixed format, so all 4,450 calls give the same 17 fields. No cleanup, no guessing.
- In this case it correctly picks up the takeover chatter. So it reads the news well.

## 8. Result: Head to Head  ·  ~85s  ·  (Ronald)  ·  MAIN RESULT

- Here's the scoreboard, and the chart underneath shows the same thing with error bars.
- Classic NLP 0.525, the LLM 0.518, and the two together 0.551. A coin flip is 0.50.
- So combining them comes out highest, a small edge over either one alone.
- I want to be honest about the size of it. All three error bars still cross 0.50. With 400 test rows, this is promising rather than proven. We're not claiming we solved it.
- But the combination beating either piece is a hint that the two pipelines see different things. We look at that directly in a couple of slides.

## 9. Where the News Actually Shows Up  ·  ~70s  ·  (Ronald)

- So why is everything so close to chance? We counted coverage day by day around each deal.
- On the announcement day, a company gets about 12 articles. In the 90-day run-up, it's about a quarter of an article a day. That's the same trickle as any random quiet period.
- So the news exists, it just shows up on the day of the deal, dozens of times heavier, not before.
- And this tells us which kind of problem we have. Either our method is too weak, which better features could fix, or the information isn't there, which nothing can fix. The day-zero spike proves the tools do catch deal news when it exists. So it's the data, not the method.

## 10. The Same Tools Do Work, One Week Later  ·  ~70s  ·  (Ronald)

- To prove that, we pointed the exact same pipeline at the announcement week instead of the run-up. Different question: did a deal just happen?
- There it hits 0.79. Same features, same models. The only change is which week we look at.
- You can see why in the driver numbers: about 1.8 articles a day in an announcement week, versus almost nothing in a quiet one.
- So the point is the gap. 0.79 when the news is there, around 0.5 when it isn't. The method works. The early news just isn't there to read. And spotting deals as they land is a genuinely useful tool on its own.

## 11. Are the LLM Signals New Information?  ·  ~60s  ·  (Ronald)

- This comes back to why combining helped. Each square asks whether the LLM's scores and the classic features rank companies the same way.
- The colours are mostly pale, which means they're mostly not measuring the same thing. The LLM's takeover signals are largely separate from the word counts and sentiment.
- That's the reason the two do a bit better together than apart. They read different things, so combining them adds a little.
- It's a small effect, but a sensible one, not a fluke of one number.

## 12. Can We Trust the LLM Score?  ·  ~80s  ·  (Ronald)

- The obvious worry with an LLM: it was trained up to late 2023, before most of our deals. Maybe it's remembering the outcome instead of predicting it.
- So, three checks. First, we asked it to guess deals with no news shown at all. It scored 50%, a coin flip, and no better on old deals it might have seen than on new ones. So it's not leaning on memory.
- Second, we hid the company names and scored again. The result barely moved, 0.518 to 0.501. So it's reading the words, not recognizing a famous name.
- Third, we scored the same windows twice. The two runs agree at 0.90. Stable, not random.
- All three came back clean.

## 13. Every LLM Score Cites Its Source  ·  ~50s  ·  (Ronald)

- One more thing we built in, because you asked for it earlier in the project: the model has to quote the exact headline behind each score.
- Across the events we checked, every quote matched a real headline word for word. None were made up.
- The reason it matters: an analyst can't act on a bare number. A score you can click through to the actual headline is one you can check and trust.

## 14. What We Found  ·  ~60s  ·  (Ronald)

- Five takeaways. One: free news doesn't reliably predict these deals early. The best AUC is 0.551, and the range still includes chance.
- Two: the limit is the data, not the method. The same setup hits 0.79 the week a deal lands.
- Three: the two pipelines work best together, since they read different things, though the edge is small.
- Four: the LLM is honest. It reads rather than remembers, and it cites its sources.
- Five: one thing works today. Spotting deals as they're announced, from free news, for about two dollars of compute.

## 15. What We Would Do Next  ·  ~45s  ·  (Ronald)

- The biggest lever here isn't a fancier model. It's a different input. News is a late signal.
- So we'd go upstream: company fundamentals like debt, cash, a cheap valuation, activist investors building a stake. And the text inside filings, which tends to hint at a sale months earlier.
- Two smaller steps: run one paid news feed once, to measure what the free-only rule costs us, and get a bigger test set to firm up the numbers.

## 16. Thank You  ·  ~15s

- That's us. The full write-up, the notebooks, and the code are all in the repo.
- We've got backup slides on the prior research and the data cleaning if they're useful. Happy to take questions.

---

## If you run short on time

Cut or speed through, in this order:
1. Slide 13 (citations): mention it in one line off slide 12.
2. Slide 7 (the example call): describe it in one line off slide 6.
3. Slide 4 (the data funnel): the headline number is enough.

Never cut 3, 8, 9, or 10. The design and the where-the-signal-lives story are the whole argument.

## Likely questions

- **"Is 0.55 a real result?"** → Honestly, not yet. The point estimate is above chance and the combination is highest, but the 95% ranges include 0.50. We call it promising, not proven.
- **"Isn't the LLM just recognising these companies?"** → Slide 12, name-masking: the score barely moves.
- **"Did more data hold this up?"** → We ran a larger batch later. The combined lead is small and moves around at this sample size, which is why we don't overclaim it. The honest read is that all three are close and just above chance.
- **"Did you try richer text?"** → Weeks 3-4 tested full article bodies too; also weak. Filings are the natural next step.
- **"Why not smaller deals?"** → No free news below $1B, so the question becomes unanswerable, not answered.
