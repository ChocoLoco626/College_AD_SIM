from datetime import date, timedelta
import random
from career import apply_season_review
from world import simulate_week
from postseason import process_postseason
from management import management_tick, ensure_management_schema

def parse_date(x): return date.fromisoformat(x)

def events_on(d):
    from calendar_data import CALENDAR
    return [desc for ds,desc in CALENDAR if ds == d.isoformat()]

def advance_days(game, days):
    ensure_management_schema(game)
    rng = random.Random(game["rng_seed"] + len(game["world"]["results"]) * 13 + days)
    for _ in range(days):
        d = parse_date(game["date"]) + timedelta(days=1)
        game["date"] = d.isoformat()

        # Daily finances.
        s = game["world"]["schools"][game["current_school"]]
        daily_rev = max(5_000, s["prestige"] * 900)
        daily_exp = max(4_000, s["prestige"] * 760)
        game["finances"]["revenue"] += daily_rev
        game["finances"]["expenses"] += daily_exp
        game["finances"]["cash"] += daily_rev - daily_exp

        # Persistent world games once per week.
        if d.weekday() == 5:
            simulate_week(game["world"], d, rng)

        management_tick(game)
        process_postseason(game)

        # Small world news.
        if d.weekday() == 0 and rng.random() < .25:
            game["news"].insert(0, rng.choice([
                "A coaching staff is drawing interest from another program.",
                "Boosters are pushing for a facilities upgrade.",
                "A rising recruit has become a hot commodity on the trail.",
                "A conference commissioner is monitoring membership rumors.",
                "An AD at another school is under pressure after a slow start."
            ]))
            game["news"] = game["news"][:30]

        # July 31 is the annual career checkpoint.
        if d.month == 7 and d.day == 31:
            apply_season_review(game)

    return game

def season_phase(game):
    d = parse_date(game["date"])
    if d.month in (8,9,10): return "Fall / Football"
    if d.month in (11,12,1): return "Basketball / Winter"
    if d.month in (2,3,4): return "Championship Spring"
    if d.month in (5,6,7): return "Offseason"
    return "Transition"

def current_calendar_events(game):
    d = parse_date(game["date"])
    from calendar_data import CALENDAR
    return [(ds,desc) for ds,desc in CALENDAR if abs((date.fromisoformat(ds)-d).days) <= 30]
