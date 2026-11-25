# Ditto v2: one-page PRD

**Status:** concept and analytics prototype on synthetic data. No live users. **Author:** Divyanshi Purohit. **Date:** 25 Nov 2026.

## Problem

Independent creatives and micro, small and medium-sized businesses (MSMEs) spend too long finding each other. Owners sift through portfolios with no clear link between their brief and a creative's skills, rate and availability. Creatives pitch for projects that do not fit. Both sides lose time before any work starts.

Hypothesis: a structured brief that returns scored, explained matches shortens the search. This build tests the logic on synthetic data only. No real user has confirmed the problem.

## Users

- **Owner:** runs an MSME with no design or marketing team, posts one project at a time, has a fixed budget and deadline.
- **Creative:** freelance designer, writer or video editor who lists skills, day rate, availability, area and style tags.

## Feature

The owner enters a brief: project type, skills needed, budget, start date, style, area. Ditto returns five ranked creatives. Each match shows its score and a plain-language reason, for example "Matched on branding and illustration, day rate within budget, available from your start date."

## Scoring

Rule-based and visible. Starting weights, to be tuned: skills 40%, budget 25%, availability 20%, style 15%. The score uses no personal attributes such as name, gender, age or nationality.

## Success metrics (synthetic data, 100 briefs against 200 creatives)

- **Primary: shortlist rate.** Share of briefs where a simulated owner shortlists at least one of the top five. The shortlist rule sits in the data note. Starting target: 80% or higher.
- **Exposure guardrail:** no creative appears in the top five for more than 20% of briefs, and at least 50% of creatives appear in at least one top five.
- **Explainability guardrail:** 100% of matches carry a reason generated from the actual score components.

## Out of scope

Payments, messaging, contracts, reviews, real users, live data, trained machine learning models.

## Test plan

Ten cases, including no match, tied scores, a budget below every rate, one creative who dominates the rankings, and missing fields. Each case logs expected result, actual result and fix.

## Risks and limits

- Synthetic data reflects my assumptions. Results show the logic works, not that the market behaves this way.
- Replacing synthetic data with real data can introduce bias that this build cannot detect.
- Weights and targets are untested starting points.

## Next, with real users

Interview five owners and five creatives before changing any weight.
