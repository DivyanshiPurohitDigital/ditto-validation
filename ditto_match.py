#!/usr/bin/env python3
"""Ditto matching engine v1.0.0 (rule-based, no machine learning).

SYNTHETIC DATA ONLY. Output describes the logic on synthetic records. It is not
market evidence and not evidence of product-market fit.

SCORE = 0.40 skills + 0.25 budget + 0.20 availability + 0.15 style   (PRD v2 weights, untested)

  skills        share of the brief's required skills the creative has.
  budget        cost = day rate x estimated effort days, same currency only.
                1.0 at or below the brief's budget minimum, falling linearly to 0.5 at
                the budget maximum, then to 0.0 at 1.5x the maximum.
  availability  capacity ratio x start factor. Capacity = overlap of the creative's
                window and the brief window, in days, x days per week / 7, divided by
                effort, capped at 1. Start factor = 1 - lateness / brief window.
  style         share of the brief's style tags the creative also lists.
                Brief with no style tags: style is skipped and the other weights are
                rescaled for that brief (same rule for every creative).
                Creative with no style tags: style scores 0.

HARD GATES (never scored, never overridden): currency mismatch, missing essential
skill, location incompatibility (hybrid or on-site brief needs a non-remote creative in
the brief's region), incomplete profile.

RANKING: feasible (cost within budget maximum and capacity >= effort) ranks above
not feasible; then score; then a seeded hash of (seed, brief, creative), so ties never
favour a creative by id or input order. Top 5 per brief.

Scoring reads only the fields in SCORING_FIELDS. Name, email, portfolio, seniority band,
discipline and city are never read. The script verifies this.

Usage: python3 ditto_match.py [--data-dir DIR] [--out-dir DIR] [--seed N]
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import random
import sys
from collections import Counter, defaultdict

ENGINE_VERSION = "1.0.0"
WEIGHTS = {"skills": 0.40, "budget": 0.25, "availability": 0.20, "style": 0.15}  # PRD v2
TOP_N = 5
BUDGET_FLOOR = 0.5            # budget score at the budget maximum
OVER_BUDGET_ZERO_AT = 1.5     # budget score reaches 0 at this multiple of the maximum
STRONG_MIN = 0.6              # component at or above this is described as a strength
PRD_MAX_EXPOSURE = 0.20       # PRD guardrail: no creative in top five for more than 20% of briefs
PRD_MIN_COVERAGE = 0.50       # PRD guardrail: at least 50% of creatives in at least one top five
LIFT_BAND = (0.67, 1.5)       # review band for exposure vs random draw; hypothesis
LOW_POWER_N = 10              # groups smaller than this are flagged low power
CURRENCY_SYMBOL = {"GBP": "\u00a3", "EUR": "\u20ac", "USD": "$"}

SCORING_FIELDS_CREATIVE = ("id", "currency", "skills", "day_rate_minor", "min_project_budget_minor",
                           "availability_start", "availability_end", "days_per_week", "work_mode",
                           "region", "style_tags")
SCORING_FIELDS_BRIEF = ("id", "currency", "required_skills", "essential_skills", "budget_min_minor",
                        "budget_max_minor", "earliest_start", "deadline", "estimated_effort_days",
                        "work_mode", "location_region", "style_tags")
REQUIRED_CREATIVE = ("currency", "skills", "day_rate_minor", "availability_start", "availability_end",
                     "days_per_week", "work_mode")
REQUIRED_BRIEF = ("currency", "required_skills", "budget_max_minor", "earliest_start", "deadline",
                  "estimated_effort_days", "work_mode")
AUDIT_GROUPS = ("discipline", "region", "seniority_band", "currency", "work_mode")  # audit only


def D(s):
    return dt.date.fromisoformat(s)


def blank(v):
    return v is None or v == "" or v == []


def label(s):
    return s.replace("_", " ")


def join_and(items):
    items = [label(i) for i in items]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def money(minor, cur):
    major = minor / 100.0
    txt = "{:,.0f}".format(major) if abs(major - round(major)) < 1e-9 else "{:,.2f}".format(major)
    return CURRENCY_SYMBOL.get(cur, cur + " ") + txt


def tiebreak(seed, brief_id, creative_id):
    h = hashlib.sha256(("%s|%s|%s" % (seed, brief_id, creative_id)).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


# ---------------------------------------------------------------- gates and scores

def gate(c, b):
    """Return None if the pair passes the critical gates, else a reason code."""
    if any(blank(c.get(k)) for k in REQUIRED_CREATIVE):
        return "incomplete_creative_profile"
    if c["currency"] != b["currency"]:
        return "currency_mismatch"
    if not set(b.get("essential_skills") or []) <= set(c["skills"]):
        return "essential_skill_missing"
    if b["work_mode"] != "remote":
        if c["work_mode"] == "remote" or blank(c.get("region")) or c["region"] != b.get("location_region"):
            return "location_incompatible"
    return None


def availability(c, b):
    effort = b["estimated_effort_days"]
    earliest, deadline = D(b["earliest_start"]), D(b["deadline"])
    ws, we = max(earliest, D(c["availability_start"])), min(deadline, D(c["availability_end"]))
    window = max(1, (deadline - earliest).days)
    lateness = max(0, (D(c["availability_start"]) - earliest).days)
    overlap = max(0, (we - ws).days + 1) if we >= ws else 0
    capacity = overlap * c["days_per_week"] / 7.0
    ratio = min(1.0, capacity / effort) if effort > 0 else 1.0
    start_factor = max(0.0, 1.0 - lateness / float(window))
    return {"score": ratio * start_factor, "capacity_days": round(capacity, 2), "effort_days": effort,
            "capacity_ratio": ratio, "lateness_days": lateness, "overlap_days": overlap,
            "feasible": ratio >= 1.0}


def budget(c, b):
    cost = c["day_rate_minor"] * b["estimated_effort_days"]
    bmin, bmax = b.get("budget_min_minor") or b["budget_max_minor"], b["budget_max_minor"]
    if cost <= bmin:
        s = 1.0
    elif cost <= bmax:
        s = 1.0 - (1.0 - BUDGET_FLOOR) * (cost - bmin) / float(bmax - bmin) if bmax > bmin else 1.0
    else:
        s = max(0.0, BUDGET_FLOOR * (1.0 - (cost - bmax) / (bmax * (OVER_BUDGET_ZERO_AT - 1.0))))
    over = cost > bmax or c.get("min_project_budget_minor", 0) > bmax
    return {"score": s, "estimated_cost_minor": cost, "day_rate_minor": c["day_rate_minor"],
            "budget_min_minor": bmin, "budget_max_minor": bmax, "feasible": not over,
            "creative_min_minor": c.get("min_project_budget_minor", 0), "cost_vs_max": cost / float(bmax)}


def skills(c, b):
    req = list(b["required_skills"])
    have = set(c["skills"])
    got = [s for s in req if s in have]
    return {"score": len(got) / float(len(req)), "covered": got,
            "missing": [s for s in req if s not in have], "required_count": len(req)}


def style(c, b):
    bt = list(b.get("style_tags") or [])
    if not bt:
        return {"score": None, "skipped": True, "shared": [], "requested": 0}
    ct = set(c.get("style_tags") or [])
    shared = [t for t in bt if t in ct]
    return {"score": len(shared) / float(len(bt)), "skipped": False, "shared": shared,
            "requested": len(bt), "creative_has_tags": bool(ct)}


def effective_weights(brief):
    w = dict(WEIGHTS)
    if blank(brief.get("style_tags")):
        w["style"] = 0.0
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def score_pair(c, b, weights):
    comp = {"skills": skills(c, b), "budget": budget(c, b),
            "availability": availability(c, b), "style": style(c, b)}
    total = sum(weights[k] * (comp[k]["score"] or 0.0) for k in comp if weights[k] > 0)
    feasible = comp["budget"]["feasible"] and comp["availability"]["feasible"]
    return {"score": total, "feasible": feasible, "components": comp}


# ---------------------------------------------------------------- reasons

def clause(name, comp, cur):
    """Return (is_strength, text). Text uses only values stored in the component."""
    s = comp["score"]
    if name == "skills":
        n, k = comp["required_count"], len(comp["covered"])
        if not comp["missing"]:
            return True, "skills (all %d required: %s)" % (n, join_and(comp["covered"]))
        return s >= STRONG_MIN, "skills (%d of %d required: %s; missing %s)" % (
            k, n, join_and(comp["covered"]), join_and(comp["missing"]))
    if name == "budget":
        cost, lo, hi = comp["estimated_cost_minor"], comp["budget_min_minor"], comp["budget_max_minor"]
        rng = "%s to %s" % (money(lo, cur), money(hi, cur)) if lo < hi else money(hi, cur)
        basis = "%s a day" % money(comp["day_rate_minor"], cur)
        if cost > hi:
            return False, "budget (estimated cost %s at %s is %d%% over your maximum of %s)" % (
                money(cost, cur), basis, round((comp["cost_vs_max"] - 1) * 100), money(hi, cur))
        if not comp["feasible"]:
            return False, "budget (the creative\u2019s minimum project fee of %s is above your maximum of %s)" % (
                money(comp["creative_min_minor"], cur), money(hi, cur))
        if s >= STRONG_MIN:
            return True, "budget (estimated cost %s at %s, inside your %s)" % (money(cost, cur), basis, rng)
        return False, "budget (estimated cost %s at %s, near the top of your %s)" % (money(cost, cur), basis, rng)
    if name == "availability":
        late, cap, eff = comp["lateness_days"], comp["capacity_days"], comp["effort_days"]
        if not comp["feasible"]:
            return False, "availability (about %g of the %g working days needed before your deadline)" % (cap, eff)
        if late == 0:
            return True, "availability (free from your start date)"
        if s >= STRONG_MIN:
            return True, "availability (free %d days after your start date, still inside your deadline)" % late
        return False, "availability (starts %d days after your start date)" % late
    if name == "style":
        if comp["skipped"]:
            return None, "style was not scored because the brief lists no style tags"
        if not comp.get("creative_has_tags", True):
            return False, "style (the creative lists no style tags)"
        k, m = len(comp["shared"]), comp["requested"]
        if s >= STRONG_MIN:
            return True, "style (shares %s)" % join_and(comp["shared"])
        if k == 0:
            return False, "style (shares none of your style tags)"
        return False, "style (shares %d of your %d style tags)" % (k, m)
    raise ValueError(name)


def build_reason(result, cur):
    """Pure function of the stored components. Verified against them in checks."""
    strong, weak, notes = [], [], []
    for name in ("skills", "budget", "availability", "style"):
        is_strong, text = clause(name, result["components"][name], cur)
        (notes if is_strong is None else strong if is_strong else weak).append(text)
    parts = []
    if strong:
        parts.append("Matched on " + "; ".join(strong) + ".")
    else:
        parts.append("No strong matches.")
    if weak:
        parts.append("Weaker on " + "; ".join(weak) + ".")
    if not result["feasible"]:
        parts.append("Does not fit your budget or deadline.")
    if notes:
        parts.append(notes[0][0].upper() + notes[0][1:] + ".")
    return " ".join(parts)


# ---------------------------------------------------------------- ranking

SUPPORTED_CURRENCIES = ("GBP", "EUR", "USD")
WORK_MODES = ("remote", "hybrid", "on_site")


def brief_problem(b):
    """Return a list of plain-language problems. Empty list means the brief is valid."""
    out = []
    miss = [k for k in REQUIRED_BRIEF if blank(b.get(k))]
    if b.get("work_mode") not in (None, "remote") and blank(b.get("location_region")):
        miss.append("location_region")
    if miss:
        out.append("missing " + ", ".join(label(k).replace(" minor", "") for k in miss))
    if not blank(b.get("currency")) and b["currency"] not in SUPPORTED_CURRENCIES:
        out.append("unsupported currency %s" % b["currency"])
    if not blank(b.get("work_mode")) and b["work_mode"] not in WORK_MODES:
        out.append("work mode must be remote, hybrid or on site")
    try:
        bmax, bmin = b.get("budget_max_minor"), b.get("budget_min_minor")
        if not blank(bmax) and bmax <= 0:
            out.append("budget maximum must be above 0")
        if not blank(bmax) and not blank(bmin) and bmin > bmax:
            out.append("budget minimum is above the budget maximum")
        if not blank(b.get("estimated_effort_days")) and b["estimated_effort_days"] <= 0:
            out.append("estimated effort must be above 0 days")
    except TypeError:
        out.append("budget and effort must be numbers")
    if not blank(b.get("earliest_start")) and not blank(b.get("deadline")):
        try:
            if D(b["deadline"]) <= D(b["earliest_start"]):
                out.append("deadline must be after the start date")
        except ValueError:
            out.append("dates must be valid YYYY-MM-DD dates")
    if not blank(b.get("required_skills")) and not set(b.get("essential_skills") or []) <= set(b["required_skills"]):
        out.append("essential skills must be part of the required skills")
    return out


GATE_ORDER = ("incomplete_creative_profile", "currency_mismatch", "essential_skill_missing", "location_incompatible")


def no_match_text(brief, gates, n):
    """Plain-language reason from the gate funnel: the first stage that leaves nobody."""
    left, cur = n, brief["currency"]
    for g in GATE_ORDER:
        before, left = left, left - gates.get(g, 0)
        if left > 0:
            continue
        if g == "incomplete_creative_profile":
            return "No match: every creative profile is incomplete.", g
        if g == "currency_mismatch":
            return "No match: no creative lists a day rate in %s." % cur, g
        if g == "essential_skill_missing":
            return ("No match: %d creatives list rates in %s, but none has every essential skill (%s)."
                    % (before, cur, join_and(brief.get("essential_skills") or [])), g)
        return ("No match: %d creatives have the essential skills, but none can work %s in %s."
                % (before, label(brief["work_mode"]), brief.get("location_region")), g)
    return "No match.", "none"


def rank_brief(brief_full, creatives_full, seed):
    problem = brief_problem(brief_full)
    if problem:
        return {"brief_id": brief_full["id"], "status": "invalid_brief", "problems": problem,
                "candidate_count": 0, "feasible_count": 0, "matches": [], "gate_counts": {},
                "pool_ids": [], "feasible_pool_ids": [], "blocker": "invalid_brief",
                "no_match_reason": "Brief is not valid: %s." % "; ".join(problem)}
    brief = {k: brief_full.get(k) for k in SCORING_FIELDS_BRIEF}          # whitelist: nothing else is read
    creatives = [{k: c.get(k) for k in SCORING_FIELDS_CREATIVE} for c in creatives_full]
    weights = effective_weights(brief)
    cands, gates = [], Counter()
    for c in creatives:
        g = gate(c, brief)
        if g:
            gates[g] += 1
            continue
        r = score_pair(c, brief, weights)
        r["creative"] = c
        r["tb"] = tiebreak(seed, brief["id"], c["id"])
        cands.append(r)
    cands.sort(key=lambda r: (not r["feasible"], -round(r["score"], 9), r["tb"]))
    matches = []
    for i, r in enumerate(cands[:TOP_N], 1):
        matches.append({
            "rank": i, "creative_id": r["creative"]["id"], "score": round(r["score"] * 100, 1),
            "feasible": r["feasible"], "components": r["components"],
            "weights": weights, "reason": build_reason(r, brief["currency"]), "_raw": r["score"],
        })
    out = {"brief_id": brief["id"], "status": "ok" if matches else "no_candidates",
           "candidate_count": len(cands), "feasible_count": sum(1 for r in cands if r["feasible"]),
           "matches": matches, "gate_counts": {g: gates[g] for g in GATE_ORDER if gates.get(g)},
           "pool_ids": [r["creative"]["id"] for r in cands],
           "feasible_pool_ids": [r["creative"]["id"] for r in cands if r["feasible"]], "blocker": None}
    if not matches:
        out["no_match_reason"], out["blocker"] = no_match_text(brief, gates, len(creatives))
    elif out["feasible_count"] == 0:
        out["blocker"] = "budget_or_deadline"
        out["no_match_reason"] = ("No creative fits both budget and deadline. Closest candidates are shown and marked "
                                  "as not feasible.")
    return out


# ---------------------------------------------------------------- fairness

def gini(values):
    xs = sorted(values)
    n, s = len(xs), float(sum(xs))
    if n == 0 or s == 0:
        return 0.0
    return (2.0 * sum((i + 1) * x for i, x in enumerate(xs))) / (n * s) - (n + 1.0) / n


def fairness(creatives, results, n_briefs, tier):
    """Exposure over all briefs. tier 'shown' = top five as returned; 'feasible' = feasible matches only.

    Lift compares each creative's slots with the slots a random draw of five from the same
    candidate pool would give, counted only on briefs where more than five candidates compete.
    Where five or fewer compete, everyone is shown and ranking has no effect on exposure."""
    ids = [c["id"] for c in creatives]
    all_exp, con_exp, expected, in_pool = Counter(), Counter(), defaultdict(float), Counter()
    contested = 0
    for res in results:
        pool = res["pool_ids"] if tier == "shown" else res["feasible_pool_ids"]
        shown = [m["creative_id"] for m in res["matches"] if tier == "shown" or m["feasible"]]
        for cid in pool:
            in_pool[cid] += 1
        for cid in shown:
            all_exp[cid] += 1
        if len(pool) > TOP_N:
            contested += 1
            for cid in shown:
                con_exp[cid] += 1
            for cid in pool:
                expected[cid] += TOP_N / float(len(pool))
    vals = [all_exp.get(i, 0) for i in ids]
    total = sum(vals)
    top_id = max(ids, key=lambda i: (all_exp.get(i, 0), i))
    with_exp = sum(1 for v in vals if v > 0)
    ceiling = sum(1 for i in ids if in_pool.get(i, 0) > 0)
    top10 = sorted(vals, reverse=True)[:10]
    rep = {
        "tier": tier, "briefs": n_briefs, "slots_filled": total,
        "max_exposure_creative": top_id, "max_exposure_briefs": all_exp.get(top_id, 0),
        "max_exposure_share": all_exp.get(top_id, 0) / float(n_briefs),
        "creatives_with_exposure": with_exp, "creative_coverage": with_exp / float(len(ids)),
        "coverage_ceiling_creatives_passing_gates_for_any_brief": ceiling,
        "coverage_ceiling_share": ceiling / float(len(ids)),
        "coverage_among_creatives_passing_gates": round(with_exp / float(ceiling), 3) if ceiling else 0.0,
        "zero_exposure_never_passed_gates": len(ids) - ceiling,
        "zero_exposure_passed_gates_but_not_top_five": ceiling - with_exp,
        "gini_all_creatives": round(gini(vals), 3),
        "gini_creatives_passing_gates_for_any_brief": round(gini([all_exp.get(i, 0) for i in ids if in_pool.get(i, 0) > 0]), 3),
        "top10_share_of_slots": round(sum(top10) / float(total), 3) if total else 0.0,
        "briefs_where_ranking_chooses_among_more_than_5": contested,
        "guardrail_max_exposure_le_20pct": all_exp.get(top_id, 0) / float(n_briefs) <= PRD_MAX_EXPOSURE,
        "guardrail_coverage_ge_50pct": with_exp / float(len(ids)) >= PRD_MIN_COVERAGE,
        "_contested_slots_equal_expected": abs(sum(con_exp.values()) - sum(expected.values())) < 1e-6,
    }
    return rep, all_exp, con_exp, expected, in_pool


def group_table(creatives, all_exp, con_exp, expected, in_pool, field):
    rows = []
    groups = defaultdict(list)
    for c in creatives:
        groups[c.get(field)].append(c["id"])
    total = float(sum(all_exp.values()))
    for g, ids in sorted(groups.items(), key=lambda kv: (-len(kv[1]), str(kv[0]))):
        slots = sum(all_exp.get(i, 0) for i in ids)
        exp = sum(expected.get(i, 0.0) for i in ids)
        lift = sum(con_exp.get(i, 0) for i in ids) / exp if exp > 0 else None
        rows.append({"group": g, "creatives": len(ids), "share_of_creatives": round(len(ids) / float(len(creatives)), 3),
                     "slots": slots, "share_of_slots": round(slots / total, 3) if total else 0.0,
                     "mean_slots_per_creative": round(slots / float(len(ids)), 2),
                     "creatives_passing_gates_for_any_brief": sum(1 for i in ids if in_pool.get(i, 0) > 0),
                     "lift_vs_random_among_candidates": round(lift, 2) if lift is not None else None,
                     "low_power": len(ids) < LOW_POWER_N,
                     "review_flag": bool(lift is not None and len(ids) >= LOW_POWER_N and
                                         (lift < LIFT_BAND[0] or lift > LIFT_BAND[1]))})
    return rows


# ---------------------------------------------------------------- simulated shortlist

SHORTLIST_TARGET = 0.80       # PRD target
SHORTLIST_RULES = {
    "S1": ("feasible and covers at least half of the required skills", lambda x: x["feasible"] and x["components"]["skills"]["score"] >= 0.5),
    "S2": ("feasible and covers every required skill", lambda x: x["feasible"] and x["components"]["skills"]["score"] >= 1.0),
    "S3": ("feasible, covers every required skill and shares a style tag",
           lambda x: x["feasible"] and x["components"]["skills"]["score"] >= 1.0 and len(x["components"]["style"]["shared"]) >= 1),
}


def shortlist_report(results):
    """Simulated owner. A brief counts as shortlisted when at least one top-five match meets the rule.

    The rules read score components only, never the weighted total, so changing a weight does not
    change who is shortlisted. This tests supply, not owner behaviour."""
    n = len(results)
    rows = {}
    for key, (text, fn) in SHORTLIST_RULES.items():
        hit = sum(1 for r in results if any(fn(x) for x in r["matches"]))
        rows[key] = {"rule": text, "briefs_shortlisted": hit, "shortlist_rate": hit / float(n),
                     "meets_80pct_target": hit / float(n) >= SHORTLIST_TARGET}
    rows["ceiling_briefs_with_any_feasible_creative"] = sum(1 for r in results if r["feasible_count"] > 0)
    return rows


# ---------------------------------------------------------------- checks

def public(res):
    return [(m["creative_id"], m["score"], m["feasible"]) for m in res["matches"]]


def run_all(creatives, briefs, seed):
    return [rank_brief(b, creatives, seed) for b in briefs]


def checks(creatives, briefs, results, seed, baseline_path):
    out = []

    def chk(name, cond):
        out.append((name, bool(cond)))

    chk("weights sum to 1", abs(sum(WEIGHTS.values()) - 1.0) < 1e-9)
    chk("one result per brief", len(results) == len(briefs))
    chk("at most %d matches, ranks 1..n" % TOP_N, all([m["rank"] for m in r["matches"]] == list(range(1, len(r["matches"]) + 1))
                                                        and len(r["matches"]) <= TOP_N for r in results))
    chk("no creative repeated within a brief", all(len({m["creative_id"] for m in r["matches"]}) == len(r["matches"]) for r in results))
    ok_order = True
    for r in results:
        keys = [(not m["feasible"], -round(m["_raw"], 9)) for m in r["matches"]]
        ok_order &= keys == sorted(keys)
    chk("matches ordered feasible first, then score", ok_order)
    cmap = {c["id"]: c for c in creatives}
    bmap = {b["id"]: b for b in briefs}
    chk("every match passes the hard gates", all(gate(cmap[m["creative_id"]], bmap[r["brief_id"]]) is None
                                                  for r in results for m in r["matches"]))
    chk("no cross-currency match", all(cmap[m["creative_id"]]["currency"] == bmap[r["brief_id"]]["currency"]
                                       for r in results for m in r["matches"]))
    ok = True
    for r in results:
        b = bmap[r["brief_id"]]
        for m in r["matches"]:
            rebuilt = build_reason({"components": m["components"], "feasible": m["feasible"]}, b["currency"])
            ok &= (rebuilt == m["reason"]) and set(m["components"]) == set(WEIGHTS) and bool(m["reason"])
            ok &= abs(sum(m["weights"][k] * (m["components"][k]["score"] or 0.0) for k in WEIGHTS) * 100 - m["score"]) < 0.06
    chk("every reason rebuilds from its stored components; score equals weighted sum", ok)

    # audit-field invariance: scramble every field the engine must not read
    rng = random.Random(seed)
    scr = [dict(c) for c in creatives]
    bands = [c.get("seniority_band") for c in scr]
    discs = [c.get("discipline") for c in scr]
    cities = [c.get("city") for c in scr]
    rng.shuffle(bands)
    rng.shuffle(discs)
    rng.shuffle(cities)
    for i, c in enumerate(scr):
        c["display_name"], c["email"], c["portfolio_url"] = "X%d" % i, "x%d@example.com" % i, None
        c["seniority_band"], c["discipline"], c["city"] = bands[i], discs[i], cities[i]
    chk("scoring ignores name, email, portfolio, seniority, discipline, city",
        [public(r) for r in run_all(scr, briefs, seed)] == [public(r) for r in results])
    chk("ranking independent of input order", [public(r) for r in run_all(list(reversed(creatives)), briefs, seed)]
        == [public(r) for r in results])

    # tie handling: identical clones of a matched creative must not be ordered by id or input order
    tb = next((r for r in results if r["matches"]), None)
    if tb is not None:
        brief = bmap[tb["brief_id"]]
        base_c = cmap[tb["matches"][0]["creative_id"]]
        clones = []
        for i in range(30):
            cl = dict(base_c)
            cl["id"] = "tie_%02d" % i
            clones.append(cl)
        a = [m["creative_id"] for m in rank_brief(brief, clones, seed)["matches"]]
        b2 = [m["creative_id"] for m in rank_brief(brief, list(reversed(clones)), seed)["matches"]]
        c2 = [m["creative_id"] for m in rank_brief(brief, clones, seed + 1)["matches"]]
        chk("tied scores: stable under input order, not id-ordered, seed changes the order",
            a == b2 and a != ["tie_%02d" % i for i in range(TOP_N)] and a != c2)

    if baseline_path and os.path.exists(baseline_path):
        base = {p["brief_id"]: set(p["viable_creative_ids"]) for p in json.load(open(baseline_path))["per_brief"]}
        agree = True
        for r in results:
            feas = {c["id"] for c in creatives if gate(c, bmap[r["brief_id"]]) is None and
                    score_pair(c, bmap[r["brief_id"]], effective_weights(bmap[r["brief_id"]]))["feasible"]}
            agree &= feas == base[r["brief_id"]]
        chk("feasible set equals generator ground-truth baseline for every brief", agree)
    return out


# ---------------------------------------------------------------- io

def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")


def strip(res):
    r = {k: v for k, v in res.items() if k not in ("pool_ids", "feasible_pool_ids")}
    r["matches"] = [{k: v for k, v in m.items() if k != "_raw"} for m in res["matches"]]
    return r


def main():
    ap = argparse.ArgumentParser(description="Ditto matching engine (synthetic data only).")
    ap.add_argument("--data-dir", default="ditto_synthetic_out")
    ap.add_argument("--out-dir", default="ditto_match_out")
    ap.add_argument("--seed", type=int, default=20261125, help="tie-break seed")
    args = ap.parse_args()
    creatives = json.load(open(os.path.join(args.data_dir, "creatives.json"), encoding="utf-8"))["records"]
    briefs = json.load(open(os.path.join(args.data_dir, "briefs.json"), encoding="utf-8"))["records"]
    results = run_all(creatives, briefs, args.seed)
    os.makedirs(args.out_dir, exist_ok=True)

    meta = {"label": "SYNTHETIC DATA ONLY. Not market evidence.", "engine_version": ENGINE_VERSION,
            "weights": WEIGHTS, "top_n": TOP_N, "budget_floor": BUDGET_FLOOR,
            "over_budget_zero_at": OVER_BUDGET_ZERO_AT, "strong_min": STRONG_MIN, "tie_break_seed": args.seed}
    write_json(os.path.join(args.out_dir, "matches.json"), {"meta": meta, "briefs": [strip(r) for r in results]})
    with open(os.path.join(args.out_dir, "matches.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["brief_id", "rank", "creative_id", "score", "feasible", "skills", "budget", "availability", "style", "reason"])
        for r in results:
            for m in r["matches"]:
                cs = m["components"]
                w.writerow([r["brief_id"], m["rank"], m["creative_id"], m["score"], str(m["feasible"]).lower()] +
                           [("" if cs[k]["score"] is None else round(cs[k]["score"], 3)) for k in WEIGHTS] + [m["reason"]])

    # fairness
    shown, a_s, c_s, e_s, p_s = fairness(creatives, results, len(briefs), "shown")
    feas, a_f, c_f, e_f, p_f = fairness(creatives, results, len(briefs), "feasible")
    groups = {f: group_table(creatives, a_s, c_s, e_s, p_s, f) for f in AUDIT_GROUPS}
    fair_ok = shown.pop("_contested_slots_equal_expected") and feas.pop("_contested_slots_equal_expected")
    briefs_summary = {
        "briefs": len(briefs),
        "with_5_matches": sum(1 for r in results if len(r["matches"]) == TOP_N),
        "with_1_to_4_matches": sum(1 for r in results if 0 < len(r["matches"]) < TOP_N),
        "with_no_match": sum(1 for r in results if not r["matches"]),
        "with_at_least_one_feasible": sum(1 for r in results if r["feasible_count"] > 0),
        "feasible_share_of_shown_matches": round(sum(1 for r in results for m in r["matches"] if m["feasible"]) /
                                                  float(max(1, sum(len(r["matches"]) for r in results))), 3),
        "no_match_stage_where_pool_reaches_zero": dict(Counter(r["blocker"] for r in results if not r["matches"])),
        "matches_but_none_feasible": sum(1 for r in results if r["matches"] and r["feasible_count"] == 0),
    }
    shortlist = shortlist_report(results)
    report = {"meta": meta, "briefs_summary": briefs_summary, "shortlist_simulated_owner": shortlist,
              "exposure_shown_top_five": shown,
              "exposure_feasible_only": feas, "audit_groups_shown_top_five": groups,
              "audit_note": "Group fields are used for this audit only. The engine never reads them."}
    write_json(os.path.join(args.out_dir, "fairness_report.json"), report)

    chk = checks(creatives, briefs, results, args.seed, os.path.join(args.data_dir, "ground_truth_baseline.json"))
    chk.append(("contested slots equal expected slots in total (lift baseline is 1.00)", fair_ok))

    print("=== Ditto matching engine %s (SYNTHETIC, NOT MARKET EVIDENCE) ===" % ENGINE_VERSION)
    print("weights: " + ", ".join("%s %d%%" % (k, round(v * 100)) for k, v in WEIGHTS.items()))
    print("briefs: %(briefs)d | 5 matches: %(with_5_matches)d | 1 to 4: %(with_1_to_4_matches)d | none: %(with_no_match)d | "
          "matches but none feasible: %(matches_but_none_feasible)d | at least one feasible: %(with_at_least_one_feasible)d" % briefs_summary)
    print("feasible share of shown matches: %.1f%%" % (100 * briefs_summary["feasible_share_of_shown_matches"]))
    print("no-match briefs by gate that empties the pool: %s" % briefs_summary["no_match_stage_where_pool_reaches_zero"])
    print("\nSIMULATED SHORTLIST RATE (PRD target 80%; rules read components, not the weighted total)")
    for key in SHORTLIST_RULES:
        row = shortlist[key]
        print("  %s %-60s %d of %d briefs (%.0f%%) %s" % (key, row["rule"], row["briefs_shortlisted"], len(briefs),
                                                          100 * row["shortlist_rate"], "PASS" if row["meets_80pct_target"] else "FAIL"))
    print("  ceiling: %d briefs have at least one creative that fits budget and deadline" % shortlist["ceiling_briefs_with_any_feasible_creative"])
    for name, rep in (("EXPOSURE, top five as shown", shown), ("EXPOSURE, feasible matches only", feas)):
        print("\n%s" % name)
        print("  slots filled: %d | briefs where ranking chooses among more than 5: %d" % (rep["slots_filled"], rep["briefs_where_ranking_chooses_among_more_than_5"]))
        print("  max exposure: %s in %d of %d briefs (%.0f%%) | guardrail <= 20%%: %s" % (
            rep["max_exposure_creative"], rep["max_exposure_briefs"], rep["briefs"], 100 * rep["max_exposure_share"],
            "PASS" if rep["guardrail_max_exposure_le_20pct"] else "FAIL"))
        print("  creatives with at least one slot: %d of %d (%.0f%%) | guardrail >= 50%%: %s" % (
            rep["creatives_with_exposure"], len(creatives), 100 * rep["creative_coverage"],
            "PASS" if rep["guardrail_coverage_ge_50pct"] else "FAIL"))
        print("  coverage ceiling: %d creatives (%.0f%%) pass the hard gates for at least one brief; %.0f%% of those got a slot" % (
            rep["coverage_ceiling_creatives_passing_gates_for_any_brief"], 100 * rep["coverage_ceiling_share"],
            100 * rep["coverage_among_creatives_passing_gates"]))
        print("  Gini (all creatives): %.3f | Gini (creatives passing gates for any brief): %.3f | top 10 share of slots: %.0f%%" % (
            rep["gini_all_creatives"], rep["gini_creatives_passing_gates_for_any_brief"], 100 * rep["top10_share_of_slots"]))
    print("\nAUDIT GROUPS (top five as shown; lift = contested-brief slots / slots a random draw would give; 1.00 = ranking neutral)")
    for f, rows in groups.items():
        print(" %s:" % f)
        for r in rows:
            print("   %-26s creatives %3d | slots %3d (%4.1f%% of slots vs %4.1f%% of creatives) | lift %s%s%s" % (
                r["group"], r["creatives"], r["slots"], 100 * r["share_of_slots"], 100 * r["share_of_creatives"],
                "n/a" if r["lift_vs_random_among_candidates"] is None else "%.2f" % r["lift_vs_random_among_candidates"],
                "  [review]" if r["review_flag"] else "", "  [low power]" if r["low_power"] else ""))
    print("\nSAMPLE MATCHES")
    shown_n = 0
    for r in results:
        if r["matches"] and shown_n < 3 and r["feasible_count"] > 0:
            m = r["matches"][0]
            print("  %s rank 1 %s score %.1f feasible %s\n    %s" % (r["brief_id"], m["creative_id"], m["score"], m["feasible"], m["reason"]))
            shown_n += 1
    for stage in ("currency_mismatch", "essential_skill_missing", "location_incompatible"):
        nm = next((r for r in results if not r["matches"] and r["blocker"] == stage), None)
        if nm:
            print("  %s: %s" % (nm["brief_id"], nm["no_match_reason"]))
    nf = next((r for r in results if r["matches"] and r["feasible_count"] == 0), None)
    if nf:
        print("  %s rank 1 %s: %s\n    %s" % (nf["brief_id"], nf["matches"][0]["creative_id"], nf["no_match_reason"], nf["matches"][0]["reason"]))
    print("\nchecks:")
    for name, ok in chk:
        print("  [%s] %s" % ("PASS" if ok else "FAIL", name))
    bad = [n for n, ok in chk if not ok]
    if bad:
        print("FAILED: %s" % bad)
        sys.exit(1)
    print("all checks passed; files written to %s" % args.out_dir)


if __name__ == "__main__":
    main()
