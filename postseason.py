import random
from datetime import date, timedelta
from history import ensure_history_schema, record_tournament_run, record_championship
from scheduling import conference_for_sport


def _ensure(game):
    w=game["world"]
    w.setdefault("postseason_results", [])
    w.setdefault("postseason_done", [])
    w.setdefault("championships", [])
    w.setdefault("school_postseason", {})
    w.setdefault("conference_postseason", [])
    for sid in w["schools"]:
        w["school_postseason"].setdefault(sid, [])
    ensure_history_schema(w)
    return w


def _season_key(game):
    d=date.fromisoformat(game["date"])
    start = d.year if d.month >= 8 else d.year - 1
    return f"{start}-{start+1}"


def _strength(w,sid,sport):
    s=w["schools"][sid]
    cid=s["coaches"].get(sport)
    c=w["coaches"].get(cid,{}) if cid else {}
    nil=s.get("nil_allocations",{}).get(sport,0)
    nil_effect=min(12,(nil/1_000_000)*1.2)
    return s.get("prestige",50)*.60 + s.get("facilities",50)*.15 + c.get("overall",50)*.22 + nil_effect


def _game(w,a,b,sport,rng,dt,tournament,round_name,seed_a=None,seed_b=None):
    sa=_strength(w,a,sport); sb=_strength(w,b,sport)
    p=1/(1+10**(-(sa-sb)/15))
    wa=rng.random()<p
    winner,loser=(a,b) if wa else (b,a)
    if sport in ("men_basketball","women_basketball"):
        margin=max(1,int(abs(sa-sb)*.18+rng.randint(1,10)))
        score_w=58+rng.randint(0,38)+margin//3
        score_l=max(45,score_w-margin)
    else:
        margin=max(1,int(abs(sa-sb)*.18+rng.randint(1,9)))
        score_w=17+rng.randint(0,34)+margin//2
        score_l=max(0,score_w-margin)
    rec={"date":dt,"sport":sport,"tournament":tournament,"round":round_name,
         "winner":winner,"loser":loser,"winner_score":score_w,"loser_score":score_l}
    if seed_a is not None:
        rec["seed_a"]=seed_a; rec["seed_b"]=seed_b
    w["postseason_results"].append(rec)
    season=_season_key({"date":dt})
    for sid,outcome,opp in [(winner,"W",loser),(loser,"L",winner)]:
        w["school_postseason"][sid].append({
            "season":season,"sport":sport,"tournament":tournament,"round":round_name,
            "result":outcome,"opponent":w["schools"][opp]["name"],
            "score":f"{score_w}-{score_l}" if sid==winner else f"{score_l}-{score_w}"
        })
    return winner


def _mark(w,key):
    if key not in w["postseason_done"]:
        w["postseason_done"].append(key)


def _already(w,key): return key in w["postseason_done"]


def _conference_rankings(w, conference, sport):
    members=[sid for sid,s in w["schools"].items() if conference_for_sport(s, sport)==conference and sport in s.get("records",{})]
    rows=[]
    for sid in members:
        games=[r for r in w.get("results",[]) if r.get("sport")==sport and r.get("conference_game") and (r.get("winner")==sid or r.get("loser")==sid)]
        cw=sum(r.get("winner")==sid for r in games)
        cl=sum(r.get("loser")==sid for r in games)
        overall=w["schools"][sid].get("season_records",w["schools"][sid]["records"])[sport]
        pct=cw/max(1,cw+cl)
        rows.append((pct, cw, overall["w"], w["schools"][sid].get("prestige",50), sid))
    rows.sort(reverse=True)
    return rows


def _conference_football_championships(game):
    w=_ensure(game); season=_season_key(game); key=f"{season}:conference:football"
    if _already(w,key): return
    rng=random.Random(game["rng_seed"]+hash(key)%10_000_000)
    made=False
    for conf,info in w.get("conferences",{}).items():
        members=[sid for sid in info.get("members",[]) if w["schools"].get(sid,{}).get("subdivision")=="FBS"]
        if len(members)<2 or conf in ("Independent","Independent / Other D-I"): continue
        ranked=_conference_rankings(w,conf,"football")
        ranked=[x for x in ranked if x[4] in members]
        if len(ranked)<2: continue
        a,b=ranked[0][4],ranked[1][4]
        win=_game(w,a,b,"football",rng,"2026-12-05",f"{conf} Championship","Conference Championship")
        w["conference_postseason"].append({"season":season,"sport":"football","conference":conf,"round":"Conference Championship","winner":win,"loser":b if win==a else a})
        w.setdefault("conference_championships", []).append({"season":season,"sport":"football","conference":conf,"champion":win,"runner_up":b if win==a else a})
        made=True
    _mark(w,key)
    return made


def _conference_basketball_tournaments(game,sport):
    w=_ensure(game); season=_season_key(game); key=f"{season}:conference:{sport}"
    if _already(w,key): return
    rng=random.Random(game["rng_seed"]+hash(key)%10_000_000)
    base=date(2027,3,1) if sport=="men_basketball" else date(2027,3,2)
    for conf,info in w.get("conferences",{}).items():
        members=[sid for sid in info.get("members",[]) if sport in w["schools"].get(sid,{}).get("records",{})]
        if len(members)<4 or conf in ("Independent","Independent / Other D-I"): continue
        ranked=_conference_rankings(w,conf,sport)
        ordered=[x[4] for x in ranked if x[4] in members]
        if len(ordered)<4: continue
        size=8 if len(ordered)>=8 else 4
        field=ordered[:size]
        round_num=0
        while len(field)>1:
            round_num+=1
            winners=[]
            dt=(base+timedelta(days=round_num-1)).isoformat()
            for i in range(0,len(field),2):
                winners.append(_game(w,field[i],field[i+1],sport,rng,dt,f"{conf} Tournament",f"Round {round_num}"))
            field=winners
        champ=field[0]
        w["conference_postseason"].append({"season":season,"sport":sport,"conference":conf,"round":"Conference Tournament","winner":champ})
        w.setdefault("conference_championships", []).append({"season":season,"sport":sport,"conference":conf,"champion":champ})
    _mark(w,key)


def _basketball_tournament(game,sport,dt):
    w=_ensure(game); season=_season_key(game); key=f"{season}:{sport}:ncaa"
    if _already(w,key): return
    rng=random.Random(game["rng_seed"]+hash(key)%10_000_000)
    eligible=[]
    for sid,s in w["schools"].items():
        r=s.get("season_records",s["records"])[sport]; games=r["w"]+r["l"]
        if games>=8:
            champ_bonus=0
            if any(x.get("season")==season and x.get("sport")==sport and x.get("winner")==sid for x in w.get("conference_postseason",[])):
                champ_bonus=4
            eligible.append((r["w"]/(games or 1)*70+s["prestige"]*.30+champ_bonus,sid))
    eligible.sort(reverse=True)
    field=[sid for _,sid in eligible[:76]]
    if len(field)<76:
        field=[sid for _,sid in sorted([(w["schools"][sid]["prestige"],sid) for sid in w["schools"]],reverse=True)[:76]]
    opening=field[52:76]
    current=field[:52]
    for i in range(0,len(opening),2):
        current.append(_game(w,opening[i],opening[i+1],sport,rng,dt,"NCAA Tournament","Opening Round",65+i//2,66+i//2))
    current=sorted(current,key=lambda sid:w["schools"][sid]["prestige"],reverse=True)
    rounds=[("First Round",32),("Second Round",16),("Sweet 16",8),("Elite Eight",4),("Final Four",2),("National Championship",1)]
    dates=["2027-03-18","2027-03-20","2027-03-25","2027-03-27","2027-04-03","2027-04-05"] if sport=="men_basketball" else ["2027-03-19","2027-03-21","2027-03-26","2027-03-28","2027-04-02","2027-04-04"]
    for (rnd,_),d in zip(rounds,dates):
        for sid in current:
            record_tournament_run(w, season, sport, rnd, sid)
        winners=[]
        losers=[]
        for i in range(0,len(current),2):
            a,b=current[i],current[i+1]
            win=_game(w,a,b,sport,rng,d,"NCAA Tournament",rnd)
            winners.append(win)
            losers.append(b if win==a else a)
        current=winners
    champ=current[0]
    runner=None
    if w.get("postseason_results"):
        last=w["postseason_results"][-1]
        runner=last.get("loser")
    w["championships"].append({"season":season,"sport":sport,"championship":f"NCAA {sport.replace('_',' ').title()}","school":champ,"runner_up":runner})
    record_championship(w, season, sport, champ, f"NCAA {sport.replace('_',' ').title()}", runner)
    _mark(w,key)


def _football_postseason(game):
    w=_ensure(game); current_date=game["date"]; season=_season_key(game)
    rng=random.Random(game["rng_seed"]+hash(season+"football")%10_000_000)
    fbs=[sid for sid,s in w["schools"].items() if s.get("subdivision")=="FBS"]
    if len(fbs)<12: return
    ranked=[]
    champs={x.get("winner") for x in w.get("conference_postseason",[]) if x.get("season")==season and x.get("sport")=="football"}
    for sid in fbs:
        r=w["schools"][sid].get("season_records",w["schools"][sid]["records"])["football"]; games=r["w"]+r["l"]
        if games>=2:
            conf_bonus=3 if sid in champs else 0
            score=r["w"]*8-r["l"]*2+w["schools"][sid]["prestige"]*.35+conf_bonus
            ranked.append((score,sid))
    ranked.sort(reverse=True); top12=[sid for _,sid in ranked[:12]]
    if len(top12)<12: return
    if not _already(w,f"{season}:football:cfp_first"):
        pairings=[(top12[4],top12[11]),(top12[5],top12[10]),(top12[6],top12[9]),(top12[7],top12[8])]
        winners=[_game(w,a,b,"football",rng,"2026-12-18","College Football Playoff","First Round") for a,b in pairings]
        w["_cfp_current"]=top12[:4]+winners; _mark(w,f"{season}:football:cfp_first")
    if current_date >= "2026-12-30" and not _already(w,f"{season}:football:cfp_qf"):
        current=w.get("_cfp_current",top12)
        qf=[_game(w,a,b,"football",rng,"2026-12-30","College Football Playoff","Quarterfinal") for a,b in [(current[0],current[7]),(current[1],current[6]),(current[2],current[5]),(current[3],current[4])]]
        w["_cfp_current"]=qf; _mark(w,f"{season}:football:cfp_qf")
    if current_date >= "2027-01-14" and not _already(w,f"{season}:football:cfp_sf"):
        current=w.get("_cfp_current",[])
        if len(current)==4:
            w["_cfp_current"]=[_game(w,current[0],current[1],"football",rng,"2027-01-14","College Football Playoff","Semifinal"),_game(w,current[2],current[3],"football",rng,"2027-01-15","College Football Playoff","Semifinal")]
        _mark(w,f"{season}:football:cfp_sf")
    if current_date >= "2027-01-25" and not _already(w,f"{season}:football:cfp_final"):
        current=w.get("_cfp_current",[])
        if len(current)==2:
            champ=_game(w,current[0],current[1],"football",rng,"2027-01-25","College Football Playoff","National Championship")
            w["championships"].append({"season":season,"sport":"football","championship":"College Football Playoff National Championship","school":champ,"runner_up":current[1]})
            record_championship(w, season, "football", champ, "College Football Playoff National Championship", current[1])
        _mark(w,f"{season}:football:cfp_final")
    if current_date >= "2026-12-23" and not _already(w,f"{season}:football:bowls"):
        selected=set(top12)
        bowl_eligible=[sid for _,sid in ranked if sid not in selected and w["schools"][sid]["records"]["football"]["w"]>=6]
        bowl_names=["Sun Bowl","Gator Bowl","Citrus Bowl","Alamo Bowl","Holiday Bowl","Liberty Bowl","Music City Bowl","Texas Bowl","Pinstripe Bowl","Independence Bowl","Las Vegas Bowl","Birmingham Bowl"]
        for i in range(0,min(len(bowl_eligible)-1,len(bowl_names)*2),2):
            rec_before=len(w["postseason_results"])
            _game(w,bowl_eligible[i],bowl_eligible[i+1],"football",rng,"2026-12-23","College Football Bowl","Bowl Game")
            w["postseason_results"][rec_before]["bowl"]=bowl_names[i//2]
        _mark(w,f"{season}:football:bowls")


def process_postseason(game):
    d=game["date"]
    if d >= "2026-12-05":
        _conference_football_championships(game)
    if d >= "2026-12-18":
        _football_postseason(game)
    if d >= "2027-03-01":
        _conference_basketball_tournaments(game,"men_basketball")
        _conference_basketball_tournaments(game,"women_basketball")
    if d >= "2027-03-14":
        _basketball_tournament(game,"men_basketball","2027-03-14")
        _basketball_tournament(game,"women_basketball","2027-03-14")
    return game


def school_postseason_history(game,sid):
    _ensure(game); return list(reversed(game["world"]["school_postseason"].get(sid,[])))


def latest_champions(game):
    _ensure(game); return list(reversed(game["world"]["championships"][-20:]))
