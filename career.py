import random
from datetime import date
from world import available_jobs
from names import person_name


def ensure_career_schema(game):
    c = game.setdefault("career", {})
    c.setdefault("job_security", 72)
    c.setdefault("board_approval", 65)
    c.setdefault("reputation", 30)
    c.setdefault("seasons", 0)
    c.setdefault("career_wins", 0)
    c.setdefault("career_losses", 0)
    c.setdefault("fundraising", 0)
    c.setdefault("job_offers", 0)
    c.setdefault("job_offer_pool", [])
    c.setdefault("job_moves", 0)
    c.setdefault("last_move", None)
    world = game.setdefault("world", {})
    world.setdefault("job_openings", [])
    world.setdefault("job_history", [])
    world.setdefault("job_market_last_tick", None)
    world.setdefault("coach_market_last_tick", None)
    return game


def _season_key_for_date(ds):
    d = date.fromisoformat(ds)
    start = d.year if d.month >= 8 else d.year - 1
    return f"{start}-{start+1}"


def _school_season_record(world, sid, season, sport):
    w = l = 0
    for r in world.get("results", []):
        if r.get("sport") != sport or r.get("season") != season:
            continue
        if r.get("winner") == sid:
            w += 1
        elif r.get("loser") == sid:
            l += 1
    return w, l


def _school_resume_score(world, sid, season):
    # A simple AD performance index across the three headline sports.
    score = 0.0
    weights = {"football": 1.0, "men_basketball": 0.75, "women_basketball": 0.5}
    for sport, wt in weights.items():
        w, l = _school_season_record(world, sid, season, sport)
        games = w + l
        if games:
            score += wt * ((w - l) / games) * 100
    return score


def _new_ai_ad(world, sid, reputation=None, rng=None):
    rng = rng or random.Random()
    school = world["schools"][sid]
    p = int(school.get("prestige", 50))
    rep = reputation if reputation is not None else max(25, min(90, p + rng.randint(-18, 12)))
    aid = f"ad_{sid}_{rng.randint(1000,999999)}"
    world["ad_people"][aid] = {
        "name": person_name(rng),
        "reputation": int(max(20, min(99, rep))),
        "years": 0,
        "school_id": sid,
        "status": "Active",
    }
    school["ad_id"] = aid
    return aid


def _close_opening(game, sid, reason="Filled"):
    openings = game["world"].get("job_openings", [])
    for opening in openings:
        if opening.get("school_id") == sid and opening.get("status") == "Open":
            opening["status"] = "Filled"
            opening["closed_date"] = game["date"]
            opening["closed_reason"] = reason
            return opening
    return None


def open_ad_job(game, sid, reason, rng=None):
    ensure_career_schema(game)
    rng = rng or random.Random(game["rng_seed"] + len(game["world"].get("job_history", [])) * 31)
    world = game["world"]
    if sid == game["current_school"]:
        return False
    school = world["schools"].get(sid)
    if not school or school.get("ad_id") is None:
        return False
    if any(x.get("school_id") == sid and x.get("status") == "Open" for x in world.get("job_openings", [])):
        return False
    aid = school.get("ad_id")
    ad = world.get("ad_people", {}).get(aid, {})
    if ad:
        ad["status"] = "Fired" if "fire" in reason.lower() or "pressure" in reason.lower() else "Departed"
        ad["left_date"] = game["date"]
    school["ad_id"] = None
    opening = {
        "id": f"opening_{len(world.get('job_history', [])) + len(world.get('job_openings', [])) + 1}_{rng.randint(1000,999999)}",
        "school_id": sid,
        "opened_date": game["date"],
        "reason": reason,
        "status": "Open",
        "required": max(25, int(school.get("prestige", 50)) - 18),
        "applicants": [],
    }
    world.setdefault("job_openings", []).append(opening)
    world.setdefault("job_history", []).append({**opening})
    game["news"].insert(0, f"{school['name']} has an AD opening: {reason}.")
    game["news"] = game["news"][:30]
    return True


def _ai_fill_openings(game, rng):
    """Let the living job market resolve some vacancies without the player."""
    ensure_career_schema(game)
    world = game["world"]
    current = game["current_school"]
    open_jobs = [x for x in world.get("job_openings", []) if x.get("status") == "Open" and x.get("school_id") != current]
    for opening in open_jobs:
        sid = opening["school_id"]
        school = world["schools"][sid]
        age = max(0, (date.fromisoformat(game["date"]) - date.fromisoformat(opening["opened_date"])).days)
        # Give the player a meaningful window to see openings, while preventing the world from freezing.
        if age < 21 and rng.random() < 0.72:
            continue
        if age < 45 and rng.random() < 0.45:
            continue
        required = int(opening.get("required", max(25, school.get("prestige", 50)-18)))
        candidates = []
        for aid, ad in world.get("ad_people", {}).items():
            if ad.get("status") != "Active" or ad.get("school_id") in (None, sid, current):
                continue
            ar = int(ad.get("reputation", 30))
            if ar + rng.randint(-5, 8) >= required:
                fit = ar + school.get("prestige", 50) * 0.35 + rng.random() * 12
                candidates.append((fit, aid))
        if not candidates:
            continue
        candidates.sort(reverse=True)
        _, aid = candidates[0]
        old_sid = world["ad_people"][aid].get("school_id")
        if old_sid in world["schools"] and world["schools"][old_sid].get("ad_id") == aid:
            world["schools"][old_sid]["ad_id"] = None
            # Immediately create an interim AD so the old school has leadership.
            _new_ai_ad(world, old_sid, reputation=max(25, int(world["ad_people"][aid].get("reputation", 30))-3), rng=rng)
        world["ad_people"][aid]["school_id"] = sid
        world["ad_people"][aid]["years"] = 0
        world["ad_people"][aid]["status"] = "Active"
        school["ad_id"] = aid
        opening["status"] = "Filled"
        opening["closed_date"] = game["date"]
        opening["closed_reason"] = "Accepted by another AD"
        game["news"].insert(0, f"{school['name']} hired {world['ad_people'][aid]['name']} as its new AD.")
        game["news"] = game["news"][:30]


def job_market_tick(game, force=False):
    """Create/resolve realistic AD vacancies during the season."""
    ensure_career_schema(game)
    world = game["world"]
    current = game["current_school"]
    d = date.fromisoformat(game["date"])
    marker = d.isoformat()
    if not force and world.get("job_market_last_tick") == marker:
        return
    world["job_market_last_tick"] = marker
    rng = random.Random(game["rng_seed"] + d.toordinal() * 17 + game["career"].get("seasons", 0) * 991)

    # Evaluate once a week. Higher-pressure programs have a higher chance of making a move.
    if d.weekday() == 0 or force:
        season = _season_key_for_date(game["date"])
        open_count = sum(1 for x in world.get("job_openings", []) if x.get("status") == "Open")
        if open_count < 8:
            schools = [(sid, s) for sid, s in world["schools"].items() if sid != current and s.get("ad_id") is not None]
            rng.shuffle(schools)
            for sid, school in schools:
                if open_count >= 3 and rng.random() < 0.86:
                    break
                aid = school.get("ad_id")
                ad = world["ad_people"].get(aid, {})
                years = int(ad.get("years", 1))
                perf = _school_resume_score(world, sid, season)
                pressure = (school.get("prestige", 50) - int(ad.get("reputation", 50))) * 0.8
                bad_season = perf < -12
                long_tenure = years >= 10 and rng.random() < 0.25
                fire_prob = 0.012 + max(0, pressure) * 0.0018 + (0.025 if bad_season else 0) + (0.02 if long_tenure else 0)
                if rng.random() < fire_prob:
                    reason = "Fired after board pressure" if bad_season or pressure > 15 else "AD vacancy after a leadership change"
                    if open_ad_job(game, sid, reason, rng):
                        open_count += 1
                        if rng.random() < 0.45:
                            break

    _ai_fill_openings(game, rng)


def career_reputation(game):
    ensure_career_schema(game)
    s = game["world"]["schools"][game["current_school"]]
    rep = game["career"]["reputation"]
    for sport in ("football", "men_basketball", "women_basketball"):
        r = s["records"][sport]
        rep += (r["w"] - r["l"]) * 0.18
    rep += (s["facilities"] - 50) * 0.08
    rep += game["career"].get("career_wins", 0) * 0.03
    return max(20, min(99, round(rep)))


def evaluate_board(game):
    s = game["world"]["schools"][game["current_school"]]
    football = s["records"]["football"]
    basketball = s["records"]["men_basketball"]
    goals = s["goals"]
    score = 50
    score += (football["w"] - goals["football_wins"]) * 5
    score += (basketball["w"] - goals["basketball_wins"]) * 2
    score += (s["facilities"] - 50) * .4
    score += game["career"].get("fundraising", 0) / max(1, goals["fundraising"]) * 10
    return max(0, min(100, round(score)))


def apply_season_review(game):
    ensure_career_schema(game)
    s = game["world"]["schools"][game["current_school"]]
    season_start = int(game["date"][:4]) - 1
    season = f"{season_start}-{season_start+1}"
    postseason = game["world"].get("school_postseason", {}).get(game["current_school"], [])
    season_post = [x for x in postseason if str(x.get("season","")).startswith(str(season_start))]
    post_wins = sum(1 for x in season_post if x.get("result") == "W")
    post_losses = sum(1 for x in season_post if x.get("result") == "L")
    reg_wins = 0
    reg_losses = 0
    for r in game["world"].get("results", []):
        if r.get("season") != season:
            continue
        if r.get("winner") == game["current_school"]: reg_wins += 1
        if r.get("loser") == game["current_school"]: reg_losses += 1
    game["career"]["career_wins"] += reg_wins + post_wins
    game["career"]["career_losses"] += reg_losses + post_losses
    board = evaluate_board(game)
    if post_wins:
        board = min(100, board + post_wins * 2)
    if any(x.get("round") == "National Championship" and x.get("result") == "W" for x in season_post):
        board = min(100, board + 12)

    game["career"]["board_approval"] = board
    if board < 30:
        game["career"]["job_security"] = max(0, game["career"]["job_security"] - 25)
    elif board < 50:
        game["career"]["job_security"] = max(0, game["career"]["job_security"] - 10)
    else:
        game["career"]["job_security"] = min(100, game["career"]["job_security"] + 8)
    game["career"]["reputation"] = career_reputation(game)
    game["career"]["seasons"] += 1

    # A player with critically low security can be dismissed at the annual checkpoint.
    if game["career"]["job_security"] <= 0:
        game["career"]["job_security"] = 40
        game["career"]["board_approval"] = 55
        game["news"].insert(0, f"Your board fired you at {s['name']}. You remain in the AD job market.")
        open_ad_job(game, game["current_school"], "Your board dismissed you", random.Random(game["rng_seed"] + game["career"]["seasons"]))

    # Refresh the living market first, then generate the player's five choices.
    job_market_tick(game, force=True)
    offers = get_job_market(game, force_refresh=True)
    game["career"]["job_offers"] = len(offers)
    game["career"]["job_offer_pool"] = offers
    game["history"].append({
        "season": season,
        "school": s["name"],
        "board_approval": board,
        "reputation": game["career"]["reputation"]
    })
    return board


def get_job_market(game, force_refresh=False):
    ensure_career_schema(game)
    existing = game.get("career", {}).get("job_offer_pool", [])
    if existing and not force_refresh:
        return existing
    rng = random.Random(game["rng_seed"] + game["career"]["seasons"] * 101 + 9001)
    current = game["current_school"]
    world = game["world"]

    # First use real open vacancies, then add schools willing to recruit the player.
    offers = []
    for opening in world.get("job_openings", []):
        if opening.get("status") != "Open" or opening.get("school_id") == current:
            continue
        sid = opening["school_id"]
        school = world["schools"][sid]
        required = int(opening.get("required", max(25, school.get("prestige", 50)-18)))
        if game["career"]["reputation"] + rng.randint(-3, 6) >= required:
            offers.append({
                "school_id": sid,
                "required": required,
                "type": "Open position",
                "reason": opening.get("reason", "AD opening"),
                "opening_id": opening.get("id"),
                "expires": opening.get("opened_date"),
            })

    candidate_jobs = available_jobs(world, current, game["career"]["reputation"], rng, limit=30)
    seen = {x["school_id"] for x in offers}
    for x in candidate_jobs:
        if x["school_id"] in seen:
            continue
        offers.append({**x, "type": "Recruiting offer", "reason": "The school is pursuing an experienced AD."})
        seen.add(x["school_id"])

    # Rank offers around the player's natural next step, but preserve some variety.
    offers.sort(key=lambda x: (
        world["schools"][x["school_id"]].get("prestige", 50),
        1 if x.get("type") == "Open position" else 0,
        rng.random()
    ), reverse=True)

    if len(offers) < 5:
        fallback = []
        for sid, school in world["schools"].items():
            if sid == current or sid in seen:
                continue
            gap = abs(school.get("prestige", 50) - game["career"]["reputation"])
            fallback.append((gap, rng.random(), sid))
        fallback.sort()
        for _, _, sid in fallback:
            school = world["schools"][sid]
            offers.append({
                "school_id": sid,
                "required": max(25, school.get("prestige", 50)-18),
                "type": "Exploratory offer",
                "reason": "The school is monitoring your career.",
            })
            if len(offers) >= 5:
                break
    return offers[:5]


def take_job(game, school_id):
    ensure_career_schema(game)
    old = game["current_school"]
    if school_id == old or school_id not in game["world"]["schools"]:
        return False
    new = game["world"]["schools"][school_id]
    old_name = game["world"]["schools"][old]["name"]
    # The player's move leaves the old school with a generated interim AD.
    old_school = game["world"]["schools"][old]
    old_aid = old_school.get("ad_id")
    if old_aid and old_aid in game["world"].get("ad_people", {}):
        game["world"]["ad_people"][old_aid]["status"] = "Departed"
        game["world"]["ad_people"][old_aid]["left_date"] = game["date"]
    _new_ai_ad(game["world"], old, reputation=max(25, game["career"]["reputation"] - 4), rng=random.Random(game["rng_seed"] + game["career"].get("job_moves", 0) * 71 + 19))

    aid = new.get("ad_id")
    if aid is None:
        aid = _new_ai_ad(game["world"], school_id, reputation=game["career"]["reputation"], rng=random.Random(game["rng_seed"] + 12345))
    game["world"]["ad_people"][aid] = {
        "name": game["player"]["name"], "reputation": game["career"]["reputation"],
        "years": 0, "school_id": school_id, "status": "Player"
    }
    new["ad_id"] = aid
    _close_opening(game, school_id, "Accepted by player")
    game["current_school"] = school_id
    game["career"]["job_security"] = 72
    game["career"]["job_offer_pool"] = []
    game["career"]["job_offers"] = 0
    game["career"]["job_moves"] = game["career"].get("job_moves", 0) + 1
    game["career"]["last_move"] = f"{old_name} -> {new['name']}"
    game["news"].insert(0, f"You accepted the AD job at {new['name']}.")
    return True
