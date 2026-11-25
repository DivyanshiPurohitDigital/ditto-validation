-- Ditto matching engine and fairness check in SQL. Synthetic data only.
-- Runs on SQLite 3.25 or later (window functions). Written in standard SQL, so it ports to Postgres or DuckDB
-- with small changes: julianday() becomes date subtraction, and MIN()/MAX() of two values becomes LEAST()/GREATEST().
-- ditto_sql.py loads the tables, runs every block below, and reconciles the results to the Python engine.
--
-- Tables: creatives, creative_skills, creative_styles, briefs, brief_skills, brief_styles, project_types,
--         tiebreak (seeded SHA-256 per brief and creative, computed in Python because SQLite has no SHA-256),
--         matches_py (Python top five, used only for reconciliation).
-- Weights: skills 0.40, budget 0.25, availability 0.20, style 0.15. If a brief has no style tags, style is dropped
--          and the other weights are rescaled.

-- name: view_pair_gates
-- Hard gates for every brief and creative pair: currency, essential skills, location.
CREATE VIEW pair_gates AS
SELECT b.id AS brief_id,
       c.id AS creative_id,
       (c.currency = b.currency) AS ok_currency,
       (NOT EXISTS (
            SELECT 1 FROM brief_skills bs
            WHERE bs.brief_id = b.id AND bs.is_essential = 1
              AND NOT EXISTS (SELECT 1 FROM creative_skills cs
                              WHERE cs.creative_id = c.id AND cs.skill = bs.skill))) AS ok_skills,
       (b.work_mode = 'remote'
        OR (c.work_mode <> 'remote' AND c.region = b.location_region)) AS ok_location
FROM briefs b CROSS JOIN creatives c;

-- name: view_pair_scores
-- Score every pair that passes the gates. Money is compared only inside one currency (the gate guarantees it).
CREATE VIEW pair_scores AS
WITH cand AS (
    SELECT brief_id, creative_id FROM pair_gates WHERE ok_currency AND ok_skills AND ok_location
),
sk AS (
    SELECT cand.brief_id, cand.creative_id,
           1.0 * SUM(CASE WHEN cs.skill IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*) AS skills_score
    FROM cand
    JOIN brief_skills bs ON bs.brief_id = cand.brief_id
    LEFT JOIN creative_skills cs ON cs.creative_id = cand.creative_id AND cs.skill = bs.skill
    GROUP BY cand.brief_id, cand.creative_id
),
st AS (
    SELECT cand.brief_id, cand.creative_id,
           COUNT(bt.tag) AS n_tags,
           SUM(CASE WHEN ct.tag IS NOT NULL THEN 1 ELSE 0 END) AS n_shared
    FROM cand
    LEFT JOIN brief_styles bt ON bt.brief_id = cand.brief_id
    LEFT JOIN creative_styles ct ON ct.creative_id = cand.creative_id AND ct.tag = bt.tag
    GROUP BY cand.brief_id, cand.creative_id
),
base AS (
    SELECT cand.brief_id, cand.creative_id,
           b.estimated_effort_days AS effort,
           COALESCE(NULLIF(b.budget_min_minor, 0), b.budget_max_minor) AS bmin,
           b.budget_max_minor AS bmax,
           c.day_rate_minor * b.estimated_effort_days AS cost,
           c.min_project_budget_minor AS creative_min,
           c.days_per_week AS dpw,
           MAX(1, CAST(julianday(b.deadline) - julianday(b.earliest_start) AS INTEGER)) AS window_days,
           MAX(0, CAST(julianday(c.availability_start) - julianday(b.earliest_start) AS INTEGER)) AS lateness,
           CASE WHEN MIN(b.deadline, c.availability_end) >= MAX(b.earliest_start, c.availability_start)
                THEN julianday(MIN(b.deadline, c.availability_end))
                     - julianday(MAX(b.earliest_start, c.availability_start)) + 1
                ELSE 0 END AS overlap_days
    FROM cand
    JOIN briefs b ON b.id = cand.brief_id
    JOIN creatives c ON c.id = cand.creative_id
),
comp AS (
    SELECT base.*,
           CASE WHEN cost <= bmin THEN 1.0
                WHEN cost <= bmax THEN CASE WHEN bmax > bmin
                                            THEN 1.0 - 0.5 * (cost - bmin) * 1.0 / (bmax - bmin)
                                            ELSE 1.0 END
                ELSE MAX(0.0, 0.5 * (1.0 - (cost - bmax) * 1.0 / (bmax * 0.5))) END AS budget_score,
           (cost <= bmax AND creative_min <= bmax) AS budget_ok,
           overlap_days * dpw / 7.0 AS capacity
    FROM base
),
av AS (
    SELECT comp.*,
           MIN(1.0, capacity / effort) * MAX(0.0, 1.0 - lateness * 1.0 / window_days) AS availability_score,
           (capacity >= effort) AS availability_ok
    FROM comp
)
SELECT av.brief_id, av.creative_id,
       sk.skills_score, av.budget_score, av.availability_score,
       CASE WHEN st.n_tags = 0 THEN NULL ELSE 1.0 * st.n_shared / st.n_tags END AS style_score,
       (av.budget_ok AND av.availability_ok) AS feasible,
       (0.40 * sk.skills_score + 0.25 * av.budget_score + 0.20 * av.availability_score
        + CASE WHEN st.n_tags = 0 THEN 0.0 ELSE 0.15 * st.n_shared * 1.0 / st.n_tags END)
       / (CASE WHEN st.n_tags = 0 THEN 0.85 ELSE 1.0 END) AS score
FROM av
JOIN sk ON sk.brief_id = av.brief_id AND sk.creative_id = av.creative_id
JOIN st ON st.brief_id = av.brief_id AND st.creative_id = av.creative_id;

-- name: view_ranked
-- Rank within each brief: fits budget and deadline first, then score, then the seeded tie-break.
CREATE VIEW ranked AS
SELECT ps.*,
       ROW_NUMBER() OVER (PARTITION BY ps.brief_id
                          ORDER BY ps.feasible DESC, ROUND(ps.score, 9) DESC, t.tb ASC) AS rnk,
       COUNT(*) OVER (PARTITION BY ps.brief_id) AS pool_size
FROM pair_scores ps
JOIN tiebreak t ON t.brief_id = ps.brief_id AND t.creative_id = ps.creative_id;

-- name: view_top_five
CREATE VIEW top_five AS SELECT * FROM ranked WHERE rnk <= 5;

-- name: q_funnel
-- What happens to each brief, and the gate that empties the pool when nothing passes.
WITH g AS (
    SELECT brief_id,
           SUM(ok_currency) AS after_currency,
           SUM(ok_currency AND ok_skills) AS after_skills,
           SUM(ok_currency AND ok_skills AND ok_location) AS after_location
    FROM pair_gates GROUP BY brief_id
),
f AS (
    SELECT b.id AS brief_id, COALESCE(SUM(r.feasible), 0) AS feasible_count
    FROM briefs b LEFT JOIN ranked r ON r.brief_id = b.id GROUP BY b.id
)
SELECT CASE WHEN g.after_location = 0 AND g.after_currency = 0 THEN '1. no candidate: no creative prices in the currency'
            WHEN g.after_location = 0 AND g.after_skills = 0 THEN '2. no candidate: no creative has every essential skill'
            WHEN g.after_location = 0 THEN '3. no candidate: skilled creatives exist, none can work in the place'
            WHEN f.feasible_count = 0 THEN '4. candidates found, none fit budget and deadline'
            ELSE '5. at least one match fits budget and deadline' END AS outcome,
       COUNT(*) AS briefs
FROM g JOIN f ON f.brief_id = g.brief_id
GROUP BY outcome ORDER BY outcome;

-- name: q_exposure_per_creative
-- Slots won in the top five, and how many briefs each creative was a candidate for.
SELECT c.id AS creative_id, c.discipline, c.region, c.seniority_band, c.work_mode, c.currency,
       COALESCE(t.slots, 0) AS slots,
       COALESCE(p.candidate_briefs, 0) AS candidate_briefs
FROM creatives c
LEFT JOIN (SELECT creative_id, COUNT(*) AS slots FROM top_five GROUP BY creative_id) t ON t.creative_id = c.id
LEFT JOIN (SELECT creative_id, COUNT(*) AS candidate_briefs FROM ranked GROUP BY creative_id) p ON p.creative_id = c.id
ORDER BY slots DESC, c.id;

-- name: q_exposure_summary
-- Most exposed creative, coverage, ceiling, concentration, Gini (all creatives and gate-passing creatives).
WITH e AS (
    SELECT c.id,
           COALESCE((SELECT COUNT(*) FROM top_five t WHERE t.creative_id = c.id), 0) AS x,
           (SELECT COUNT(*) FROM ranked r WHERE r.creative_id = c.id) AS cand
    FROM creatives c
),
r_all AS (SELECT x, ROW_NUMBER() OVER (ORDER BY x) AS i, COUNT(*) OVER () AS n, SUM(x) OVER () AS s FROM e),
r_pool AS (SELECT x, ROW_NUMBER() OVER (ORDER BY x) AS i, COUNT(*) OVER () AS n, SUM(x) OVER () AS s FROM e WHERE cand > 0),
top10 AS (SELECT SUM(x) AS s10 FROM (SELECT x FROM e ORDER BY x DESC LIMIT 10))
SELECT (SELECT MAX(x) FROM e) AS max_slots,
       (SELECT SUM(x > 0) FROM e) AS creatives_with_slot,
       (SELECT SUM(cand > 0) FROM e) AS coverage_ceiling,
       ROUND(2.0 * (SELECT SUM(i * x) FROM r_all) / ((SELECT MAX(n) FROM r_all) * (SELECT MAX(s) FROM r_all))
             - ((SELECT MAX(n) FROM r_all) + 1.0) / (SELECT MAX(n) FROM r_all), 3) AS gini_all,
       ROUND(2.0 * (SELECT SUM(i * x) FROM r_pool) / ((SELECT MAX(n) FROM r_pool) * (SELECT MAX(s) FROM r_pool))
             - ((SELECT MAX(n) FROM r_pool) + 1.0) / (SELECT MAX(n) FROM r_pool), 3) AS gini_pool,
       ROUND(1.0 * (SELECT s10 FROM top10) / (SELECT SUM(x) FROM e), 3) AS top10_share;

-- name: q_shortlist
-- Simulated owner, rule S1: a top-five match fits budget and deadline and covers at least half the required skills.
SELECT 'S1' AS rule, COUNT(*) AS briefs_shortlisted
FROM briefs b
WHERE EXISTS (SELECT 1 FROM top_five t WHERE t.brief_id = b.id AND t.feasible = 1 AND t.skills_score >= 0.5)
UNION ALL
SELECT 'S2', COUNT(*) FROM briefs b
WHERE EXISTS (SELECT 1 FROM top_five t WHERE t.brief_id = b.id AND t.feasible = 1 AND t.skills_score >= 1.0)
UNION ALL
SELECT 'S3', COUNT(*) FROM briefs b
WHERE EXISTS (SELECT 1 FROM top_five t WHERE t.brief_id = b.id AND t.feasible = 1 AND t.skills_score >= 1.0
                AND t.style_score IS NOT NULL AND t.style_score > 0);

-- name: q_group_lift
-- Exposure against a random draw of five from the same candidate pool, on briefs with more than five candidates.
-- Lift 1.00 means ranking is neutral. Group fields are read here for the audit only, never by scoring.
WITH contested AS (SELECT brief_id, pool_size FROM ranked GROUP BY brief_id HAVING pool_size > 5),
exp AS (
    SELECT r.creative_id, SUM(5.0 / r.pool_size) AS expected
    FROM ranked r JOIN contested k ON k.brief_id = r.brief_id GROUP BY r.creative_id
),
won AS (
    SELECT t.creative_id, COUNT(*) AS slots_contested
    FROM top_five t JOIN contested k ON k.brief_id = t.brief_id GROUP BY t.creative_id
),
per AS (
    SELECT c.id, c.discipline, c.region, c.seniority_band, c.work_mode, c.currency,
           COALESCE(e.expected, 0) AS expected, COALESCE(w.slots_contested, 0) AS won_c,
           (SELECT COUNT(*) FROM top_five t WHERE t.creative_id = c.id) AS slots
    FROM creatives c LEFT JOIN exp e ON e.creative_id = c.id LEFT JOIN won w ON w.creative_id = c.id
)
SELECT 'discipline' AS grp_type, discipline AS grp, COUNT(*) AS creatives, SUM(slots) AS slots,
       ROUND(SUM(expected), 2) AS expected, ROUND(SUM(won_c) / NULLIF(SUM(expected), 0), 2) AS lift FROM per GROUP BY discipline
UNION ALL
SELECT 'region', region, COUNT(*), SUM(slots), ROUND(SUM(expected), 2), ROUND(SUM(won_c) / NULLIF(SUM(expected), 0), 2) FROM per GROUP BY region
UNION ALL
SELECT 'seniority_band', seniority_band, COUNT(*), SUM(slots), ROUND(SUM(expected), 2), ROUND(SUM(won_c) / NULLIF(SUM(expected), 0), 2) FROM per GROUP BY seniority_band
UNION ALL
SELECT 'currency', currency, COUNT(*), SUM(slots), ROUND(SUM(expected), 2), ROUND(SUM(won_c) / NULLIF(SUM(expected), 0), 2) FROM per GROUP BY currency
UNION ALL
SELECT 'work_mode', work_mode, COUNT(*), SUM(slots), ROUND(SUM(expected), 2), ROUND(SUM(won_c) / NULLIF(SUM(expected), 0), 2) FROM per GROUP BY work_mode;

-- name: q_supply_demand
-- Creatives against briefs by discipline, to show where supply and demand do not meet.
SELECT d.discipline,
       COALESCE(s.creatives, 0) AS creatives,
       COALESCE(n.briefs, 0) AS briefs,
       ROUND(1.0 * COALESCE(s.creatives, 0) / NULLIF(n.briefs, 0), 2) AS creatives_per_brief,
       COALESCE(p.creatives_in_a_pool, 0) AS creatives_in_a_pool,
       COALESCE(w.creatives_with_slot, 0) AS creatives_with_slot,
       COALESCE(f.briefs_with_a_feasible_match, 0) AS briefs_with_a_feasible_match
FROM (SELECT DISTINCT discipline FROM creatives) d
LEFT JOIN (SELECT discipline, COUNT(*) AS creatives FROM creatives GROUP BY discipline) s ON s.discipline = d.discipline
LEFT JOIN (SELECT pt.discipline, COUNT(*) AS briefs FROM briefs b JOIN project_types pt ON pt.project_type = b.project_type
           GROUP BY pt.discipline) n ON n.discipline = d.discipline
LEFT JOIN (SELECT c.discipline, COUNT(DISTINCT r.creative_id) AS creatives_in_a_pool FROM ranked r
           JOIN creatives c ON c.id = r.creative_id GROUP BY c.discipline) p ON p.discipline = d.discipline
LEFT JOIN (SELECT c.discipline, COUNT(DISTINCT t.creative_id) AS creatives_with_slot FROM top_five t
           JOIN creatives c ON c.id = t.creative_id GROUP BY c.discipline) w ON w.discipline = d.discipline
LEFT JOIN (SELECT pt.discipline, COUNT(DISTINCT b.id) AS briefs_with_a_feasible_match
           FROM briefs b JOIN project_types pt ON pt.project_type = b.project_type
           JOIN ranked r ON r.brief_id = b.id AND r.feasible = 1 GROUP BY pt.discipline) f ON f.discipline = d.discipline
ORDER BY creatives DESC;

-- name: q_by_work_mode
SELECT b.work_mode, COUNT(*) AS briefs,
       SUM(EXISTS (SELECT 1 FROM ranked r WHERE r.brief_id = b.id)) AS briefs_with_candidates,
       SUM(EXISTS (SELECT 1 FROM ranked r WHERE r.brief_id = b.id AND r.feasible = 1)) AS briefs_with_feasible
FROM briefs b GROUP BY b.work_mode ORDER BY briefs DESC;

-- name: dq_row_counts
SELECT (SELECT COUNT(*) FROM creatives) = 200 AND (SELECT COUNT(*) FROM briefs) = 100 AS ok;

-- name: dq_unique_ids
SELECT (SELECT COUNT(*) - COUNT(DISTINCT id) FROM creatives) + (SELECT COUNT(*) - COUNT(DISTINCT id) FROM briefs) AS violations;

-- name: dq_not_null_money_and_dates
SELECT COUNT(*) AS violations FROM (
    SELECT id FROM creatives WHERE day_rate_minor IS NULL OR min_project_budget_minor IS NULL OR availability_start IS NULL OR availability_end IS NULL
    UNION ALL
    SELECT id FROM briefs WHERE budget_max_minor IS NULL OR earliest_start IS NULL OR deadline IS NULL OR estimated_effort_days IS NULL);

-- name: dq_accepted_currency
SELECT (SELECT COUNT(*) FROM creatives WHERE currency NOT IN ('GBP','EUR','USD'))
     + (SELECT COUNT(*) FROM briefs WHERE currency NOT IN ('GBP','EUR','USD')) AS violations;

-- name: dq_accepted_work_mode
SELECT (SELECT COUNT(*) FROM creatives WHERE work_mode NOT IN ('remote','hybrid','on_site'))
     + (SELECT COUNT(*) FROM briefs WHERE work_mode NOT IN ('remote','hybrid','on_site')) AS violations;

-- name: dq_budget_range
SELECT COUNT(*) AS violations FROM briefs WHERE budget_min_minor > budget_max_minor OR budget_max_minor <= 0;

-- name: dq_dates
SELECT (SELECT COUNT(*) FROM briefs WHERE deadline <= earliest_start)
     + (SELECT COUNT(*) FROM creatives WHERE availability_end <= availability_start) AS violations;

-- name: dq_essential_inside_required
-- Every brief skill flagged essential must be a required skill: here essential is a flag on the brief's skill list,
-- so check that no brief has an essential flag on a skill it does not list, and every brief lists at least one skill.
SELECT (SELECT COUNT(*) FROM briefs b WHERE NOT EXISTS (SELECT 1 FROM brief_skills s WHERE s.brief_id = b.id)) AS violations;

-- name: dq_referential_integrity
SELECT (SELECT COUNT(*) FROM creative_skills WHERE creative_id NOT IN (SELECT id FROM creatives))
     + (SELECT COUNT(*) FROM brief_skills WHERE brief_id NOT IN (SELECT id FROM briefs))
     + (SELECT COUNT(*) FROM matches_py WHERE creative_id NOT IN (SELECT id FROM creatives) OR brief_id NOT IN (SELECT id FROM briefs)) AS violations;

-- name: dq_at_most_five_matches
SELECT COUNT(*) AS violations FROM (SELECT brief_id FROM top_five GROUP BY brief_id HAVING COUNT(*) > 5);

-- name: dq_ranks_contiguous
SELECT COUNT(*) AS violations FROM (SELECT brief_id FROM top_five GROUP BY brief_id HAVING MIN(rnk) <> 1 OR MAX(rnk) <> COUNT(*));

-- name: dq_no_cross_currency_match
SELECT COUNT(*) AS violations FROM top_five t
JOIN briefs b ON b.id = t.brief_id JOIN creatives c ON c.id = t.creative_id WHERE b.currency <> c.currency;

-- name: dq_no_protected_columns
-- Column names in the loaded tables must not include protected attributes.
SELECT COUNT(*) AS violations FROM (
    SELECT name FROM pragma_table_info('creatives') UNION ALL SELECT name FROM pragma_table_info('briefs'))
WHERE lower(name) IN ('age','date_of_birth','dob','gender','sex','ethnicity','race','religion','belief','disability',
                      'health_condition','sexual_orientation','marital_status','pregnancy','nationality');
