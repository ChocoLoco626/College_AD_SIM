from collections import defaultdict
from datetime import date
from scheduling import conference_for_sport

SPORT_LABELS = {
    'football': 'Football',
    'men_basketball': "Men's Basketball",
    'women_basketball': "Women's Basketball",
}


def season_bounds(season):
    start = int(str(season)[:4])
    return date(start, 8, 1), date(start + 1, 7, 31)


def _season_results(world, season, sport):
    lo, hi = season_bounds(season)
    out = []
    for r in world.get('results', []):
        if r.get('sport') != sport:
            continue
        try:
            d = date.fromisoformat(r.get('date', '1900-01-01'))
        except Exception:
            continue
        if lo <= d <= hi:
            out.append(r)
    return sorted(out, key=lambda x: x.get('date', ''))


def build_team_stats(world, season, sport):
    schools = world.get('schools', {})
    stats = {sid: {
        'w': 0, 'l': 0, 'conf_w': 0, 'conf_l': 0,
        'points_for': 0, 'points_against': 0, 'games': 0,
        'opponents': [], 'recent': [], 'streak': '-'
    } for sid in schools}

    results = _season_results(world, season, sport)
    for r in results:
        a, b = r.get('home'), r.get('away')
        winner, loser = r.get('winner'), r.get('loser')
        if winner not in stats or loser not in stats:
            continue
        conf_game = bool(r.get('conference_game'))
        stats[winner]['w'] += 1
        stats[loser]['l'] += 1
        stats[winner]['games'] += 1
        stats[loser]['games'] += 1
        stats[winner]['opponents'].append(loser)
        stats[loser]['opponents'].append(winner)
        stats[winner]['recent'].append(1)
        stats[loser]['recent'].append(0)
        if conf_game:
            stats[winner]['conf_w'] += 1
            stats[loser]['conf_l'] += 1

    # Recent form and opponent win percentage (SOS) are calculated from this season's results.
    for sid, st in stats.items():
        gp = st['games']
        st['pct'] = st['w'] / gp if gp else 0.0
        st['conf_pct'] = st['conf_w'] / (st['conf_w'] + st['conf_l']) if (st['conf_w'] + st['conf_l']) else 0.0
        st['recent_form'] = sum(st['recent'][-10:]) / max(1, len(st['recent'][-10:]))
        if st['recent']:
            last = st['recent'][-1]
            n = 0
            for x in reversed(st['recent']):
                if x != last:
                    break
                n += 1
            st['streak'] = ('W' if last else 'L') + str(n)

    for sid, st in stats.items():
        opp_pcts = []
        for oid in st['opponents']:
            o = stats.get(oid)
            if o and o['games']:
                opp_pcts.append(o['pct'])
        st['sos'] = sum(opp_pcts) / len(opp_pcts) if opp_pcts else 0.0
        school = schools.get(sid, {})
        prestige = float(school.get('prestige', 50))
        st['prestige_score'] = max(0.0, min(1.0, prestige / 100.0))
        # A transparent simulation rating: results matter most, with SOS, conference record,
        # recent form and program strength helping separate teams with similar records.
        st['power'] = (
            st['pct'] * 52
            + st['sos'] * 18
            + st['conf_pct'] * 10
            + st['recent_form'] * 8
            + st['prestige_score'] * 12
        )
        st['resume'] = st['pct'] * 60 + st['sos'] * 25 + st['conf_pct'] * 10 + st['prestige_score'] * 5
    return stats


def national_rankings(world, season, sport, limit=25):
    stats = build_team_stats(world, season, sport)
    eligible = []
    for sid, st in stats.items():
        s = world['schools'].get(sid, {})
        if sport == 'football' and s.get('subdivision') not in ('FBS', 'FCS'):
            continue
        if sport in ('men_basketball', 'women_basketball') and sport not in s.get('records', {}):
            continue
        eligible.append((sid, st))
    eligible.sort(key=lambda item: (item[1]['power'], item[1]['resume'], item[1]['pct'], world['schools'][item[0]].get('prestige', 0)), reverse=True)
    return [(i + 1, sid, st) for i, (sid, st) in enumerate(eligible[:limit])]


def conference_standings(world, season, sport, conference):
    stats = build_team_stats(world, season, sport)
    members = world.get('conferences', {}).get(conference, {}).get('members', [])
    rows = []
    for sid in members:
        if sid not in stats:
            continue
        st = stats[sid]
        school = world['schools'][sid]
        rows.append((sid, st, school))
    rows.sort(key=lambda x: (x[1]['conf_pct'], x[1]['conf_w'], x[1]['pct'], x[1]['sos'], x[2].get('prestige', 0)), reverse=True)
    return [(i + 1, sid, st, school) for i, (sid, st, school) in enumerate(rows)]


def all_conference_summaries(world, season, sport):
    summaries = []
    for name in sorted(world.get('conferences', {})):
        rows = conference_standings(world, season, sport, name)
        if not rows:
            continue
        leader = rows[0]
        summaries.append({
            'Conference': name,
            'Teams': len(rows),
            'Leader': leader[3]['name'],
            'Leader Conf': f"{leader[2]['conf_w']}-{leader[2]['conf_l']}",
            'Leader Overall': f"{leader[2]['w']}-{leader[2]['l']}",
            'Power Avg': round(sum(r[2]['power'] for r in rows) / len(rows), 1),
        })
    return summaries
