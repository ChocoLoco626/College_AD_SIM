import streamlit as st
import pandas as pd
from database import init_db, create_user, authenticate_user, list_saves, save_game, load_game
from game_state import create_game
from simulation import advance_days, season_phase, current_calendar_events
from career import get_job_market, take_job, career_reputation

st.set_page_config(page_title="College AD Simulator V5", page_icon="🏟️", layout="wide")
init_db()

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "game" not in st.session_state:
    st.session_state.game = None

def money(x): return "${:,.0f}".format(x)

st.title("🏟️ College Athletic Director Simulator — V5")
st.caption("Career Mode • Persistent World • Generated People • 2026–27 NCAA calendar")

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
        st.session_state.game = load_game(st.session_state.user_id, choice)
        st.rerun()

if st.session_state.game is None:
    st.header("Start your AD career")
    st.write("Career Mode begins at a lower-prestige Division I school. You build trust, win games, improve the department, and earn opportunities at bigger programs.")
    name = st.text_input("Your name", value="Alex Carter")
    if st.button("Begin Career", type="primary"):
        # Load school data locally.
        import json
        from pathlib import Path
        schools = json.loads(Path("data/schools.json").read_text())
        st.session_state.game = create_game(schools, name)
        st.rerun()
    st.stop()

g = st.session_state.game
school = g["world"]["schools"][g["current_school"]]
school_name = school["name"]

st.sidebar.markdown(f"### {school_name}")
st.sidebar.write(f"**Date:** {g['date']}")
st.sidebar.write(f"**Phase:** {season_phase(g)}")
st.sidebar.metric("Career Reputation", g["career"]["reputation"])
st.sidebar.progress(g["career"]["job_security"]/100, text=f"Job security: {g['career']['job_security']}%")

tabs = st.tabs(["🏠 Dashboard","📅 Calendar","🏈 Programs","💼 Job Market","👥 People","📰 World","📜 Career"])

with tabs[0]:
    st.header(f"{school_name}")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Reputation", g["career"]["reputation"])
    c2.metric("Board Approval", g["career"]["board_approval"])
    c3.metric("Cash", money(g["finances"]["cash"]))
    c4.metric("Facilities", school["facilities"])
    st.subheader("Program records")
    rows=[]
    for sport,r in school["records"].items():
        rows.append({"Sport":sport.replace("_"," ").title(),"W":r["w"],"L":r["l"]})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.subheader("Board goals")
    st.json(school["goals"])
    st.subheader("Recent news")
    for n in g["news"][:8]:
        st.write("•", n)

    st.divider()
    st.subheader("Advance time")
    a,b,c,d = st.columns(4)
    if a.button("Advance 1 day"): advance_days(g,1); st.rerun()
    if b.button("Advance 1 week"): advance_days(g,7); st.rerun()
    if c.button("Advance 1 month"): advance_days(g,30); st.rerun()
    if d.button("Advance 1 year"): advance_days(g,365); st.rerun()

with tabs[1]:
    st.header("2026–27 Calendar")
    rows=current_calendar_events(g)
    st.dataframe(pd.DataFrame(rows, columns=["Date","Event"]), use_container_width=True, hide_index=True)

with tabs[2]:
    st.header("Your athletic programs")
    for sport in school["records"]:
        cid=school["coaches"][sport]
        coach=g["world"]["coaches"][cid]
        with st.expander(sport.replace("_"," ").title()):
            r=school["records"][sport]
            st.write(f"**Record:** {r['w']}-{r['l']}")
            st.write(f"**Head Coach:** {coach['name']}")
            st.write(f"**Overall:** {coach['overall']}  •  **Recruiting:** {coach['recruiting']}  •  **Development:** {coach['development']}")
            st.write(f"**Personality:** {coach['personality']}  •  **Strength:** {coach['trait']}")

with tabs[3]:
    st.header("AD Job Market")
    st.write("Your reputation determines which schools will consider you. Moving jobs changes your career history and the world keeps moving at your former school.")
    jobs=get_job_market(g)
    if not jobs:
        st.info("No schools are currently willing to interview you. Build your résumé and check again after the season.")
    for j in jobs:
        s=g["world"]["schools"][j["school_id"]]
        cols=st.columns([3,1,1,1])
        cols[0].markdown(f"### {s['name']}\nPrestige: **{s['prestige']}**  •  Conference: **{s['conference']}**")
        cols[1].write(f"Required rep\n**{j['required']}**")
        cols[2].write(f"Budget\n**{money(s['budget'])}**")
        if cols[3].button("Accept", key="job_"+j["school_id"]):
            take_job(g,j["school_id"])
            g["career"]["job_offers"] += 1
            st.rerun()

with tabs[4]:
    st.header("People")
    st.subheader("Your Athletic Department")
    for sport,cid in school["coaches"].items():
        c=g["world"]["coaches"][cid]
        st.write(f"**{sport.replace('_',' ').title()} — {c['name']}** | OVR {c['overall']} | {c['trait']} | {c['personality']}")
    st.write(f"**University President:** {school['president']}")
    st.divider()
    st.subheader("Other ADs")
    rows=[]
    for sid,s in list(g["world"]["schools"].items())[:40]:
        if sid == g["current_school"]: continue
        ad=g["world"]["ad_people"][s["ad_id"]]
        rows.append({"School":s["name"],"AD":ad["name"],"Rep":ad["reputation"],"Prestige":s["prestige"]})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with tabs[5]:
    st.header("Living College Athletics World")
    st.write(f"**{len(g['world']['schools'])} schools** are loaded into this save. Results are persisted instead of being regenerated when you open a page.")
    st.metric("Recorded games", len(g["world"]["results"]))
    st.subheader("Latest world results")
    recent=g["world"]["results"][-20:][::-1]
    rows=[]
    for r in recent:
        rows.append({
            "Date":r["date"],"Sport":r["sport"].replace("_"," ").title(),
            "Winner":g["world"]["schools"][r["winner"]]["name"],
            "Loser":g["world"]["schools"][r["loser"]]["name"]
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with tabs[6]:
    st.header("Your AD Career")
    st.write(f"**{g['player']['name']} — Director of Athletics**")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Reputation",g["career"]["reputation"])
    c2.metric("Seasons",g["career"]["seasons"])
    c3.metric("Career Wins",g["career"]["career_wins"])
    c4.metric("Job Moves",g["career"]["job_offers"])
    st.subheader("Career history")
    if g["history"]:
        st.dataframe(pd.DataFrame(g["history"]), use_container_width=True, hide_index=True)
    else:
        st.info("Your résumé will begin filling in at the first season review on July 31.")
    st.subheader("Career philosophy")
    st.write("Start small → earn trust → win → build facilities → develop coaches → improve reputation → pursue bigger jobs.")
