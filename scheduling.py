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

def ensure_schedule_schema(world):
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
    w=sport_window(sport, season)
    members=[sid for sid,s in world["schools"].items() if sport != "football" or s.get("subdivision") in ("FBS","FCS")]
    schedule={sid:[] for sid in members}
    pairs=[]; pairset=set(); counts={sid:0 for sid in members}

    def add_pair(a,b,is_conf):
        if a==b: return False
        key=tuple(sorted((a,b)))
        if key in pairset: return False
        pairs.append((a,b,is_conf)); pairset.add(key); counts[a]+=1; counts[b]+=1
        return True

    # Conference schedules: use sport-specific membership (football can differ from the primary conference).
    sport_confs = {}
    for sid in members:
        conf_name = conference_for_sport(world["schools"][sid], sport)
        sport_confs.setdefault(conf_name, []).append(sid)
    for conf_name, cm in sport_confs.items():
        if len(cm)<2: continue
        rng.shuffle(cm)
        target=min(w["conf_games"], len(cm)-1)
        # Each pass gives each school approximately two games; stop once everyone reaches target.
        for shift in range(1, len(cm)):
            if all(sum(1 for a,b,is_conf in pairs if is_conf and (a==sid or b==sid)) >= target for sid in cm):
                break
            rotated=cm[shift:]+cm[:shift]
            for i in range(0,len(cm)-1,2):
                a=cm[i]; b=rotated[i]
                add_pair(a,b,True)
                if counts[a] >= target and counts[b] >= target:
                    continue

    # Non-conference games fill each team's target total. Prefer different conferences.
    max_attempts=max(1000,len(members)*50)
    attempts=0
    while attempts<max_attempts and any(counts[sid] < w["games"] for sid in members):
        attempts+=1
        a=min((sid for sid in members if counts[sid] < w["games"]), key=lambda x:counts[x], default=None)
        if a is None: break
        preferred=[b for b in members if b!=a and counts[b]<w["games"] and conference_for_sport(world["schools"][b], sport)!=conference_for_sport(world["schools"][a], sport) and tuple(sorted((a,b))) not in pairset]
        candidates=preferred or [b for b in members if b!=a and counts[b]<w["games"] and tuple(sorted((a,b))) not in pairset]
        if not candidates: break
        b=min(candidates,key=lambda x:counts[x]) if len(candidates)>20 else rng.choice(candidates)
        add_pair(a,b,False)

    # Calendar dates are assigned without double-booking a school.
    dates=_game_dates(w, max(1,len(pairs)), sport, rng)
    busy={sid:set() for sid in members}
    for idx,(a,b,is_conf) in enumerate(pairs):
        chosen=None
        for d in dates:
            if d not in busy[a] and d not in busy[b]:
                chosen=d; break
        if chosen is None:
            # Continue the calendar after the normal window if an unusually large schedule requires it.
            first_sat=w["start"] + timedelta(days=(5 - w["start"].weekday()) % 7)
            chosen=first_sat + timedelta(days=(idx % 14) * 7)
        busy[a].add(chosen); busy[b].add(chosen)
        home=rng.choice([True,False]); ds=chosen.isoformat()
        _add(schedule,a,ds,b,home,sport,is_conf)
        _add(schedule,b,ds,a,not home,sport,is_conf)

    for sid in schedule:
        schedule[sid].sort(key=lambda x:x["date"])
    world["schedules"].setdefault(season,{})[sport]=schedule
    return schedule


def generate_season_schedules(world, season, seed):
    ensure_schedule_schema(world)
    if season in world.get("schedule_generated", []):
        return world["schedules"].get(season,{})
    rng=random.Random(seed + sum(ord(c) for c in season)*97)
    for sport in SPORT_RULES:
        _schedule_sport(world,sport,season,rng)
    world["schedule_generated"].append(season)
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
