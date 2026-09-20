# Canada GenAI usage brief

Week of 5 to 12 February 2026. Source: Anthropic Economic Index, roughly one million sampled Claude.ai conversations and one million first-party API conversations. Every figure below comes from the SQL metrics and was re-derived by a separate implementation before this brief was written.

## What stands out

**1. Canada is a high-use market.** Its 25,902 sampled conversations put it 6th of 115 countries on usage per resident (index 4.47, 95% band 4.41 to 4.52; 1.0 is the pooled average of those countries). Singapore is highest at 6.49.
*Reading it:* the index says how much a place uses the product relative to its population, not what share of people use it.

**2. Use per resident varies 3.8-fold across provinces.** British Columbia is highest (1.36) and Saskatchewan lowest (0.36, band 0.32 to 0.40). Provinces with fewer than 200 sampled conversations are left out.
*For an internal rollout:* a regional gap this size is a reason to check whether local enablement differs before assuming a product problem. That is a hypothesis to test, not a finding.

**3. Canadian use leans away from work.** 39.7% of Canadian conversations are work-related against 45.4% elsewhere, which is 5.7 points lower (95% interval -6.3 to -5.1). Coursework share is 2.4 points higher, and the automation pattern, where the person delegates a task and reviews the result, is less common (39.7% against 45.7%). Classified task success is 72.4% against 69.9%; the gap is statistically clear (interval +1.9 to +3.0 points).
*For an internal rollout:* consumer habits in Canada point toward personal and study use, so work-specific examples are the thing an enterprise assistant has to supply. Again a hypothesis.

**4. Some request types over- and under-index.** The most over-represented request category in Canada is "Assist with job applications, career transitions, and interview preparation" (index 1.37, band 1.30 to 1.45). The most under-represented is "Provide entertainment recommendations and sports information including schedules and results" (index 0.49, band 0.42 to 0.57). Of the 4 finance-adjacent categories I flagged, 1 over-index ("Provide financial information, tax guidance, and consumer purchase assistance") and 0 under-index.

**5. API usage looks different from chat.** In the first-party API sample 74.2% of conversations are work-related (Claude.ai: 45.2%), 79.7% follow an automation pattern (45.5%), and 50.5% are classified as successful (69.9%). A deployed, programmatic use case is a different thing to measure than a person chatting.

**6. Exposure differs by occupation group.** Business and Financial Operations ranks 5 of 22 groups on mean observed exposure (0.177); 86% of its occupations show any exposure. Its most exposed occupation is Market Research Analysts and Marketing Specialists (0.65). Computer and Mathematical ranks first.

## Read before quoting

- These are sampled, model-classified conversations, not a census of users. Small geographies carry wide bands.
- "Success" is a classifier label assigned to a conversation, not an outcome reported by the person.
- "Rest of world" means every other sampled conversation, including those with no usable country.
- One week of data: nothing here shows change over time.

---
*Verification: 53 of 53 figures matched the independent implementation.*
