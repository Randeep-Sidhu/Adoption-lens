# Data sources

Everything in `artifacts/` is computed from the files below. Nothing is simulated.

## Usage data

| | Claude.ai | First-party API |
|---|---|---|
| File | `aei_raw_claude_ai_2026-02-05_to_2026-02-12.csv` | `aei_raw_1p_api_2026-02-05_to_2026-02-12.csv` |
| Rows | 425,257 | 195,156 |
| Size | 96,018,130 bytes | 43,957,174 bytes |
| SHA-256 | `9c53320b8732ac2e88fc2c95fbdefa02222f04333a41d4f4e947861409798cf1` | `b3bcd68e7f6d820ffbb50a3c53d71ec2a122556fc2a38226cd86951a054bd4c8` |
| Geography | Global, 100+ countries, subregions of many countries | Global only |

Published by Anthropic in the Anthropic Economic Index, `release_2026_03_24`, at Hugging Face revision
`7fc50b03e2bd9fc2a011794a96c2ac69e666fd40` (dataset `Anthropic/EconomicIndex`). Each file covers one week, 5 to 12
February 2026, and is a sample of about one million conversations. The release is pinned because it is the most recent one
that ships weekly raw files in this layout. The downloader checks both SHA-256 values and the loader refuses a file whose
columns differ from the ones listed in `adoption_lens/config.py`.

The data is released under CC-BY. This project is not affiliated with or endorsed by Anthropic.

> Massenkoff, M., Lyubich, E., McCrory, P., Appel, R., and Heller, R. (2026). *Anthropic Economic Index report: Learning
> curves.* https://www.anthropic.com/research/economic-index-march-2026-report

## Reference tables (`data/reference/`)

| File | What it is | Source |
|---|---|---|
| `population_wb_2024.csv` | Total population, 2024, 216 countries | World Bank indicator SP.POP.TOTL, through the `datasets/population` mirror on GitHub (ODC-PDDL). Retrieved 20 September 2026; the source file has SHA-256 `7d2dd6a17f5ed7916de1f89a9c116791e64d207f2e2f6ce47c57e1ab46f0088a`. Regional aggregates were dropped. |
| `countryInfo.txt` | Country names, ISO codes, continents | GeoNames (CC BY 4.0). Its population column is not used: the figures are from around 2018. |
| `ca_population.csv` | Population of Canada and its 13 provinces and territories on 1 April 2026 | Statistics Canada, *Canada's population estimates, first quarter 2026*, The Daily, 17 June 2026. Typed in by hand; a test checks that the provinces add up to the national total. |
| `job_exposure.csv` | Observed exposure score for 756 occupations | Anthropic Economic Index, `labor_market_impacts/job_exposure.csv`, copied unchanged. |
| `soc_major_groups.csv` | The 23 major groups of the Standard Occupational Classification | US Bureau of Labor Statistics, typed in by hand. Group 55 (military) has no occupations in the exposure file. |
| `territories.csv` | Overseas territories that the usage file lists both as a subregion of a country and as a country | ISO 3166-2, checked against the data by `python -m adoption_lens.investigate rollup`. |
| `finance_lens.csv` | Four request categories close to financial services work | My judgement. See the note in `metric_dictionary.md`. |

Countries with no World Bank figure (Taiwan and Réunion have enough conversations to matter) stay out of the usage
index and appear everywhere else.

## Test fixtures

`tests/fixtures/aei_slice_claude_ai.csv` (1,576 rows) and `aei_slice_api.csv` (70 rows) are rows copied from the two real
files, in the same layout, for 28 geographies. They let the test suite run without the 140 MB download. They are not a
random sample and should not be analysed.
