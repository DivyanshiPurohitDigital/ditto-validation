#!/usr/bin/env python3
"""Ditto test plan: ten cases run against ditto_match.py on synthetic data.

SYNTHETIC DATA ONLY. Each case states the expected result, runs the engine, and
records the actual result and PASS or FAIL. Case 4 passes when the fairness check
flags the dominating creative, because the engine has no exposure cap.

Usage: python3 test_cases.py [--data-dir ditto_synthetic_out] [--json out.json]
Run ditto_synth.py first so the data folder exists.
"""
import argparse
import copy
import json
import os
import random
import sys

import ditto_match as m

SEED = 20261125


def load(data_dir):
    c = json.load(open(os.path.join(data_dir, "creatives.json"), encoding="utf-8"))["records"]
    b = json.load(open(os.path.join(data_dir, "briefs.json"), encoding="utf-8"))["records"]
    return c, b


def pick(briefs, results, cond):
    bm = {x["id"]: x for x in briefs}
    for r in results:
        if cond(r, bm[r["brief_id"]]):
            return bm[r["brief_id"]], r
    raise RuntimeError("no brief satisfies the condition")


def case_1(C, B, R):
    b, _ = pick(B, R, lambda r, x: x["work_mode"] == "remote" and x["currency"] == "GBP" and r["matches"])
    b = copy.deepcopy(b)
    b["essential_skills"] = ["skill_nobody_lists"]
    b["required_skills"] = sorted(set(b["required_skills"]) | {"skill_nobody_lists"})
    r = m.rank_brief(b, C, SEED)
    ok = not r["matches"] and "essential skill" in r.get("no_match_reason", "")
    return ("Zero matches and a plain-language reason that names the essential skills as the blocker.",
            "matches=%d; reason: %s" % (len(r["matches"]), r.get("no_match_reason")), ok)


def case_2(C, B, R):
    r0 = next(r for r in R if r["matches"])
    b = next(x for x in B if x["id"] == r0["brief_id"])
    base = next(c for c in C if c["id"] == r0["matches"][0]["creative_id"])
    clones = []
    for i in range(30):
        cl = dict(base)
        cl["id"] = "tie_%02d" % i
        clones.append(cl)
    a = [x["creative_id"] for x in m.rank_brief(b, clones, SEED)["matches"]]
    rev = [x["creative_id"] for x in m.rank_brief(b, list(reversed(clones)), SEED)["matches"]]
    other = [x["creative_id"] for x in m.rank_brief(b, clones, SEED + 1)["matches"]]
    scores = {x["score"] for x in m.rank_brief(b, clones, SEED)["matches"]}
    ok = len(scores) == 1 and a == rev and a != ["tie_%02d" % i for i in range(5)] and a != other
    return ("30 identical creatives tie. Order is stable under input order, is not by id, and changes with the tie-break seed.",
            "single score %s; stable=%s; id-ordered=%s; seed changes order=%s" % (
                sorted(scores), a == rev, a == ["tie_%02d" % i for i in range(5)], a != other), ok)


def case_3(C, B, R):
    b, _ = pick(B, R, lambda r, x: r["feasible_count"] > 0)
    b = copy.deepcopy(b)
    b["budget_min_minor"], b["budget_max_minor"] = 500, 1000
    r = m.rank_brief(b, C, SEED)
    ok = (len(r["matches"]) > 0 and r["feasible_count"] == 0 and all(not x["feasible"] for x in r["matches"])
          and "over your maximum" in r["matches"][0]["reason"] and "No creative fits both budget and deadline" in r["no_match_reason"])
    return ("Candidates still shown, all marked not feasible, reasons state the percentage over budget, brief-level note says nothing fits.",
            "matches=%d; feasible=%d; note: %s" % (len(r["matches"]), r["feasible_count"], r.get("no_match_reason")), ok)


def case_4(C, B, R):
    tags = sorted({t for x in B for t in x["style_tags"]})
    skills = sorted({s for c in C for s in c["skills"]})
    dom = {"id": "cr_dominator", "currency": "GBP", "skills": skills, "day_rate_minor": 5000,
           "min_project_budget_minor": 500, "availability_start": "2026-01-01", "availability_end": "2030-01-01",
           "days_per_week": 5, "work_mode": "hybrid", "region": "London", "style_tags": tags}
    R2 = m.run_all(C + [dom], B, SEED)
    rep, *_ = m.fairness(C + [dom], R2, len(B), "shown")
    rank1 = sum(1 for r in R2 if r["matches"] and r["matches"][0]["creative_id"] == "cr_dominator")
    flagged = not rep["guardrail_max_exposure_le_20pct"] and rep["max_exposure_creative"] == "cr_dominator"
    return ("A creative who lists every skill, charges 50 GBP a day and is always free is ranked first wherever eligible, and the exposure guardrail reports FAIL.",
            "dominator rank 1 in %d briefs; exposure %d of %d briefs (%.0f%%); guardrail <= 20%%: %s" % (
                rank1, rep["max_exposure_briefs"], len(B), 100 * rep["max_exposure_share"],
                "PASS" if rep["guardrail_max_exposure_le_20pct"] else "FAIL (flagged)"), flagged and rank1 > 0)


def case_5(C, B, R):
    r0 = next(r for r in R if r["matches"] and r["matches"][0]["feasible"])
    b = next(x for x in B if x["id"] == r0["brief_id"])
    base = next(c for c in C if c["id"] == r0["matches"][0]["creative_id"])
    nostyle, norate = dict(base), dict(base)
    nostyle["id"], nostyle["style_tags"] = "c_nostyle", None
    norate["id"], norate["day_rate_minor"] = "c_norate", None
    try:
        r = m.rank_brief(b, [base, nostyle, norate], SEED)
    except Exception as e:  # noqa: BLE001
        return ("No exception; missing rate excludes the creative; missing style scores 0 with a stated reason.", "exception: %r" % e, False)
    ids = {x["creative_id"]: x for x in r["matches"]}
    ok = ("c_norate" not in ids and "c_nostyle" in ids and ids["c_nostyle"]["components"]["style"]["score"] == 0.0
          and "lists no style tags" in ids["c_nostyle"]["reason"])
    return ("No exception; missing rate excludes the creative; missing style scores 0 with a stated reason.",
            "matched ids=%s; nostyle style score=%s" % (sorted(ids), ids.get("c_nostyle", {}).get("components", {}).get("style", {}).get("score")), ok)


def case_6(C, B, R):
    b, _ = pick(B, R, lambda r, x: r["matches"])
    b = copy.deepcopy(b)
    b["style_tags"] = []
    r = m.rank_brief(b, C, SEED)
    w = r["matches"][0]["weights"]
    ok = abs(sum(w.values()) - 1.0) < 1e-9 and w["style"] == 0 and "not scored" in r["matches"][0]["reason"]
    return ("Style weight drops to 0, remaining weights rescale to sum 1, reason says style was not scored.",
            "weights=%s; sum=%.3f" % ({k: round(v, 3) for k, v in w.items()}, sum(w.values())), ok)


def case_7(C, B, R):
    b, _ = pick(B, R, lambda r, x: r["matches"])
    b1, b2 = copy.deepcopy(b), copy.deepcopy(b)
    b1["budget_min_minor"], b1["budget_max_minor"] = b["budget_max_minor"] + 100000, b["budget_max_minor"]
    b2["estimated_effort_days"] = 0
    r1, r2 = m.rank_brief(b1, C, SEED), m.rank_brief(b2, C, SEED)
    ok = r1["status"] == "invalid_brief" and r2["status"] == "invalid_brief" and not r1["matches"] and not r2["matches"]
    return ("Budget minimum above maximum, and effort of 0 days, are rejected as invalid briefs with no matches.",
            "min>max: status=%s, matches=%d; effort 0: status=%s, matches=%d" % (r1["status"], len(r1["matches"]), r2["status"], len(r2["matches"])), ok)


def case_8(C, B, R):
    b, _ = pick(B, R, lambda r, x: r["matches"])
    b = copy.deepcopy(b)
    b["deadline"] = b["earliest_start"]
    r = m.rank_brief(b, C, SEED)
    ok = r["status"] == "invalid_brief" and not r["matches"]
    return ("Deadline on or before the start date is rejected as an invalid brief with no matches.",
            "status=%s, matches=%d" % (r["status"], len(r["matches"])), ok)


def case_9(C, B, R):
    cm = {c["id"]: c for c in C}
    isolated = all(cm[x["creative_id"]]["currency"] == r_b["currency"]
                   for r_b, r in ((next(y for y in B if y["id"] == rr["brief_id"]), rr) for rr in R) for x in r["matches"])
    b, _ = pick(B, R, lambda r, x: x["work_mode"] == "remote" and x["currency"] == "GBP" and r["matches"])
    be = copy.deepcopy(b)
    be["currency"] = "EUR"
    re_ = m.rank_brief(be, C, SEED)
    eur_only = all(cm[x["creative_id"]]["currency"] == "EUR" for x in re_["matches"])
    bj = copy.deepcopy(b)
    bj["currency"] = "JPY"
    rj = m.rank_brief(bj, C, SEED)
    ok = isolated and eur_only and rj["status"] == "invalid_brief"
    return ("No match in any of the 100 briefs crosses currency. A GBP brief switched to EUR returns EUR creatives only, with no conversion. An unsupported currency (JPY) is rejected.",
            "all 100 briefs isolated=%s; EUR variant: %d matches, all EUR=%s; JPY status=%s" % (isolated, len(re_["matches"]), eur_only, rj["status"]), ok)


def case_10(C, B, R):
    rng = random.Random(SEED)
    scr = [dict(c) for c in C]
    bands, discs, cities = [c["seniority_band"] for c in scr], [c["discipline"] for c in scr], [c["city"] for c in scr]
    for lst in (bands, discs, cities):
        rng.shuffle(lst)
    for i, c in enumerate(scr):
        c["display_name"], c["email"], c["portfolio_url"] = "X%d" % i, "x%d@example.com" % i, None
        c["seniority_band"], c["discipline"], c["city"] = bands[i], discs[i], cities[i]
    R2 = m.run_all(scr, B, SEED)
    same = all(m.public(a) == m.public(b) for a, b in zip(R, R2))
    return ("Scrambling name, email, portfolio, seniority, discipline and city changes no top-five list across all 100 briefs.",
            "identical for all %d briefs: %s" % (len(B), same), same)


CASES = [
    ("1", "No match", case_1), ("2", "Tied scores", case_2), ("3", "Budget below every rate", case_3),
    ("4", "One creative dominates", case_4), ("5", "Missing fields on a creative", case_5),
    ("6", "Brief with no style tags", case_6), ("7", "Invalid budget range and effort", case_7),
    ("8", "Invalid dates", case_8), ("9", "Currency isolation and unsupported currency", case_9),
    ("10", "Protected-field invariance", case_10),
]


def main():
    ap = argparse.ArgumentParser(description="Ditto ten-case test plan (synthetic data).")
    ap.add_argument("--data-dir", default="ditto_synthetic_out")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    C, B = load(args.data_dir)
    R = m.run_all(C, B, SEED)
    out = []
    for cid, name, fn in CASES:
        try:
            expected, actual, ok = fn(C, B, R)
        except Exception as e:  # noqa: BLE001
            expected, actual, ok = "(case raised an exception)", "exception: %r" % e, False
        out.append({"case": cid, "name": name, "expected": expected, "actual": actual, "status": "PASS" if ok else "FAIL"})
        print("[%s] case %s %s\n    expected: %s\n    actual:   %s" % ("PASS" if ok else "FAIL", cid, name, expected, actual))
    if args.json:
        json.dump(out, open(args.json, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    n_fail = sum(1 for r in out if r["status"] == "FAIL")
    print("\n%d of %d cases pass" % (len(out) - n_fail, len(out)))
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
