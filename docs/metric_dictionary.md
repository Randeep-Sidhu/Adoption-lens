# Metric dictionary

What every number in this project means. The SQL in `adoption_lens/sql/` implements these definitions, the pandas code
in `adoption_lens/reference.py` implements them again from scratch, and `tests/test_spec_sync.py` fails if the
thresholds written here stop matching the code.

## Conventions

| Term | Meaning |
|---|---|
| Sample | The Anthropic Economic Index samples about one million conversations per source for one week (5 to 12 February 2026). Every "conversation" below is a sampled conversation, not a user. |
| Source | `claude_ai` (Free, Pro and Max chat) or `api` (Anthropic's first-party API). The API file has global rows only. |
| Unclassified geography | `NONE`, `not_classified`, and any `-not_classified` subregion. These conversations have no usable location and are excluded from every geography metric. |
| Classified | Conversations that carry a real label for the facet in question. `none` and `not_classified` labels are excluded from denominators. |
| Minimum sample | A geography needs at least 200 conversations in the relevant denominator to appear in a metric, and a request category needs at least 30 conversations in that geography to get a location quotient. |
| Interval | 95% throughout, z = 1.96. Shares use the Wilson interval; differences use the Wald interval for two independent proportions; location quotients use the log-ratio interval. |
| Rest of parent | For a country, every other sampled conversation in the world. For a province or state, every other conversation in its country. The comparison group is the parent minus the geography, so the two groups never overlap. |

## m_geo_usage

Usage per resident, for countries and Canadian provinces.

- **Grain:** one row per country or province in the peer set.
- **Peer set:** countries with at least 200 conversations, a known country code and a World Bank total-population figure for 2024; provinces with at least 200 conversations and a Statistics Canada population estimate for 1 April 2026. Countries and provinces are indexed in separate peer sets, so the two indexes are not comparable with each other.
- **share_of_known:** conversations divided by all conversations in known-geography countries (for provinces: all conversations in the Canadian provinces).
- **per_100k:** conversations per 100,000 residents.
- **usage_index:** the geography's conversations per resident divided by the pooled rate of its peer set (sum of conversations over sum of population). 1.0 is the peer-set average. Population-weighted, the index averages exactly 1 within each peer set.
- **usage_index_lo / hi:** the index times (1 plus or minus 1.96 over the square root of conversations), a normal approximation to Poisson sampling.
- **Not the same as:** Anthropic's own Usage Index, which uses working-age population.

## m_shares

One long table of four shares per geography and source.

| metric | numerator | denominator |
|---|---|---|
| `work_share` | work | work + personal + coursework |
| `coursework_share` | coursework | work + personal + coursework |
| `automation_share` | directive + feedback loop | directive + feedback loop + learning + task iteration + validation |
| `success_rate` | yes | yes + no |

Automation is the directive and feedback-loop collaboration patterns; augmentation is learning, task iteration and validation. "None" and "not_classified" labels are left out. `success_rate` is a classifier label attached to a conversation, not something a person reported.

## m_vs_rest

Each country against the rest of the world and each subregion against the rest of its country, for every share in `m_shares`.

- Reported only when the comparison group has at least 200 conversations.
- `diff` is the geography's share minus the rest-of-parent share, with a Wald interval.

## m_request_mix

Which request categories a place over- or under-uses, at level 2 of the request taxonomy (26 categories for Claude.ai).

- **Grain:** country or province x category, Claude.ai only.
- **share:** category conversations over classified conversations in the geography (the `not_classified` category is excluded).
- **lq:** location quotient, the geography's share divided by the rest-of-parent share. Above 1 means over-represented.
- **Minimum:** the category needs at least 30 conversations in the geography.
- **is_finance_lens:** the category appears in `data/reference/finance_lens.csv`. The list is a judgement call: four categories about financial information, business analysis, legal and fraud work, and trading or financial software.

## m_platform_gap

API against Claude.ai at the global level, for the four shares. `diff` is API minus Claude.ai. The request taxonomies of the two sources do not overlap (one shared category name out of 22 and 26), so request mix is not compared across sources.

## m_function_exposure

Anthropic's observed exposure score by occupation, grouped by SOC major group (the first two digits of the occupation code).

- `mean_exposure` is the unweighted mean across the occupations in the group. It is not weighted by employment.
- `share_with_exposure` is the share of occupations with a score above zero.
- `rank_by_mean` uses standard competition ranking: tied groups share a rank and the next rank is skipped.
- `most_exposed_occupation` breaks ties alphabetically.

## Change control

A change to a definition means changing this file, the SQL, the reference implementation, the golden expected values in
`adoption_lens/golden.py` and, for a threshold, `adoption_lens/config.py`. The tests fail until all of them agree.
