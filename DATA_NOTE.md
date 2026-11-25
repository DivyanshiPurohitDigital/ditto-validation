# Data note (synthetic_v1, generator 1.0.0, engine 1.0.0)

## Purpose

The data lets the build test hard-eligibility rules, weighted scoring, explanations and a fairness check on records that can never be mistaken for real activity. It is not evidence that UK small businesses struggle to find creatives, that matching helps, or that anyone would pay.

## Scope

200 synthetic creatives and 100 synthetic briefs. UK regions and cities only. Currencies GBP, EUR and USD. No real people, businesses, brands, scraped content, credentials, awards, client lists or protected characteristics. Every record carries `is_demo=true`, `data_source=synthetic_v1`, the seed, the generator version and the reference date (2026-11-25).

## Generation method

One seeded `random.Random` drives every draw in a fixed order. Creative day rate = discipline typical rate (A01) x seniority multiplier (A03) x lognormal noise (A04), clamped (A05) and set at the currency's nominal level (A07). Brief budgets are drawn log-uniformly within each project type's range (A15). Hard cases are planted with exact quotas (A22): budget below market, deadline too tight, rare skill combination, thin location. Exactly 25% of creatives have collaboration goals and communication preferences set to null (A24). Money is stored as integer minor units with an explicit currency and is never converted.

## Constraints asserted at runtime (16 checks)

Counts 200 and 100. Unique ids. Essential skills inside required skills. Budget minimum at or below maximum. Creative minimum budget at or below preferred budget. Deadline after earliest start. Availability end after start. Currencies GBP, EUR or USD. Money fields are non-negative integers. No protected-attribute field names. Emails on example.com or example.invalid. Demo flag and provenance on every record. Hybrid and on-site briefs have a location. URLs on example.invalid. Simulated consent on every brief.

## Assumption register: data generation

Confidence: H high, M medium, L low, VL very low. Evidence sources are listed at the end. "Hypothesis" means the author chose the value and no source supports it.

| ID | Assumption | Value used | Basis | Conf. | Effect if wrong |
|---|---|---|---|---|---|
| A01 | Typical UK day rate by discipline (GBP) | Graphic and brand 372; illustration 359; UX/UI 448; copywriting 408; content writing 339; social 326; photography 475; video 427; motion 385; brand strategy 494; art direction 409; 3D 430 | YunoJuno 2026 rates report; Malt UK for UX. These are platform averages that lean towards agency and enterprise buyers | M | Budget fit shifts. If small-business rates are lower, too many briefs fail on budget |
| A01b | Front-end development and audio rates | 400 each | Hypothesis | L | Fill rates for website and podcast briefs distort |
| A02 | Discipline mix of creatives | See `DISCIPLINE_WEIGHTS` in the generator | Hypothesis | L | Supply per project type changes |
| A03 | Seniority shares and rate multipliers | 20/40/30/10 for junior, midweight, senior, lead; multipliers 0.70, 0.90, 1.02, 1.10 | Shares: hypothesis. Multipliers: YunoJuno design rates by experience | L | Rate spread and budget eligibility change |
| A04 | Rate dispersion | Lognormal, sd 0.15 | Hypothesis | L | Width of the budget-fit boundary changes |
| A05 | Rate floor and ceiling | 0.5x and 1.9x the typical rate | Ceiling from the YunoJuno top-decile design rate. Floor: hypothesis | L | Extremes and below-market briefs change |
| A06 | Currency share | Creatives 85/10/5 GBP/EUR/USD; briefs 90/7/3 | Hypothesis | VL | Number of currency exclusions changes |
| A07 | Nominal price level for new amounts in other currencies | EUR 1.15, USD 1.25 | Hypothesis. Not an exchange rate. Never applied to an existing amount | VL | Non-GBP budget fit is unreliable. Tests currency handling, not EUR or USD economics |
| A08 | Regional distribution of creatives | London 30.3, South East 16.0, North West 9, East 8, South West 7, Scotland 7, West Midlands 6, Yorkshire 5.7, East Midlands 4, Wales 3, North East 2, Northern Ireland 2 | DCMS employment estimates 2025 and House of Lords Library for the larger regions. The rest is hypothesis. Measures all creative-industry jobs, not freelancers | M | On-site and hybrid viability by region changes |
| A09 | Regional distribution of briefs | London 18, South East 15, others per code | London and South East from DBT business counts via secondary sources. The rest is hypothesis | L | Local demand changes |
| A10 | Creative work mode | Remote 45, hybrid 40, on site 15 | Hypothesis. ONS data covers all workers, not creatives | L | Location filter strictness changes |
| A11 | Brief work mode | Remote 50, hybrid 35, on site 15 | Hypothesis | L | Same as A10 |
| A12 | Days per week available | 1:5, 2:15, 3:25, 4:25, 5:30 percent | Hypothesis | VL | Capacity changes |
| A13 | Share available immediately | 30% | Hypothesis | VL | Urgent briefs look easier than they are |
| A14 | Availability start and window length | Start 1 to 60 days ahead; window 30 to 180 days | Hypothesis | VL | Deadline-fit rates change |
| A15 | Project budget ranges (GBP) | Logo 500 to 5,000; website 1,500 to 10,000; social 300 to 2,500; product photography 300 to 2,000; promo video 1,500 to 6,000; explainer 3,000 to 10,000; copywriting 500 to 3,000; packaging 1,000 to 6,000; pitch deck 500 to 3,000; illustration 400 to 3,000; podcast 500 to 3,000; 3D 1,000 to 6,000 | Supplier pricing pages for the first six, with conflicting low ends. The rest is hypothesis | L | Budget eligibility is the parameter most likely to be wrong |
| A16 | Effort in working days per project type | Logo 3 to 10; website 8 to 25; others per code | Hypothesis | L | Budget and availability checks are mis-sized |
| A17 | Calendar duration, at least ceil(effort x 7/4) for normal briefs | See code | Hypothesis | L | Normal briefs easier or harder than real ones |
| A18 | Project type mix | Logo 16, website 16, social 14, photography 10, video 9, copy 9, explainer 6, deck 6, packaging 5, illustration 4, 3D 3, podcast 2 | Hypothesis | L | Demand by discipline changes. Content writing and front-end development have no demand, so those creatives never appear |
| A19 | Sector mix of briefs | See `SECTORS` | Loosely informed by DBT sector shares, weighted towards consumer-facing sectors by hypothesis | L | None modelled. Low impact |
| A20 | Size bands of briefs | No employees 35, 1 to 9 40, 10 to 49 20, 50 to 249 5 | Hypothesis | L | None modelled. Low impact |
| A21 | Brief earliest start | 7 to 60 days after the reference date | Hypothesis | VL | Availability overlap changes |
| A22 | Planted hard cases | Normal 70, budget below market 10, deadline too tight 8, rare skill combination 6, thin location 6 | Hypothesis | L | The baseline fill rate is set by design. Do not read it as a market rate |
| A23 | Portfolio URL present | 60% | Hypothesis | VL | Missing-field handling tests change |
| A24 | Creatives with missing optional fields | Exactly 25% | Hypothesis | VL | Null-handling tests change |
| A25 | Willingness to pay a service fee | Would pay 25, would pay if the shortlist is useful 35, unsure 20, would not 20 percent | Hypothesis | VL | Says nothing about real willingness to pay. Do not report it |
| A26 | Fee amount | 25 to 150 in the brief's currency at nominal level | Hypothesis | VL | Same as A25 |
| A27 | Skill taxonomy | 14 disciplines, 5 or 6 skills each | Author construction | M | Skill matching granularity changes |
| A28 | Style tag taxonomy | 18 neutral aesthetic tags | Author construction, non-protected | M | Style-score sensitivity changes |
| A29 | Money rounding | Nearest 5 major units, minimum 5 | Convention | H | Negligible |
| A30 | Secondary skill probabilities | 0.3 per adjacent discipline; 0.4 chance of an extra skill on a brief | Hypothesis | L | Rare-skill coverage changes |
| A31 | Original scoring weights | 30/20/20/15/15 including goals and preferences | Superseded by the PRD v2 weights (E01). Not used | n/a | None |
| A32 | Reference date | 2026-11-25, overridable | Project instruction | H | None |
| A33 | Share of small businesses that buy creative services | Not used. Every brief is a buyer by construction | The latest official figure is 19% commissioning external design agencies (Design Council, 2005 to 2006) | VL | The data cannot estimate demand |

## Assumption register: engine

| ID | Assumption | Value | Basis | Effect if wrong |
|---|---|---|---|---|
| E01 | Score weights | Skills 40, budget 25, availability 20, style 15 | PRD v2. Untested starting points | Rankings change. The hard-constraint feasible set does not |
| E02 | Skills score | Share of the brief's required skills the creative lists. Essential skills are a hard gate | Design choice | A creative who lists more skills gains. Self-declared lists can be inflated |
| E03 | Budget score | Cost = day rate x estimated effort days. 1.0 at or below the budget minimum, 0.5 at the maximum, 0 at 1.5x the maximum. The 0.5 floor is a hypothesis | Design choice | Cheaper creatives gain exposure inside the range |
| E04 | Availability score | Capacity ratio x start factor. Capacity = overlap days x days per week / 7. Feasible when capacity is at least the effort. Start factor = 1 minus lateness over the brief window | Design choice | Late starters lose score even when they fit |
| E05 | Style score | Share of the brief's style tags the creative lists. A creative with no tags scores 0. A brief with no tags drops style and rescales the other weights for every creative | Design choice | Incomplete creative profiles are penalised |
| E06 | Hard gates | Currency match, every essential skill, location (a hybrid or on-site brief needs a non-remote creative in the brief's region), complete profile | Project rules: never compare currencies, never let a score override a critical incompatibility | The 200-creative pool is thin for local briefs |
| E07 | Ranking order | Feasible first, then score, then SHA-256 of seed, brief id and creative id | Design choice | A feasible match can outrank a higher-scoring infeasible one. Ties never favour an id |
| E08 | Reason wording | A component at or above 0.6 is described as a strength | Design choice | Wording only |
| E09 | Fairness review band | Lift outside 0.67 to 1.5 is flagged for review. Groups under 10 creatives are marked low power | Hypothesis | Flags are prompts for review, not findings |
| E10 | Fairness benchmark | Expected slots for each candidate = 5 divided by the candidate pool, counted only on briefs with more than 5 candidates | Design choice | Where 5 or fewer compete, ranking has no effect on exposure |
| E11 | Brief validation | Rejected: missing required fields, unsupported currency, unknown work mode, budget minimum above maximum, budget maximum at or below 0, effort at or below 0, deadline not after start, invalid dates, essential skills outside required skills | Found by test cases 7 to 9 | Invalid briefs would otherwise be scored |
| E12 | Audit groups | Discipline, region, seniority band, currency and work mode are read only by the audit, never by scoring | Fairness rule | Verified by test case 10 |

## Simulated shortlist rule

The PRD asks for the shortlist rule to sit in this note. A simulated owner shortlists a top-five match when it meets the rule. A brief counts as shortlisted when at least one of its top five is shortlisted. The rules read score components, never the weighted total, so changing a weight does not change who is shortlisted.

- S1 (headline): the match fits budget and deadline and covers at least half of the required skills.
- S2: fits budget and deadline and covers every required skill.
- S3: fits budget and deadline, covers every required skill and shares at least one style tag.

The thresholds are hypotheses. The rule tests supply on synthetic data. It does not predict what an owner would do.

## Bias and fairness notes

- No field holds age, gender, ethnicity, religion, disability or another protected characteristic. The generator rejects field names on a protected list.
- Names are numbered placeholders, which avoids cultural or gender signals.
- Seniority is about experience and is labelled a hypothesis. It is never read by scoring.
- The data leans towards London (A08). On-site matching favours London.
- Region and day rate could act as proxies in real data. Audit shortlist outcomes by region and rate before any live use.

## What the data can and cannot establish

It can exercise eligibility rules, scoring, explanations, null handling, currency isolation and the fairness check. It cannot show that small businesses struggle to find creatives, that they would pay a fee, what real fill rates are, or that matching helps. Baseline fill rates are produced by the assumptions above.

## Reproducibility

`python3 ditto_synth.py --seed 20261125 --reference-date 2026-11-25` then `python3 ditto_match.py`. Sorted JSON keys and no runtime timestamps. The same seed, reference date and Python minor version produce identical files.

## Evidence used

Accessed 25 November 2026. Platform averages and supplier pages are weak evidence.

- YunoJuno 2026 freelancer rates report: https://www.yunojuno.com/freelancer-rates-report
- Malt UK average freelance rates: https://www.malt.uk/t/average-freelance-rates/graphic-digital-design/ux-designer
- DCMS Sector Economic Estimates, Employment, 2025: https://www.gov.uk/government/statistics/economic-estimates-employment-january-2025-to-december-2025-for-dcms-sectors/dcms-sector-economic-estimates-employment-january-2025-to-december-2025
- House of Commons Library, Business statistics: https://researchbriefings.files.parliament.uk/documents/SN06152/SN06152.pdf
- Design Council, The Value of Design Factfinder: https://www.designcouncil.org.uk/fileadmin/uploads/dc/Documents/TheValueOfDesignFactfinder_Design_Council.pdf
- Supplier pricing guides for project budgets (low quality, conflicting): https://www.meetbob.co.uk/how-much-does-branding-cost-uk/ and https://www.graphicsmonkey.co.uk/blog/how-much-does-professional-graphic-design-cost

## Change log

- 1.0.0 (2026-11-25): generator A01 to A33. Engine E01 to E12. Shortlist rule S1 to S3.
- 1.0.1 (2026-11-25): SQL layer (`queries.sql`, `ditto_sql.py`) reconciles to the Python engine. Tie-break values are computed in Python and loaded, because SQLite has no SHA-256. Commercial model inputs are hypotheses, listed in `ditto_commercial_model.xlsx`. No change to generated data or scoring.
