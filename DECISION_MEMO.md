# Decision memo: build, adapt or leverage

Synthetic data only. No live users. This memo records why the matching is rule-based today and where an AI model could be added later.

## Decision

Build deterministic, rule-based scoring now. Do not use a model for ranking. Consider adapting an existing LLM for one narrow task later, parsing a free-text brief into structured fields, and only with an evaluation.

## Options

| Option | Value | Feasibility | Limits |
|---|---|---|---|
| Build rule-based scoring (chosen) | Every score and reason traces to inputs. No data needed to start. Free to run | Built and tested | Weights are guesses. Skills are self-declared. Cannot learn |
| Adapt an existing LLM to parse briefs | Owners write free text, so intake is easier | Possible. Needs an evaluation set and a paid or rate-limited API, which the PRD rules out for now | Can misread a brief. Needs a human check |
| Leverage embeddings or an off-the-shelf recommender | May catch similar skills the rules miss | Needs real match outcomes to judge | Harder to explain. Fairness is harder to audit. No outcome data exists |
| Use an existing marketplace's matching | No build effort | Not available for this concept | No control over the logic |

## Why rule-based first

- The first question is whether a brief can return matches an owner can understand and challenge. A model cannot answer it without outcome data, and there is none.
- Explainability is a requirement. All 233 reasons are rebuilt from stored components and checked.
- Testing is direct. Ten cases ran against expected results, and two defects were found and fixed.
- No protected attribute is used. A test confirms that name, email, seniority and city change no ranking.

## What the build showed

- Only 19 of 100 synthetic briefs have any creative who fits budget and deadline. Supply and the budget and effort assumptions limit the result more than the scoring does.
- Coverage is capped at 50%. 100 of 200 creatives pass the hard gates for any brief.
- An injected creative who lists every skill reaches 56% of briefs. Self-declared skill lists are a risk, and the engine has no exposure cap.

## Where an LLM could help, and how to judge it

- **Task:** turn a free-text brief into required skills, budget, dates and region.
- **Evaluation:** 30 briefs labelled by hand. Measure field accuracy, count invented skills, and require a human to confirm before scoring.
- **Rule:** the model proposes fields. The deterministic engine scores them. The score never comes from a model.
- **Stop rule:** do not use it if invented fields exceed an agreed limit, or if owners say they prefer the form.

## Responsible AI checks

- Data quality: accuracy, completeness and bias of skills and rates. Self-declared data is unverified.
- Fairness: exposure spread, coverage and lift against a random draw, reviewed by group.
- Transparency: a reason for every match, and a message for every non-match.
- Human control: the owner decides. Nothing is automated beyond ranking.

## What would change this decision

- Real match outcomes at volume, which would let a learned ranker be tested against the rules.
- Interview evidence that owners cannot complete the form.
- Evidence that rule-based matches miss relevant creatives.

## Limits

This memo reflects a synthetic build and my assumptions. It is not evidence about a real market.
