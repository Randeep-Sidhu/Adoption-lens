# AdoptionLens

How does Canada use generative AI compared with the rest of the world? This project answers that from real data: Anthropic's public Economic Index, which samples about a million Claude.ai conversations and a million first-party API conversations for one week in February 2026.

I built it to practise the part of analytics work that comes after the query runs. Every metric is defined in writing, computed twice by independent code, and checked against numbers I worked out by hand. The written brief refuses to publish a figure it cannot re-derive. The dashboard is the small part; most of the effort went into the checks.

Two things to keep in mind. The unit is a sampled conversation, not a person. And this is public data about one AI product, not any organisation's internal usage.

## What it shows

Canada ranks 6th of 115 countries on conversations per resident. Its usage index is 4.47 (95% band 4.41 to 4.52), where 1.0 is the pooled average of the countries compared. Singapore is first at 6.49. Inside Canada the range is wide: British Columbia is at 1.36 and Saskatchewan at 0.36, which is 3.8 times lower, and their bands do not overlap.

Canadian conversations are less work-related than everyone else's, 39.7% against 45.4%, and the 95% interval on that gap runs from 5.1 to 6.3 points. The delegate-and-review pattern is also less common (39.7% against 45.7%). Relative to the rest of the world, Canadians ask more about job applications (1.37 times the share) and about financial and tax questions (1.20), and less about entertainment and sports (0.49).

API traffic is a different thing. 74.2% of API conversations are work-related against 45.2% in chat, and the classifier marks 50.5% of them successful against 69.9%. On occupations, Business and Financial Operations ranks 5th of 22 groups on mean exposure.

[`artifacts/brief.md`](artifacts/brief.md) is the full readout, and every number in it was re-derived by the second implementation before it was written.

## How the numbers are checked

Each metric exists twice. The SQL in `adoption_lens/sql/` (DuckDB) produces the outputs. A separate pandas implementation, written from the definitions in [`docs/metric_dictionary.md`](docs/metric_dictionary.md) rather than from the SQL, recomputes everything, and the two are compared cell by cell: 55,309 cells, no differences.

Two implementations written by the same person can share a misunderstanding, so there are two more layers. A small hand-built dataset in `golden.py` has its expected values worked out on paper, and each geography in it exists to trigger one rule (a country with no population, a state that is nearly all of its country, a tie in a ranking). Eighteen invariants check things that must hold whatever the data is, for example that the population-weighted usage index averages exactly 1 within its peer set. Twenty data checks run on the source files before any of that.

To find out whether those layers can see a bug at all, I break the SQL on purpose. Twenty-six defects, each a small change of the sort that happens in real work, are injected one at a time and each has to be caught. All 26 are. The real data alone catches 25; it misses a ranking function that stops leaving a gap after ties, because no two occupation groups tie in the real file. The golden data catches it. [`docs/qa_strategy.md`](docs/qa_strategy.md) has the full table.

## Things I ran into

- In France, the Netherlands and the US, subregion counts add up to more than the country count (by 688, 70 and 632). Each gap is exactly the overseas territories that the file lists both as a subregion and as a country. The data check verifies that instead of ignoring those three countries.
- The GeoNames population column is about eight years old (Canada at 37.1M). I switched country populations to the World Bank's 2024 figures, which moved Canada's index from 4.62 to 4.47 and left its rank at 6th. Taiwan and Réunion have no World Bank figure and are left out of the index.
- Comparing a province with "the rest of Canada" breaks down when the province is nearly all of the country, which happens in small countries. Drilling into an injected bug showed comparison groups with a handful of conversations. I added a 200-conversation minimum, which removed 155 of 2,141 comparisons.
- Namibia's country code is `NA`, which a default CSV reader turns into a missing value.
- 46 confidence-interval bounds in the API file are negative for quantities like hours. That is ordinary bootstrap behaviour near zero, and nothing here uses those columns.

## Running it

```
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m adoption_lens.fetch
python -m adoption_lens.pipeline
pytest
streamlit run streamlit_app.py
```

`fetch` downloads the two source files (about 140 MB) from a pinned Hugging Face revision and checks their SHA-256 values. They are not committed to the repository. Without them `pytest` skips the six tests that need the full files and runs everything else against a slice of real rows. The dashboard reads only what is committed (`artifacts/` and one reference table).

## Limits

- One week of data, so nothing here shows change over time.
- Conversations are sampled and labelled by a model. "Success" is a classifier label, not an outcome anyone reported.
- The usage index uses total population. Anthropic's own index uses working-age population, so the numbers are not comparable with theirs.
- Country populations are for 2024 and provincial ones for April 2026. The two are indexed in separate peer sets and should not be compared with each other.
- The finance-related request categories are a list I chose (`data/reference/finance_lens.csv`).
- Exposure scores are averaged across occupations without weighting by employment.
- This covers Claude only and says nothing about other tools.

## Layout

| Path | What is in it |
|---|---|
| `adoption_lens/sql/` | The metric layer, eight DuckDB files |
| `adoption_lens/reference.py` | The independent pandas implementation |
| `adoption_lens/golden.py` | Hand-built dataset and its expected values |
| `adoption_lens/mutants.py` | The 26 injected defects |
| `adoption_lens/dq.py`, `compare.py` | Data checks, reconciliation and invariants |
| `adoption_lens/readout.py` | The brief and its figure verification |
| `adoption_lens/fetch.py`, `pipeline.py`, `investigate.py` | Download, full run, drill-down on a finding or a defect |
| `streamlit_app.py` | The dashboard |
| `artifacts/` | Output of the last pipeline run: metric tables, brief, QA results |
| `data/reference/` | Small reference tables, sourced in `docs/data_sources.md` |
| `tests/` | The test suite, run by CI on every push |

## Credits

Usage and exposure data: Anthropic Economic Index, released by Anthropic under CC-BY. Massenkoff, Lyubich, McCrory, Appel and Heller (2026), *Anthropic Economic Index report: Learning curves*. This project is not affiliated with or endorsed by Anthropic. Populations: World Bank and Statistics Canada. Country names and codes: GeoNames (CC BY 4.0). Code is MIT licensed.
