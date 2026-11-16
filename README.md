# Cricket under pressure

A cricket analytics project built for Round 1 of SupeRR Selector Season 2. It ranks IPL and T20 international batters and bowlers by how they perform in difficult match situations, compared with their ordinary performance and players facing similar conditions.

## Results

The supplied dataset contains 200,999 delivery records. After filtering, the analysis covers 773 matches and 184,930 deliveries, including 49,064 pressure deliveries. Shashank Singh leads the batting rankings and Sufiyan Muqeem leads the bowling rankings.

The complete eligible rankings are in [results/bat.csv](results/bat.csv) and [results/bowl.csv](results/bowl.csv). The [methodology report](reports/SupeRR-Round-1-Methodology.pdf) explains the top ten selections.

## Run locally

Use Python 3.12 and run these commands from the repository root.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/analyze.py --data-dir data --output-dir results
```

On Windows, activate the environment with `.venv\Scripts\activate`.

Put these original files in `data/` first:

- ball_by_ball.csv
- matches.csv
- competitions.csv
- teams.csv
- playing_eleven.csv
- competition_team_player_mapping.csv

The data comes from the competition pack and is excluded from this project download. The script uses only these local files. No API keys are needed.

## Method

Pressure is identified before each delivery. In the first innings, the last four overs and early wicket collapses qualify. In a chase, the required rate must be between 4 and 15, with limited time remaining, a demanding rate, or an early collapse. The report gives the exact thresholds.

Batting value rewards runs and charges six runs for a striker dismissal. Bowling value rewards credited wickets at six runs each and subtracts runs charged to the bowler. Deliveries are compared within competition type, year, innings, phase, wickets lost and pressure status. The current match is excluded from the benchmark.

A player needs 90 pressure events across 12 matches and 120 ordinary events. Both performance estimates are pulled toward average with a 60-event adjustment. Dropping each pressure match in turn measures how much the estimate depends on individual games.

```text
rating = 100 × (pressure value + 0.30 × improvement − uncertainty penalty)
```

The script also calculates an alternative rating with half the improvement weight and half the uncertainty penalty.

## Output columns

| Column | Meaning |
| --- | --- |
| striker_id / bowler_id | Original player ID |
| name | Player name |
| total | Sum of context-adjusted pressure values |
| N / M / O | Pressure events / pressure matches / ordinary events |
| base / P | Adjusted ordinary / pressure value per event |
| lift | P minus base |
| se | Match deletion uncertainty penalty |
| score | Final ranking score |
| positive | Fraction of pressure matches above the context benchmark |
| alt / alt_rank | Alternative score / rank |

## Checks and limitations

The pipeline checks innings completion and chase outcomes, and checks selected player IDs against rosters and playing XIs. Competition-team IDs are checked against the team file. Report rankings were checked against the exported tables.

Revised targets, shortened games, abandoned matches, super overs and two other domestic tournaments are excluded. The six-run wicket value and pressure cutoffs are assumptions. Individual opponents and pitch conditions are not modelled. A high rating describes this sample and carries uncertainty, especially near the eligibility threshold.


