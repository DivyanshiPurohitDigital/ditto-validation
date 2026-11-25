# User stories and acceptance criteria

Synthetic data only. Every story maps to a test in `TEST_LOG.md`, a built-in engine check, or a scripted page check. Status is stated plainly: a story marked built has been tested in a scripted DOM and in Python, not on a real device and not with a real user.

## Built

**US1. See five matches for my brief.** As an owner, I want to enter a brief and see the five best creatives, so that I do not sift portfolios.
- Given a valid brief, when I tap Find matches, then I see up to five creatives ranked, each with a score out of 100 and four component scores (skills, budget, availability, style).
- Given the same brief entered in the browser and run in Python, then both return the same top five, scores and reasons.
- Evidence: page checks (example brief returns 5 cards; all 100 example briefs equal the Python top five); parity check, 233 matches, 0 differences.

**US2. Understand why a creative was matched.** As an owner, I want a plain-language reason, so that I can challenge it.
- Given a match, then the reason names what it matched on and where it is weaker, with figures from its scores.
- Given a creative missing a required skill, then the reason names the missing skill.
- Given a brief with no style tags, then the reason says style was not scored.
- Evidence: engine check that every reason rebuilds from its stored components (233 of 233); case 6.

**US3. Never see a creative who cannot do the job.** As an owner, I want impossible matches removed, so that I do not waste time.
- Given an essential skill, then no match lacks it.
- Given a GBP brief, then no EUR or USD creative appears, and no amount is converted.
- Given a hybrid or on-site brief, then every match is non-remote and in the brief's region.
- Given a creative with a missing day rate or skills, then the creative is excluded.
- Evidence: engine checks (every match passes the hard gates; no cross-currency match); cases 5 and 9.

**US4. Know when nothing fits.** As an owner, I want a clear message, so that I know what to change.
- Given no creative passes the hard gates, then I see zero matches and the gate that emptied the pool, for example "none has every essential skill".
- Given candidates exist but none fit budget and deadline, then they are shown, marked "Does not fit budget or deadline", with the percentage over budget.
- Evidence: cases 1 and 3.

**US5. See affordable, available creatives first.** As an owner with a fixed budget and deadline, I want matches that fit to rank first.
- Given a mix of candidates, then every match that fits budget and deadline ranks above every match that does not, even when its score is lower.
- Given such a mix, then the page says a lower card can show a higher score.
- Evidence: engine check (feasible first, then score); page message.

**US6. Be told when my brief is invalid.** As an owner, I want bad input rejected, so that I do not get misleading matches.
- Given a budget minimum above the maximum, an effort of 0 days, a deadline on or before the start, invalid dates, an unsupported currency, or essential skills outside the required skills, then I see "Brief is not valid" with the reason and no matches.
- Evidence: cases 7, 8 and 9 (two defects found and fixed); page checks.

**US7. Ties never favour a creative.** As an analyst, I want ties broken neutrally, so that no creative gains from its id or position.
- Given identical scores, then order is the same whatever the input order, does not follow creative id, and changes with the tie-break seed.
- Evidence: case 2; engine tie check.

**US8. Irrelevant fields never change a ranking.** As a creative, I want name, email, portfolio, seniority, discipline and city ignored by scoring.
- Given those fields are scrambled across all creatives, then no top-five list changes for any of the 100 briefs.
- Evidence: case 10; engine invariance check.

**US9. See whether the matching is working.** As a product analyst, I want the metrics screen, so that I can judge the build against the PRD.
- Given all 100 briefs, then the screen shows shortlist rate, most exposed creative, coverage and share of reasons built from components, each against its target with pass or miss.
- Then it states the ceilings that cap two of them.
- Evidence: page checks (four stat cards; chart with 73 bars); fairness report.

**US10. Spot a creative who dominates.** As an analyst, I want the exposure guardrail to flag a dominating creative.
- Given one creative reaches more than 20% of briefs, then the guardrail reports a miss and names the creative.
- Evidence: case 4 (an injected creative reaches 56% of briefs and is flagged). Detection is built. Mitigation is not.

## Backlog (not built)

- **B1. Creative profile intake.** Given a creative enters skills, day rate, availability, region and style tags, when they consent, then the profile is stored and can be matched.
- **B2. Consent and privacy notice.** Given any real participant data is collected, then a notice names the controller, what is collected, why and how long it is kept, before consent is taken. Not built. Until it exists, the build stays in demo use.
- **B3. Exposure cap.** Given a creative has reached its share of recent briefs, then ranking reduces its exposure. Design needs interview evidence and real usage (open item O1).

## Traceability

| Story | Tests |
|---|---|
| US1 | Page checks; parity check (233 matches) |
| US2 | Engine reason check; case 6 |
| US3 | Engine gate and currency checks; cases 5 and 9 |
| US4 | Cases 1 and 3 |
| US5 | Engine ordering check; page message |
| US6 | Cases 7, 8, 9; page checks |
| US7 | Case 2 |
| US8 | Case 10 |
| US9 | Page checks; fairness report |
| US10 | Case 4 |
