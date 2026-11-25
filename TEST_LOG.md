# Test log

Synthetic data only. Run `python3 test_cases.py` after `python3 ditto_synth.py`. Each case states the expected result, the actual result and the fix.

First run: 7 of 10 cases passed. Two engine defects and one test-harness error. After the fixes: 10 of 10 pass.

| # | Case | Expected | Actual, first run | Fix | Actual, after fix |
|---|---|---|---|---|---|
| 1 | No match | Zero matches and a plain-language reason naming the essential skills as the blocker | PASS. 0 matches. "No match: 171 creatives list rates in GBP, but none has every essential skill (skill nobody lists)." | None needed | PASS |
| 2 | Tied scores | 30 identical creatives tie. Order is stable under input order, is not by id, and changes with the tie-break seed | PASS. One score (65.0). Stable under reversal. Not id-ordered. Seed changes the order | None needed | PASS |
| 3 | Budget below every rate | Candidates shown, all marked not feasible, reasons state the percentage over budget, brief note says nothing fits | PASS. 2 matches, 0 feasible | None needed | PASS |
| 4 | One creative dominates | A creative listing every skill, charging 50 GBP a day and always free ranks first wherever eligible, and the exposure guardrail reports FAIL | PASS as a detection test. The dominator ranks first in 56 briefs (56%). The guardrail reports FAIL | None. The engine has no exposure cap. Logged as open item O1 | PASS (flagged) |
| 5 | Missing fields on a creative | No exception. Missing day rate excludes the creative. Missing style tags score 0 with a stated reason | PASS | None needed | PASS |
| 6 | Brief with no style tags | Style weight 0, other weights rescale to sum 1, reason says style was not scored | PASS. Weights 0.471, 0.294, 0.235, 0 | None needed | PASS |
| 7 | Invalid budget range and effort | Budget minimum above maximum, and effort of 0 days, are rejected with no matches | FAIL. Both briefs were scored (status ok, 2 matches). A creative over budget could receive a budget score of 1.0 | Added validation to `brief_problem`: budget minimum above maximum, budget maximum at or below 0, effort at or below 0 | PASS |
| 8 | Invalid dates | Deadline on or before the start date is rejected with no matches | FAIL. Scored as a normal brief (status ok, 2 matches) | Added validation: deadline must be after the start date, dates must be valid ISO dates | PASS |
| 9 | Currency isolation and unsupported currency | No cross-currency match in any of the 100 briefs. A GBP brief switched to EUR returns EUR creatives only. JPY is rejected | FAIL. Test-harness error: no EUR brief in the data had candidates, so the case raised an exception before reaching the engine. Engine behaviour for JPY before the fix was not observed | Rewrote the case to switch a GBP brief to EUR. Added validation: only GBP, EUR and USD are accepted | PASS |
| 10 | Protected-field invariance | Scrambling name, email, portfolio, seniority, discipline and city changes no top-five list across 100 briefs | PASS | None needed | PASS |

## Other checks run

- Generator: 16 constraint checks pass (counts, unique ids, essential skills inside required skills, budget minimum at or below maximum, deadline after start, valid currencies, integer minor units, no protected fields, reserved email domains).
- Engine: 13 built-in checks pass (weights sum to 1, ranks 1 to 5, no repeated creative, feasible-first ordering, every match passes the hard gates, no cross-currency match, every reason rebuilds from its stored components and the score equals the weighted sum, field invariance, input-order independence, tie handling, feasible set equals the generator baseline for every brief, lift baseline).
- Browser engine: the JavaScript port returns the same top five, scores, feasibility flags and reasons as the Python engine for all 100 briefs (233 matches compared, 0 differences).
- SQL layer: 34 checks pass. SQL rebuilds the engine and returns the same top five, scores, feasibility flags, funnel, exposure, Gini, shortlist rates and lift for all 36 groups as Python. The feasible set equals the generator baseline. 16 data-quality queries find 0 violations, and an injected bad brief is caught by all five queries tested.
- Analytics hook: 6 scripted checks pass. The page works with no PostHog present. With a stub, events fire once each, carry is_demo, and hold counts and flags only.
- Web page: 21 scripted checks pass in jsdom (form flow, validation messages, region field, tab routing, metric cards, chart, all 100 example briefs equal to the Python top five).

## Not tested

- Real browsers and phones. The page was exercised in jsdom only.
- Accessibility audit, performance, long-running behaviour.
- Anything on real data. All records are synthetic and no user has used the page.
- The effect of changing any weight.

## Open items

- O1. No exposure cap. Test case 4 shows one creative can reach 56% of briefs. Mitigation needs a design decision (for example a time-windowed cap per creative) and real usage to tune it.
- O2. Shortlist rule S1 is a hypothesis. It tests supply, not owner behaviour.
- O3. Effort days are a synthetic assumption (A16). A real intake form does not collect them.
