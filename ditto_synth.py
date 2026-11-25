#!/usr/bin/env python3
"""Ditto MVP Validation: synthetic data generator (synthetic_v1).

SYNTHETIC DATA ONLY. Every record is fictional, flagged is_demo=true and is
not market evidence. Standard library only. No network calls at runtime.
Usage: python3 ditto_synth.py [--seed N] [--reference-date YYYY-MM-DD] [--out-dir DIR]
"""
import argparse
import csv
import datetime as dt
import json
import math
import os
import random
import statistics
from collections import Counter

GENERATOR_VERSION = "1.0.0"
DATA_SOURCE = "synthetic_v1"
DEFAULT_SEED = 20261125
DEFAULT_REFERENCE_DATE = "2026-11-25"
N_CREATIVES, N_BRIEFS = 200, 100
CURRENCIES = ("GBP", "EUR", "USD")
EMAIL_DOMAINS = ("example.com", "example.invalid")
URL_HOST = "example.invalid"
PROTECTED_FIELDS = {"age", "date_of_birth", "dob", "gender", "sex", "ethnicity", "race",
                    "religion", "belief", "disability", "health_condition",
                    "sexual_orientation", "marital_status", "pregnancy", "nationality"}

# Comments give assumption IDs from the data note register.
# A01: typical UK day rate (GBP, major units). A27: skill taxonomy.
DISCIPLINES = {
    "graphic_brand_design": (372, ["logo_design", "brand_identity", "typography", "packaging_design", "presentation_design", "print_design"]),
    "illustration": (359, ["illustration", "editorial_illustration", "character_design", "hand_lettering", "infographics"]),
    "ux_ui_web_design": (448, ["web_design", "ui_design", "ux_research", "wireframing", "prototyping"]),
    "front_end_web_dev": (400, ["html_css", "javascript", "wordpress", "shopify", "webflow"]),
    "copywriting": (408, ["copywriting", "web_copy", "tone_of_voice", "scriptwriting", "seo_writing"]),
    "content_writing": (339, ["content_writing", "blog_writing", "seo_writing", "newsletter_writing", "proofreading"]),
    "social_media": (326, ["social_content_creation", "content_calendar", "community_management", "short_form_video", "social_media_management"]),
    "photography": (475, ["product_photography", "photo_retouching", "lifestyle_photography", "food_photography", "event_photography"]),
    "videography_editing": (427, ["videography", "video_editing", "colour_grading", "short_form_video", "scriptwriting"]),
    "motion_animation": (385, ["motion_graphics", "explainer_animation", "2d_animation", "storyboarding", "video_editing"]),
    "brand_strategy": (494, ["brand_strategy", "positioning", "naming", "tone_of_voice", "audience_research"]),
    "art_direction": (409, ["art_direction", "campaign_concepts", "shoot_direction", "brand_identity", "presentation_design"]),
    "audio_podcast": (400, ["podcast_editing", "audio_mixing", "podcast_production", "sound_design", "voiceover_direction"]),
    "3d_cgi": (430, ["3d_modelling", "3d_rendering", "product_visualisation", "3d_animation", "texturing"]),
}
ADJACENT = {  # A30: adjacent disciplines for secondary skills
    "graphic_brand_design": ["illustration", "art_direction"],
    "illustration": ["graphic_brand_design"],
    "ux_ui_web_design": ["front_end_web_dev", "graphic_brand_design"],
    "front_end_web_dev": ["ux_ui_web_design"],
    "copywriting": ["content_writing", "brand_strategy"],
    "content_writing": ["copywriting", "social_media"],
    "social_media": ["content_writing", "photography"],
    "photography": ["videography_editing", "art_direction"],
    "videography_editing": ["motion_animation", "photography"],
    "motion_animation": ["videography_editing", "3d_cgi"],
    "brand_strategy": ["copywriting", "graphic_brand_design"],
    "art_direction": ["graphic_brand_design", "photography"],
    "audio_podcast": ["videography_editing"],
    "3d_cgi": ["motion_animation"],
}
ADJACENT_SKILL_PROB, BRIEF_EXTRA_SKILL_PROB = 0.3, 0.4  # A30
DISCIPLINE_WEIGHTS = {"graphic_brand_design": 14, "illustration": 7, "ux_ui_web_design": 9,
                      "front_end_web_dev": 6, "copywriting": 8, "content_writing": 7,
                      "social_media": 9, "photography": 9, "videography_editing": 8,
                      "motion_animation": 7, "brand_strategy": 4, "art_direction": 4,
                      "audio_podcast": 3, "3d_cgi": 5}  # A02
SENIORITY = {"junior": (20, 0.70), "midweight": (40, 0.90), "senior": (30, 1.02), "lead": (10, 1.10)}  # A03
RATE_NOISE_SD, RATE_FLOOR, RATE_CEILING = 0.15, 0.5, 1.9  # A04, A05
CREATIVE_CURRENCY = {"GBP": 85, "EUR": 10, "USD": 5}  # A06
BRIEF_CURRENCY = {"GBP": 90, "EUR": 7, "USD": 3}  # A06
# A07: nominal price level used only when generating a NEW amount in that currency.
# It is never applied to an existing amount and is not an exchange rate.
NOMINAL_LEVEL = {"GBP": 1.0, "EUR": 1.15, "USD": 1.25}
CITIES = {
    "London": ["London"], "South East": ["Brighton", "Oxford", "Reading", "Southampton"],
    "North West": ["Manchester", "Liverpool", "Preston"], "East of England": ["Cambridge", "Norwich", "Ipswich"],
    "South West": ["Bristol", "Exeter", "Plymouth"], "Scotland": ["Glasgow", "Edinburgh", "Dundee"],
    "West Midlands": ["Birmingham", "Coventry"], "Yorkshire and the Humber": ["Leeds", "Sheffield", "York"],
    "East Midlands": ["Nottingham", "Leicester", "Derby"], "Wales": ["Cardiff", "Swansea"],
    "North East": ["Newcastle upon Tyne", "Sunderland"], "Northern Ireland": ["Belfast", "Derry"],
}
CREATIVE_REGION = {"London": 30.3, "South East": 16.0, "North West": 9.0, "East of England": 8.0,
                   "South West": 7.0, "Scotland": 7.0, "West Midlands": 6.0,
                   "Yorkshire and the Humber": 5.7, "East Midlands": 4.0, "Wales": 3.0,
                   "North East": 2.0, "Northern Ireland": 2.0}  # A08
BRIEF_REGION = {"London": 18, "South East": 15, "North West": 10, "East of England": 10,
                "South West": 9, "Scotland": 7, "West Midlands": 8, "Yorkshire and the Humber": 7,
                "East Midlands": 7, "Wales": 4, "North East": 3, "Northern Ireland": 2}  # A09
CREATIVE_MODE = {"remote": 45, "hybrid": 40, "on_site": 15}  # A10
BRIEF_MODE = {"remote": 50, "hybrid": 35, "on_site": 15}  # A11
DAYS_PER_WEEK = {1: 5, 2: 15, 3: 25, 4: 25, 5: 30}  # A12
IMMEDIATE_SHARE, START_OFFSET, WINDOW_DAYS = 0.30, (1, 60), (30, 180)  # A13, A14


def _pt(disc, req, ess, budget, effort, duration, weight, deliverables):
    return {"disc": disc, "req": req, "ess": ess, "budget": budget, "effort": effort,
            "duration": duration, "weight": weight, "deliverables": deliverables}


# A15 budget (GBP major min, max), A16 effort (working days), A17 duration (calendar days), A18 weight
PROJECT_TYPES = {
    "logo_brand_identity": _pt("graphic_brand_design", ["logo_design", "brand_identity", "typography"], ["logo_design", "brand_identity"], (500, 5000), (3, 10), (14, 42), 16, ["primary logo", "colour palette", "brand guidelines"]),
    "website_design": _pt("ux_ui_web_design", ["web_design", "ui_design", "wireframing"], ["web_design", "ui_design"], (1500, 10000), (8, 25), (21, 60), 16, ["sitemap", "page designs", "responsive templates"]),
    "social_media_content_package": _pt("social_media", ["social_content_creation", "content_calendar", "short_form_video"], ["social_content_creation", "content_calendar"], (300, 2500), (3, 10), (14, 31), 14, ["content calendar", "post templates", "short videos"]),
    "product_photography": _pt("photography", ["product_photography", "photo_retouching"], ["product_photography"], (300, 2000), (1, 4), (3, 14), 10, ["packshots", "lifestyle images"]),
    "promo_video": _pt("videography_editing", ["videography", "video_editing", "scriptwriting"], ["videography", "video_editing"], (1500, 6000), (4, 12), (14, 42), 9, ["60 to 120 second edit", "social cutdowns"]),
    "motion_explainer": _pt("motion_animation", ["explainer_animation", "motion_graphics", "storyboarding"], ["explainer_animation", "motion_graphics"], (3000, 10000), (6, 18), (21, 49), 6, ["script", "storyboard", "60 second animation"]),
    "copywriting_package": _pt("copywriting", ["copywriting", "web_copy", "tone_of_voice"], ["copywriting", "web_copy"], (500, 3000), (2, 8), (7, 21), 9, ["website copy", "tone of voice notes"]),
    "packaging_design": _pt("graphic_brand_design", ["packaging_design", "typography", "print_design"], ["packaging_design"], (1000, 6000), (4, 12), (21, 49), 5, ["pack artwork", "print-ready files"]),
    "pitch_deck_design": _pt("graphic_brand_design", ["presentation_design", "typography"], ["presentation_design"], (500, 3000), (2, 6), (5, 15), 6, ["slide master", "designed deck"]),
    "illustration_set": _pt("illustration", ["illustration", "editorial_illustration"], ["illustration"], (400, 3000), (2, 8), (7, 30), 4, ["illustration set"]),
    "podcast_production": _pt("audio_podcast", ["podcast_editing", "audio_mixing", "podcast_production"], ["podcast_editing", "audio_mixing"], (500, 3000), (2, 8), (7, 30), 2, ["edited episodes", "show audio template"]),
    "3d_product_render": _pt("3d_cgi", ["3d_modelling", "3d_rendering", "product_visualisation"], ["3d_modelling", "3d_rendering"], (1000, 6000), (3, 10), (14, 35), 3, ["3D model", "rendered stills"]),
}
SECTORS = {"retail": 14, "hospitality": 9, "professional_services": 16, "health_wellness": 9,
           "tech": 9, "construction": 10, "education": 5, "charity_social_enterprise": 6,
           "food_drink": 10, "property": 7, "other": 5}  # A19
SIZE_BANDS = {"no_employees": 35, "micro_1_9": 40, "small_10_49": 20, "medium_50_249": 5}  # A20
BRIEF_START_OFFSET = (7, 60)  # A21
SCENARIOS = {"normal": 70, "budget_below_market": 10, "deadline_too_tight": 8,
             "rare_skill_combo": 6, "thin_location": 6}  # A22
PORTFOLIO_SHARE, MISSING_OPTIONAL_SHARE = 0.6, 0.25  # A23, A24
FEE_RESPONSES = {"would_pay": 25, "would_pay_if_shortlist_useful": 35, "unsure": 20, "would_not_pay": 20}  # A25
FEE_RANGE_MAJOR = (25, 150)  # A26
STYLE_TAGS = ["minimalist", "bold", "playful", "editorial", "corporate", "hand_drawn", "retro",
              "luxury", "eco_conscious", "tech_forward", "warm_and_friendly", "monochrome",
              "colourful", "geometric", "organic", "documentary", "cinematic", "data_led"]  # A28
GOALS = ["long_term_client", "portfolio_growth", "steady_monthly_work", "interesting_briefs",
         "small_business_focus", "purpose_led_work"]
COMMS = ["email", "video_call", "phone", "async_messaging", "in_person"]
OBJECTIVES = ["launch_new_brand", "refresh_existing_brand", "increase_online_sales", "generate_leads",
              "explain_product", "grow_social_audience", "support_funding_pitch", "improve_product_listings"]
COLLAB_PREFS = ["fixed_price_preferred", "day_rate_acceptable", "weekly_check_in", "minimal_meetings",
                "collaborative_workshops"]
MIN_BASE_RATE = min(v[0] for v in DISCIPLINES.values())


def wchoice(rng, weights):
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def quota(rng, weights, n):
    """Exact counts by largest remainder, then shuffled, so planted shares are fixed."""
    total = float(sum(weights.values()))
    raw = {k: n * v / total for k, v in weights.items()}
    counts = {k: int(math.floor(x)) for k, x in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - counts[k], reverse=True)[:n - sum(counts.values())]:
        counts[k] += 1
    out = [k for k in weights for _ in range(counts[k])]
    rng.shuffle(out)
    return out


def minor(major):
    """A29: integer minor units, rounded to the nearest 5 major units, minimum 500."""
    return max(500, int(round(major * 100 / 500.0)) * 500)


def iso(d):
    return d.isoformat()


def meta(seed, ref):
    return {"is_demo": True, "data_source": DATA_SOURCE, "seed": seed,
            "generator_version": GENERATOR_VERSION, "reference_date": iso(ref)}


def make_creatives(rng, seed, ref):
    missing = set(rng.sample(range(1, N_CREATIVES + 1), round(N_CREATIVES * MISSING_OPTIONAL_SHARE)))
    out = []
    for i in range(1, N_CREATIVES + 1):
        cid = "cr_%04d" % i
        disc = wchoice(rng, DISCIPLINE_WEIGHTS)
        base, pool = DISCIPLINES[disc]
        skills = rng.sample(pool, rng.randint(3, len(pool)))
        for adj in ADJACENT[disc]:
            if rng.random() < ADJACENT_SKILL_PROB:
                extra = rng.choice(DISCIPLINES[adj][1])
                if extra not in skills:
                    skills.append(extra)
        band = wchoice(rng, {k: v[0] for k, v in SENIORITY.items()})
        cur = wchoice(rng, CREATIVE_CURRENCY)
        rate = base * SENIORITY[band][1] * rng.lognormvariate(0, RATE_NOISE_SD)
        rate = min(max(rate, base * RATE_FLOOR), base * RATE_CEILING) * NOMINAL_LEVEL[cur]
        day_rate = minor(rate)
        min_budget = minor(day_rate / 100.0 * rng.uniform(1.0, 3.0))
        pref_budget = minor(min_budget / 100.0 * rng.uniform(1.5, 3.0))
        start = ref if rng.random() < IMMEDIATE_SHARE else ref + dt.timedelta(days=rng.randint(*START_OFFSET))
        end = start + dt.timedelta(days=rng.randint(*WINDOW_DAYS))
        region = wchoice(rng, CREATIVE_REGION)
        ptypes = [p for p, v in PROJECT_TYPES.items() if v["disc"] == disc or v["disc"] in ADJACENT[disc]]
        rec = {
            "id": cid, "display_name": "Demo Creative %03d" % i, "email": "creative%03d@example.com" % i,
            "discipline": disc, "skills": sorted(skills),
            "seniority_band": band, "seniority_band_is_hypothesis": True,
            "currency": cur, "day_rate_minor": day_rate,
            "min_project_budget_minor": min_budget, "preferred_project_budget_minor": pref_budget,
            "availability_start": iso(start), "availability_end": iso(end),
            "days_per_week": wchoice(rng, DAYS_PER_WEEK),
            "region": region, "city": rng.choice(CITIES[region]),
            "work_mode": wchoice(rng, CREATIVE_MODE),
            "style_tags": sorted(rng.sample(STYLE_TAGS, rng.randint(2, 4))),
            "preferred_project_types": sorted(rng.sample(ptypes, rng.randint(1, min(3, len(ptypes))))),
            "collaboration_goals": sorted(rng.sample(GOALS, rng.randint(1, 3))),
            "communication_preferences": sorted(rng.sample(COMMS, rng.randint(1, 3))),
            "portfolio_url": ("https://portfolio.%s/%s" % (URL_HOST, cid)) if rng.random() < PORTFOLIO_SHARE else None,
            "synthetic_scenario": "missing_optional_fields" if i in missing else "normal",
        }
        if i in missing:
            rec["collaboration_goals"] = None
            rec["communication_preferences"] = None
        rec.update(meta(seed, ref))
        out.append(rec)
    return out


def make_briefs(rng, seed, ref):
    scenarios = quota(rng, SCENARIOS, N_BRIEFS)
    out = []
    for j in range(1, N_BRIEFS + 1):
        bid, scen = "br_%04d" % j, scenarios[j - 1]
        ptype = wchoice(rng, {k: v["weight"] for k, v in PROJECT_TYPES.items()})
        pt = PROJECT_TYPES[ptype]
        required, essential = list(pt["req"]), list(pt["ess"])
        if rng.random() < BRIEF_EXTRA_SKILL_PROB:
            extra = rng.choice(DISCIPLINES[pt["disc"]][1])
            if extra not in required:
                required.append(extra)
        cur = wchoice(rng, BRIEF_CURRENCY)
        lo, hi = pt["budget"]
        budget_max = math.exp(rng.uniform(math.log(lo), math.log(hi)))
        effort = rng.randint(*pt["effort"])
        duration = rng.randint(*pt["duration"])
        mode = wchoice(rng, BRIEF_MODE)
        region = wchoice(rng, BRIEF_REGION)
        if scen == "budget_below_market":
            budget_max = MIN_BASE_RATE * RATE_FLOOR * effort * rng.uniform(0.4, 0.9)
        if scen == "deadline_too_tight":
            effort = max(effort, 3)
            duration = max(1, effort // 3)
        else:
            duration = max(duration, int(math.ceil(effort * 7 / 4.0)))  # A17 feasibility rule
        if scen == "rare_skill_combo":
            others = [d for d in DISCIPLINES if d != pt["disc"] and d not in ADJACENT[pt["disc"]]]
            for d in rng.sample(others, 2):
                s = rng.choice(DISCIPLINES[d][1])
                if s not in required:
                    required.append(s)
                if s not in essential:
                    essential.append(s)
        if scen == "thin_location":
            mode, region = "on_site", rng.choice(["Northern Ireland", "North East"])
        bmax = minor(budget_max * NOMINAL_LEVEL[cur])
        bmin = min(bmax, minor(bmax / 100.0 * rng.uniform(0.5, 0.85)))
        earliest = ref + dt.timedelta(days=rng.randint(*BRIEF_START_OFFSET))
        sector, size = wchoice(rng, SECTORS), wchoice(rng, SIZE_BANDS)
        objectives = sorted(rng.sample(OBJECTIVES, rng.randint(1, 2)))
        style = sorted(rng.sample(STYLE_TAGS, rng.randint(1, 3)))
        fee = wchoice(rng, FEE_RESPONSES)
        fee_amount = minor(rng.uniform(*FEE_RANGE_MAJOR) * NOMINAL_LEVEL[cur]) if fee.startswith("would_pay") else None
        city = rng.choice(CITIES[region])
        rec = {
            "id": bid, "business_name": "Demo Business %03d" % j, "email": "brief%03d@example.com" % j,
            "sector": sector, "size_band": size, "project_type": ptype,
            "project_description": ("Synthetic brief %s: a fictional %s business in the %s sector wants %s. "
                                    "Main objective: %s. Preferred style: %s. Generated text; it describes "
                                    "no real organisation or brand.") % (bid, size, sector, ptype.replace("_", " "),
                                                                         objectives[0], ", ".join(style)),
            "deliverables": list(pt["deliverables"]),
            "required_skills": sorted(required), "essential_skills": sorted(essential),
            "style_tags": style,
            "reference_urls": ["https://reference.%s/%s/ref-%d" % (URL_HOST, bid, k) for k in range(1, rng.randint(0, 3) + 1)],
            "currency": cur, "budget_min_minor": bmin, "budget_max_minor": bmax,
            "earliest_start": iso(earliest), "deadline": iso(earliest + dt.timedelta(days=duration)),
            "expected_duration_days": duration, "estimated_effort_days": effort,
            "work_mode": mode,
            "location_region": region if mode != "remote" else None,
            "location_city": city if mode != "remote" else None,
            "objectives": objectives,
            "communication_preferences": sorted(rng.sample(COMMS, rng.randint(1, 2))),
            "collaboration_preferences": sorted(rng.sample(COLLAB_PREFS, rng.randint(1, 2))),
            "service_fee_response": fee, "service_fee_amount_minor": fee_amount,
            "consent": True, "consent_is_simulated": True,
            "synthetic_scenario": scen,
        }
        rec.update(meta(seed, ref))
        out.append(rec)
    return out


def hard_eligible(c, b):
    """Deterministic hard-eligibility rules. Never compares across currencies."""
    if c["currency"] != b["currency"]:
        return False, "currency_mismatch"
    if not set(b["essential_skills"]) <= set(c["skills"]):
        return False, "essential_skills"
    effort = b["estimated_effort_days"]
    if c["day_rate_minor"] * effort > b["budget_max_minor"] or c["min_project_budget_minor"] > b["budget_max_minor"]:
        return False, "budget"
    ws = max(dt.date.fromisoformat(b["earliest_start"]), dt.date.fromisoformat(c["availability_start"]))
    we = min(dt.date.fromisoformat(b["deadline"]), dt.date.fromisoformat(c["availability_end"]))
    if we < ws or ((we - ws).days + 1) * c["days_per_week"] / 7.0 < effort:
        return False, "availability"
    if b["work_mode"] != "remote" and (c["work_mode"] == "remote" or c["region"] != b["location_region"]):
        return False, "location"
    return True, "eligible"


def baseline(creatives, briefs):
    per = []
    for b in briefs:
        ok, reasons = [], Counter()
        for c in creatives:
            good, why = hard_eligible(c, b)
            if good:
                ok.append(c["id"])
            else:
                reasons[why] += 1
        per.append({"brief_id": b["id"], "synthetic_scenario": b["synthetic_scenario"],
                    "viable_count": len(ok), "viable_creative_ids": ok,
                    "first_failure_reason_counts": dict(sorted(reasons.items()))})
    by_scen = {}
    for s in SCENARIOS:
        rows = [p for p in per if p["synthetic_scenario"] == s]
        by_scen[s] = {"briefs": len(rows), "with_at_least_one_viable": sum(1 for p in rows if p["viable_count"] > 0)}
    return {"label": "SYNTHETIC BASELINE: hard constraints only. Not market evidence.",
            "with_at_least_one_viable": sum(1 for p in per if p["viable_count"] > 0),
            "briefs": len(per), "by_scenario": by_scen, "per_brief": per}


def validate(creatives, briefs):
    checks = []

    def chk(name, cond):
        checks.append((name, bool(cond)))

    allrec = creatives + briefs
    money = ("day_rate_minor", "min_project_budget_minor", "preferred_project_budget_minor",
             "budget_min_minor", "budget_max_minor", "service_fee_amount_minor")
    chk("creative count == %d" % N_CREATIVES, len(creatives) == N_CREATIVES)
    chk("brief count == %d" % N_BRIEFS, len(briefs) == N_BRIEFS)
    chk("unique ids", len({r["id"] for r in allrec}) == len(allrec))
    chk("essential skills subset of required", all(set(b["essential_skills"]) <= set(b["required_skills"]) for b in briefs))
    chk("brief budget min <= max", all(b["budget_min_minor"] <= b["budget_max_minor"] for b in briefs))
    chk("creative min budget <= preferred", all(c["min_project_budget_minor"] <= c["preferred_project_budget_minor"] for c in creatives))
    chk("deadline after earliest start", all(b["deadline"] > b["earliest_start"] for b in briefs))
    chk("availability end after start", all(c["availability_end"] > c["availability_start"] for c in creatives))
    chk("valid currencies", all(r["currency"] in CURRENCIES for r in allrec))
    chk("integer minor units", all(type(r[k]) is int and r[k] >= 0 for r in allrec for k in money if r.get(k) is not None))
    chk("no protected-attribute fields", all(not ({k.lower() for k in r} & PROTECTED_FIELDS) for r in allrec))
    chk("emails on reserved domains", all(r["email"].rsplit("@", 1)[-1] in EMAIL_DOMAINS for r in allrec))
    chk("demo flag and provenance on every record", all(r["is_demo"] is True and r["data_source"] == DATA_SOURCE
                                                        and isinstance(r["seed"], int)
                                                        and r["generator_version"] == GENERATOR_VERSION for r in allrec))
    chk("hybrid and on-site briefs have a location", all(b["location_region"] and b["location_city"]
                                                         for b in briefs if b["work_mode"] != "remote"))
    urls = [c["portfolio_url"] for c in creatives if c["portfolio_url"]] + [u for b in briefs for u in b["reference_urls"]]
    chk("URLs on placeholder host", all(u.split("/")[2].endswith(URL_HOST) for u in urls))
    chk("simulated consent on every brief", all(b["consent"] is True and b["consent_is_simulated"] is True for b in briefs))
    return checks


def cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "|".join(str(x) for x in v)
    return v


def write_csv(path, records):
    fields = sorted(records[0])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            w.writerow({k: cell(r[k]) for k in fields})


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")


def dist(name, values):
    c = Counter(values)
    print("  %s: %s" % (name, ", ".join("%s=%d" % (k, v) for k, v in sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0]))))))


def main():
    ap = argparse.ArgumentParser(description="Ditto synthetic data generator (synthetic_v1). Not market evidence.")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--reference-date", default=DEFAULT_REFERENCE_DATE)
    ap.add_argument("--out-dir", default="ditto_synthetic_out")
    args = ap.parse_args()
    ref = dt.date.fromisoformat(args.reference_date)
    rng = random.Random(args.seed)
    creatives = make_creatives(rng, args.seed, ref)
    briefs = make_briefs(rng, args.seed, ref)
    base = baseline(creatives, briefs)
    os.makedirs(args.out_dir, exist_ok=True)
    header = {"label": "SYNTHETIC DATA ONLY. Not market evidence.", **meta(args.seed, ref)}
    write_json(os.path.join(args.out_dir, "creatives.json"), {"meta": header, "records": creatives})
    write_json(os.path.join(args.out_dir, "briefs.json"), {"meta": header, "records": briefs})
    write_json(os.path.join(args.out_dir, "ground_truth_baseline.json"), {"meta": header, **base})
    write_csv(os.path.join(args.out_dir, "creatives.csv"), creatives)
    write_csv(os.path.join(args.out_dir, "briefs.csv"), briefs)

    print("=== Ditto synthetic data validation report (SYNTHETIC, NOT MARKET EVIDENCE) ===")
    print("generator %s, data_source %s, seed %d, reference date %s" % (GENERATOR_VERSION, DATA_SOURCE, args.seed, iso(ref)))
    print("counts: creatives=%d briefs=%d" % (len(creatives), len(briefs)))
    print("creatives:")
    for k in ("discipline", "seniority_band", "currency", "region", "work_mode", "days_per_week", "synthetic_scenario"):
        dist(k, [c[k] for c in creatives])
    for cur in CURRENCIES:
        rates = [c["day_rate_minor"] for c in creatives if c["currency"] == cur]
        if rates:
            print("  median day rate %s (minor units, this currency only): %d" % (cur, statistics.median(rates)))
    print("  portfolio_url present: %d" % sum(1 for c in creatives if c["portfolio_url"]))
    print("briefs:")
    for k in ("project_type", "sector", "size_band", "currency", "work_mode", "service_fee_response", "synthetic_scenario"):
        dist(k, [b[k] for b in briefs])
    print("hard-constraint baseline: %d of %d briefs have at least one viable creative" % (base["with_at_least_one_viable"], base["briefs"]))
    for s, v in base["by_scenario"].items():
        print("  %s: %d of %d" % (s, v["with_at_least_one_viable"], v["briefs"]))
    checks = validate(creatives, briefs)
    print("constraint checks:")
    for name, ok in checks:
        print("  [%s] %s" % ("PASS" if ok else "FAIL", name))
    failed = [n for n, ok in checks if not ok]
    if failed:
        raise AssertionError("validation failed: %s" % failed)
    print("all checks passed; files written to %s" % args.out_dir)


if __name__ == "__main__":
    main()
