
import json
from pathlib import Path
import pandas as pd
import streamlit as st

from database import init_db, create_user, authenticate_user, list_saves, save_game, load_game
from game_state import create_game
from simulation import advance_days, season_phase, current_calendar_events
from career import get_job_market, take_job
from management import (
    ensure_management_schema, available_nil, set_nil_allocation,
    available_boosters, invest_facility, coach_candidates,
    fire_head_coach, hire_head_coach, NIL_SPORTS
)
from postseason import school_postseason_history, latest_champions

st.set_page_config(page_title="College AD Simulator V6", page_icon="🏟️", layout="wide")
init_db()

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "game" not in st.session_state:
    st.session_state.game = None

def money(x): return "${:,.0f}".format(x)

def migrate_game(g):
    ensure_management_schema(g)
    g.setdefault("version", 6)
    g.setdefault("news", [])
    g["world"].setdefault("postseason_results", [])
    g["world"].setdefault("postseason_done", [])
    g["world"].setdefault("championships", [])
    g["world"].setdefault("school_postseason", {})
    for sid in g["world"]["schools"]:
        g["world"]["school_postseason"].setdefault(sid, [])
    return g

st.title("🏟️ College Athletic Director Simulator — V6")
st.caption("Career Mode • Persistent World • Coaches • NIL • Facilities • Postseason")

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
st.sidebar.metric("Career Reputation", g["career"]["reputation"])
st.sidebar.progress(g["career"]["job_security"]/100, text=f"Job security: {g['career']['job_security']}%")

tabs = st.tabs([
    "🏠 Dashboard","📅 Calendar","🏈 Programs","💰 Money & NIL",
    "🏆 Postseason","💼 Job Market","👥 People","📰 World","📜 Career"
])

with tabs[0]:
    st.header(school_name)
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Reputation", g["career"]["reputation"])
    c2.metric("Board Approval", g["career"]["board_approval"])
    c3.metric("Cash", money(g["finances"]["cash"]))
    c4.metric("NIL Budget", money(g["finances"]["nil_budget"]))
    c5.metric("Booster Funds", money(g["finances"]["booster_funds"]))
    st.subheader("Program records")
    rows=[]
    for sport,r in school["records"].items():
        rows.append({"Sport":sport.replace("_"," ").title(),"W":r["w"],"L":r["l"]})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    champs=[x for x in g["world"].get("championships",[]) if x["school"]==g["current_school"]]
    if champs:
        st.subheader("Championships")
        st.dataframe(pd.DataFrame(champs), use_container_width=True, hide_index=True)
    st.subheader("Board goals")
    st.json(school["goals"])
    st.subheader("Recent news")
    for n in g["news"][:8]: st.write("•", n)
    st.divider()
    st.subheader("Advance time")
    a,b,c,d=st.columns(4)
    if a.button("Advance 1 day"): advance_days(g,1); st.rerun()
    if b.button("Advance 1 week"): advance_days(g,7); st.rerun()
    if c.button("Advance 1 month"): advance_days(g,30); st.rerun()
    if d.button("Advance 1 year"): advance_days(g,365); st.rerun()

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
            r=school["records"][sport]
            st.write(f"**Record:** {r['w']}-{r['l']}")
            if coach:
                st.write(f"**Head Coach:** {coach['name']}")
                st.write(f"**Overall:** {coach['overall']} • **Recruiting:** {coach['recruiting']} • **Development:** {coach['development']}")
                st.write(f"**Personality:** {coach['personality']} • **Strength:** {coach['trait']} • **Contract:** {coach.get('contract_years',1)} years")
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
                    cc[4].write(f"Salary\n**{money(cand['salary'])}**")
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
    st.write("Postseason games are simulated as the calendar advances. Results persist in the save and feed into your résumé, board review, program prestige, and championship history.")
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
    st.header("AD Job Market")
    jobs=get_job_market(g)
    if not jobs:
        st.info("No schools are currently willing to hire you. Build your résumé and check again.")
    for j in jobs:
        s=g["world"]["schools"][j["school_id"]]
        cols=st.columns([3,1,1,1])
        cols[0].markdown(f"### {s['name']}\nPrestige: **{s['prestige']}** • Conference: **{s['conference']}**")
        cols[1].write(f"Required rep\n**{j['required']}**")
        cols[2].write(f"Budget\n**{money(s['budget'])}**")
        if cols[3].button("Accept",key="job_"+j["school_id"]):
            take_job(g,j["school_id"]); g["career"]["job_offers"]+=1; st.rerun()

with tabs[6]:
    st.header("People")
    st.subheader("Your Athletic Department")
    for sport,cid in school["coaches"].items():
        c=g["world"]["coaches"].get(cid)
        if c: st.write(f"**{sport.replace('_',' ').title()} — {c['name']}** | OVR {c['overall']} | {c['trait']} | {c['personality']}")
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

with tabs[7]:
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

with tabs[8]:
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
