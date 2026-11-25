# Market plan (hypotheses)

Synthetic build, no live users. Facts from outside the build were read on 25 November 2026 and carry their sources. Everything else is my assumption and is labelled. The inputs are in `ditto_commercial_model.xlsx`.

## The question

Can a curated matching service for independent creatives become a viable two-sided marketplace? The build tests the matching logic. This plan tests whether the economics could work if the logic does.

## What the build says about supply

- Only 19 of 100 synthetic briefs have any creative who fits budget and deadline.
- Remote briefs do far better than local ones: 43 of 45 remote briefs have a candidate, against 17 of 55 hybrid or on-site briefs.
- Half the creatives can never appear, because no brief needs their skills, they price in a currency no brief uses, or no local brief exists for them.
- Reading: with 200 creatives, liquidity limits the result more than ranking does. A real launch would start remote-first, in a few disciplines, with a curated pool.

## Published fees for context

| Platform | Charged to | Fee reported | Caveat |
|---|---|---|---|
| Upwork | Client | Marketplace fee up to 7.99% on the free plan | Upwork support page. Other pages show lower rates for some clients |
| Upwork | Freelancer | Variable fee, reported 0% to 15% per contract | Range comes from third-party sites. Some report a flat 10%. Unverified |
| Fiverr | Seller | 20% of each order | Fiverr community blog and many third-party sites |
| Fiverr | Buyer | 5.5% service fee plus a small-order fee | Third-party guide. Threshold varies |
| Malt | Freelancer | Usually 5% excluding tax | Reported for France. UK terms not checked |

Not researched: PeoplePerHour and YunoJuno fees, matching methods and transparency features, and take rates of listed marketplaces from their filings. Sources are in the Benchmarks sheet of the model.

## Market size (ranges, not a forecast)

UK businesses with 1 to 249 employees: about 1.41 million (Department for Business and Trade estimates for 2025, size bands read via a secondary source). Businesses with no employees are excluded because many are freelancers.

| | Low | Base | High |
|---|---|---|---|
| Share buying creative services in a year | 5% | 10% | 19% |
| Projects per buyer per year | 1 | 2 | 3 |
| Annual creative project spend (base, GBP) | | about 597 million | |
| Ditto share reached | 0.1% | 0.5% | 1% |
| Ditto project value per year (base, GBP) | | about 3.0 million | |
| Ditto revenue per year at 10% take (base, GBP) | | about 0.3 million | |

The 19% is the latest official figure I found: businesses commissioning external design agencies in 2005 to 2006 (Design Council). It is outdated. The other shares, the projects per buyer, the share reached and the average project value (about £2,118, from synthetic budget ranges) are hypotheses. The output moves almost one for one with each of them, so treat the size as an order of magnitude only.

## Unit economics on the base hypotheses

- One brief yields about £101 of project value (19% shortlisted, 25% hired, £2,118 average).
- At a 10% take rate that is about £10 of revenue, about £3 of processing cost and about £24 of acquisition cost per brief (60% from new owners at £40 each).
- Base-case monthly contribution is about minus £2,000. The low case is about minus £2,600. The high case is about plus £3,450.
- Break-even needs about 16 hires per 100 briefs (the base case gives about 5), or acquisition cost near zero. With zero acquisition cost, break-even is about 43 briefs a month.
- Reading: the model is most sensitive to hires per brief and acquisition cost, not to the take rate. Interviews should test how often a shortlist becomes a hire and how owners would be reached.

## Pricing options to test

- Take rate on project value. Published rates range from about 5% to 20% depending on the side and platform.
- Flat fee per delivered shortlist. The synthetic assumption is £25 to £150 and has no evidence.
- Subscription for creatives. Not modelled.

Ask in interviews what owners and creatives have paid for matching and what felt fair.

## Regulation and responsible AI (not legal advice)

- **UK.** The Data (Use and Access) Act 2025 replaced Article 22 of the UK GDPR with Articles 22A to 22D. Law-firm summaries report that section 80 came into force on 5 February 2026, and the ICO says all the Act's data protection provisions are now in force (updated 19 June 2026). Solely automated significant decisions are allowed with safeguards, and the restriction on using special category data in them remains. In Ditto the owner makes the decision and the engine ranks. Whether any step is a "significant decision" or "solely automated" is a legal question to confirm.
- **EU.** Annex III point 4 of the EU AI Act covers "employment, workers' management and access to self-employment". A law-firm summary of the Commission's draft guidelines says freelancers and platform workers are in scope. The Digital Omnibus on AI moved the Annex III obligations from 2 August 2026 to 2 December 2027, according to several law-firm sources. A matching engine for freelancers could fall in scope for EU users. I have not assessed it. Ditto is UK-first and synthetic.
- **Design response, not a compliance claim:** a reason for every match, a human decision, no protected attributes read by scoring, an exposure audit and a test log.

## Markets angle (my reasoning, not evidence)

A matching engine is the core of an exchange, and the same questions apply.

- **Liquidity:** thin pools produce no matches. The 19-of-100 result is a liquidity result.
- **Price discovery:** day rates and budgets are the price signal. Ditto compares cost with budget and never converts currency.
- **Priority rules:** exchanges publish how orders are prioritised. Ditto's rule is fits budget and deadline first, then score, then a neutral seeded tie-break, and every match shows its reason.
- **Concentration:** one creative reaching 56% of briefs in a stress test is a market-power risk, and the exposure audit flags it.
- Link to my dissertation: marketplace acquisitions can be tested as a subset of my AI-startup acquisitions dataset. I have not done this. Nothing here describes any exchange's systems.

## What the interviews will change

| Evidence | Model input |
|---|---|
| Budgets quoted by project type | Average project value |
| Whether a shortlist led to a hire | Shortlist-to-hire conversion |
| How owners found creatives | Acquisition cost per owner |
| Fees paid for matching | Take rate and flat fee |
| Remote against local | Share of briefs that can be remote |

## Sources

- https://www.gov.uk/guidance/data-use-and-access-act-2025-data-protection-and-privacy-changes
- https://ico.org.uk/for-organisations/adm/
- https://www.legislation.gov.uk/ukpga/2025/18/section/80/enacted
- https://publicationportalpreview.hoganlovells.com/en/publications/ai-and-automated-decisionmaking-in-the-uk-part-i-the-new-rules-and-regulatory-guidance
- https://natlawreview.com/article/eu-digital-omnibus-ai-enters-force
- https://knowledge.dlapiper.com/dlapiperknowledge/globalemploymentlatestdevelopments/2026/The-Digital-AI-Omnibus-Proposed-deferral-of-high-risk-AI-obligations-under-the-AI-Act
- https://www.mccannfitzgerald.com/knowledge/technology/employment-spotlight-eu-ai-act-draft-guidelines-on-high-risk-ai-classification
- https://support.upwork.com/hc/en-us/articles/4660220468499
- https://support.upwork.com/hc/en-us/articles/211062538
- https://community.fiverr.com/public/blogs/buyers-guide-understanding-fiverrs-payment-process-2025-05-30
- https://wise.com/gb/blog/fiverr-payments
- https://www.expatica.com/fr/working/self-employment/best-apps-to-make-money-2174794/
- https://researchbriefings.files.parliament.uk/documents/SN06152/SN06152.pdf
- https://www.designcouncil.org.uk/fileadmin/uploads/dc/Documents/TheValueOfDesignFactfinder_Design_Council.pdf

## Limits

Synthetic build. Every model input is a hypothesis until the interviews are done. Competitor matching methods were not researched. The regulatory points are summaries from law-firm and regulator pages, and a lawyer should confirm them before any real launch.
