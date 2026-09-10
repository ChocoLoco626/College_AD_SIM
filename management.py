
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

def management_tick(game):
    ensure_management_schema(game)
    # NIL produces small recurring recruiting/retention effects through the program strength calculation.
    return game
