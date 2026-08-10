# NBA Playoff Roster Database

This project parses 2024-25 Basketball Reference roster pages with Beautiful Soup and pandas, then loads the 2025 playoff teams and their players into a normalized MySQL database.

The implemented scope is roster data only. It does not scrape schedules, games, box scores, or player playoff statistics.

## Data model

The loader creates two tables:

- `teams`: one row per team and season.
- `players`: roster details linked to `teams` by a foreign key.

Player rows include the Basketball Reference identifier, jersey number, name, position, height, weight, birth date, nationality, experience, and college. Unique constraints make repeated loads update existing roster rows instead of duplicating them.

## Requirements

- Python 3.10 or newer
- MySQL 8 or newer
- Network access to Basketball Reference for live requests

Install the Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Database configuration

Set credentials through environment variables. Do not commit them.

```bash
export NBA_DB_HOST=127.0.0.1
export NBA_DB_PORT=3306
export NBA_DB_USER=your_user
export NBA_DB_PASSWORD=your_password
export NBA_DB_NAME=nba_playoff_rosters
```

The configured MySQL user must be allowed to create the selected database and its tables.

## Run

Load every configured 2025 playoff roster:

```bash
python RosterScraper.py
```

Load selected teams:

```bash
python RosterScraper.py --teams BOS,NYK
```

The live scraper waits 5 seconds between requests by default. Basketball Reference can return HTTP 403 to automated clients. If that happens, save a roster page through a browser and parse that real page without changing the ETL path:

```bash
python RosterScraper.py --teams BOS --html-file /path/to/BOS-2025.html
```

Use `--no-load` to inspect the pandas rows without writing to MySQL.

## Example queries

Roster size by team:

```sql
SELECT t.abbr, COUNT(*) AS roster_size
FROM teams t
JOIN players p ON p.team_id = t.team_id
GROUP BY t.team_id, t.abbr
ORDER BY t.abbr;
```

Players by position:

```sql
SELECT t.abbr, p.position, COUNT(*) AS players
FROM teams t
JOIN players p ON p.team_id = t.team_id
GROUP BY t.abbr, p.position
ORDER BY t.abbr, p.position;
```

## Stack

- Python
- requests
- Beautiful Soup with lxml
- pandas
- mysql-connector-python
- MySQL

## Limitations

- The project covers rosters only.
- Live scraping depends on Basketball Reference allowing the request.
- The loader verifies table and row counts, not the historical accuracy of source data.
