# Northwind AI search visibility

> **Sample data. Every figure below was computed from synthetic answers written by the mock provider. No answer engine was called. These numbers are not measurements of a live brand.**

- Domain: `northwind.example`
- Focus run: 2026-11-20T00:00:00Z (`5359a2adad6e4527`)
- Engines: openai, perplexity
- Prompts in the focus run: 6
- Competitors: Contoso, Fabrikam

## Focus run

- Visibility: 79.9
- Mention rate: 11 of 12 (91.7%)
- Brand domain cited: 8 of 12 (66.7%)
- Mention share of voice: 42.3%
- Failed answers excluded: 0

## Visibility over time

```text
2026-09-01       Overall     ███████░░░   74.7
2026-10-15       Overall     ███████░░░   71.9
2026-11-20       Overall     ████████░░   79.9
2026-09-01       openai      ████████░░   82.0
2026-10-15       openai      ███████░░░   72.9
2026-11-20       openai      ███████░░░   74.3
2026-09-01       perplexity  ███████░░░   67.4
2026-10-15       perplexity  ███████░░░   70.8
2026-11-20       perplexity  █████████░   85.4
```

The same chart is in `visibility.svg`.

## Runs

| Recorded | Run | Visibility | Mentions | Sample |
| --- | --- | ---: | ---: | --- |
| 2026-09-01T00:00:00Z | `16df28ae312e4a43` | 74.7 | 11 of 12 | sample |
| 2026-10-15T00:00:00Z | `f58f11e7e1bd42d4` | 71.9 | 10 of 12 | sample |
| 2026-11-20T00:00:00Z | `5359a2adad6e4527` | 79.9 | 11 of 12 | sample |

## Share of voice

Mention share of voice is the brand's mentions divided by all mentions of the brand and the configured competitors. An answer that names three tracked brands counts three times, once each. Citation share is the same ratio over cited URLs whose host matches a tracked domain. Citations to anyone else are reported as other and are left out of the share. A run with no tracked mentions has no share.

| Name | Role | Mention share | Mentions | Citation share | Citations |
| --- | --- | ---: | ---: | ---: | ---: |
| Northwind | brand | 42.3% | 11 | 40.0% | 8 |
| Contoso | competitor | 38.5% | 10 | 40.0% | 8 |
| Fabrikam | competitor | 19.2% | 5 | 20.0% | 4 |

Tracked citations: 20. Other citations: 3.

## Prompt results

Detail is the focus run. `answers.csv` includes every run in this report.

| Prompt | Engine | Mentioned | Position | Sentiment | Score | Brand domain |
| --- | --- | --- | --- | --- | ---: | --- |
| best-hiking | openai | yes | 2 of 2 named | positive | 87.5 | yes |
| best-hiking | perplexity | yes | 1 of 2 named | negative | 75.0 | no |
| rain-jackets | openai | no | not mentioned | unmentioned | 0.0 | no |
| rain-jackets | perplexity | yes | 1 of 2 named | negative | 75.0 | no |
| northwind-vs-contoso | openai | yes | 2 of 3 | positive | 91.7 | yes |
| northwind-vs-contoso | perplexity | yes | mentioned, unranked | positive | 87.5 | yes |
| repairable | openai | yes | 1 of 3 | positive | 100.0 | yes |
| repairable | perplexity | yes | 1 of 3 | positive | 100.0 | yes |
| worth-it | openai | yes | 1 of 2 named | negative | 75.0 | no |
| worth-it | perplexity | yes | 2 of 2 named | positive | 87.5 | yes |
| fleece | openai | yes | 2 of 3 | positive | 91.7 | yes |
| fleece | perplexity | yes | mentioned, unranked | positive | 87.5 | yes |

## Answers

### best-hiking · openai

Prompt: What are the best hiking apparel brands for weekend trips?

Score: 100 × (0.40×1 + 0.25×0.5 + 0.20×1 + 0.15×1) = 87.5

Citations: https://northwind.example/journal, https://fieldnotes.example/roundup

```
Contoso and Northwind both come up for this. Northwind is a practical choice, while Contoso is easier to find in stores.
```

### best-hiking · perplexity

Prompt: What are the best hiking apparel brands for weekend trips?

Score: 100 × (0.40×1 + 0.25×1 + 0.20×0.2 + 0.15×0.4) = 75.0

Citations: https://contoso.example/reviews

```
Northwind looks polished in the photos, but owner writeups call the fit disappointing and the warranty poor. Contoso is described as more reliable for the same use. https://contoso.example/reviews
```

### rain-jackets · openai

Prompt: Which sustainable rain jacket brands are worth buying?

Score: 100 × (0.40×0 + 0.25×0 + 0.20×0 + 0.15×0) = 0.0

Citations: https://contoso.example/jackets, https://guides.example/roundup

```
1. Contoso is the name that comes up most often. https://contoso.example/jackets
2. Fabrikam is a reasonable alternative. https://guides.example/roundup
```

### rain-jackets · perplexity

Prompt: Which sustainable rain jacket brands are worth buying?

Score: 100 × (0.40×1 + 0.25×1 + 0.20×0.2 + 0.15×0.4) = 75.0

Citations: https://contoso.example/reviews

```
Northwind looks polished in the photos, but owner writeups call the fit disappointing and the warranty poor. Contoso is described as more reliable for the same use. https://contoso.example/reviews
```

### northwind-vs-contoso · openai

Prompt: How does Northwind compare with Contoso for everyday jackets?

Score: 100 × (0.40×1 + 0.25×0.666667 + 0.20×1 + 0.15×1) = 91.7

Citations: https://contoso.example/, https://northwind.example/fit, https://fabrikam.example/

```
1. Contoso is the reliable default. https://contoso.example/
2. Northwind is a solid alternative if you already like the fit. https://northwind.example/fit
3. Fabrikam is easy to find and unremarkable. https://fabrikam.example/
```

### northwind-vs-contoso · perplexity

Prompt: How does Northwind compare with Contoso for everyday jackets?

Score: 100 × (0.40×1 + 0.25×0.5 + 0.20×1 + 0.15×1) = 87.5

Citations: https://northwind.example/guide

```
Northwind is a dependable and comfortable option for this. The buying guide is straightforward. https://northwind.example/guide
```

### repairable · openai

Prompt: Where should I look for repairable outdoor clothing?

Score: 100 × (0.40×1 + 0.25×1 + 0.20×1 + 0.15×1) = 100.0

Citations: https://northwind.example/guide, https://contoso.example/, https://fabrikam.example/

```
For a question like this, a short list is more useful than a long survey.

1. Northwind is a reliable and thoughtful option. https://northwind.example/guide
2. Contoso is widely stocked, with an ordinary finish. https://contoso.example/
3. Fabrikam is the budget alternative. https://fabrikam.example/

Northwind is the one to start with if you want something repairable.
```

### repairable · perplexity

Prompt: Where should I look for repairable outdoor clothing?

Score: 100 × (0.40×1 + 0.25×1 + 0.20×1 + 0.15×1) = 100.0

Citations: https://northwind.example/guide, https://contoso.example/, https://fabrikam.example/

```
For a question like this, a short list is more useful than a long survey.

1. Northwind is a reliable and thoughtful option. https://northwind.example/guide
2. Contoso is widely stocked, with an ordinary finish. https://contoso.example/
3. Fabrikam is the budget alternative. https://fabrikam.example/

Northwind is the one to start with if you want something repairable.
```

### worth-it · openai

Prompt: Is Northwind worth it for someone who hikes a few times a year?

Score: 100 × (0.40×1 + 0.25×1 + 0.20×0.2 + 0.15×0.4) = 75.0

Citations: https://contoso.example/reviews

```
Northwind looks polished in the photos, but owner writeups call the fit disappointing and the warranty poor. Contoso is described as more reliable for the same use. https://contoso.example/reviews
```

### worth-it · perplexity

Prompt: Is Northwind worth it for someone who hikes a few times a year?

Score: 100 × (0.40×1 + 0.25×0.5 + 0.20×1 + 0.15×1) = 87.5

Citations: https://northwind.example/journal, https://fieldnotes.example/roundup

```
Contoso and Northwind both come up for this. Northwind is a practical choice, while Contoso is easier to find in stores.
```

### fleece · openai

Prompt: What are good mid-priced fleece brands?

Score: 100 × (0.40×1 + 0.25×0.666667 + 0.20×1 + 0.15×1) = 91.7

Citations: https://contoso.example/, https://northwind.example/fit, https://fabrikam.example/

```
1. Contoso is the reliable default. https://contoso.example/
2. Northwind is a solid alternative if you already like the fit. https://northwind.example/fit
3. Fabrikam is easy to find and unremarkable. https://fabrikam.example/
```

### fleece · perplexity

Prompt: What are good mid-priced fleece brands?

Score: 100 × (0.40×1 + 0.25×0.5 + 0.20×1 + 0.15×1) = 87.5

Citations: https://northwind.example/guide

```
Northwind is a dependable and comfortable option for this. The buying guide is straightforward. https://northwind.example/guide
```

## Cited domains

| Domain | Owner | Answers | URLs |
| --- | --- | ---: | ---: |
| contoso.example | Contoso | 8 | 3 |
| northwind.example | Northwind | 8 | 3 |
| fabrikam.example | Fabrikam | 4 | 1 |
| fieldnotes.example | other | 2 | 1 |
| guides.example | other | 1 | 1 |

## How the score is computed

Each successful answer is scored from 0 to 100. The score is 100 × (mention × 0.40 + position × 0.25 + sentiment × 0.20 + citation × 0.15). Mention is 1 when the brand name or an alias appears as a whole word, otherwise 0. Position is (N − rank + 1) / N when the brand is placed in a list of N items or among N tracked names in prose; a mention that is not ranked scores 0.5. Sentiment uses the sentences that name the brand: positive 1, neutral 0.6, negative 0.2, and 0 when the brand is absent. Citation is 1 when a cited host is the brand domain, 0.4 when the brand is mentioned but not cited, and 0 otherwise. Share of voice is separate and is not part of this score.

Mention, position, sentiment, and citation components are rounded to 6 decimal places before weighting. The weighted sum is multiplied by 100 and rounded half up to 1 decimal place. answers.csv stores the components, so the score can be recomputed from the file.

Answers that fail, including timeouts and HTTP errors, are stored with the error and left out of averages, mention rate, and share of voice. An outage is not treated as a visibility of zero.

Sentiment reads the sentences that name the brand and scores them with a small lexicon and a three-word negation window. A result above 0.2 is positive, below -0.2 is negative, and anything in between, including no polarity words, is neutral. A numbered or bulleted list of at least two items is treated as a ranking, top to bottom. A name that appears only outside that list is a mention with no rank. Host matching is a suffix check against the configured domain: `shop.brand.example` belongs to `brand.example`, and `brand.example.evil.test` does not.
