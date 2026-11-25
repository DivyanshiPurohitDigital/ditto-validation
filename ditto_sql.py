#!/usr/bin/env python3
"""Run the Ditto engine and fairness check in SQL, reconcile it to the Python engine, export BI tables.

SYNTHETIC DATA ONLY. Loads creatives, briefs and the Python results into SQLite, runs every block in
queries.sql, then checks that SQL gives the same top five, funnel, exposure, shortlist and lift figures as
ditto_match.py, and that the data-quality queries find no violations. Writes CSV tables for a BI tool.

Usage: python3 ditto_sql.py [--data-dir ditto_synthetic_out] [--match-dir ditto_match_out] [--out-dir ditto_bi_out]
Run ditto_synth.py and ditto_match.py first. Standard library only (sqlite3 needs SQLite 3.25 or later).
"""
import argparse
import csv
import json
import os
import re
import sqlite3
import sys

import ditto_match as m
import ditto_synth as S

SEED = 20261125

DDL = """
CREATE TABLE creatives (id TEXT PRIMARY KEY, discipline TEXT, region TEXT, work_mode TEXT, currency TEXT,
    seniority_band TEXT, day_rate_minor INTEGER, min_project_budget_minor INTEGER,
    availability_start TEXT, availability_end TEXT, days_per_week INTEGER);
CREATE TABLE creative_skills (creative_id TEXT, skill TEXT);
CREATE TABLE creative_styles (creative_id TEXT, tag TEXT);
CREATE TABLE briefs (id TEXT PRIMARY KEY, project_type TEXT, currency TEXT, budget_min_minor INTEGER,
    budget_max_minor INTEGER, earliest_start TEXT, deadline TEXT, estimated_effort_days INTEGER,
    work_mode TEXT, location_region TEXT);
CREATE TABLE brief_skills (brief_id TEXT, skill TEXT, is_essential INTEGER);
CREATE TABLE brief_styles (brief_id TEXT, tag TEXT);
CREATE TABLE project_types (project_type TEXT PRIMARY KEY, discipline TEXT);
CREATE TABLE tiebreak (brief_id TEXT, creative_id TEXT, tb TEXT);
CREATE TABLE matches_py (brief_id TEXT, rank INTEGER, creative_id TEXT, score REAL, feasible INTEGER);
"""


def blocks(path):
    cur, out = None, {}
    for line in open(path, encoding="utf-8"):
        mm = re.match(r"-- name: (\w+)", line)
        if mm:
            cur = mm.group(1)
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "".join(v).strip().rstrip(";") for k, v in out.items()}


def load(con, data_dir, match_dir):
    C = json.load(open(os.path.join(data_dir, "creatives.json"), encoding="utf-8"))["records"]
    B = json.load(open(os.path.join(data_dir, "briefs.json"), encoding="utf-8"))["records"]
    P = json.load(open(os.path.join(match_dir, "matches.json"), encoding="utf-8"))["briefs"]
    con.executescript(DDL)
    con.executemany("INSERT INTO creatives VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        (c["id"], c["discipline"], c["region"], c["work_mode"], c["currency"], c["seniority_band"], c["day_rate_minor"],
         c["min_project_budget_minor"], c["availability_start"], c["availability_end"], c["days_per_week"]) for c in C])
    con.executemany("INSERT INTO creative_skills VALUES (?,?)", [(c["id"], s) for c in C for s in c["skills"]])
    con.executemany("INSERT INTO creative_styles VALUES (?,?)", [(c["id"], t) for c in C for t in c["style_tags"]])
    con.executemany("INSERT INTO briefs VALUES (?,?,?,?,?,?,?,?,?,?)", [
        (b["id"], b["project_type"], b["currency"], b["budget_min_minor"], b["budget_max_minor"], b["earliest_start"],
         b["deadline"], b["estimated_effort_days"], b["work_mode"], b["location_region"]) for b in B])
    rows = []
    for b in B:
        assert set(b["essential_skills"]) <= set(b["required_skills"]), b["id"]
        rows += [(b["id"], s, 1 if s in b["essential_skills"] else 0) for s in b["required_skills"]]
    con.executemany("INSERT INTO brief_skills VALUES (?,?,?)", rows)
    con.executemany("INSERT INTO brief_styles VALUES (?,?)", [(b["id"], t) for b in B for t in (b["style_tags"] or [])])
    con.executemany("INSERT INTO project_types VALUES (?,?)", [(k, v["disc"]) for k, v in S.PROJECT_TYPES.items()])
    con.executemany("INSERT INTO tiebreak VALUES (?,?,?)", [(b["id"], c["id"], format(m.tiebreak(SEED, b["id"], c["id"]), "016x")) for b in B for c in C])
    con.executemany("INSERT INTO matches_py VALUES (?,?,?,?,?)", [
        (p["brief_id"], x["rank"], x["creative_id"], x["score"], 1 if x["feasible"] else 0) for p in P for x in p["matches"]])
    return C, B, P


def run(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    return cols, cur.fetchall()


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Ditto engine in SQL, reconciled to Python (synthetic data).")
    ap.add_argument("--data-dir", default="ditto_synthetic_out")
    ap.add_argument("--match-dir", default="ditto_match_out")
    ap.add_argument("--out-dir", default="ditto_bi_out")
    args = ap.parse_args()
    con = sqlite3.connect(":memory:")
    C, B, P = load(con, args.data_dir, args.match_dir)
    Q = blocks(os.path.join(os.path.dirname(os.path.abspath(__file__)), "queries.sql"))
    for name in [k for k in Q if k.startswith("view_")]:
        con.execute(Q[name])
    fr = json.load(open(os.path.join(args.match_dir, "fairness_report.json"), encoding="utf-8"))
    gt = json.load(open(os.path.join(args.data_dir, "ground_truth_baseline.json"), encoding="utf-8"))
    checks = []

    def chk(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # 1. top five equals Python
    _, sql_top = run(con, "SELECT brief_id, rnk, creative_id, ROUND(score*100,1), feasible FROM top_five ORDER BY brief_id, rnk")
    py_top = [(p["brief_id"], x["rank"], x["creative_id"], x["score"], 1 if x["feasible"] else 0) for p in P for x in p["matches"]]
    same_ids = [r[:3] for r in sql_top] == [r[:3] for r in py_top]
    max_diff = max((abs(a[3] - b[3]) for a, b in zip(sql_top, py_top)), default=0) if len(sql_top) == len(py_top) else 99
    chk("SQL top five equals Python top five for all %d briefs (%d matches)" % (len(B), len(py_top)), same_ids,
        "max score difference %.2f" % max_diff)
    chk("SQL scores within 0.1 of Python scores", max_diff <= 0.1 + 1e-9)
    chk("SQL feasibility flags equal Python", [r[4] for r in sql_top] == [r[4] for r in py_top])

    # 2. feasible set equals the generator ground truth
    _, feas = run(con, "SELECT brief_id, creative_id FROM ranked WHERE feasible = 1")
    sql_feas = {}
    for b, c in feas:
        sql_feas.setdefault(b, set()).add(c)
    gt_feas = {p["brief_id"]: set(p["viable_creative_ids"]) for p in gt["per_brief"]}
    chk("SQL feasible set equals generator ground-truth baseline for every brief",
        all(sql_feas.get(b["id"], set()) == gt_feas[b["id"]] for b in B))

    # 3. funnel
    cols, funnel = run(con, Q["q_funnel"])
    fmap = {r[0]: r[1] for r in funnel}
    bs = fr["briefs_summary"]
    stage = bs["no_match_stage_where_pool_reaches_zero"]
    chk("funnel: no candidate (skills) = Python", fmap.get("2. no candidate: no creative has every essential skill", 0) == stage.get("essential_skill_missing", 0))
    chk("funnel: no candidate (place) = Python", fmap.get("3. no candidate: skilled creatives exist, none can work in the place", 0) == stage.get("location_incompatible", 0))
    chk("funnel: none feasible = Python", fmap.get("4. candidates found, none fit budget and deadline", 0) == bs["matches_but_none_feasible"])
    chk("funnel: at least one feasible = Python", fmap.get("5. at least one match fits budget and deadline", 0) == bs["with_at_least_one_feasible"])
    chk("funnel covers all 100 briefs", sum(fmap.values()) == len(B))

    # 4. exposure summary
    cols, rows = run(con, Q["q_exposure_summary"])
    es = dict(zip(cols, rows[0]))
    ex = fr["exposure_shown_top_five"]
    chk("most exposed creative: slots = Python", es["max_slots"] == ex["max_exposure_briefs"], "%s" % es["max_slots"])
    chk("creatives with a slot = Python", es["creatives_with_slot"] == ex["creatives_with_exposure"], "%s" % es["creatives_with_slot"])
    chk("coverage ceiling = Python", es["coverage_ceiling"] == ex["coverage_ceiling_creatives_passing_gates_for_any_brief"], "%s" % es["coverage_ceiling"])
    chk("Gini (all creatives) = Python", abs(es["gini_all"] - ex["gini_all_creatives"]) < 0.0011, "%s" % es["gini_all"])
    chk("Gini (gate-passing creatives) = Python", abs(es["gini_pool"] - ex["gini_creatives_passing_gates_for_any_brief"]) < 0.0011, "%s" % es["gini_pool"])
    chk("top 10 share = Python", abs(es["top10_share"] - ex["top10_share_of_slots"]) < 0.0011, "%s" % es["top10_share"])

    # 5. shortlist
    _, sl = run(con, Q["q_shortlist"])
    sl = dict(sl)
    sh = fr["shortlist_simulated_owner"]
    for k in ("S1", "S2", "S3"):
        chk("shortlist %s = Python" % k, sl[k] == sh[k]["briefs_shortlisted"], "%s of %d" % (sl[k], len(B)))

    # 6. group lift
    cols, gl = run(con, Q["q_group_lift"])
    sql_lift = {(r[0], str(r[1])): r[5] for r in gl}
    ok, n = True, 0
    for field, rows_py in fr["audit_groups_shown_top_five"].items():
        for r in rows_py:
            a, b = sql_lift.get((field, str(r["group"]))), r["lift_vs_random_among_candidates"]
            n += 1
            if (a is None) != (b is None) or (a is not None and abs(a - b) > 0.011):
                ok = False
    chk("lift for all %d groups equals Python (tolerance 0.011)" % n, ok)

    # 7. data-quality queries
    for name in [k for k in Q if k.startswith("dq_")]:
        cols, rows = run(con, Q[name])
        v = rows[0][0]
        good = (v == 1) if cols[0] == "ok" else (v == 0)
        chk("data quality: " + name[3:].replace("_", " "), good, "violations %s" % (0 if cols[0] == "ok" and v == 1 else v))

    # exports for a BI tool
    os.makedirs(args.out_dir, exist_ok=True)
    for fname, qname in (("bi_funnel.csv", "q_funnel"), ("bi_exposure.csv", "q_exposure_per_creative"),
                         ("bi_supply_demand.csv", "q_supply_demand"), ("bi_groups.csv", "q_group_lift"),
                         ("bi_by_work_mode.csv", "q_by_work_mode")):
        cols, rows = run(con, Q[qname])
        write_csv(os.path.join(args.out_dir, fname), cols, rows)
    n_b = float(len(B))
    summary = [
        ["Simulated shortlist rate (S1)", round(100 * sl["S1"] / n_b, 1), 80, "target: at least"],
        ["Most exposed creative, % of briefs", round(100 * es["max_slots"] / n_b, 1), 20, "limit: at most"],
        ["Creatives with a slot, %", round(100 * es["creatives_with_slot"] / len(C), 1), 50, "target: at least"],
        ["Coverage ceiling, %", round(100 * es["coverage_ceiling"] / len(C), 1), 50, "context"],
        ["Gini, all creatives", es["gini_all"], "", "context"],
        ["Top 10 creatives, % of slots", round(100 * es["top10_share"], 1), "", "context"],
    ]
    write_csv(os.path.join(args.out_dir, "bi_summary.csv"), ["metric", "value", "threshold", "note"], summary)

    # 8. the data-quality queries must be able to fail: inject bad rows, expect violations, remove them
    con.execute("INSERT INTO briefs VALUES ('bad_1','logo_brand_identity','JPY',90000,50000,'2026-12-10','2026-12-01',5,'moon',NULL)")
    caught = {}
    for name in ("dq_budget_range", "dq_dates", "dq_accepted_currency", "dq_accepted_work_mode", "dq_essential_inside_required"):
        caught[name] = run(con, Q[name])[1][0][0]
    con.execute("DELETE FROM briefs WHERE id = 'bad_1'")
    chk("data-quality queries detect an injected bad brief (budget, dates, currency, work mode, no skills)",
        all(v >= 1 for v in caught.values()), ", ".join("%s=%s" % (k[3:], v) for k, v in caught.items()))
    chk("injected row removed", run(con, "SELECT COUNT(*) FROM briefs")[1][0][0] == len(B))

    print("=== Ditto SQL layer (SYNTHETIC, NOT MARKET EVIDENCE) ===")
    print("SQLite %s | %d creatives, %d briefs, %d Python matches loaded" % (sqlite3.sqlite_version, len(C), len(B), len(py_top)))
    for name, ok, detail in checks:
        print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name, (" (%s)" % detail) if detail else ""))
    print("BI tables written to %s: %s" % (args.out_dir, ", ".join(sorted(os.listdir(args.out_dir)))))
    bad = [n for n, ok, _ in checks if not ok]
    if bad:
        print("FAILED: %s" % bad)
        sys.exit(1)
    print("all %d checks passed" % len(checks))


if __name__ == "__main__":
    main()
