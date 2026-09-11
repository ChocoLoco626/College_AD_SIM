from datetime import date, timedelta

import random

NIL_SPORTS = ["football", "men_basketball", "women_basketball", "baseball", "softball", "volleyball"]

FACILITY_TYPES = {
    "football": ["Football facilities", "Stadium", "Strength & conditioning", "Football recruiting"],
    "men_basketball": ["Basketball arena", "Men's basketball practice facility", "Basketball recruiting"],
    "women_basketball": ["Women's basketball facilities", "Women's basketball recruiting"],
    "baseball": ["Baseball stadium", "Baseball facilities"],
    "softball": ["Softball facilities"],
    "general": ["Academic support", "Sports medicine", "Athletic training", "Travel", "General athletics"]
}

def ensure_management_schema(game):
    f = game.setdefault("finances", {})
    s = game["world"]["schools"][game["current_school"]]
    f.setdefault("nil_budget", int(s.get("budget", 20_000_000) * .015))
    f.setdefault("nil_allocations", {sport: 0 for sport in NIL_SPORTS})
    s.setdefault("nil_allocations", {sport: 0 for sport in NIL_SPORTS})
    f.setdefault("booster_funds", int(s.get("budget", 20_000_000) * .08))
    f.setdefault("booster_allocations", {})
    f.setdefault("facility_spending", {})
    f.setdefault("coach_buyouts", 0)
    f.setdefault("coach_narratives", [])
    f.setdefault("financial_history", [])
    # Booster personalities are persistent and their confidence determines future funding.
    s.setdefault("boosters", [])
    if not s["boosters"]:
        rng = random.Random(game.get("rng_seed", 1) + hash(s.get("name", "school")) % 100000)
        archetypes = [("Lead Booster", "wins", 92), ("Facilities Donor", "facilities", 78), ("NIL Collective", "nil", 84), ("Community Donor", "stability", 68)]
        for i, (name, focus, wealth) in enumerate(archetypes):
            s["boosters"].append({"id": f"booster_{s.get('name','school')}_{i}", "name": name, "focus": focus, "wealth": wealth + rng.randint(-12, 12), "confidence": 68 + rng.randint(-8, 10)})
    s.setdefault("booster_confidence", 68)
    s.setdefault("booster_history", [])
    s.setdefault("booster_last_tick", None)
    # Upgrade legacy coaches with a real annual salary.
    for _cid in s.get("coaches", {}).values():
        if _cid and _cid in game["world"].get("coaches", {}):
            _c=game["world"]["coaches"][_cid]
            _c.setdefault("salary", int(250_000 + _c.get("overall",50) * 65_000))
            _c.setdefault("program_fit", 60)
    s.setdefault("facility_levels", {sport: max(1, min(10, round(s.get("facilities", 50)/10))) for sport in NIL_SPORTS})
    s.setdefault("facility_investments", [])
    s.setdefault("coach_history", [])
    return game

def available_nil(game):
    ensure_management_schema(game)
    f = game["finances"]
    return max(0, f["nil_budget"] - sum(f["nil_allocations"].values()))

def set_nil_allocation(game, sport, amount):
    ensure_management_schema(game)
    if sport not in NIL_SPORTS:
        return False, "Invalid sport."
    amount = max(0, int(amount))
    f = game["finances"]
    s = game["world"]["schools"][game["current_school"]]
    other = sum(v for k,v in f["nil_allocations"].items() if k != sport)
    if other + amount > f["nil_budget"]:
        return False, "That allocation exceeds the NIL budget."
    f["nil_allocations"][sport] = amount
    s["nil_allocations"][sport] = amount
    return True, f"NIL allocation for {sport.replace('_',' ').title()} set to ${amount:,.0f}."

def available_boosters(game):
    ensure_management_schema(game)
    f=game["finances"]
    return max(0, f["booster_funds"] - sum(f["booster_allocations"].values()))

def invest_facility(game, category, amount):
    ensure_management_schema(game)
    amount=max(0,int(amount))
    if amount <= 0:
        return False, "Investment must be positive."
    if amount > available_boosters(game):
        return False, "Not enough unallocated booster funds."
    s=game["world"]["schools"][game["current_school"]]
    f=game["finances"]
    f["booster_allocations"][category]=f["booster_allocations"].get(category,0)+amount
    f["facility_spending"][category]=f["facility_spending"].get(category,0)+amount
    # $1M of targeted investment is meaningful, with diminishing returns.
    gain = max(1, min(8, int((amount / 1_000_000) ** .65)))
    s["facilities"] = min(99, s.get("facilities",50) + gain)
    s["facility_investments"].append({
        "date": game["date"], "category": category, "amount": amount, "gain": gain
    })
    game["career"]["fundraising"] = game["career"].get("fundraising",0) + amount
    return True, f"${amount:,.0f} invested in {category}; facilities improved by {gain}."

def coach_program_fit(game, coach, sport, school=None):
    """How attractive the current program is to this coach (0-100)."""
    ensure_management_schema(game)
    world = game["world"]
    school = school or world["schools"][game["current_school"]]
    current_sid = coach.get("school_id")
    current_prestige = world.get("schools", {}).get(current_sid, {}).get("prestige", 45) if current_sid else 45
    fit = 52 + (school.get("prestige", 50) - current_prestige) * 0.48
    fit += (school.get("facilities", 50) - 50) * 0.28
    allocation = school.get("nil_allocations", {}).get(sport, 0)
    peer = _coach_peer_nil_need(game, sport) if world.get("schools") else 0
    if peer:
        fit += max(-12, min(12, (allocation / peer - 0.7) * 20))
    personality = coach.get("personality")
    if personality == "ambitious": fit += (school.get("prestige", 50) - 50) * 0.10
    elif personality == "players-first": fit += (school.get("facilities", 50) - 50) * 0.10
    elif personality == "steady": fit += 4 if school.get("academic", 70) >= 75 else -2
    return int(max(10, min(98, round(fit))))

def negotiate_coach_salary(game, sport, new_salary):
    ensure_management_schema(game)
    school = game["world"]["schools"][game["current_school"]]
    cid = school.get("coaches", {}).get(sport)
    coach = game["world"]["coaches"].get(cid) if cid else None
    if not coach: return False, "No head coach is currently assigned."
    new_salary = int(max(100_000, new_salary))
    minimum = int(200_000 + coach.get("overall", 50) * 35_000)
    if new_salary < minimum:
        coach["satisfaction"] = max(0, int(coach.get("satisfaction", 72)) - 6)
        return False, f"The coach will not accept less than about ${minimum:,.0f}."
    old = int(coach.get("salary", minimum))
    coach["salary"] = new_salary
    delta = new_salary - old
    coach["satisfaction"] = min(100, max(0, int(coach.get("satisfaction",72)) + (5 if delta > 0 else -4)))
    game["news"].insert(0, f"You renegotiated {coach['name']}'s salary to ${new_salary:,.0f} per year.")
    return True, f"{coach['name']}'s salary is now ${new_salary:,.0f}."

def booster_tick(game):
    """Update persistent booster confidence and unlock more funding when the program earns trust."""
    ensure_management_schema(game)
    world=game["world"]; school=world["schools"][game["current_school"]]
    marker=game.get("date")
    if school.get("booster_last_tick") == marker:
        return int(game["finances"].get("booster_funds",0))
    school["booster_last_tick"]=marker
    season = school.get("season_records", {})
    headline=[]
    for sport in ("football","men_basketball","women_basketball"):
        r=season.get(sport,{"w":0,"l":0}); gp=r["w"]+r["l"]
        headline.append(r["w"]/gp if gp else .5)
    win_pct=sum(headline)/len(headline)
    coach_sats=[]
    for sport,cid in school.get("coaches",{}).items():
        if cid and cid in world.get("coaches",{}): coach_sats.append(world["coaches"][cid].get("satisfaction",70))
    avg_sat=sum(coach_sats)/len(coach_sats) if coach_sats else 65
    for b in school.get("boosters",[]):
        change=(win_pct-.5)*22 + (school.get("facilities",50)-55)*.04 + (avg_sat-65)*.025
        if b.get("focus")=="facilities": change += (school.get("facilities",50)-55)*.08
        if b.get("focus")=="nil":
            nil_ratio=sum(school.get("nil_allocations",{}).values())/max(1, world["schools"][game["current_school"]].get("budget",1)*.015)
            change += (nil_ratio-.6)*3
        if b.get("focus")=="stability": change += (game["career"].get("board_approval",65)-65)*.03
        b["confidence"]=int(max(15,min(100,round(b.get("confidence",68)+change))))
    avg=int(round(sum(b["confidence"] for b in school.get("boosters",[]))/max(1,len(school.get("boosters",[])))))
    school["booster_confidence"]=avg
    base=int(school.get("budget",20_000_000)*.08)
    funding=int(base*(0.45+avg/100*0.85))
    game["finances"]["booster_funds"]=max(0,funding)
    school.setdefault("booster_history",[]).append({"date":game["date"],"confidence":avg,"funding":funding})
    school["booster_history"]=school["booster_history"][-12:]
    return funding

def coach_candidates(game, sport, limit=8):
    ensure_management_schema(game)
    world=game["world"]; current=world["schools"][game["current_school"]]
    rng=random.Random(game["rng_seed"] + len(world["coaches"])*17 + len(world["results"]))
    candidates=[]
    for cid,c in world["coaches"].items():
        if c.get("sport") != sport: continue
        sid=c.get("school_id")
        if sid == game["current_school"]: continue
        other=world["schools"].get(sid)
        if not other: continue
        candidates.append({
            "id":cid, "name":c["name"], "overall":c["overall"],
            "recruiting":c["recruiting"], "development":c["development"],
            "contract_years":c.get("contract_years",1),
            "current_school":other["name"], "current_prestige":other["prestige"],
            "salary": int(c.get("salary", 250_000 + c["overall"] * 65_000)),
            "fit": coach_program_fit(game, c, sport, current)
        })
    # Add generated assistants / free agents.
    for i in range(4):
        base=max(40,min(92,current["prestige"]+rng.randint(-12,18)))
        from names import coach_profile
        c=coach_profile(rng,base)
        cid=f"candidate_{game['current_school']}_{sport}_{len(candidates)}_{rng.randint(1,999999)}"
        c["school_id"]=None; c["sport"]=sport; c["years"]=rng.randint(1,12)
        world["coaches"][cid]=c
        candidates.append({
            "id":cid,"name":c["name"],"overall":c["overall"],"recruiting":c["recruiting"],
            "development":c["development"],"contract_years":c["contract_years"],
            "current_school":"Free agent / assistant","current_prestige":base,
            "salary":int(c.get("salary", 250_000 + c["overall"] * 65_000)),
            "fit": coach_program_fit(game, c, sport, current)
        })
    candidates.sort(key=lambda x:(x["overall"],x["recruiting"]), reverse=True)
    return candidates[:limit]

def fire_head_coach(game, sport):
    ensure_management_schema(game)
    s=game["world"]["schools"][game["current_school"]]
    cid=s["coaches"].get(sport)
    if not cid: return False, "No head coach is currently assigned."
    coach=game["world"]["coaches"][cid]
    buyout=int(coach.get("contract_years",1) * max(150_000, coach["overall"]*18_000))
    game["finances"]["cash"]-=buyout
    game["finances"]["coach_buyouts"]+=buyout
    game["career"]["board_approval"]=max(0,game["career"].get("board_approval",65)-3)
    s["coach_history"].append({"date":game["date"],"action":"Fired","sport":sport,"coach":coach["name"],"buyout":buyout})
    s["coaches"][sport]=None
    game["news"].insert(0,f"You fired {coach['name']} as {sport.replace('_',' ').title()} head coach. Buyout: ${buyout:,.0f}.")
    return True, f"{coach['name']} was fired. Buyout: ${buyout:,.0f}."

def hire_head_coach(game, sport, candidate_id):
    ensure_management_schema(game)
    s=game["world"]["schools"][game["current_school"]]
    if s["coaches"].get(sport):
        return False, "Fire or replace the current coach first."
    c=game["world"]["coaches"].get(candidate_id)
    if not c or c.get("sport") != sport:
        return False, "Candidate unavailable."
    fit = coach_program_fit(game, c, sport, s)
    if fit < 38:
        return False, f"{c['name']} is not interested enough in this program (fit {fit}/100). Improve prestige, facilities, or NIL."
    salary=int(c.get("salary", 250_000 + c["overall"] * 65_000))
    if game["finances"]["cash"] < salary:
        return False, f"Not enough cash for the estimated first-year salary of ${salary:,.0f}."
    old_school_id = c.get("school_id")
    if old_school_id and old_school_id in game["world"]["schools"]:
        old_school = game["world"]["schools"][old_school_id]
        if old_school["coaches"].get(sport) == candidate_id:
            old_school["coaches"][sport] = None
            old_school.setdefault("coach_history", []).append({
                "date": game["date"], "action": "Left for another school",
                "sport": sport, "coach": c["name"]
            })
    c["school_id"]=game["current_school"]
    c["contract_years"]=max(2,c.get("contract_years",1))
    c["salary"]=salary
    c["satisfaction"]=max(55,min(96,40+fit//2))
    c["program_fit"]=fit
    s["coaches"][sport]=candidate_id
    s["coach_history"].append({"date":game["date"],"action":"Hired","sport":sport,"coach":c["name"],"salary":salary})
    game["finances"]["cash"]-=salary
    game["career"]["board_approval"]=min(100,game["career"].get("board_approval",65)+1)
    game["news"].insert(0,f"You hired {c['name']} to lead {sport.replace('_',' ').title()}.")
    return True, f"Hired {c['name']} for an estimated first-year salary of ${salary:,.0f}."


def _coach_peer_nil_need(game, sport):
    """Estimate a sport's competitive NIL level from similar-prestige schools."""
    world = game["world"]
    cur = world["schools"][game["current_school"]]
    peers = []
    for sid, school in world["schools"].items():
        if school.get("conference") != cur.get("conference"):
            continue
        if sid == game["current_school"]:
            continue
        peers.append(school.get("nil_allocations", {}).get(sport, 0))
    if not peers:
        peers = [school.get("nil_allocations", {}).get(sport, 0) for school in world["schools"].values()]
    peers = [int(x) for x in peers if x is not None]
    return int(sorted(peers)[len(peers)//2]) if peers else 0


def _coach_should_demand(game, coach, school, sport, rng):
    if coach.get("demand"):
        return False
    # No constant demands: coaches become more restless when the program underfunds NIL,
    # loses games, or the coach has a hot market value.
    allocation = int(school.get("nil_allocations", {}).get(sport, 0))
    peer = _coach_peer_nil_need(game, sport)
    rec = school.get("season_records", school.get("records", {})).get(sport, {"w":0,"l":0})
    games = rec["w"] + rec["l"]
    pct = rec["w"] / games if games else .5
    underfunded = peer > 0 and allocation < peer * .72
    hot = coach.get("overall",50) >= max(70, school.get("prestige",50)+10)
    probability = 0.025
    if underfunded: probability += 0.16
    if pct < .42: probability += 0.07
    if hot: probability += 0.04
    fit=coach_program_fit(game,coach,sport,school)
    if fit < 55: probability += (55-fit)*0.012
    if coach.get("personality") == "ambitious": probability += 0.04
    return rng.random() < probability


def create_coach_demand(game, sport, coach_id, rng=None):
    ensure_management_schema(game)
    world=game["world"]; school=world["schools"][game["current_school"]]
    coach=world["coaches"].get(coach_id)
    if not coach or coach.get("school_id") != game["current_school"] or coach.get("sport") != sport:
        return False
    rng = rng or random.Random(game["rng_seed"] + len(game.get("news",[]))*17)
    peer = _coach_peer_nil_need(game, sport)
    current = int(school.get("nil_allocations",{}).get(sport,0))
    base = max(500_000, int(max(peer, current) * rng.uniform(.12,.24)))
    requested = max(500_000, int((current + base) / 500_000) * 500_000)
    requested = min(requested, max(1_000_000, int(game["finances"].get("nil_budget",0) * .60)))
    deadline = (date.fromisoformat(game["date"]) + timedelta(days=rng.randint(14,35))).isoformat()
    demand={
        "sport":sport,"coach_id":coach_id,"requested_nil":requested,"created":game["date"],
        "deadline":deadline,"status":"Pending","message":rng.choice([
            "I need more NIL support to keep our recruiting competitive.",
            "Our roster is asking what we're willing to invest. I need you to move on NIL.",
            "I'm getting calls because other programs are offering more resources. We need to respond.",
            "If we want to compete at this level, our NIL commitment has to increase."
        ])
    }
    coach["demand"]=demand
    coach["last_demand_date"]=game["date"]
    coach["satisfaction"]=max(20,int(coach.get("satisfaction",72))-8)
    game["finances"].setdefault("coach_narratives",[]).append({**demand,"coach":coach["name"],"date":game["date"]})
    game["news"].insert(0,f"{coach['name']} is demanding ${requested:,.0f} more NIL support for {sport.replace('_',' ').title()}.")
    game["news"]=game["news"][:30]
    return True


def resolve_coach_demand(game, sport, action):
    ensure_management_schema(game)
    world=game["world"]; school=world["schools"][game["current_school"]]
    cid=school.get("coaches",{}).get(sport); coach=world["coaches"].get(cid) if cid else None
    demand=coach.get("demand") if coach else None
    if not coach or not demand or demand.get("status") != "Pending":
        return False,"No pending coach demand."
    requested=int(demand.get("requested_nil",0)); f=game["finances"]
    current=int(f.get("nil_allocations",{}).get(sport,0))
    if action == "approve":
        target=current+requested
        other=sum(v for k,v in f["nil_allocations"].items() if k != sport)
        if other+target > int(f.get("nil_budget",0)):
            return False,"You cannot meet the request with the current NIL budget."
        f["nil_allocations"][sport]=target
        school["nil_allocations"][sport]=target
        coach["satisfaction"]=min(100,int(coach.get("satisfaction",72))+24)
        demand["status"]="Approved"; demand["resolved_date"]=game["date"]
        game["news"].insert(0,f"You approved {coach['name']}'s NIL request. They are satisfied with the commitment.")
        return True,f"NIL increased by ${requested:,.0f} for {sport.replace('_',' ').title()}."
    if action == "negotiate":
        compromise=max(250_000,requested//2)
        target=current+compromise
        other=sum(v for k,v in f["nil_allocations"].items() if k != sport)
        if other+target > int(f.get("nil_budget",0)):
            return False,"Even a compromise would exceed the current NIL budget."
        f["nil_allocations"][sport]=target; school["nil_allocations"][sport]=target
        coach["satisfaction"]=min(100,int(coach.get("satisfaction",72))+10)
        demand["status"]="Negotiated"; demand["resolved_date"]=game["date"]; demand["agreed_nil"]=compromise
        game["news"].insert(0,f"You negotiated a smaller NIL increase with {coach['name']}.")
        return True,f"You added ${compromise:,.0f} to the {sport.replace('_',' ').title()} NIL allocation."
    if action == "deny":
        coach["satisfaction"]=max(0,int(coach.get("satisfaction",72))-18)
        demand["status"]="Denied"; demand["resolved_date"]=game["date"]
        game["news"].insert(0,f"You denied {coach['name']}'s NIL request. They are unhappy and may explore other jobs.")
        return True,"Request denied. Coach satisfaction fell."
    return False,"Unknown action."


def _coach_leave_for_ai_market(game, coach, sport, rng):
    world=game["world"]; sid=coach.get("school_id")
    if not sid or sid == game["current_school"]:
        return False
    school=world["schools"].get(sid)
    if not school: return False
    # Find a stronger destination.
    options=[]
    for osid, other in world["schools"].items():
        if osid==sid: continue
        gap=other.get("prestige",50)-school.get("prestige",50)
        if gap < 8: continue
        if other.get("coaches",{}).get(sport) is None:
            options.append((gap+rng.random()*10,osid))
    if not options: return False
    options.sort(reverse=True); dest=options[0][1]
    school["coaches"][sport]=None
    coach["school_id"]=dest; coach["satisfaction"]=78; coach["demand"]=None
    world["schools"][dest]["coaches"][sport]=next(cid for cid,c in world["coaches"].items() if c is coach)
    school.setdefault("coach_history",[]).append({"date":game["date"],"action":"Coach left","sport":sport,"coach":coach["name"],"destination":world["schools"][dest]["name"]})
    game["news"].insert(0,f"{coach['name']} left {school['name']} for {world['schools'][dest]['name']}.")
    game["news"]=game["news"][:30]
    return True


def _user_coach_may_leave(game, coach, sport, rng):
    """Very unhappy player-controlled coaches can be poached by a more attractive program."""
    world=game["world"]; sid=coach.get("school_id")
    if sid != game["current_school"] or coach.get("satisfaction",70) > 18:
        return False
    school=world["schools"][sid]
    options=[]
    for osid,other in world["schools"].items():
        if osid==sid: continue
        if other.get("prestige",50) < school.get("prestige",50)+8: continue
        dest_cid=other.get("coaches",{}).get(sport)
        dest_c=world.get("coaches",{}).get(dest_cid) if dest_cid else None
        if dest_c and dest_c.get("overall",0) >= coach.get("overall",0)+8: continue
        fit=coach_program_fit(game,coach,sport,other)
        if fit >= 68: options.append((fit+other.get("prestige",50)*.25,osid,dest_cid))
    if not options or rng.random()>0.18: return False
    _,dest,dest_cid=max(options)
    if dest_cid:
        displaced=world["coaches"].get(dest_cid)
        if displaced: displaced["school_id"]=None; displaced["satisfaction"]=50
    school["coaches"][sport]=None
    coach["school_id"]=dest; coach["satisfaction"]=82; coach["demand"]=None; coach["program_fit"]=coach_program_fit(game,coach,sport,world["schools"][dest])
    world["schools"][dest]["coaches"][sport]=next(cid for cid,c in world["coaches"].items() if c is coach)
    school.setdefault("coach_history",[]).append({"date":game["date"],"action":"Coach departed","sport":sport,"coach":coach["name"],"destination":world["schools"][dest]["name"]})
    game["news"].insert(0,f"{coach['name']} left {school['name']} for {world['schools'][dest]['name']} after becoming unhappy with the program.")
    game["news"]=game["news"][:30]
    return True

def coach_market_tick(game):
    """Weekly coach morale, NIL demands, and AI movement."""
    ensure_management_schema(game)
    world=game["world"]
    d=date.fromisoformat(game["date"])
    if d.weekday()!=0: return game
    marker=d.isoformat()
    if world.setdefault("coach_market_last_tick",None)==marker: return game
    world["coach_market_last_tick"]=marker
    rng=random.Random(game["rng_seed"] + d.toordinal()*29 + len(world.get("results",[]))*7)
    for cid,coach in list(world.get("coaches",{}).items()):
        sid=coach.get("school_id"); sport=coach.get("sport")
        if not sid or not sport or sid not in world["schools"]: continue
        school=world["schools"][sid]
        rec=school.get("season_records",school.get("records",{})).get(sport,{"w":0,"l":0}); games=rec["w"]+rec["l"]
        fit=coach_program_fit(game,coach,sport,school)
        coach["program_fit"]=fit
        sat=int(coach.get("satisfaction",72))
        if fit > sat + 4: sat += 1
        elif fit < sat - 4: sat -= 1
        if games and rec["w"]>rec["l"]: sat += 1
        elif games and rec["w"]<rec["l"]: sat -= 1
        coach["satisfaction"]=max(0,min(100,sat))
        if coach.get("demand") and coach["demand"].get("status")=="Pending":
            deadline=date.fromisoformat(coach["demand"]["deadline"])
            if d >= deadline:
                coach["satisfaction"]=max(0,int(coach.get("satisfaction",72))-12)
                coach["demand"]["status"]="Expired"; coach["demand"]["resolved_date"]=game["date"]
                if sid==game["current_school"]:
                    game["news"].insert(0,f"{coach['name']} says the NIL deadline passed. They are considering leaving.")
                elif coach["satisfaction"]<35 and rng.random()<.35:
                    _coach_leave_for_ai_market(game,coach,sport,rng)
        elif _coach_should_demand(game,coach,school,sport,rng):
            create_coach_demand(game,sport,cid,rng)
        if sid==game["current_school"]:
            _user_coach_may_leave(game,coach,sport,rng)
        if coach.get("satisfaction",72)<25 and sid!=game["current_school"] and rng.random()<.10:
            _coach_leave_for_ai_market(game,coach,sport,rng)
    return game

def management_tick(game):
    ensure_management_schema(game)
    # NIL produces small recurring recruiting/retention effects through the program strength calculation.
    return game
