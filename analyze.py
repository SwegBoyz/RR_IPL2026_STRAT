"""Reproduce the Round 1 pressure rankings from the six supplied CSV files."""

from pathlib import Path
import pandas as pd, numpy as np
import argparse
parser = argparse.ArgumentParser(description='Rank IPL and T20I players in pressure situations.')
parser.add_argument('--data-dir', type=Path, default=Path('data'))
parser.add_argument('--output-dir', type=Path, default=Path('results'))
args = parser.parse_args()
data_dir = args.data_dir
args.output_dir.mkdir(parents=True, exist_ok=True)

def read(innings_summary):
    return pd.read_csv(data_dir / (innings_summary + '.csv'), low_memory=False)
matches = read('matches').merge(read('competitions'), on='comp_id', validate='many_to_one')
deliveries = read('ball_by_ball')
matches = matches[matches.comp_name.str.startswith('IPL ') | matches.match_format.eq('T20I')].copy()
matches = matches[matches[['first_inn_revised_overs', 'second_inn_revised_overs', 'revised_target']].isna().all(axis=1) & ~matches.result.str.contains('D/L|DLS|abandon|no result', case=False, na=True)]
matches['family'] = np.where(matches.comp_name.str.startswith('IPL '), 'IPL', 'T20I')
deliveries = deliveries[deliveries.innings.isin([1, 2])].merge(matches, on='match_id', validate='many_to_one')
deliveries = deliveries.sort_values(['match_id', 'innings', 'overid', 'innings_ball_num'], kind='stable')
deliveries['legal'] = ~deliveries.extras_type.isin(['Overstep', 'other', 'wide'])
deliveries['teamruns'] = deliveries.runs + deliveries.extras1_runs + deliveries.extras_2_runs
grouped = deliveries.groupby(['match_id', 'innings'])
deliveries['before'] = grouped.legal.cumsum() - deliveries.legal.astype(int)
deliveries['wk'] = grouped.is_wicket.cumsum() - deliveries.is_wicket.astype(int)
deliveries['score'] = grouped.teamruns.cumsum() - deliveries.teamruns
innings_summary = grouped.agg(balls=('legal', 'sum'), w=('is_wicket', 'sum'), r=('teamruns', 'sum')).unstack()
valid = innings_summary.index[(innings_summary['balls', 1].eq(120) | innings_summary['w', 1].eq(10)) & (innings_summary['balls', 1] <= 120) & (innings_summary['balls', 2] <= 120) & ((innings_summary['balls', 2] == 120) | (innings_summary['w', 2] == 10) | (innings_summary['r', 2] > innings_summary['r', 1]))]
deliveries = deliveries[deliveries.match_id.isin(valid)].copy()
deliveries['left'] = 120 - deliveries.before
deliveries['need'] = 1 + deliveries.match_id.map(innings_summary['r', 1]) - deliveries.score
end = deliveries[deliveries.innings.eq(2)].groupby('match_id').tail(1)
tie = end.need.eq(end.teamruns)
bad = end.loc[((end.need <= end.teamruns) != end.batting_team_id.eq(end.win_team_id)) & ~tie, 'match_id']
bad = set(bad) | set(deliveries.loc[(deliveries.need <= 0) & deliveries.innings.eq(2) | (deliveries.left <= 0) | (deliveries.wk >= 10), 'match_id'])
deliveries = deliveries[~deliveries.match_id.isin(bad)].copy()
deliveries['rr'] = 6 * deliveries.need / deliveries.left
deliveries['collapse'] = (deliveries.before < 36) & (deliveries.wk >= 3) | (deliveries.before < 90) & (deliveries.wk >= 5)
deliveries['pressure'] = np.where(deliveries.innings.eq(1), deliveries.collapse | (deliveries.left <= 24), deliveries.rr.between(4, 15) & ((deliveries.left <= 30) | (deliveries.left <= 60) & (deliveries.rr >= 10) | deliveries.collapse))
deliveries['phase'] = pd.cut(deliveries.before, [-1, 35, 89, 119], labels=['powerplay', 'middle', 'death'])
deliveries['stock'] = pd.cut(deliveries.wk, [-1, 2, 5, 9], labels=['0–2', '3–5', '6–9'])
deliveries['year'] = deliveries.match_date.str[:4]
print('COVER', deliveries.groupby('family').agg(matches=('match_id', 'nunique'), rows=('legal', 'size'), pressure=('pressure', 'sum')), deliveries.match_date.min(), deliveries.match_date.max())
print(deliveries.groupby(['innings', 'pressure']).size())
context_columns = ['family', 'year', 'innings', 'phase', 'stock', 'pressure']

def rank_role(rank_role):
    is_batting = rank_role == 'bat'
    player_id_column = 'striker_id' if is_batting else 'bowler_id'
    player_name_column = 'striker_name' if is_batting else 'bowler_name'
    events = deliveries[deliveries.extras_type.ne('wide')].copy() if is_batting else deliveries.copy()
    events['V'] = events.runs - 6 * (events.dismissed_player_id.eq(events.striker_id) & events.is_wicket) if is_batting else 6 * events.dismissal_type.isin(['Caught', 'Bowled', 'LBW', 'Stump', 'Hit Wicket']) - (events.runs + events.extras1_runs.where(events.extras_type.isin(['wide', 'Overstep', 'other']), 0))

    def outside(keys):
        grouped = events.groupby(keys, observed=True).V
        ratings = events.groupby(keys + ['match_id'], observed=True).V
        return (grouped.transform('sum') - ratings.transform('sum'), grouped.transform('size') - ratings.transform('size'))
    broad_sum, broad_count = outside(['family', 'innings', 'phase'])
    peer_sum, peer_count = outside(context_columns)
    events['v'] = events.V - (peer_sum + 30 * broad_sum / broad_count) / (peer_count + 30)
    assert events.v.notna().all()
    match_values = events.groupby([player_id_column, 'match_id', 'pressure']).v.agg(['sum', 'size']).reset_index()
    pressure_matches = match_values[match_values.pressure].copy()
    ordinary = match_values[~match_values.pressure].groupby(player_id_column)[['sum', 'size']].sum()
    pressure_matches['mean'] = pressure_matches['sum'] / pressure_matches['size']
    ratings = pressure_matches.groupby(player_id_column).agg(total=('sum', 'sum'), N=('size', 'sum'), M=('match_id', 'size'))
    ratings['O'] = ordinary['size']
    ratings['base'] = ordinary['sum'] / (ordinary['size'] + 60)
    ratings = ratings[(ratings.N >= 90) & (ratings.M >= 12) & (ratings.O >= 120)].copy()
    ratings['P'] = ratings.total / (ratings.N + 60)
    ratings['lift'] = ratings.P - ratings.base
    pressure_matches = pressure_matches.join(ratings[['total', 'N', 'base']], on=player_id_column, how='inner')
    pressure_matches['deleted'] = (pressure_matches.total - pressure_matches['sum']) / (pressure_matches.N - pressure_matches['size'] + 60)
    deleted_mean = pressure_matches.groupby(player_id_column).deleted.transform('mean')
    ratings['se'] = np.sqrt(((pressure_matches.deleted - deleted_mean) ** 2).groupby(pressure_matches[player_id_column]).sum() * (ratings.M - 1) / ratings.M)
    ratings['score'] = 100 * (ratings.P + 0.3 * ratings.lift - ratings.se)
    ratings['positive'] = pressure_matches['mean'].gt(0).groupby(pressure_matches[player_id_column]).mean()
    ratings['alt'] = 100 * (ratings.P + 0.15 * ratings.lift - 0.5 * ratings.se)
    ratings['alt_rank'] = ratings.alt.rank(ascending=False)
    ratings['name'] = events.groupby(player_id_column)[player_name_column].agg(lambda z: z.mode().iloc[0])
    ratings = ratings.sort_values(['score', 'N'], ascending=False)
    ratings.to_csv(args.output_dir / (rank_role + '.csv'))
    print(rank_role, len(ratings), ratings.head(12)[['name', 'N', 'M', 'base', 'P', 'positive', 'score', 'alt_rank']].round(3).to_string(index=False))
rank_role('bat')
rank_role('bowl')
roster = read('competition_team_player_mapping')
xi = read('playing_eleven')
teams = read('teams')
for role_name, id_column, team in [('bat', 'striker_id', 'batting_team_id'), ('bowl', 'bowler_id', 'bowling_team_id')]:
    ids = set(pd.read_csv(args.output_dir / (role_name + '.csv')).iloc[:10, 0])
    selected_events = deliveries[deliveries[id_column].isin(ids)]

    def pairs(f, keys):
        return set(map(tuple, f[keys].to_numpy()))
    print(role_name, 'selected IDs all in roster and XI', ids <= set(roster.player_id), ids <= set(xi.player_id), 'team match', pairs(selected_events, ['comp_id', team]) <= pairs(teams, ['comp_id', 'team_id']))
print('full', len(read('ball_by_ball')), len(deliveries), len(bad))
