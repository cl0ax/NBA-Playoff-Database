# NBA Playoff Database

Web-scraping ETL pipeline for turning NBA playoff roster, schedule, and box-score pages into a normalized MySQL database.

The committed code currently contains the Basketball Reference roster scraper/staging step in `RosterScraper.py`. The database import stage is documented below as the target 4-table schema.

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

`RosterScraper.py` defines `popDataFrame()`, which loops through the 2025 playoff teams and prints each scraped roster table.

```bash
python -c "from RosterScraper import popDataFrame; popDataFrame()"
```

The scraper waits 5 seconds between team requests to reduce load on Basketball Reference.

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

Target MySQL schema for the normalized 4-table import:

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
```

## Stack

- Python for scraping and ETL orchestration
- `requests` for HTTP fetching
- Beautiful Soup with `lxml` for HTML parsing
- `pandas` for staging tabular data
- MySQL for durable relational storage
