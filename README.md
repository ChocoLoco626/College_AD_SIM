# College AD Simulator V5

V5 is a career-first Streamlit college athletics simulator.

## What changed from V4

- Career Mode is now the core loop.
- You start at a lower-prestige Division I school instead of choosing a powerhouse.
- Reputation, job security, board approval and career history are persistent.
- A job market lets you move to larger programs as you earn trust.
- Every school has a generated AD, president and coaching staff.
- Generated people have persistent names, ratings, personalities and career attributes.
- The world keeps producing persistent game results independently of the player.
- Results are stored in the save instead of being regenerated whenever a page opens.
- 2026–27 NCAA calendar dates are represented locally.
- Saves/accounts remain SQLite-based for a simple Streamlit prototype.

## Current data note

The `data/schools.json` file contains 343 normalized playable school entries carried forward from the V4 seed dataset. It is intentionally labeled a **seed dataset**, not a verified claim that every one of the NCAA's current 361 active Division I institutions is represented exactly.

The NCAA reports 361 active Division I institutions as of July 2026. Before calling this a fully verified NCAA database, the school/conference dataset should be reconciled against the NCAA membership directory.

## Official calendar anchors used for V5

- FCS football first contest: Aug. 27, 2026
- FBS football first contest: Sept. 3, 2026
- DI men's and women's basketball first contest: Nov. 2, 2026
- Baseball first contest: Feb. 19, 2027
- Men's lacrosse first contest: Feb. 6, 2027
- Women's beach volleyball first contest: Feb. 25, 2027
- Men's Final Four: Apr. 3 & 5, 2027
- Women's Final Four: Apr. 2 & 4, 2027
- Women's College World Series window: June 2027

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Next major systems

1. Verified 361-school canonical NCAA dataset and sport-specific conference membership.
2. Exact/generated schedules by sport.
3. Recruiting classes, prospects and transfer portal.
4. NIL/roster management.
5. Coach hiring/firing and buyouts.
6. Conference tournaments and NCAA postseason.
7. Conference realignment.
8. Contracts and AD interviews.
9. School presidents/boosters/media events.
10. External database support for durable Streamlit Cloud accounts.

## Streamlit Cloud note

SQLite is excellent for local/prototype use, but Streamlit Cloud's filesystem should not be treated as permanent multi-user storage. For a production deployment, connect the save/account layer to a hosted PostgreSQL/Supabase-style database.
