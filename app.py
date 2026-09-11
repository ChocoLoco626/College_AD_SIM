
import json
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import streamlit as st

from database import init_db, create_user, authenticate_user, list_saves, save_game, load_game
from game_state import create_game
from simulation import advance_days, simulate_to_season_end, season_phase, current_calendar_events
from career import get_job_market, take_job, ensure_career_schema, job_market_tick
from management import (
    ensure_management_schema, available_nil, set_nil_allocation,
    available_boosters, invest_facility, coach_candidates,
    fire_head_coach, hire_head_coach, NIL_SPORTS, resolve_coach_demand, negotiate_coach_salary, booster_tick, coach_program_fit
)
from postseason import school_postseason_history, latest_champions
from history import ensure_history_schema, legacy_for_school, NCAA_DI_CHAMPIONSHIP_SPORTS
from rankings import national_rankings, conference_standings, all_conference_summaries, SPORT_LABELS
from scheduling import conference_for_sport
from scheduling import ensure_schedule_schema, generate_season_schedules, current_season_schedule, negotiate_game, season_key

st.set_page_config(page_title="College AD Simulator V14", page_icon="🏟️", layout="wide")
init_db()

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "game" not in st.session_state:
    st.session_state.game = None

def money(x): return "${:,.0f}".format(x)

def migrate_game(g):
    ensure_management_schema(g)
    ensure_career_schema(g)
    job_market_tick(g)
    ensure_schedule_schema(g["world"])
    generate_season_schedules(g["world"], season_key(g["date"]), g["rng_seed"])
    ensure_history_schema(g["world"])
    try:
        booster_tick(g)
    except Exception:
        pass
    g.setdefault("version", 14)
    g.setdefault("news", [])
    g["world"].setdefault("postseason_results", [])
    g["world"].setdefault("postseason_done", [])
    g["world"].setdefault("championships", [])
    g["world"].setdefault("school_postseason", {})
    for sid, s in g["world"]["schools"].items():
        s.setdefault("season_records", {sport:{"w":0,"l":0} for sport in s.get("records",{})})
        s.setdefault("career_records", {sport:dict(r) for sport,r in s.get("records",{}).items()})
        s.setdefault("prestige_history", [])
        # Existing V13 saves have cumulative records. Rebuild current-season records from results.
        for sport in s.get("season_records",{}): s["season_records"][sport]={"w":0,"l":0}
    current_season = season_key(g["date"])
    for r in g["world"].get("results",[]):
        if r.get("season") != current_season: continue
        for sid,outcome in ((r.get("winner"),"w"),(r.get("loser"),"l")):
            if sid in g["world"]["schools"] and r.get("sport") in g["world"]["schools"][sid].get("season_records",{}):
                g["world"]["schools"][sid]["season_records"][r["sport"]][outcome]+=1
    return g

st.title("🏟️ College Athletic Director Simulator — V14")
st.caption("Career Mode • Persistent World • Coaches • NIL • Facilities • Postseason • Living Coach Market")

if st.session_state.user_id is None:
    tab1, tab2 = st.tabs(["Sign in", "Create account"])
    with tab1:
        u = st.text_input("Username", key="login_u")
        p = st.text_input("Password", type="password", key="login_p")
        if st.button("Sign in", type="primary"):
            uid = authenticate_user(u, p)
            if uid:
                st.session_state.user_id = uid
                st.rerun()
            st.error("Invalid username or password.")
    with tab2:
        u2 = st.text_input("New username")
        p2 = st.text_input("New password", type="password")
        if st.button("Create account"):
            if len(u2) < 3 or len(p2) < 6:
                st.warning("Use at least 3 characters for the username and 6 for the password.")
            else:
                ok,msg = create_user(u2,p2)
                (st.success if ok else st.error)(msg)
    st.stop()

st.sidebar.success("Signed in")
if st.sidebar.button("Sign out"):
    st.session_state.user_id = None
    st.session_state.game = None
    st.rerun()

saves = list_saves(st.session_state.user_id)
st.sidebar.subheader("Career saves")
save_name = st.sidebar.text_input("Save name", value="My Career")
if st.sidebar.button("Save career", type="primary") and st.session_state.game:
    save_game(st.session_state.user_id, save_name, st.session_state.game)
    st.sidebar.success("Saved.")

if saves:
    choice = st.sidebar.selectbox("Load save", ["—"] + [x[0] for x in saves])
    if choice != "—" and st.sidebar.button("Load selected"):
        st.session_state.game = migrate_game(load_game(st.session_state.user_id, choice))
        st.rerun()

if st.session_state.game is None:
    st.header("Start your AD career")
    st.write("Start at a lower-prestige Division I school, build the department, manage coaches and money, win championships, and earn opportunities at bigger programs.")
    name = st.text_input("Your name", value="Alex Carter")
    if st.button("Begin Career", type="primary"):
        schools = json.loads(Path("data/schools.json").read_text(encoding="utf-8"))
        st.session_state.game = create_game(schools, name)
        st.session_state.game = migrate_game(st.session_state.game)
        st.rerun()
    st.stop()

g = migrate_game(st.session_state.game)
school = g["world"]["schools"][g["current_school"]]
school_name = school["name"]
ensure_management_schema(g)

st.sidebar.markdown(f"### {school_name}")
st.sidebar.write(f"**Date:** {g['date']}")
st.sidebar.write(f"**Phase:** {season_phase(g)}")
st.sidebar.metric("Program Prestige", school.get("prestige",50))
st.sidebar.metric("Career Reputation", g["career"]["reputation"])
st.sidebar.progress(g["career"]["job_security"]/100, text=f"Job security: {g['career']['job_security']}%")

tabs = st.tabs([
    "🏠 Dashboard","📅 Calendar","🏈 Programs","💰 Money & NIL",
    "🏆 Postseason","📋 Schedules","🏢 Conferences","📊 Rankings","🏛️ History","💼 Job Market","👥 People","📰 World","📜 Career"
])

with tabs[0]:
    st.header(school_name)
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Program Prestige", school.get("prestige",50))
    c2.metric("Career Reputation", g["career"]["reputation"])
    c3.metric("Board Approval", g["career"]["board_approval"])
    c4.metric("Cash", money(g["finances"]["cash"]))
    c5.metric("Booster Funds", money(g["finances"]["booster_funds"]))
    st.subheader("Current-season records")
    rows=[]
    for sport,r in school.get("season_records",school["records"]).items():
        rows.append({"Sport":sport.replace("_"," ").title(),"W":r["w"],"L":r["l"]})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    champs=[x for x in g["world"].get("championships",[]) if x["school"]==g["current_school"]]
    if champs:
        st.subheader("Championships")
        st.dataframe(pd.DataFrame(champs), use_container_width=True, hide_index=True)
    st.subheader("Board goals")
    st.json(school["goals"])
    if school.get("prestige_history"):
        st.subheader("Prestige progression")
        ph=pd.DataFrame(school["prestige_history"])
        st.line_chart(ph.set_index("season")["new"])
    if g["finances"].get("financial_history"):
        st.subheader("Year-over-year finances")
        fh=pd.DataFrame(g["finances"]["financial_history"]).set_index("season")
        st.line_chart(fh[["revenue","expenses","cash"]])
        st.bar_chart(fh[["revenue","expenses","nil_budget","booster_funds"]])
    st.subheader("Recent news")
    for n in g["news"][:8]: st.write("•", n)
    st.divider()
    st.subheader("Advance time")
    a,b,c,d=st.columns(4)
    if a.button("Advance 1 day"): advance_days(g,1); st.rerun()
    if b.button("Advance 1 week"): advance_days(g,7); st.rerun()
    if c.button("Advance 1 month"): advance_days(g,30); st.rerun()
    if d.button("Simulate season", type="primary"):
        simulate_to_season_end(g); st.rerun()
    st.caption("Simulate season runs the rest of the current academic year, plays the saved schedules and postseason, completes the July 31 season review, updates prestige/boosters/finances, resets season records, and generates your next job offers.")

with tabs[1]:
    st.header("2026–27 Calendar")
    rows=current_calendar_events(g)
    st.dataframe(pd.DataFrame(rows, columns=["Date","Event"]), use_container_width=True, hide_index=True)

with tabs[2]:
    st.header("Your Athletic Programs")
    st.caption("You can now evaluate, fire, and hire head coaches. Coaching decisions affect program strength, board approval, finances, and your career.")
    for sport in school["records"]:
        cid=school["coaches"].get(sport)
        coach=g["world"]["coaches"].get(cid) if cid else None
        with st.expander(sport.replace("_"," ").title(), expanded=(sport in ("football","men_basketball"))):
            r=school.get("season_records",school["records"])[sport]
            st.write(f"**Current-season Record:** {r['w']}-{r['l']}")
            cr=school.get("career_records",school["records"])[sport]
            st.caption(f"All-time program record: {cr['w']}-{cr['l']}")
            if coach:
                st.write(f"**Head Coach:** {coach['name']}")
                st.write(f"**Overall:** {coach['overall']} • **Recruiting:** {coach['recruiting']} • **Development:** {coach['development']}")
                fit=coach.get("program_fit",coach_program_fit(g,coach,sport,school))
                st.write(f"**Personality:** {coach['personality']} • **Strength:** {coach['trait']} • **Contract:** {coach.get('contract_years',1)} years")
                st.write(f"**Salary:** {money(coach.get('salary',250_000 + coach['overall']*65_000))} / year • **Program fit:** {fit}/100")
                sat=coach.get("satisfaction",72)
                st.progress(max(0,min(100,sat))/100, text=f"Coach satisfaction: {sat}/100")
                salary_now=int(coach.get("salary",250_000 + coach["overall"]*65_000))
                salary_offer=st.number_input("Coach salary offer", min_value=100_000, max_value=8_000_000, value=salary_now, step=25_000, key=f"salary_{sport}")
                if st.button("Renegotiate salary", key=f"salary_btn_{sport}"):
                    ok,msg=negotiate_coach_salary(g,sport,salary_offer); (st.success if ok else st.error)(msg); st.rerun()
                demand=coach.get("demand")
                if demand and demand.get("status")=="Pending":
                    st.warning(f"**{coach['name']} is demanding ${int(demand['requested_nil']):,.0f} more NIL** before {demand['deadline']}.\n\n{demand['message']}")
                    dc=st.columns(3)
                    if dc[0].button("Approve NIL",key=f"approve_demand_{sport}"):
                        ok,msg=resolve_coach_demand(g,sport,"approve"); (st.success if ok else st.error)(msg); st.rerun()
                    if dc[1].button("Negotiate",key=f"negotiate_demand_{sport}"):
                        ok,msg=resolve_coach_demand(g,sport,"negotiate"); (st.success if ok else st.error)(msg); st.rerun()
                    if dc[2].button("Deny",key=f"deny_demand_{sport}"):
                        ok,msg=resolve_coach_demand(g,sport,"deny"); (st.success if ok else st.error)(msg); st.rerun()
                if st.button(f"Fire {coach['name']}", key=f"fire_{sport}"):
                    ok,msg=fire_head_coach(g,sport)
                    (st.success if ok else st.error)(msg)
                    st.rerun()
            else:
                st.warning("This program currently has no head coach.")
            if not coach:
                candidates=coach_candidates(g,sport)
                for cand in candidates:
                    cc=st.columns([3,1,1,1,1])
                    cc[0].write(f"**{cand['name']}**\n{cand['current_school']}")
                    cc[1].write(f"OVR\n**{cand['overall']}**")
                    cc[2].write(f"Recruit\n**{cand['recruiting']}**")
                    cc[3].write(f"Dev\n**{cand['development']}**")
                    cc[4].write(f"Salary\n**{money(cand['salary'])}**\nFit **{cand.get('fit',0)}/100**")
                    if cc[4].button("Hire", key=f"hire_{sport}_{cand['id']}"):
                        ok,msg=hire_head_coach(g,sport,cand["id"])
                        (st.success if ok else st.error)(msg)
                        st.rerun()

with tabs[3]:
    st.header("Money, NIL & Facilities")
    f=g["finances"]
    a,b,c=st.columns(3)
    a.metric("Cash",money(f["cash"]))
    b.metric("Unallocated NIL",money(available_nil(g)))
    c.metric("Unallocated Booster Funds",money(available_boosters(g)))
    st.metric("Booster Confidence", f"{school.get('booster_confidence',68)}/100")

    st.subheader("NIL allocation")
    st.write("Move your NIL budget toward sports where recruiting and player retention matter most.")
    for sport in NIL_SPORTS:
        current=f["nil_allocations"].get(sport,0)
        new=st.number_input(
            sport.replace("_"," ").title(), min_value=0, max_value=int(f["nil_budget"]),
            value=int(current), step=100_000, key=f"nil_{sport}"
        )
        if st.button(f"Set {sport.replace('_',' ').title()} NIL", key=f"setnil_{sport}"):
            ok,msg=set_nil_allocation(g,sport,new)
            (st.success if ok else st.error)(msg)
            st.rerun()

    st.divider()
    st.subheader("Booster-funded facilities")
    st.write("Targeted investments improve your department and can raise recruiting/program strength.")
    categories=[
        "Football facilities","Stadium","Strength & conditioning","Football recruiting",
        "Basketball arena","Men's basketball practice facility","Basketball recruiting",
        "Women's basketball facilities","Women's basketball recruiting",
        "Baseball stadium","Baseball facilities","Softball facilities",
        "Academic support","Sports medicine","Athletic training","Travel","General athletics"
    ]
    category=st.selectbox("Investment area",categories)
    amount=st.number_input("Investment amount",min_value=0,step=250_000,value=1_000_000,key="facility_amount")
    if st.button("Invest booster funds",type="primary"):
        ok,msg=invest_facility(g,category,amount)
        (st.success if ok else st.error)(msg)
        st.rerun()
    if school.get("facility_investments"):
        st.subheader("Recent facility investments")
        st.dataframe(pd.DataFrame(school["facility_investments"][-15:][::-1]),use_container_width=True,hide_index=True)

with tabs[4]:
    st.header("Postseason")
    st.write("Conference championships and tournaments feed into the national postseason. Results persist in the save and feed into your résumé, board review, program prestige, and championship history.")
    cp=g["world"].get("conference_postseason",[])
    if cp:
        st.subheader("Conference Championships & Tournaments")
        rows=[]
        for r in reversed(cp[-40:]):
            winner=g["world"]["schools"].get(r.get("winner"),{}).get("name",r.get("winner",""))
            loser=g["world"]["schools"].get(r.get("loser"),{}).get("name","")
            rows.append({"Season":r.get("season",""),"Sport":r.get("sport","").replace("_"," ").title(),"Conference":r.get("conference",""),"Event":r.get("round",""),"Winner":winner,"Runner-up":loser})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    else:
        st.info("Conference postseason results will appear here after the regular season reaches championship/tournament dates.")
    current_sid=g["current_school"]
    hist=school_postseason_history(g,current_sid)
    if hist:
        st.subheader("Your postseason history")
        st.dataframe(pd.DataFrame(hist),use_container_width=True,hide_index=True)
    else:
        st.info("Your school has no recorded postseason result yet this career.")
    st.subheader("National championships")
    champs=latest_champions(g)
    if champs:
        rows=[]
        for x in champs:
            rows.append({"Season":x["season"],"Sport":x["sport"].replace("_"," ").title(),"Championship":x["championship"],"School":g["world"]["schools"][x["school"]]["name"]})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    else:
        st.info("No national championships have been simulated yet.")
    st.subheader("Recent postseason games")
    recent=g["world"].get("postseason_results",[])[-30:][::-1]
    if recent:
        rows=[]
        for r in recent:
            rows.append({
                "Date":r["date"],"Tournament":r["tournament"],"Round":r["round"],
                "Winner":g["world"]["schools"][r["winner"]]["name"],
                "Loser":g["world"]["schools"][r["loser"]]["name"],
                "Score":f"{r['winner_score']}-{r['loser_score']}",
                "Bowl":r.get("bowl","")
            })
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

with tabs[5]:
    st.header("Season Schedules")
    st.caption("Every team's schedule is generated once per season and then persists. Football is scheduled on Saturdays during the regular season, while basketball uses its normal winter calendar.")
    season_options=[]
    start_year=int(g["date"][:4])
    for y in range(max(2026,start_year-1), start_year+3):
        season_options.append(f"{y}-{y+1}")
    season=st.selectbox("Season", season_options, index=season_options.index(season_key(g["date"])) if season_key(g["date"]) in season_options else 0, key="schedule_season")
    generate_season_schedules(g["world"], season, g["rng_seed"])
    sport=st.selectbox("Sport", ["football","men_basketball","women_basketball"], format_func=lambda x:x.replace("_"," ").title(), key="schedule_sport")
    team_options=sorted(g["world"]["schools"], key=lambda sid:g["world"]["schools"][sid]["name"])
    team_sid=st.selectbox("Team", team_options, index=team_options.index(g["current_school"]), format_func=lambda sid:g["world"]["schools"][sid]["name"], key="schedule_team")
    selected_school=g["world"]["schools"][team_sid]
    st.subheader(f"{selected_school['name']} — {sport.replace('_',' ').title()} — {season}")
    sched=current_season_schedule(g["world"],team_sid,season,sport)
    if not sched:
        if sport == "football" and selected_school.get("subdivision") not in ("FBS", "FCS"):
            st.info(f"{selected_school['name']} is currently modeled as a non-football Division I school, so no football schedule is generated.")
        else:
            st.warning("This team has no games in this season. The schedule repair system will attempt to assign a slate when the season is generated.")
    rows=[]
    for x in sched:
        opp=g["world"]["schools"].get(x["opponent"],{}).get("name",x["opponent"])
        result="Scheduled"
        matching=[r for r in g["world"].get("results",[]) if r.get("date")==x["date"] and r.get("sport")==sport and {r.get("home"),r.get("away")}=={team_sid,x["opponent"]}]
        if matching:
            r=matching[-1]; won=r.get("winner")==team_sid; score=""
            result=("W" if won else "L")
        rows.append({"Date":x["date"],"Opponent":opp,"Site":"Home" if x["home"] else "Away","Type":"Conference" if x["conference_game"] else "Non-Conference","Result":result,"Status":x["status"]})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    if sport=="football":
        football_dates=sorted({x["date"] for x in sched})
        if football_dates:
            off_saturday=[d for d in football_dates if date.fromisoformat(d).weekday()!=5]
            if off_saturday:
                st.warning(f"Football schedule contains non-Saturday dates: {', '.join(off_saturday)}")
            else:
                st.success("Football regular-season games are scheduled on Saturdays.")
    st.divider()
    st.subheader("Negotiate a non-conference game")
    eligible=[sid for sid,s in g["world"]["schools"].items() if sid!=g["current_school"] and (sport!="football" or s.get("subdivision") in ("FBS","FCS"))]
    opp=st.selectbox("Opponent",eligible,format_func=lambda sid:g["world"]["schools"][sid]["name"],key="neg_opp")
    future_dates=[]
    for dd in sorted({x["date"] for x in sched if x["date"]>=g["date"] and not x["conference_game"]}):
        future_dates.append(dd)
    if not future_dates:
        future_dates=[(date.fromisoformat(g["date"])+timedelta(days=7*i)).isoformat() for i in range(1,9)]
    game_date=st.selectbox("Date (a non-conference slot will be replaced if occupied)",future_dates,key="neg_date")
    home=st.radio("Location",["We host — we pay the guarantee","We travel — we get paid"],key="neg_home")
    amount=st.number_input("Guarantee amount",min_value=0,step=25000,value=250000,key="neg_amount")
    if st.button("Submit game proposal",type="primary"):
        ok,msg=negotiate_game(g["world"],g["current_school"],opp,sport,game_date,home.startswith("We host"),amount,g["rng_seed"])
        (st.success if ok else st.warning)(msg)
        if ok: st.rerun()

with tabs[6]:
    st.header("🏢 Conference Dashboard")
    st.caption("The 2026–27 world is built around 361 Division I school records and 32 primary multi-sport conferences. Football uses sport-specific conference membership, so football-only alignments and realignment are handled separately.")
    m1,m2=st.columns(2); m1.metric("Division I schools", len(g["world"]["schools"])); m2.metric("Primary conferences represented", len({conference_for_sport(s, "men_basketball") for s in g["world"]["schools"].values()}))
    season = season_key(g["date"])
    conf_sport = st.selectbox("Sport", ["football","men_basketball","women_basketball"], format_func=lambda x: SPORT_LABELS[x], key="conf_sport")
    summaries = all_conference_summaries(g["world"], season, conf_sport)
    st.subheader("All conferences")
    st.dataframe(pd.DataFrame(summaries), use_container_width=True, hide_index=True)
    st.divider()
    conf_names = sorted({conference_for_sport(s, conf_sport) for s in g["world"]["schools"].values() if conf_sport != "football" or s.get("subdivision") in ("FBS", "FCS")})
    conf = st.selectbox("View conference", conf_names, key="conf_view")
    st.subheader(conf)
    standings = conference_standings(g["world"], season, conf_sport, conf)
    rows=[]
    for place, sid, stt, ss in standings:
        rows.append({"#":place,"School":ss["name"],"Conf":f"{stt['conf_w']}-{stt['conf_l']}","Conf %":f"{stt['conf_pct']*100:.1f}%","Overall":f"{stt['w']}-{stt['l']}","SOS":f"{stt['sos']*100:.1f}","Streak":stt["streak"],"Power":f"{stt['power']:.1f}"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.info("Conference records are calculated from completed conference games in the selected season. Teams with no games played remain visible with 0-0 records.")

with tabs[7]:
    st.header("📊 National Rankings")
    st.caption("Rankings are generated from the current simulated season using winning percentage, strength of schedule, conference performance, recent form and program strength. They are simulation rankings, not official NCAA rankings.")
    season = season_key(g["date"])
    ranking_sport = st.selectbox("Sport", ["football","men_basketball","women_basketball"], format_func=lambda x: SPORT_LABELS[x], key="ranking_sport")
    rank_limit = st.select_slider("Show", options=[10,25,50], value=25, key="rank_limit")
    ranking_rows = []
    for rank, sid, stt in national_rankings(g["world"], season, ranking_sport, rank_limit):
        ss = g["world"]["schools"][sid]
        ranking_rows.append({"Rank":rank,"School":ss["name"],"Conference":conference_for_sport(ss, ranking_sport),"Record":f"{stt['w']}-{stt['l']}","Conf":f"{stt['conf_w']}-{stt['conf_l']}","SOS":round(stt["sos"]*100,1),"Power":round(stt["power"],1),"Streak":stt["streak"]})
    st.dataframe(pd.DataFrame(ranking_rows), use_container_width=True, hide_index=True)
    st.subheader("How the ranking works")
    st.write("Power = 52% winning percentage + 18% strength of schedule + 10% conference winning percentage + 8% recent form + 12% program strength. The formula is intentionally transparent so the ranking can evolve into a more advanced NET/RPI-style model later.")

with tabs[8]:
    st.header("🏛️ Championships & Historical Records")
    st.caption("Real-world NCAA championship history is kept separate from your simulated career. Simulated Final Fours, conference titles and national championships are added as your world evolves.")
    ensure_history_schema(g["world"])
    current_sid=g["current_school"]
    legacy=legacy_for_school(g["world"], current_sid)
    a,b,c,d,e=st.columns(5)
    a.metric("National titles", legacy["national_titles"])
    b.metric("Final Fours", legacy["final_fours"])
    c.metric("Elite Eights", legacy["elite_eights"])
    d.metric("Sweet 16s", legacy["sweet_sixteens"])
    e.metric("All-sports titles", legacy["all_sports_titles"])

    sport_filter=st.selectbox("Sport", ["All","football","men_basketball","women_basketball"], format_func=lambda x: x.replace("_"," ").title())
    source_filter=st.selectbox("Record source", ["All","Official historical","Simulator career"])
    school_filter=st.text_input("Search school", value="", placeholder="e.g. Kentucky, Michigan, UConn")
    rows=[]
    for x in g["world"].get("historical_championships",[]):
        sport=x.get("sport","")
        if sport_filter!="All" and sport!=sport_filter: continue
        src="Simulator career" if x.get("simulated") else "Official historical"
        if source_filter!="All" and src!=source_filter: continue
        if school_filter and school_filter.lower() not in str(x.get("champion","")).lower(): continue
        runner=x.get("runner_up")
        runner_name=g["world"]["schools"].get(runner,{}).get("name",runner or "")
        rows.append({"Year":x.get("year"),"Sport":sport.replace("_"," ").title(),"Champion":x.get("champion"),"Runner-up":runner_name,"Source":src,"Championship":x.get("championship", "National Championship")})
    rows.sort(key=lambda r:r["Year"], reverse=True)
    st.subheader("NCAA championship sports")
    st.caption(f"The all-sports résumé is designed to track every NCAA championship sport. The current historical baseline includes football and basketball; additional sport-by-sport historical winners can be loaded into the same database without changing the career system.")
    st.write(", ".join(x.replace("_", " ").title() for x in NCAA_DI_CHAMPIONSHIP_SPORTS))

    st.subheader("National championship history")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    run_rows=[]
    for x in g["world"].get("historical_tournament_runs",[]):
        sport=x.get("sport","")
        if sport_filter!="All" and sport!=sport_filter: continue
        if school_filter and school_filter.lower() not in str(x.get("school","")).lower(): continue
        run_rows.append({"Year":x.get("year"),"Sport":sport.replace("_"," ").title(),"School":x.get("school"),"Round":x.get("round"),"Tournament":x.get("tournament","NCAA Tournament"),"Source":"Simulator" if x.get("simulated") else "Official historical"})
    run_rows.sort(key=lambda r:(r["Year"],r["Sport"],r["School"]), reverse=True)
    st.subheader("Final Four / tournament history")
    st.dataframe(pd.DataFrame(run_rows), use_container_width=True, hide_index=True)

    st.subheader("Your school's championship résumé")
    school_champs=[x for x in g["world"].get("historical_championships",[]) if x.get("school_id")==current_sid]
    if school_champs:
        st.dataframe(pd.DataFrame([{
            "Year":x.get("year"),"Sport":x.get("sport","").replace("_"," ").title(),"Champion":x.get("champion"),"Source":"Simulator" if x.get("simulated") else "Historical"
        } for x in sorted(school_champs,key=lambda z:z.get("year",0),reverse=True)]),use_container_width=True,hide_index=True)
    else:
        st.info("No championship history is linked to this school yet. Historical data remains available in the full table above.")

with tabs[9]:
    st.header("AD Job Market")
    st.caption("The AD market is now a living system. Schools can fire or lose ADs during the season, other ADs compete for openings, and your five end-of-season offers are drawn from the changing market.")

    openings=[x for x in g["world"].get("job_openings",[]) if x.get("status")=="Open"]
    if openings:
        st.subheader(f"Openings around the country ({len(openings)})")
        open_rows=[]
        for opening in openings:
            oschool=g["world"]["schools"].get(opening["school_id"],{})
            age=(date.fromisoformat(g["date"])-date.fromisoformat(opening["opened_date"])).days
            open_rows.append({"School":oschool.get("name"),"Conference":oschool.get("conference"),"Prestige":oschool.get("prestige"),"Reason":opening.get("reason"),"Opened":opening.get("opened_date"),"Days Open":max(0,age)})
        st.dataframe(pd.DataFrame(open_rows).sort_values(["Prestige","Days Open"],ascending=[False,True]),use_container_width=True,hide_index=True)
    else:
        st.info("There are no publicly open AD positions right now. The market will change as the season progresses.")

    jobs=get_job_market(g)
    if not jobs:
        st.info("Your next set of offers will be generated at the end of the season.")
    else:
        st.subheader(f"Your {len(jobs)} current offers")
        for i,j in enumerate(jobs, 1):
            s=g["world"]["schools"][j["school_id"]]
            cols=st.columns([0.4,3,1,1,1])
            cols[0].metric("#", i)
            cols[1].markdown(f"### {s['name']}\nPrestige: **{s['prestige']}** • Conference: **{s['conference']}**")
            cols[2].write(f"Required rep\n**{j['required']}**")
            cols[3].write(f"Budget\n**{money(s['budget'])}**")
            if cols[4].button("Accept offer",key="job_"+j["school_id"]):
                take_job(g,j["school_id"]); st.rerun()
        st.divider()
        st.write("Accepting an offer moves you immediately to that athletic department. Other ADs may have competed for the same opening, so market timing matters. Your reputation, résumé, championships and world history remain intact.")

with tabs[10]:
    st.header("People")
    st.subheader("Your Athletic Department")
    for sport,cid in school["coaches"].items():
        c=g["world"]["coaches"].get(cid)
        if c: st.write(f"**{sport.replace('_',' ').title()} — {c['name']}** | OVR {c['overall']} | {c['trait']} | {c['personality']} | Satisfaction {c.get('satisfaction',72)}/100")
        else: st.write(f"**{sport.replace('_',' ').title()} — VACANT**")
    st.write(f"**University President:** {school['president']}")
    st.divider()
    st.subheader("Other ADs")
    rows=[]
    for sid,s in list(g["world"]["schools"].items())[:40]:
        if sid==g["current_school"]: continue
        ad=g["world"]["ad_people"][s["ad_id"]]
        rows.append({"School":s["name"],"AD":ad["name"],"Rep":ad["reputation"],"Prestige":s["prestige"]})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

with tabs[11]:
    st.header("Living College Athletics World")
    st.write(f"**{len(g['world']['schools'])} schools** are loaded into this save. Results persist rather than being regenerated when you open a page.")
    c1,c2=st.columns(2)
    c1.metric("Regular-season games",len(g["world"]["results"]))
    c2.metric("Postseason games",len(g["world"].get("postseason_results",[])))
    recent=g["world"]["results"][-20:][::-1]
    rows=[]
    for r in recent:
        rows.append({"Date":r["date"],"Sport":r["sport"].replace("_"," ").title(),
                     "Winner":g["world"]["schools"][r["winner"]]["name"],
                     "Loser":g["world"]["schools"][r["loser"]]["name"]})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

with tabs[12]:
    st.header("Your AD Career")
    st.write(f"**{g['player']['name']} — Director of Athletics**")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Reputation",g["career"]["reputation"])
    c2.metric("Seasons",g["career"]["seasons"])
    c3.metric("Career Wins",g["career"]["career_wins"])
    c4.metric("Job Moves",g["career"]["job_offers"])
    st.subheader("Career history")
    if g["history"]: st.dataframe(pd.DataFrame(g["history"]),use_container_width=True,hide_index=True)
    else: st.info("Your résumé will begin filling in at the first season review on July 31.")
    st.subheader("Career philosophy")
    st.write("Start small → manage coaches → allocate NIL → build facilities → win → reach postseason → build your résumé → earn bigger jobs.")
