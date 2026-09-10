FIRST_NAMES = """
James Michael Robert John David William Richard Thomas Christopher Daniel
Matthew Anthony Mark Donald Steven Paul Andrew Joshua Kenneth Kevin Brian
George Edward Ronald Timothy Jason Jeffrey Ryan Jacob Gary Nicholas Eric
Jonathan Stephen Larry Justin Scott Brandon Benjamin Samuel Gregory Alexander
Patrick Jack Dennis Jerry Tyler Aaron Jose Henry Adam Douglas Nathan Peter
Zachary Kyle Walter Ethan Jeremy Harold Keith Christian Roger Noah Gerald
Dylan Jordan Cameron Logan Austin Connor Evan Caleb Luke Owen Cole Mason
Liam Carter Wyatt Grayson Jackson Aiden Jayden Hunter Gavin Blake Chase
Derek Marcus Malik Isaiah Xavier Jalen Jamal Devin Darius Trey Terrence
Jordan Andre Anthony Isaiah Micah Elijah Josiah Jeremiah Carson Cooper
Grant Wesley Parker Bennett Brody Colton Dalton Spencer Bryce Austin
Emily Sarah Jessica Ashley Amanda Jennifer Elizabeth Megan Rachel Lauren
Hannah Samantha Olivia Emma Madison Abigail Chloe Grace Lily Natalie
Brianna Kayla Taylor Morgan Alexis Sydney Brooke Hailey Kelsey Lauren
Alyssa Victoria Zoe Riley Avery Peyton Kennedy Reagan Mackenzie
""".split()

LAST_NAMES = """
Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez
Hernandez Lopez Gonzalez Wilson Anderson Thomas Taylor Moore Jackson Martin
Lee Perez Thompson White Harris Sanchez Clark Ramirez Lewis Robinson Walker
Young Allen King Wright Scott Torres Nguyen Hill Flores Green Adams Nelson
Baker Hall Rivera Campbell Mitchell Carter Roberts Gomez Phillips Evans Turner
Diaz Parker Cruz Edwards Collins Reyes Stewart Morris Morales Murphy Cook
Rogers Gutierrez Ortiz Morgan Cooper Peterson Bailey Reed Kelly Howard Ramos
Kim Cox Ward Richardson Watson Brooks Chavez Wood James Bennett Gray Mendoza
Ruiz Hughes Price Alvarez Castillo Sanders Patel Myers Long Ross Foster
Jimenez Powell Jenkins Perry Russell Sullivan Bell Coleman Butler Henderson
Barnes Fisher Vasquez Simmons Romero Jordan Patterson Alexander Hamilton Graham
Reynolds Griffin Wallace Woods West Cole Hayes Bryant Herrera Gibson Ellis
Tran Medina Aguilar Stevens Murray Ford Castro Marshall Owens Harrison
Fernandez McDonald Woods Washington Kennedy Wells
""".split()

COACH_TRAITS = [
    "player development", "recruiting", "analytics", "defense", "offense",
    "culture", "transfer evaluation", "fundraising"
]

def person_name(rng):
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"

def coach_profile(rng, prestige):
    base = max(35, min(94, prestige + rng.randint(-18, 18)))
    return {
        "name": person_name(rng),
        "overall": base,
        "recruiting": max(30, min(99, base + rng.randint(-10, 12))),
        "development": max(30, min(99, base + rng.randint(-10, 12))),
        "offense": rng.randint(40, 95),
        "defense": rng.randint(40, 95),
        "personality": rng.choice(["steady", "ambitious", "fiery", "players-first", "analytical"]),
        "trait": rng.choice(COACH_TRAITS),
        "years": rng.randint(1, 20),
        "contract_years": rng.randint(1, 5),
    }
