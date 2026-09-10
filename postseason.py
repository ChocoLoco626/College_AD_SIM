
import random
from datetime import date

def _ensure(game):
    w=game["world"]
    w.setdefault("postseason_results", [])
    w.setdefault("postseason_done", [])
    w.setdefault("championships", [])
    w.setdefault("school_postseason", {})
    for sid in w["schools"]:
        w["school_postseason"].setdefault(sid, [])
    return w

def _season_key(game):
    d=date.fromisoformat(game["date"])
    start = d.year if d.month >= 8 else d.year - 1
    return f"{start}-{start+1}"

def _strength(w,sid,sport):
    s=w["schools"][sid]
    cid=s["coaches"].get(sport)
    c=w["coaches"].get(cid,{}) if cid else {}
    nil=w.get("nil_allocations",{})
    # NIL is stored at game level; postseason strength gets a modest effect elsewhere.
    return s.get("prestige",50)*.62 + s.get("facilities",50)*.16 + c.get("overall",50)*.22

def _game(w,a,b,sport,rng,dt,tournament,round_name,seed_a=None,seed_b=None):
    sa=_strength(w,a,sport); sb=_strength(w,b,sport)
    p=1/(1+10**(-(sa-sb)/15))
    wa=rng.random()<p
    winner,loser=(a,b) if wa else (b,a)
    base=80 if sport in ("men_basketball","women_basketball") else 24
    margin=max(1,int(abs(sa-sb)*(.12 if sport.startswith("men_") or sport.startswith("women_") else .18)+rng.randint(1,base//3)))
    if sport in ("men_basketball","women_basketball"):
        score_w=58+rng.randint(0,42)+margin//3
        score_l=max(45,score_w-margin)
    else:
        score_w=17+rng.randint(0,34)+margin//2
        score_l=max(0,score_w-margin)
    rec={"date":dt,"sport":sport,"tournament":tournament,"round":round_name,
         "winner":winner,"loser":loser,"winner_score":score_w,"loser_score":score_l}
    if seed_a is not None:
        rec["seed_a"]=seed_a; rec["seed_b"]=seed_b
    w["postseason_results"].append(rec)
    for sid,outcome,opp in [(winner,"W",loser),(loser,"L",winner)]:
        w["school_postseason"][sid].append({"season":_season_key({"date":dt}), "sport":sport,
            "tournament":tournament,"round":round_name,"result":outcome,
            "opponent":w["schools"][opp]["name"],"score":f"{score_w}-{score_l}" if sid==winner else f"{score_l}-{score_w}"})
    return winner

def _mark(w,key): w["postseason_done"].append(key)

def _already(w,key): return key in w["postseason_done"]

def _basketball_tournament(game,sport,dt):
    w=_ensure(game); key=f"{_season_key(game)}:{sport}:ncaa"
    if _already(w,key): return
    rng=random.Random(game["rng_seed"]+hash(key)%10_000_000)
    eligible=[]
    for sid,s in w["schools"].items():
        r=s["records"][sport]; games=r["w"]+r["l"]
        if games>=8:
            eligible.append((r["w"]/(games or 1)*70+s["prestige"]*.30,sid))
    eligible.sort(reverse=True)
    field=[sid for _,sid in eligible[:76]]
    if len(field)<76: field=[sid for _,sid in sorted([(w["schools"][sid]["prestige"],sid) for sid in w["schools"]],reverse=True)[:76]]
    # 76-team format: 12 opening-round games -> 64.
    opening=field[52:76]
    next64=field[:52]
    for i in range(0,len(opening),2):
        a,b=opening[i],opening[i+1]
        win=_game(w,a,b,sport,rng,dt,"NCAA Tournament","Opening Round",65+i//2,66+i//2)
        next64.append(win)
    # Seed top 64 by ranking strength.
    current=sorted(next64,key=lambda sid:w["schools"][sid]["prestige"],reverse=True)
    rounds=[("First Round",32),("Second Round",16),("Sweet 16",8),("Elite Eight",4),("Final Four",2),("National Championship",1)]
    dates=["2027-03-18","2027-03-20","2027-03-25","2027-03-27","2027-04-03","2027-04-05"] if sport=="men_basketball" else ["2027-03-19","2027-03-21","2027-03-26","2027-03-28","2027-04-02","2027-04-04"]
    for (rnd,count),d in zip(rounds,dates):
        winners=[]
        # Pair strongest with weakest-ish to keep bracket deterministic.
        for i in range(0,len(current),2):
            winners.append(_game(w,current[i],current[i+1],sport,rng,d,"NCAA Tournament",rnd))
        current=winners
    champ=current[0]
    w["championships"].append({"season":_season_key(game),"sport":sport,"championship":f"NCAA {sport.replace('_',' ').title()}","school":champ})
    _mark(w,key)

def _football_postseason(game):
    w=_ensure(game)
    current_date=game["date"]
    season=_season_key(game)
    rng=random.Random(game["rng_seed"]+hash(season+"football")%10_000_000)
    fbs=[sid for sid,s in w["schools"].items() if s.get("subdivision")=="FBS"]
    if len(fbs)<12: return
    ranked=[]
    for sid in fbs:
        r=w["schools"][sid]["records"]["football"]; games=r["w"]+r["l"]
        if games>=2:
            score=r["w"]*8-r["l"]*2+w["schools"][sid]["prestige"]*.35
            ranked.append((score,sid))
    ranked.sort(reverse=True)
    top12=[sid for _,sid in ranked[:12]]
    if len(top12)<12: return
    # CFP first round: seeds 5-12, 1-4 bye.
    if not _already(w,f"{season}:football:cfp_first"):
        pairings=[(top12[4],top12[11]),(top12[5],top12[10]),(top12[6],top12[9]),(top12[7],top12[8])]
        winners=[]
        for a,b in pairings:
            winners.append(_game(w,a,b,"football",rng,"2026-12-18","College Football Playoff","First Round"))
        w["_cfp_current"]=top12[:4]+winners
        _mark(w,f"{season}:football:cfp_first")
    if current_date >= "2026-12-30" and not _already(w,f"{season}:football:cfp_qf"):
        current=w.get("_cfp_current",top12)
        qf=[]
        for a,b in [(current[0],current[7]),(current[1],current[6]),(current[2],current[5]),(current[3],current[4])]:
            qf.append(_game(w,a,b,"football",rng,"2026-12-30","College Football Playoff","Quarterfinal"))
        w["_cfp_current"]=qf
        _mark(w,f"{season}:football:cfp_qf")
    if current_date >= "2027-01-14" and not _already(w,f"{season}:football:cfp_sf"):
        current=w.get("_cfp_current",[])
        if len(current)==4:
            sf=[_game(w,current[0],current[1],"football",rng,"2027-01-14","College Football Playoff","Semifinal"),
                _game(w,current[2],current[3],"football",rng,"2027-01-15","College Football Playoff","Semifinal")]
            w["_cfp_current"]=sf
        _mark(w,f"{season}:football:cfp_sf")
    if current_date >= "2027-01-25" and not _already(w,f"{season}:football:cfp_final"):
        current=w.get("_cfp_current",[])
        if len(current)==2:
            champ=_game(w,current[0],current[1],"football",rng,"2027-01-25","College Football Playoff","National Championship")
            w["championships"].append({"season":season,"sport":"football","championship":"College Football Playoff National Championship","school":champ})
            _mark(w,f"{season}:football:cfp_final")
    # Non-CFP bowl games.
    if current_date >= "2026-12-23" and not _already(w,f"{season}:football:bowls"):
        selected=set(top12)
        bowl_eligible=[sid for _,sid in ranked if sid not in selected and w["schools"][sid]["records"]["football"]["w"]>=6]
        bowl_names=["Sun Bowl","Gator Bowl","Citrus Bowl","Alamo Bowl","Holiday Bowl","Liberty Bowl","Music City Bowl","Texas Bowl","Pinstripe Bowl","Independence Bowl","Las Vegas Bowl","Birmingham Bowl"]
        for i in range(0,min(len(bowl_eligible)-1,len(bowl_names)*2),2):
            a,b=bowl_eligible[i],bowl_eligible[i+1]
            _game(w,a,b,"football",rng,"2026-12-23","College Football Bowl","Bowl Game")
            w["postseason_results"][-1]["bowl"]=bowl_names[i//2]
        _mark(w,f"{season}:football:bowls")

def process_postseason(game):
    d=game["date"]
    # Only process once the calendar reaches the relevant dates.
    if d >= "2026-12-18":
        _football_postseason(game)
    if d >= "2027-03-14":
        _basketball_tournament(game,"men_basketball","2027-03-14")
        _basketball_tournament(game,"women_basketball","2027-03-14")
    return game

def school_postseason_history(game,sid):
    _ensure(game)
    return list(reversed(game["world"]["school_postseason"].get(sid,[])))

def latest_champions(game):
    _ensure(game)
    return list(reversed(game["world"]["championships"][-20:]))
