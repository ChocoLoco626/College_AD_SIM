import re

# Historical NCAA championship results used as the baseline for the simulator's
# legacy/history screens. These are intentionally kept separate from simulated
# results so a new career never overwrites real-world history.


# NCAA Division I championship-sport catalog. This lets the simulator keep an all-sports
# athletics résumé even as additional historical championship datasets are imported.
NCAA_DI_CHAMPIONSHIP_SPORTS = [
    "baseball", "basketball_men", "basketball_women", "cross_country_men", "cross_country_women",
    "field_hockey", "football_fbs", "football_fcs", "golf_men", "golf_women",
    "gymnastics_men", "gymnastics_women", "ice_hockey_men", "ice_hockey_women",
    "lacrosse_men", "lacrosse_women", "rowing_women", "soccer_men", "soccer_women",
    "softball", "swimming_diving_men", "swimming_diving_women", "tennis_men", "tennis_women",
    "track_field_indoor_men", "track_field_indoor_women", "track_field_outdoor_men",
    "track_field_outdoor_women", "volleyball_women", "wrestling_men", "water_polo_men",
    "water_polo_women", "beach_volleyball"
]

MEN_BASKETBALL = {
2026:'Michigan',2025:'Florida',2024:'Connecticut',2023:'Connecticut',2022:'Kansas',2021:'Baylor',2019:'Virginia',2018:'Villanova',2017:'North Carolina',2016:'Villanova',2015:'Duke',2014:'Connecticut',2013:'Louisville (vacated)',2012:'Kentucky',2011:'Connecticut',2010:'Duke',2009:'North Carolina',2008:'Kansas',2007:'Florida',2006:'Florida',2005:'North Carolina',2004:'Connecticut',2003:'Syracuse',2002:'Maryland',2001:'Duke',2000:'Michigan State',1999:'Connecticut',1998:'Kentucky',1997:'Arizona',1996:'Kentucky',1995:'UCLA',1994:'Arkansas',1993:'North Carolina',1992:'Duke',1991:'Duke',1990:'UNLV',1989:'Michigan',1988:'Kansas',1987:'Indiana',1986:'Louisville',1985:'Villanova',1984:'Georgetown',1983:'North Carolina State',1982:'North Carolina',1981:'Indiana',1980:'Louisville',1979:'Michigan State',1978:'Kentucky',1977:'Marquette',1976:'Indiana',1975:'UCLA',1974:'North Carolina State',1973:'UCLA',1972:'UCLA',1971:'UCLA',1970:'UCLA',1969:'UCLA',1968:'UCLA',1967:'UCLA',1966:'UTEP',1965:'UCLA',1964:'UCLA',1963:'Loyola (Ill.)',1962:'Cincinnati',1961:'Cincinnati',1960:'Ohio State',1959:'California',1958:'Kentucky',1957:'North Carolina',1956:'San Francisco',1955:'San Francisco',1954:'La Salle',1953:'Indiana',1952:'Kansas',1951:'Kentucky',1950:'CCNY',1949:'Kentucky',1948:'Kentucky',1947:'Holy Cross',1946:'Oklahoma State',1945:'Oklahoma State',1944:'Utah',1943:'Wyoming',1942:'Stanford',1941:'Wisconsin',1940:'Indiana',1939:'Oregon'
}

WOMEN_BASKETBALL = {
2026:'UCLA',2025:'Connecticut',2024:'South Carolina',2023:'LSU',2022:'South Carolina',2021:'Stanford',2019:'Baylor',2018:'Notre Dame',2017:'South Carolina',2016:'Connecticut',2015:'Connecticut',2014:'Connecticut',2013:'Connecticut',2012:'Baylor',2011:'Texas A&M',2010:'Connecticut',2009:'Connecticut',2008:'Tennessee',2007:'Tennessee',2006:'Maryland',2005:'Baylor',2004:'Connecticut',2003:'Connecticut',2002:'Connecticut',2001:'Notre Dame',2000:'Connecticut',1999:'Purdue',1998:'Tennessee',1997:'Tennessee',1996:'Tennessee',1995:'Connecticut',1994:'North Carolina',1993:'Texas Tech',1992:'Stanford',1991:'Tennessee',1990:'Stanford',1989:'Tennessee',1988:'Louisiana Tech',1987:'Tennessee',1986:'Texas',1985:'Old Dominion',1984:'Southern California',1983:'Southern California',1982:'Louisiana Tech'
}

# Official NCAA football championship history is complicated before the CFP era
# because multiple selectors can recognize different champions. This baseline
# uses the NCAA's listed FBS history and labels it as historical/selector-based.
FOOTBALL = {
2025:'Indiana',2024:'Ohio State',2023:'Michigan',2022:'Georgia',2021:'Georgia',2020:'Alabama',2019:'LSU',2018:'Clemson',2017:'Alabama',2016:'Clemson',2015:'Alabama',2014:'Ohio State',2013:'Florida State',2012:'Alabama',2011:'Alabama',2010:'Auburn',2009:'Alabama',2008:'Florida',2007:'LSU',2006:'Florida',2005:'Texas',2004:'Southern California',2003:'LSU / Southern California',2002:'Ohio State',2001:'Miami (Fla.)',2000:'Oklahoma',1999:'Florida State',1998:'Tennessee',1997:'Michigan / Nebraska',1996:'Florida',1995:'Nebraska',1994:'Nebraska',1993:'Florida State',1992:'Alabama',1991:'Washington / Miami (Fla.)',1990:'Colorado / Georgia Tech',1989:'Miami (Fla.)',1988:'Notre Dame',1987:'Miami (Fla.)',1986:'Penn State',1985:'Oklahoma',1984:'Brigham Young',1983:'Miami (Fla.)',1982:'Penn State',1981:'Clemson',1980:'Georgia',1979:'Alabama',1978:'Alabama / Southern California',1977:'Notre Dame',1976:'Pittsburgh',1975:'Oklahoma',1974:'Southern California / Oklahoma',1973:'Notre Dame / Alabama',1972:'Southern California',1971:'Nebraska',1970:'Nebraska / Texas / Ohio State',1969:'Texas',1968:'Ohio State',1967:'Southern California',1966:'Notre Dame / Michigan State',1965:'Michigan State / Alabama',1964:'Alabama / Arkansas / Notre Dame',1963:'Texas',1962:'Southern California',1961:'Alabama / Ohio State',1960:'Minnesota / Mississippi',1959:'Syracuse',1958:'LSU / Iowa',1957:'Ohio State / Auburn',1956:'Oklahoma',1955:'Oklahoma',1954:'UCLA / Ohio State',1953:'Maryland',1952:'Michigan State',1951:'Tennessee',1950:'Oklahoma'
}

ALIASES = {
    'uconn':'Connecticut','connecticut':'Connecticut','usc':'Southern California',
    'southern cal':'Southern California','southern california':'Southern California',
    'miami':'Miami (Fla.)','miami (fla.)':'Miami (Fla.)','penn st.':'Penn State',
    'penn state':'Penn State','nc state':'North Carolina State','north carolina state':'North Carolina State',
    'oklahoma a&m':'Oklahoma State','oklahoma state':'Oklahoma State','loyola chicago':'Loyola (Ill.)',
    'loyola (ill.)':'Loyola (Ill.)','utep':'UTEP','lsu':'LSU','texas a&m':'Texas A&M',
}

def _norm(s):
    s = re.sub(r'\s+', ' ', str(s).strip().lower())
    return ALIASES.get(s, s)

def _school_lookup(world):
    return {_norm(s['name']): sid for sid,s in world.get('schools',{}).items()}

def _resolve(world, name):
    lookup=_school_lookup(world)
    # For shared/selectors records, keep the historical label rather than forcing
    # one school to inherit the other school's championship.
    if '/' in name:
        return None
    return lookup.get(_norm(name))

def ensure_history_schema(world):
    world.setdefault('historical_championships', [])
    world.setdefault('historical_tournament_runs', [])
    world.setdefault('legacy_awards', [])
    world.setdefault('conference_championships', [])
    world.setdefault('all_sports_championships', [])
    if not world.get('_historical_seeded'):
        for sport, data in [('men_basketball', MEN_BASKETBALL), ('women_basketball', WOMEN_BASKETBALL), ('football', FOOTBALL)]:
            for year, champion in data.items():
                world['historical_championships'].append({
                    'year': year, 'sport': sport, 'champion': champion,
                    'school_id': _resolve(world, champion), 'source': 'NCAA historical record',
                    'simulated': False
                })
        # 2026 Final Fours are included because the tournament round data is useful
        # to the legacy screen even before a career has simulated a season.
        for sport, year, teams in [
            ('men_basketball', 2026, ['Michigan','UConn','Duke','Florida']),
            ('women_basketball', 2026, ['UCLA','Texas','South Carolina','UConn'])
        ]:
            for team in teams:
                world['historical_tournament_runs'].append({
                    'year':year,'sport':sport,'round':'Final Four','school':team,
                    'school_id':_resolve(world,team),'source':'NCAA 2026 bracket','simulated':False
                })
        world['_historical_seeded']=True

def record_tournament_run(world, season, sport, round_name, sid, tournament='NCAA Tournament'):
    world.setdefault('historical_tournament_runs', []).append({
        'year': int(str(season)[:4]), 'season': season, 'sport': sport,
        'round': round_name, 'school': world['schools'][sid]['name'],
        'school_id': sid, 'tournament': tournament, 'simulated': True
    })

def record_championship(world, season, sport, sid, championship, runner_up=None):
    rec={'year':int(str(season)[:4]),'season':season,'sport':sport,
         'champion':world['schools'][sid]['name'],'school_id':sid,
         'championship':championship,'runner_up':runner_up,
         'source':'Simulator','simulated':True}
    world.setdefault('historical_championships', []).append(rec)
    return rec

def legacy_for_school(world, sid):
    ensure_history_schema(world)
    titles=[x for x in world['historical_championships'] if x.get('school_id')==sid]
    runs=[x for x in world['historical_tournament_runs'] if x.get('school_id')==sid]
    return {
        'national_titles':len(titles),
        'final_fours':sum(x.get('round')=='Final Four' for x in runs),
        'elite_eights':sum(x.get('round')=='Elite Eight' for x in runs),
        'sweet_sixteens':sum(x.get('round')=='Sweet 16' for x in runs),
        'championship_years':sorted({x['year'] for x in titles}, reverse=True),
        'all_sports_titles': len([x for x in world.get('all_sports_championships', []) if x.get('school_id') == sid]),
    }
