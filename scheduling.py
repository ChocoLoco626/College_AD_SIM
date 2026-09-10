from datetime import date, timedelta
import random
from realignment import CONFERENCE_CATALOG

SPORT_RULES = {
    "football": {"games": 12, "conf_games": 8},
    "men_basketball": {"games": 30, "conf_games": 18},
    "women_basketball": {"games": 30, "conf_games": 18},
}

def sport_window(sport, season):
    start_year=int(season.split("-")[0])
    if sport == "football":
        return {**SPORT_RULES[sport], "start": date(start_year,8,27), "end": date(start_year,11,28)}
    return {**SPORT_RULES[sport], "start": date(start_year,11,2), "end": date(start_year+1,2,28)}


def season_key(d):
    if isinstance(d, str):
        d = date.fromisoformat(d)
    start = d.year if d.month >= 8 else d.year - 1
    return f"{start}-{start+1}"


def conference_for_sport(school, sport):
    if sport == "football":
        return school.get("football_conference") or school.get("conference") or "Independent"
    return school.get("conference") or "Independent"

# Known 2026 FCS programs present in the simulator seed. This also repairs older saves
# where these schools were left as generic D-I and therefore received no football schedule.
FCS_FOOTBALL_TEAMS = {
    "Abilene Christian", "Alabama A&M", "Alabama State", "Albany", "Alcorn State",
    "Austin Peay", "Bethune Cookman", "Brown", "Bryant", "Bucknell", "Butler",
    "Cal Poly", "Campbell", "Central Arkansas", "Central Connecticut", "Chattanooga",
    "Colgate", "Columbia", "Cornell", "Dartmouth", "Davidson", "Dayton", "Delaware",
    "Delaware State", "Drake", "Duquesne", "Eastern Illinois", "Eastern Kentucky",
    "Eastern Washington", "Elon", "Florida A&M", "Fordham", "Furman", "Georgetown",
    "Grambling", "Harvard", "Holy Cross", "Houston Christian", "Howard", "Idaho",
    "Idaho State", "Illinois State", "Incarnate Word", "Indiana State", "Jackson State",
    "Lafayette", "Lamar", "Lehigh", "LIU", "Maine", "Mercer", "McNeese", "Mercyhurst",
    "Merrimack", "Mississippi Valley State", "Missouri State", "Monmouth", "Montana",
    "Montana State", "Morehead State", "Morgan State", "Murray State", "New Hampshire",
    "Nicholls", "Norfolk State", "North Alabama", "North Carolina Central", "North Dakota",
    "North Dakota State", "Northern Iowa", "Northwestern State", "Penn", "Portland State",
    "Prairie View", "Prairie View A&M", "Presbyterian", "Princeton", "Rhode Island",
    "Richmond", "Robert Morris", "Sacramento State", "Samford", "South Carolina State",
    "South Dakota", "South Dakota State", "Southeastern Louisiana", "Southern",
    "Southern Illinois", "Stephen F Austin", "Stetson", "Stony Brook", "Tennessee State",
    "Tennessee Tech", "Texas A&M Commerce", "Texas Southern", "The Citadel", "Towson",
    "UC Davis", "UT Martin", "Villanova", "Wagner", "Weber State", "Western Carolina",
    "Western Illinois", "William & Mary", "Wofford", "Yale", "Youngstown State"
}

def repair_football_classification(world):
    for s in world.get("schools", {}).values():
        if s.get("subdivision") not in ("FBS", "FCS") and s.get("name") in FCS_FOOTBALL_TEAMS:
            s["subdivision"] = "FCS"


def ensure_schedule_schema(world):
    repair_football_classification(world)
    world.setdefault("conferences", {})
    world.setdefault("schedules", {})
    world.setdefault("game_contracts", [])
    world.setdefault("schedule_generated", [])
    # Rebuild membership from the school data so conference pages stay current.
    confs = {}
    for sid, s in world.get("schools", {}).items():
        conf = s.get("conference") or "Independent"
        confs.setdefault(conf, []).append(sid)
    world["conferences"] = {
        k: {"name": k, "members": sorted(v), "member_count": len(v)}
        for k, v in sorted(confs.items())
    }
    return world


def _dates(start, end):
    out=[]
    d=start
    while d<=end:
        # Football: Saturdays (plus Week Zero); basketball: mostly Mon-Sun.
        out.append(d)
        d += timedelta(days=1)
    return out


def _game_dates(window, count, sport, rng):
    if sport == "football":
        candidates=[d for d in _dates(window["start"], window["end"]) if d.weekday() == 5]
    else:
        candidates=[d for d in _dates(window["start"], window["end"]) if d.weekday() in (0,1,2,3,4,5)]
    rng.shuffle(candidates)
    return sorted(candidates[:count])


def _add(schedule, sid, date_str, opponent, home, sport, conference, contract_id=None):
    schedule.setdefault(sid, []).append({
        "date": date_str, "sport": sport, "opponent": opponent,
        "home": home, "conference_game": conference, "contract_id": contract_id,
        "status": "scheduled"
    })


def _pair_round_robin(members, games_needed, rng):
    """Greedy pairing that avoids repeat opponents where possible."""
    members=list(members); rng.shuffle(members)
    pairs=[]; used=set()
    # Several passes through shuffled rotations.
    for shift in range(1, len(members)):
        for i,a in enumerate(members):
            b=members[(i+shift)%len(members)]
            if a == b: continue
            key=tuple(sorted((a,b)))
            if key in used: continue
            pairs.append((a,b)); used.add(key)
            if len(pairs) >= games_needed: return pairs
    return pairs


def _schedule_sport(world, sport, season, rng):
    w = sport_window(sport, season)
    members = [sid for sid, s in world["schools"].items()
               if sport != "football" or s.get("subdivision") in ("FBS", "FCS")]
    schedule = {sid: [] for sid in members}
    counts = {sid: 0 for sid in members}
    conf_counts = {sid: 0 for sid in members}
    pairset = set()
    pairs = []
    target = w["games"]
    conf_target = min(w["conf_games"], target)

    def add_pair(a, b, is_conf):
        if a == b or counts[a] >= target or counts[b] >= target:
            return False
        key = tuple(sorted((a, b)))
        if key in pairset:
            return False
        if is_conf and (conf_counts[a] >= conf_target or conf_counts[b] >= conf_target):
            return False
        pairset.add(key)
        pairs.append((a, b, is_conf))
        counts[a] += 1; counts[b] += 1
        if is_conf:
            conf_counts[a] += 1; conf_counts[b] += 1
        return True

    # Greedy exact-total scheduler. It prioritizes conference games until the
    # conference target is reached, then fills the remaining slots with OOC games.
    guard = max(10000, len(members) * target * 8)
    for _ in range(guard):
        incomplete = [sid for sid in members if counts[sid] < target]
        if not incomplete:
            break
        a = min(incomplete, key=lambda sid: (counts[sid], rng.random()))
        conf_a = conference_for_sport(world["schools"][a], sport)
        candidates = [b for b in incomplete if b != a and tuple(sorted((a, b))) not in pairset]
        if not candidates:
            break
        conf_candidates = [b for b in candidates
                           if conference_for_sport(world["schools"][b], sport) == conf_a
                           and conf_counts[a] < conf_target
                           and conf_counts[b] < conf_target]
        pool = conf_candidates or candidates
        # Favor opponents that also need games, and avoid creating an extreme imbalance.
        pool.sort(key=lambda b: (counts[b], conf_counts[b]), reverse=False)
        top = pool[:min(12, len(pool))]
        b = rng.choice(top)
        is_conf = conference_for_sport(world["schools"][b], sport) == conf_a and conf_counts[a] < conf_target and conf_counts[b] < conf_target
        add_pair(a, b, is_conf)

    # A second pass handles rare odd/even deadlocks. It does not exceed the target.
    for a in members:
        while counts[a] < target:
            candidates = [b for b in members if b != a and counts[b] < target and tuple(sorted((a, b))) not in pairset]
            if not candidates:
                break
            b = min(candidates, key=lambda x: counts[x])
            is_conf = conference_for_sport(world["schools"][a], sport) == conference_for_sport(world["schools"][b], sport) and conf_counts[a] < conf_target and conf_counts[b] < conf_target
            if not add_pair(a, b, is_conf):
                break

    dates = [d for d in _dates(w["start"], w["end"]) if sport != "football" or d.weekday() == 5]
    rng.shuffle(dates)
    dates = sorted(dates)
    busy = {sid: set() for sid in members}
    for idx, (a, b, is_conf) in enumerate(pairs):
        chosen = next((d for d in dates if d not in busy[a] and d not in busy[b]), None)
        if chosen is None:
            # Basketball can use additional weekdays if the calendar gets crowded;
            # football remains on Saturdays.
            base = w["start"]
            if sport == "football":
                chosen = base + timedelta(days=(5 - base.weekday()) % 7 + (idx % 13) * 7)
            else:
                chosen = base + timedelta(days=(idx % 100))
                while chosen.weekday() == 6:
                    chosen += timedelta(days=1)
        busy[a].add(chosen); busy[b].add(chosen)
        home = rng.choice([True, False])
        ds = chosen.isoformat()
        _add(schedule, a, ds, b, home, sport, is_conf)
        _add(schedule, b, ds, a, not home, sport, is_conf)

    for sid in schedule:
        schedule[sid].sort(key=lambda x: x["date"])
    world["schedules"].setdefault(season, {})[sport] = schedule
    return schedule


def repair_missing_schedule_coverage(world, season, seed):
    """Repair older/generated worlds where an eligible school received no games."""
    ensure_schedule_schema(world)
    data = world.get("schedules", {}).get(season, {})
    rng = random.Random(seed + 7711 + sum(ord(c) for c in season))
    for sport, rules in SPORT_RULES.items():
        by_school = data.setdefault(sport, {})
        eligible = [sid for sid in world.get("schools", {})
                    if sport != "football" or world["schools"][sid].get("subdivision") in ("FBS", "FCS")]
        for sid in eligible:
            by_school.setdefault(sid, [])
        zero = [sid for sid in eligible if not by_school.get(sid)]
        # First pair programs that were completely absent from an older schedule.
        remaining = list(zero)
        while len(remaining) >= 2:
            sid = remaining.pop(0)
            oid = remaining.pop(0)
            w = sport_window(sport, season)
            used = {g.get("date") for g in by_school.get(sid, [])} | {g.get("date") for g in by_school.get(oid, [])}
            dates = [d for d in _dates(w["start"], w["end"]) if (sport != "football" or d.weekday() == 5) and d.isoformat() not in used]
            if not dates:
                break
            d = rng.choice(dates); home = rng.choice([True, False])
            _add(by_school, sid, d.isoformat(), oid, home, sport, False)
            _add(by_school, oid, d.isoformat(), sid, not home, sport, False)
        for sid in remaining:
            target_games = rules["games"]
            attempts = 0
            while len(by_school.get(sid, [])) < target_games and attempts < target_games * 5:
                attempts += 1
                candidates = [oid for oid in eligible if oid != sid and not any(g.get("opponent") == oid for g in by_school.get(sid, []))]
                if not candidates:
                    break
                rng.shuffle(candidates)
                oid = min(candidates, key=lambda x: len(by_school.get(x, [])))
                # Keep the repaired school's schedule at the sport target by making room
                # on a full opponent's slate when necessary.
                if len(by_school.get(oid, [])) >= target_games:
                    old = next((g for g in by_school[oid] if not g.get("conference_game")), by_school[oid][0] if by_school[oid] else None)
                    if old:
                        old_opp, old_date = old.get("opponent"), old.get("date")
                        by_school[oid] = [g for g in by_school[oid] if not (g.get("date") == old_date and g.get("opponent") == old_opp)]
                        if old_opp in by_school:
                            by_school[old_opp] = [g for g in by_school[old_opp] if not (g.get("date") == old_date and g.get("opponent") == oid)]
                w = sport_window(sport, season)
                used = {g.get("date") for g in by_school.get(sid, [])} | {g.get("date") for g in by_school.get(oid, [])}
                dates = [d for d in _dates(w["start"], w["end"]) if (sport != "football" or d.weekday() == 5) and d.isoformat() not in used]
                if not dates:
                    continue
                d = rng.choice(dates); home = rng.choice([True, False])
                _add(by_school, sid, d.isoformat(), oid, home, sport, False)
                _add(by_school, oid, d.isoformat(), sid, not home, sport, False)
        for sid in by_school:
            by_school[sid].sort(key=lambda x: x["date"])
    return data


def generate_season_schedules(world, season, seed):
    ensure_schedule_schema(world)
    if season in world.get("schedule_generated", []):
        repair_missing_schedule_coverage(world, season, seed)
        return world["schedules"].get(season,{})
    rng=random.Random(seed + sum(ord(c) for c in season)*97)
    for sport in SPORT_RULES:
        _schedule_sport(world,sport,season,rng)
    world["schedule_generated"].append(season)
    repair_missing_schedule_coverage(world, season, seed)
    return world["schedules"][season]


def current_season_schedule(world, sid, season, sport=None):
    ensure_schedule_schema(world)
    data=world.get("schedules",{}).get(season,{})
    if sport:
        return list(data.get(sport,{}).get(sid,[]))
    out=[]
    for sp,by_school in data.items():
        out.extend(by_school.get(sid,[]))
    return sorted(out,key=lambda x:x["date"])


def replace_nonconference_game(world, current_sid, game_date, sport):
    season=season_key(game_date)
    schedule=world.get("schedules",{}).get(season,{}).get(sport,{})
    game=next((x for x in schedule.get(current_sid,[]) if x["date"]==game_date and not x.get("conference_game")),None)
    if not game:
        return None
    opponent=game["opponent"]
    for sid in (current_sid,opponent):
        schedule.setdefault(sid,[])
        schedule[sid]=[x for x in schedule[sid] if not (x["date"]==game_date and x["opponent"] in (current_sid,opponent) and x["sport"]==sport)]
    return opponent

def negotiate_game(world, current_sid, opponent_sid, sport, game_date, home, amount, seed):
    """Create a one-game contract. Positive amount is a guarantee paid to the opponent when home=True;
    when home=False it is the amount the opponent pays the current school."""
    ensure_schedule_schema(world)
    if current_sid == opponent_sid: return False,"You cannot schedule yourself."
    if sport not in SPORT_RULES: return False,"Unsupported sport."
    amount=max(0,int(amount))
    season=season_key(game_date)
    generate_season_schedules(world,season,seed)
    # Replace the first future nonconference slot if possible.
    existing=current_season_schedule(world,current_sid,season,sport)
    if any(g["date"]==game_date and g["opponent"]==opponent_sid for g in existing):
        return False,"That opponent is already scheduled on that date."
    rng=random.Random(seed+hash((current_sid,opponent_sid,sport,game_date,amount))%1_000_000)
    a=world["schools"][current_sid]; b=world["schools"][opponent_sid]
    prestige_gap=b.get("prestige",50)-a.get("prestige",50)
    # Strong schools generally demand more to travel to weaker teams; weak schools may pay to get home games.
    expected=max(25_000, int(75_000 + max(0,prestige_gap)*45_000)) if home else max(15_000,int(50_000+max(0,-prestige_gap)*35_000))
    tolerance=max(0.45, min(2.0, 0.9 + rng.random()*0.7))
    if amount < expected*tolerance:
        return False,f"Negotiation failed. {b['name']} countered around ${expected:,.0f}."
    # If the date already has a non-conference opponent, replace that game so the schedule length stays realistic.
    replace_nonconference_game(world,current_sid,game_date,sport)
    cid=f"contract_{len(world['game_contracts'])+1}_{rng.randint(1000,999999)}"
    rec={"id":cid,"season":season,"sport":sport,"date":game_date,"home":current_sid if home else opponent_sid,
         "away":opponent_sid if home else current_sid,"amount":amount,"payer":current_sid if home else opponent_sid,
         "receiver":opponent_sid if home else current_sid,"status":"accepted"}
    world["game_contracts"].append(rec)
    # Remove one existing nonconference game involving the current school on the selected date if needed.
    for sid in (current_sid,opponent_sid):
        world["schedules"].setdefault(season,{}).setdefault(sport,{}).setdefault(sid,[])
    _add(world["schedules"][season][sport],current_sid,game_date,opponent_sid,home,sport,False,cid)
    _add(world["schedules"][season][sport],opponent_sid,game_date,current_sid,not home,sport,False,cid)
    for sid in (current_sid,opponent_sid):
        world["schedules"][season][sport][sid].sort(key=lambda x:x["date"])
    return True,f"Game contract accepted: {a['name']} vs. {b['name']} for ${amount:,.0f}."


def scheduled_games_on(world, season, dt, sport=None):
    data=world.get("schedules",{}).get(season,{})
    seen=set(); out=[]
    for sp,by_school in data.items():
        if sport and sp!=sport: continue
        for sid,games in by_school.items():
            for g in games:
                if g["date"]!=dt: continue
                key=tuple(sorted((sid,g["opponent"])))+(sp,dt)
                if key in seen: continue
                seen.add(key)
                out.append((sid,g["opponent"],sp,g))
    return out
