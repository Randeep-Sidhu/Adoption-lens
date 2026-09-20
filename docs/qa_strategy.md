# How the numbers are checked

The SQL in `adoption_lens/sql/` produces every figure. Six layers try to catch it being wrong, and a seventh test checks
whether those layers can actually see a bug.

| Layer | What it does | What it catches |
|---|---|---|
| Source checks | Verifies SHA-256 values and the column layout before anything is read | A changed or corrupted download |
| Data checks | 20 SQL checks on the raw rows: duplicates, nulls, negatives, percentages, sums to 100, count against percentage, country codes, roll-ups, coverage, reference tables | Problems in the data, as opposed to the code |
| Reconciliation | An independent pandas implementation, written from the definitions in `metric_dictionary.md` rather than from the SQL, recomputes every metric and is compared cell by cell | Logic errors in either version |
| Golden data | A hand-built dataset in the real file layout with expected values worked out on paper. Each geography exists to trigger one rule | Edge cases that never occur in the real file |
| Invariants | 18 properties that must hold whatever the data is, such as the population-weighted usage index averaging exactly 1 within its peer set | Errors that two implementations might share |
| Figure verification | Every number in the written brief is re-derived from the independent implementation. Any mismatch stamps the brief NOT VERIFIED | A wrong number reaching a reader |

## Can the layers see a bug?

Twenty-six defects are injected into the SQL one at a time, each a small change of the kind that happens in real work: a
wrong z-value, a denominator that includes unclassified rows, a comparison group that still contains the geography, a
guard removed. A defect counts as caught if reconciliation, an invariant or the hand-computed values flag it.

All 26 are caught. The real data alone catches 25. The one it misses, M25, swaps `RANK` for `DENSE_RANK` in the occupation
ranking. It goes unnoticed because no two occupation groups tie in the real file; the golden data has a tie on purpose and
catches it. Before I switched country populations to the World Bank figures, a second defect (M05) was also invisible on
the real data, because every country then had a population. Which bugs a real dataset happens to expose depends on the
dataset, which is why the golden data exists.

| Id | Defect | Reconciliation | Invariants | Hand-computed | Caught on |
|---|---|---|---|---|---|
| M01 | Confidence intervals use z = 1.645 instead of 1.96 | x |  | x | both |
| M02 | The lower Wilson bound drops its centre adjustment and no longer matches the upper bound | x |  | x | both |
| M03 | Conversations with no usable country are counted as a place | x | x | x | both |
| M04 | Tiny geographies enter the usage index | x |  | x | both |
| M05 | A country with no population stays in the peer set and inflates the pooled rate | x | x | x | both |
| M06 | Conversations per 100,000 residents is computed per million | x |  | x | both |
| M07 | The usage-index interval uses z = 1.645 | x |  | x | both |
| M08 | Provincial shares are divided by every subregion in the file, not the provinces | x |  | x | both |
| M09 | Automation share ignores the feedback-loop pattern | x |  | x | both |
| M10 | Validation conversations vanish from the denominator | x |  | x | both |
| M11 | Unclassified success labels count as failures | x |  | x | both |
| M12 | The 'none' use-case bucket is counted in the denominator | x |  | x | both |
| M13 | Shares are reported for geographies with almost no data | x |  | x | both |
| M14 | The 'rest of world' comparison group still contains the geography itself | x | x | x | both |
| M15 | Provinces are compared with the whole world instead of the rest of Canada | x |  | x | both |
| M16 | The interval for a difference ignores the variance of the comparison group | x |  | x | both |
| M17 | The 'not_classified' request bucket is treated as a use case | x |  | x | both |
| M18 | The location-quotient interval ignores sampling error in the comparison group | x |  | x | both |
| M19 | Location quotients are reported for categories with a handful of conversations | x | x | x | both |
| M20 | The comparison group for a category is the whole parent, not the parent minus the geography | x |  | x | both |
| M21 | The platform gap is Claude.ai minus API, the opposite of the label | x | x | x | both |
| M22 | The platform-gap interval uses only the Claude.ai variance | x |  | x | both |
| M23 | Mean exposure is taken over occupations that have any exposure | x | x | x | both |
| M24 | The median exposure is actually the mean | x |  | x | both |
| M25 | Ties in the exposure ranking do not leave a gap | x |  | x | golden data only |
| M26 | A comparison group of a handful of conversations is accepted | x |  | x | both |

Run one yourself with `python -m adoption_lens.investigate M14`. It reruns that defect on the real data and reports which
layer caught it, which metrics moved and the largest errors.

## Findings in the data

### Subregion counts that do not add up

For most countries the subregion counts add up exactly to the country count. Three do not:

| Country | Country count | Subregion sum | Gap | Territories listed twice | Unexplained |
|---|---|---|---|---|---|
| FR | 32,332 | 33,020 | 688 | GF=19, GP=77, MF=19, MQ=103, NC=47, PF=83, RE=340 | 0 |
| NL | 10,296 | 10,366 | 70 | AW=31, CW=39 | 0 |
| US | 222,372 | 223,004 | 632 | GU=26, PR=587, VI=19 | 0 |

Each gap equals the sum of the overseas territories that the file lists both as a subregion of the country (FR-971,
NL-AW, US-PR and so on) and as a country of their own. The check compares the gap with the territories in
`data/reference/territories.csv`, so a new discrepancy would fail it instead of being waved through.

### Other things worth knowing

- 18.4% of sampled Claude.ai conversations have no usable country. They are left out of every geography metric and stay in "rest of world".
- 1.07% of the sample is not accounted for by any country row, because small countries are not published.
- 9.0% of the published count cells hold fewer than 15 conversations.
- 46 confidence-interval lower bounds in the API file are negative for quantities such as hours, which cannot be. This is ordinary bootstrap behaviour near zero. Nothing here uses those columns, so it is reported as information rather than an error.
- Namibia's country code is `NA`. A default CSV reader turns it into a missing value, so the loader switches that off and a test covers it.
- The first version of the rest-of-parent comparison had no minimum size for the comparison group. Drilling into an injected defect showed subregions that are nearly all of their country, leaving a handful of conversations to compare against. A 200-conversation minimum removed 155 of 2,141 comparisons.
