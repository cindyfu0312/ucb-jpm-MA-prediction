# Predicting M&A from Free News

**MFE 27, Term 2. J.P. Morgan Industry Project, Group 2.**
Dexin Fu and Ronald Liu. July 2026.

## Introduction

When a public company gets bought, its stock usually jumps the day the deal is announced. So there is real money in spotting likely targets early. That is what this project set out to do. We asked one plain question: can free, public news tell us which companies are about to be acquired, before the deal is made public?

We added two rules for ourselves. First, use only free data. No paid rumor feeds. That keeps the work cheap to repeat, and it tests a sharper question: is the information even in the public record? Second, compare two ways of reading the news on the exact same articles, so the comparison is fair.

People have tried to predict takeover targets for a long time. Most of the older work uses financial data like company size, debt, and how cheap the stock looks. Those models do a little better than a coin flip, but not much, and the edge tends to disappear after trading costs. A newer line of work reads text instead, since news and filings carry information that moves prices. Large language models are the latest tool for that. But they come with a catch. A model may already know how a deal turned out because it saw the news during training. So it might look like it is predicting when it is really just remembering. A big part of our work was checking for exactly that.

## The data

We started with a list of 2,673 US deals worth $1 billion or more, from 2016 to 2026, taken from S&P Capital IQ. For each target company we pulled free news from GDELT and filings from SEC EDGAR. In all we collected close to 40,000 news articles and filing records.

For every company we looked at two 90-day stretches of news. One is the run-up to the deal. The other is a quiet period 180 days earlier, for the same company. Using the same company for both sides is important. It means the model cannot win just by learning that big, famous companies get bought. Size, industry, and how much press a company usually gets are held steady.

One more detail. The run-up window stops 7 days before the announcement. Rumors and leaks tend to cluster in those final days. If we included them, the task would look easy but be useless, because by then the market has already moved.

We also had to clean the news first. Nearly 40% of the raw items were auto-generated filing stubs, and about 17% were bot-written market summaries. Both were stripped out the same way on each side, so the cleaning could not tilt the result one way or the other.

About two-thirds of the companies had news coverage. The rest, roughly a third of the list, were mostly shell companies, asset sales, and private or foreign targets the press never wrote about. We scored the 1,156 companies that had enough news to work with, using both methods. That gave us 2,002 before-and-after windows, with the most recent 400 held back for testing.

## The two methods

**Method A, classic NLP.** This is the standard toolkit. Count the articles, measure the tone with VADER and FinBERT, and pull out distinctive words and topics. It produces about 28 numbers per window, all hand-built and well understood.

**Method B, the LLM.** Here we sent each window's headlines to a language model (gpt-4o-mini) and asked it to score 17 fields. Ten are warning signs on a 0 to 10 scale, like rumor intensity and activist pressure. One is an overall takeover chance from 0 to 100. The answers came back in a fixed format, so every company was scored the same way. The model was trained on data up to October 2023, which matters for the memory check later. The full run was 4,450 calls and cost about $2.

**Method C** simply uses both sets of features together. Out of the roughly 40 numbers across both methods, we kept the 16 that looked most useful on the training data alone.

The point of the setup is fairness. Same companies, same time split, same models on top. The only thing that changes between A and B is how the news gets turned into numbers. So any difference in the results is down to the method, not luck or a data quirk.

## Results

The best result was an AUC of 0.551. A coin flip is 0.50. So there is a small edge above chance, but the margin is not big enough to be sure. The 95% range runs from 0.495 to 0.606, so it still includes 0.50.

| Method | AUC | 95% range |
|---|---|---|
| Classic NLP (A) | 0.525 | 0.470 to 0.580 |
| LLM signals (B) | 0.518 | 0.465 to 0.571 |
| Both combined (C) | 0.551 | 0.495 to 0.606 |
| Random guess | 0.500 | - |

Classic NLP scored 0.525 and the LLM 0.518, so they landed in about the same place. Putting them together lifted it to 0.551, about 0.026 above classic NLP on its own. That small gain is a hint that the two methods pick up on slightly different things.

The most useful result came from a check we ran on the side. We pointed the same tools at the announcement week itself, instead of the run-up. The AUC jumped to 0.79, tested on 400 weeks, 200 with a deal and 200 without. The gap shows up plainly in the raw counts. On a deal week a company drew about 1.8 news articles a day, against 0.1 in a quiet week.

We also checked where the coverage sits in time. On the announcement day itself, a company drew around 12 news articles. In the 90-day run-up it sat near a quarter of an article a day, basically background noise. So the news does exist. It just shows up dozens of times heavier on the day of the deal, not before it. That tells us the method works fine. The problem is the data. There is little to find in the run-up window.

## Is the LLM trustworthy?

Because a language model might be remembering rather than reading, we ran three checks. All three came back clean.

- **Memory test.** We asked the model to guess deals with no news shown at all, using only what it might know. Across 3,602 tries it scored 50.4%, basically a coin flip. It did no better on older deals it could have seen in training (50.6%) than on newer ones (50.1%). So it is not leaning on memory.
- **Name test.** We hid the company names and scored again. The result barely moved, from 0.518 down to 0.501, a drop of 0.017. So it is reading the news, not just recognizing famous names.
- **Repeat test.** We scored the same windows a second time. The rankings lined up at 0.90 out of 1, and the 0-to-100 takeover score shifted by only 1.6 points on average. So the numbers are stable, not random.

On top of that, the model had to quote the exact headline behind each score, and we checked those quotes against the real articles. Every one matched. That makes each score easy to audit.

## Conclusion

Free news cannot reliably predict these deals ahead of time. For the most part, the information is not public until the deal is announced. This is not a problem with our tools. The same pipeline spots deals at announcement with an AUC of 0.79. The limit is the data, not the method.

The language model behaved honestly throughout. It reads the text rather than recalling the outcome, and its scores are stable and easy to check. But it only added a little over the classic approach, not a lot. On this kind of data, a good LLM and a careful bag-of-words model end up close.

One thing does work today. Spotting deals as they are announced, from free news alone, is reliable and costs almost nothing to run. The whole language-model pass cost about $2. That could support deal-flow monitoring, even if early prediction stays out of reach.

## Future work

The clearest next step is to change the input, not the model. The older research finds its signal in company financials. That is where we would look next. Things like debt, cash, how cheap the stock is, and activist investors building a stake. The text inside filings, such as annual reports and earnings calls, may also flag intent months earlier than the news does.

Two smaller steps would help too. Running one paid news feed, just once, would tell us how much the free-only rule actually costs us. And a larger test set would tighten the numbers, and could turn today's small edge into either a real signal or a clear no.

## Contributions

| Area | Dexin Fu | Ronald Liu |
|---|---|---|
| Scoping and background reading | Lead | Support |
| Deal cleaning and labels | Lead | |
| News and filing scrapers | Lead | Support |
| Classic NLP (VADER, FinBERT, topics) | Lead | |
| Data-quality fixes and diagnostics | Lead | |
| LLM extraction pipeline | | Lead |
| Trust checks (memory, name, repeat) | | Lead |
| Full-dataset run and head-to-head | Support | Lead |
| Slide decks | Weeks 2 to 4 | Week 7 and final |

Both of us reviewed every result together, and we agreed on the pass or fail marks before running any model.

## References

Araci, D. (2019). FinBERT: Financial sentiment analysis with pre-trained language models. arXiv:1908.10063.

Ambrose, B. W., and Megginson, W. L. (1992). The role of asset structure, ownership structure, and takeover defenses in determining acquisition likelihood. Journal of Financial and Quantitative Analysis, 27(4), 575-589.

Devlin, J., Chang, M.-W., Lee, K., and Toutanova, K. (2019). BERT: Pre-training of deep bidirectional transformers for language understanding. NAACL-HLT.

Hutto, C. J., and Gilbert, E. (2014). VADER: A parsimonious rule-based model for sentiment analysis of social media text. Proceedings of ICWSM-14.

Lee, D. D., and Seung, H. S. (1999). Learning the parts of objects by non-negative matrix factorization. Nature, 401, 788-791.

Leetaru, K., and Schrodt, P. A. (2013). GDELT: Global data on events, location, and tone. ISA Annual Convention.

Lopez-Lira, A., and Tang, Y. (2023). Can ChatGPT forecast stock price movements? Return predictability and large language models. arXiv:2304.07619.

Loughran, T., and McDonald, B. (2011). When is a liability not a liability? Textual analysis, dictionaries, and 10-Ks. Journal of Finance, 66(1), 35-65.

Monroe, B. L., Colaresi, M. P., and Quinn, K. M. (2008). Fightin' words: Lexical feature selection and evaluation for identifying the content of political conflict. Political Analysis, 16(4), 372-403.

Palepu, K. G. (1986). Predicting takeover targets: A methodological and empirical analysis. Journal of Accounting and Economics, 8(1), 3-35.

Powell, R. G. (2001). Takeover prediction and portfolio performance: A note. Journal of Business Finance and Accounting, 28(7-8), 993-1011.

Routledge, B. R., Sacchetto, S., and Smith, N. A. (2013). Predicting merger targets and acquirers from text. Working paper, Carnegie Mellon University.

Tetlock, P. C. (2007). Giving content to investor sentiment: The role of media in the stock market. Journal of Finance, 62(3), 1139-1168.

Data sources: S&P Capital IQ transactions database. SEC EDGAR full-text search. GDELT DOC 2.0 API.
