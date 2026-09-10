import random
from world import available_jobs

def career_reputation(game):
    # Blend results, stability, finances, facilities, and goals.
    s = game["world"]["schools"][game["current_school"]]
    rep = game["career"]["reputation"]
    for sport in ("football", "men_basketball", "women_basketball"):
        r = s["records"][sport]
        rep += (r["w"] - r["l"]) * 0.18
    rep += (s["facilities"] - 50) * 0.08
    rep += game["career"].get("career_wins", 0) * 0.03
    return max(20, min(99, round(rep)))

def evaluate_board(game):
    s = game["world"]["schools"][game["current_school"]]
    football = s["records"]["football"]
    basketball = s["records"]["men_basketball"]
    goals = s["goals"]
    score = 50
    score += (football["w"] - goals["football_wins"]) * 5
    score += (basketball["w"] - goals["basketball_wins"]) * 2
    score += (s["facilities"] - 50) * .4
    score += game["career"].get("fundraising", 0) / max(1, goals["fundraising"]) * 10
    return max(0, min(100, round(score)))

def apply_season_review(game):
    board = evaluate_board(game)
    game["career"]["board_approval"] = board
    if board < 30:
        game["career"]["job_security"] = max(0, game["career"]["job_security"] - 25)
    elif board < 50:
        game["career"]["job_security"] = max(0, game["career"]["job_security"] - 10)
    else:
        game["career"]["job_security"] = min(100, game["career"]["job_security"] + 8)
    game["career"]["reputation"] = career_reputation(game)
    game["career"]["seasons"] += 1
    game["history"].append({
        "season": game["date"][:4] + "-" + str(int(game["date"][:4])+1),
        "school": game["world"]["schools"][game["current_school"]]["name"],
        "board_approval": board,
        "reputation": game["career"]["reputation"]
    })
    return board

def get_job_market(game):
    rng = random.Random(game["rng_seed"] + game["career"]["seasons"] * 101)
    return available_jobs(game["world"], game["current_school"], game["career"]["reputation"], rng)

def take_job(game, school_id):
    old = game["current_school"]
    new = game["world"]["schools"][school_id]
    old_name = game["world"]["schools"][old]["name"]
    game["world"]["ad_people"][game["world"]["schools"][old]["ad_id"]]["name"] = game["player"]["name"]
    aid = game["world"]["schools"][school_id]["ad_id"]
    game["world"]["ad_people"][aid] = {
        "name": game["player"]["name"], "reputation": game["career"]["reputation"],
        "years": 0, "school_id": school_id
    }
    game["world"]["schools"][school_id]["ad_id"] = aid
    game["current_school"] = school_id
    game["career"]["job_security"] = 72
    game["career"]["last_move"] = f"{old_name} -> {new['name']}"
    game["news"].insert(0, f"You accepted the AD job at {new['name']}.")
    return True
