from datetime import date
import random
from world import new_world
from scheduling import ensure_schedule_schema, generate_season_schedules
from history import ensure_history_schema

def create_game(schools, player_name, seed=None):
    seed = seed if seed is not None else random.randint(1, 2_000_000_000)
    rng = random.Random(seed)
    world = new_world(schools, seed)
    ensure_schedule_schema(world)
    ensure_history_schema(world)
    generate_season_schedules(world, "2026-2027", seed)

    # Career mode starts with a lower-prestige school. The player earns access to larger jobs.
    choices = [sid for sid,s in world["schools"].items() if 25 <= s["prestige"] <= 48]
    if not choices:
        choices = list(world["schools"])
    sid = rng.choice(choices)
    s = world["schools"][sid]

    # Player replaces the randomly generated AD at the starting school.
    aid = s["ad_id"]
    world["ad_people"][aid]["name"] = player_name
    world["ad_people"][aid]["reputation"] = 30

    return {
        "version": 10,
        "mode": "career",
        "rng_seed": seed,
        "player": {"name": player_name, "title": "Director of Athletics"},
        "current_school": sid,
        "date": "2026-08-01",
        "career": {
            "reputation": 30, "job_security": 72, "board_approval": 65,
            "seasons": 0, "career_wins": 0, "career_losses": 0,
            "fundraising": 0, "job_offers": 0, "last_move": None
        },
        "finances": {"cash": int(s["budget"] * .12), "revenue": 0, "expenses": 0, "nil_budget": int(s["budget"]*.015)},
        "history": [],
        "news": [f"Welcome to your first AD job at {s['name']}. Your reputation starts at 30."],
        "world": world
    }
