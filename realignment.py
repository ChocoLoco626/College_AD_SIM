"""2026-27 Division I membership/realignment layer.

The NCAA reports 361 active Division I institutions and 44 Division I conferences for 2026-27.
This module adds the schools missing from the original seed and gives football its own
conference field where football membership differs from the primary multi-sport conference.
"""

CONFERENCE_CATALOG = [
    "America East", "American", "Atlantic 10", "ACC", "Atlantic Sun", "Big 12", "Big East",
    "Big Sky", "Big South", "Big Ten", "Big West", "CAA", "CUSA", "Horizon League", "Ivy League",
    "MAAC", "MAC", "MEAC", "Missouri Valley", "Mountain West", "Northeast", "Ohio Valley",
    "Pac-12", "Patriot League", "SEC", "SoCon", "Southland", "Summit League", "SWAC",
    "Sun Belt", "United Athletic", "WAC", "West Coast", "ASUN", "Coastal Athletic Association",
    "Southern Conference", "Metro Atlantic Athletic Conference", "Missouri Valley Conference",
    "Big South Conference", "Big Sky Conference", "Patriot League", "Independent", "Other D-I", "Other"
]

# Schools missing from the original 343-school seed. These are active/current Division I
# programs needed for the 2026-27 361-school baseline; reclassifying schools are not included.
ADDITIONS = [
    ("California Baptist", "Big West", "DI"),
    ("Charleston Southern", "Big South", "FCS"),
    ("Gardner-Webb", "Big South", "FCS"),
    ("Southern Utah", "Big Sky", "FCS"),
    ("Tarleton State", "United Athletic", "FCS"),
    ("Texas A&M-Corpus Christi", "Southland", "DI"),
    ("UT Arlington", "United Athletic", "DI"),
    ("Utah Valley", "Big West", "DI"),
    ("Seattle", "West Coast", "DI"),
    ("South Carolina Upstate", "Big South", "DI"),
    ("Louisiana Tech", "CUSA", "FBS"),
    ("UTEP", "Mountain West", "FBS"),
    ("Stonehill", "Northeast", "FCS"),
    ("UMass Lowell", "America East", "DI"),
    ("Siena", "MAAC", "DI"),
    ("Western Carolina", "SoCon", "FCS"),
    ("Utah Tech", "Big Sky", "FCS"),
    ("Southeast Missouri", "Ohio Valley", "FCS"),
]

# 2026 football realignment corrections for schools in the seed.
FOOTBALL_CONFERENCE = {
    "Alabama":"SEC","Arkansas":"SEC","Auburn":"SEC","Florida":"SEC","Georgia":"SEC","Kentucky":"SEC",
    "LSU":"SEC","Mississippi State":"SEC","Missouri":"SEC","Ole Miss":"SEC","South Carolina":"SEC",
    "Tennessee":"SEC","Texas":"SEC","Texas A&M":"SEC","Vanderbilt":"SEC",
    "Illinois":"Big Ten","Indiana":"Big Ten","Iowa":"Big Ten","Maryland":"Big Ten","Michigan":"Big Ten",
    "Michigan State":"Big Ten","Minnesota":"Big Ten","Nebraska":"Big Ten","Northwestern":"Big Ten",
    "Ohio State":"Big Ten","Oregon":"Big Ten","Penn State":"Big Ten","Purdue":"Big Ten","Rutgers":"Big Ten",
    "UCLA":"Big Ten","USC":"Big Ten","Washington":"Big Ten","Wisconsin":"Big Ten",
    "Arizona":"Big 12","Arizona State":"Big 12","BYU":"Big 12","Baylor":"Big 12","Cincinnati":"Big 12",
    "Colorado":"Big 12","Houston":"Big 12","Iowa State":"Big 12","Kansas":"Big 12","Kansas State":"Big 12",
    "Oklahoma State":"Big 12","TCU":"Big 12","Texas Tech":"Big 12","UCF":"Big 12","Utah":"Big 12","West Virginia":"Big 12",
    "Boston College":"ACC","California":"ACC","Clemson":"ACC","Duke":"ACC","Florida State":"ACC","Georgia Tech":"ACC",
    "Louisville":"ACC","Miami":"ACC","NC State":"ACC","North Carolina":"ACC","Pittsburgh":"ACC","SMU":"ACC",
    "Stanford":"ACC","Syracuse":"ACC","Virginia":"ACC","Virginia Tech":"ACC","Wake Forest":"ACC",
    "Charlotte":"American","East Carolina":"American","FAU":"American","Florida Atlantic":"American","Memphis":"American",
    "Navy":"American","North Texas":"American","Rice":"American","South Florida":"American","Temple":"American",
    "Tulane":"American","Tulsa":"American","UAB":"American","UTSA":"American",
    "Jacksonville State":"CUSA","Kennesaw State":"CUSA","Liberty":"CUSA","Middle Tennessee":"CUSA",
    "New Mexico State":"CUSA","Sam Houston":"CUSA","Western Kentucky":"CUSA","FIU":"CUSA","Florida International":"CUSA",
    "Delaware":"CUSA","Missouri State":"CUSA","Louisiana Tech":"CUSA",
    "Air Force":"Mountain West","Boise State":"Mountain West","Colorado State":"Mountain West","Fresno State":"Mountain West",
    "Nevada":"Mountain West","New Mexico":"Mountain West","San Diego State":"Mountain West","San Jose State":"Mountain West",
    "UNLV":"Mountain West","Utah State":"Mountain West","Wyoming":"Mountain West","UTEP":"Mountain West",
    "Appalachian State":"Sun Belt","Coastal Carolina":"Sun Belt","Georgia Southern":"Sun Belt","Georgia State":"Sun Belt",
    "James Madison":"Sun Belt","Marshall":"Sun Belt","Old Dominion":"Sun Belt","South Alabama":"Sun Belt",
    "Southern Miss":"Sun Belt","Texas State":"Sun Belt","Troy":"Sun Belt","Arkansas State":"Sun Belt","Louisiana-Monroe":"Sun Belt",
    "Louisiana":"Sun Belt","South Alabama":"Sun Belt","Texas State":"Sun Belt",
    "Akron":"MAC","Ball State":"MAC","Bowling Green":"MAC","Buffalo":"MAC","Central Michigan":"MAC","Eastern Michigan":"MAC",
    "Kent State":"MAC","Miami Ohio":"MAC","Northern Illinois":"MAC","Ohio":"MAC","Toledo":"MAC","Western Michigan":"MAC",
    "Sacramento State":"MAC",
    "Army":"Independent","Notre Dame":"Independent","UConn":"Independent","UMass":"Independent","Navy":"American",
    "North Dakota State":"MVFC","South Dakota State":"MVFC","Montana State":"Big Sky","Montana":"Big Sky",
    "Weber State":"Big Sky","Eastern Washington":"Big Sky","Idaho State":"Big Sky","Sacramento State":"MAC",
    "Abilene Christian":"United Athletic","Austin Peay":"United Athletic","Central Arkansas":"United Athletic",
    "Eastern Kentucky":"United Athletic","North Alabama":"United Athletic","Stephen F Austin":"United Athletic","Tarleton State":"United Athletic",
}

def apply_2026_27_realignment(schools):
    """Mutate a list of school dicts to add the missing 18 schools and sport-specific football alignment."""
    existing={s.get('name') for s in schools}
    for name, conf, subdivision in ADDITIONS:
        if name in existing:
            continue
        schools.append({
            "name": name, "conference": conf, "football_conference": FOOTBALL_CONFERENCE.get(name, conf),
            "subdivision": subdivision, "prestige": 45, "academics": 65, "facilities": 45,
            "fan_support": 45, "budget": 7000000, "id": "sch_"+name.lower().replace(' ','_').replace('&','and').replace('-','_'),
            "state":"", "city":""
        })
        existing.add(name)
    for s in schools:
        s.setdefault('football_conference', FOOTBALL_CONFERENCE.get(s.get('name'), s.get('conference','Independent')))
        if s.get('name') in FOOTBALL_CONFERENCE:
            s['football_conference']=FOOTBALL_CONFERENCE[s['name']]
    return schools
