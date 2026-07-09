# NBA Playoff Database

Web-scraping ETL pipeline that turns NBA playoff roster, schedule, and box-score pages into a normalized MySQL database you can query for player, team, and game-level playoff stats.

The workflow is: scrape Basketball Reference pages, stage the data with pandas, load it into MySQL, then ask questions of the playoff data with SQL.

## Prerequisites

- Python 3.10+
- MySQL 8.x
- Python packages: `pandas`, `requests`, `beautifulsoup4`, `lxml`
- Network access to Basketball Reference

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pandas requests beautifulsoup4 lxml
```

## Run

`RosterScraper.py` defines `popDataFrame()`, which loops through the 2025 playoff teams and prints each scraped roster table before the staged data is loaded into MySQL.

```bash
python -c "from RosterScraper import popDataFrame; popDataFrame()"
```

The scraper waits 5 seconds between team requests to reduce load on Basketball Reference. After staging, import the cleaned DataFrames into the MySQL tables below and query the database directly.

## Sample Output

Current console output starts with the team abbreviation, followed by the parsed roster table HTML:

```text
BOS
<table class="sortable stats_table" id="roster">
  ...
</table>
NYK
<table class="sortable stats_table" id="roster">
  ...
</table>
```

MySQL schema for the normalized 4-table database:

| Table | Purpose | Key columns |
|---|---|---|
| `teams` | One row per playoff team | `team_id`, `abbr`, `name`, `conference`, `season` |
| `players` | Player roster records | `player_id`, `team_id`, `name`, `position`, `height` |
| `games` | Playoff schedule/game metadata | `game_id`, `season`, `game_date`, `round`, `home_team_id`, `away_team_id` |
| `box_scores` | Per-player game stats | `box_score_id`, `game_id`, `player_id`, `minutes`, `points`, `rebounds`, `assists` |

Example staged roster rows:

| player_id | team | position | height |
|---:|---|---|---|
| 1 | BOS | G | 6-4 |
| 2 | BOS | F | 6-6 |
| 3 | NYK | C | 7-0 |

## Querying the Data

Once the data is loaded into MySQL, the project becomes a playoff stats database. Example questions the schema supports:

Top playoff scorers:

```sql
SELECT
  p.name,
  t.abbr AS team,
  SUM(b.points) AS total_points
FROM box_scores b
JOIN players p ON p.player_id = b.player_id
JOIN teams t ON t.team_id = p.team_id
GROUP BY p.player_id, p.name, t.abbr
ORDER BY total_points DESC
LIMIT 10;
```

Returns the highest-scoring players across loaded playoff box scores.

Team roster size by position:

```sql
SELECT
  t.abbr AS team,
  p.position,
  COUNT(*) AS players
FROM players p
JOIN teams t ON t.team_id = p.team_id
GROUP BY t.abbr, p.position
ORDER BY t.abbr, p.position;
```

Returns each playoff team's roster count split by position.

Average team points per game:

```sql
SELECT
  t.abbr AS team,
  ROUND(AVG(team_points), 1) AS avg_points
FROM (
  SELECT
    g.game_id,
    p.team_id,
    SUM(b.points) AS team_points
  FROM box_scores b
  JOIN players p ON p.player_id = b.player_id
  JOIN games g ON g.game_id = b.game_id
  GROUP BY g.game_id, p.team_id
) game_totals
JOIN teams t ON t.team_id = game_totals.team_id
GROUP BY t.team_id, t.abbr
ORDER BY avg_points DESC;
```

Returns team scoring averages from the loaded playoff games.

## Architecture

```text
Basketball Reference pages
        |
        v
requests + BeautifulSoup scraper
        |
        v
pandas staging DataFrames
        |
        v
validated SQL import
        |
        v
normalized MySQL tables
        |
        v
SQL queries for player, team, and game stats
```

## Stack

- Python for scraping and ETL orchestration
- `requests` for HTTP fetching
- Beautiful Soup with `lxml` for HTML parsing
- `pandas` for staging tabular data
- MySQL for durable relational storage
