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
            "salary": int(250_000 + c["overall"] * 65_000)
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
            "salary":int(250_000 + c["overall"] * 65_000)
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
    salary=int(250_000 + c["overall"] * 65_000)
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
    rec = school.get("records", {}).get(sport, {"w":0,"l":0})
    games = rec["w"] + rec["l"]
    pct = rec["w"] / games if games else .5
    underfunded = peer > 0 and allocation < peer * .72
    hot = coach.get("overall",50) >= max(70, school.get("prestige",50)+10)
    probability = 0.025
    if underfunded: probability += 0.16
    if pct < .42: probability += 0.07
    if hot: probability += 0.04
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
        rec=school.get("records",{}).get(sport,{"w":0,"l":0}); games=rec["w"]+rec["l"]
        if games and rec["w"]>rec["l"]: coach["satisfaction"]=min(100,int(coach.get("satisfaction",72))+1)
        elif games and rec["w"]<rec["l"]: coach["satisfaction"]=max(0,int(coach.get("satisfaction",72))-1)
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
        if coach.get("satisfaction",72)<25 and sid!=game["current_school"] and rng.random()<.10:
            _coach_leave_for_ai_market(game,coach,sport,rng)
    return game

def management_tick(game):
    ensure_management_schema(game)
    # NIL produces small recurring recruiting/retention effects through the program strength calculation.
    return game
