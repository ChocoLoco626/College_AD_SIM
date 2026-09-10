import random
from names import person_name, coach_profile

SPORTS = {
    "football": {"season_start": "2026-08-27", "strength_weight": 1.0},
    "men_basketball": {"season_start": "2026-11-02", "strength_weight": 0.65},
    "women_basketball": {"season_start": "2026-11-02", "strength_weight": 0.62},
    "baseball": {"season_start": "2027-02-19", "strength_weight": 0.55},
    "softball": {"season_start": "2027-02-19", "strength_weight": 0.53},
    "volleyball": {"season_start": "2026-08-28", "strength_weight": 0.50},
}

def new_world(schools, seed):
    rng = random.Random(seed)
    world = {"schools": {}, "coaches": {}, "ad_people": {}, "jobs": [],
             "results": [], "history": [], "news": []}
    for s in schools:
        sid = s["id"]
        p = int(s.get("prestige", 50))
        world["schools"][sid] = {
            "name": s["name"], "conference": s.get("conference", "Independent"),
            "subdivision": s.get("subdivision", "DI"), "prestige": p,
            "budget": max(18_000_000, p * 2_100_000),
            "facilities": max(25, min(95, p + rng.randint(-15, 15))),
            "academic": rng.randint(55, 95),
            "attendance": max(5000, int(p * rng.uniform(300, 700))),
            "records": {sport: {"w": 0, "l": 0} for sport in SPORTS},
            "nil_allocations": {sport: 0 for sport in SPORTS},
            "facility_levels": {sport: max(1, min(10, round((p + rng.randint(-10,10))/10))) for sport in SPORTS},
            "facility_investments": [], "coach_history": [],
            "coaches": {sport: None for sport in SPORTS},
            "ad_id": None,
            "president": person_name(rng),
            "goals": {
                "football_wins": max(3, round(p/18)),
                "basketball_wins": max(8, round(p/7)),
                "fundraising": max(1_000_000, p * 65_000)
            }
        }
        # Football/basketball coaches for every school; other sports get coaches too.
        for sport in SPORTS:
            cid = f"coach_{sid}_{sport}"
            world["coaches"][cid] = coach_profile(rng, p)
            world["coaches"][cid]["school_id"] = sid
            world["coaches"][cid]["sport"] = sport
            world["coaches"][cid].setdefault("satisfaction", 72)
            world["coaches"][cid].setdefault("last_demand_date", None)
            world["coaches"][cid].setdefault("demand", None)
            world["coaches"][cid].setdefault("career_years", 0)
            world["schools"][sid]["coaches"][sport] = cid
        aid = f"ad_{sid}"
        world["ad_people"][aid] = {
            "name": person_name(rng),
            "reputation": max(25, min(90, p + rng.randint(-20, 15))),
            "years": rng.randint(1, 12),
            "school_id": sid
        }
        world["schools"][sid]["ad_id"] = aid
    return world

def school_strength(world, sid, sport):
    s = world["schools"][sid]
    cid = s["coaches"].get(sport)
    coach = world["coaches"].get(cid, {})
    nil = s.get("nil_allocations", {}).get(sport, 0)
    nil_effect = min(12, (nil / 1_000_000) * 1.2)
    return s["prestige"] * 0.58 + s["facilities"] * 0.14 + coach.get("overall", 50) * 0.20 + nil_effect

def play_game(world, a, b, sport, rng, date):
    sa = school_strength(world, a, sport)
    sb = school_strength(world, b, sport)
    # Home advantage is modest.
    pa = 1 / (1 + 10 ** (-(sa + 3 - sb) / 18))
    win_a = rng.random() < pa
    winner, loser = (a, b) if win_a else (b, a)
    world["schools"][winner]["records"][sport]["w"] += 1
    world["schools"][loser]["records"][sport]["l"] += 1
    world["results"].append({
        "date": date, "sport": sport, "home": a, "away": b,
        "winner": winner, "loser": loser
    })
    return winner, loser

def simulate_week(world, date, rng):
    ids=list(world["schools"])
    rng.shuffle(ids)
    if date.month in (8,9,10,11,12) and date >= __import__("datetime").date(2026,8,27):
        sport="football"
        eligible=[sid for sid in ids if world["schools"][sid].get("subdivision")=="FBS" or sport in world["schools"][sid]["records"]]
        pairs=[]
        for i in range(0,min(len(eligible)-1,160),2):
            a,b=eligible[i],eligible[i+1]
            pairs.append((a,b))
        for a,b in pairs[:80]:
            play_game(world,a,b,sport,rng,date.isoformat())
    if date.month in (11,12,1,2,3):
        for sport in ("men_basketball","women_basketball"):
            eligible=ids[:]
            for i in range(0,min(len(eligible)-1,160),2):
                play_game(world,eligible[i],eligible[i+1],sport,rng,date.isoformat())
    if date.month in (2,3,4,5,6):
        for sport in ("baseball","softball"):
            eligible=ids[:]
            for i in range(0,min(len(eligible)-1,60),2):
                play_game(world,eligible[i],eligible[i+1],sport,rng,date.isoformat())

def conference_table(world, conference, sport):
    rows = []
    for sid, s in world["schools"].items():
        if s["conference"] != conference:
            continue
        r = s["records"][sport]
        rows.append({"School": s["name"], "W": r["w"], "L": r["l"],
                     "Pct": round(r["w"] / max(1, r["w"]+r["l"]), 3),
                     "Prestige": s["prestige"]})
    return sorted(rows, key=lambda x: (x["Pct"], x["Prestige"]), reverse=True)

def available_jobs(world, current_sid, reputation, rng, limit=8):
    candidates = []
    for sid, s in world["schools"].items():
        if sid == current_sid:
            continue
        p = s["prestige"]
        # Reputation gate with some randomness.
        required = max(25, p - 18)
        if reputation + rng.randint(-5, 7) >= required:
            candidates.append((p + rng.random()*5, sid, required))
    candidates.sort(reverse=True)
    return [{"school_id": sid, "required": req} for _, sid, req in candidates[:limit]]
