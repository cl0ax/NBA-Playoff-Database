import argparse
from datetime import date
import os
from pathlib import Path
import re
import time
from io import StringIO

from bs4 import BeautifulSoup
import pandas as pd
import requests


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

PLAYOFF_TEAMS_2025 = {
    "CLE": "Cleveland Cavaliers",
    "BOS": "Boston Celtics",
    "NYK": "New York Knicks",
    "IND": "Indiana Pacers",
    "MIL": "Milwaukee Bucks",
    "DET": "Detroit Pistons",
    "ORL": "Orlando Magic",
    "MIA": "Miami Heat",
    "OKC": "Oklahoma City Thunder",
    "HOU": "Houston Rockets",
    "LAL": "Los Angeles Lakers",
    "DEN": "Denver Nuggets",
    "LAC": "Los Angeles Clippers",
    "MIN": "Minnesota Timberwolves",
    "GSW": "Golden State Warriors",
    "MEM": "Memphis Grizzlies",
}

SEASON = 2025
BASE_URL = "https://www.basketball-reference.com/teams/{team}/{season}.html"
DATABASE_NAME = re.compile(r"^[A-Za-z0-9_]+$")


def _cell_text(row, data_stat):
    cell = row.find(["th", "td"], attrs={"data-stat": data_stat})
    return cell.get_text(" ", strip=True) if cell else ""


def parse_roster(html, team_abbr, team_name=None, season=SEASON):
    """Parse one Basketball Reference roster table into a pandas DataFrame."""
    team_abbr = team_abbr.upper()
    team_name = team_name or PLAYOFF_TEAMS_2025.get(team_abbr, team_abbr)
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="roster")
    if table is None:
        raise ValueError(f"No roster table found for {team_abbr}")

    rows = []
    for row in table.select("tbody tr"):
        player_cell = row.find("td", attrs={"data-stat": "player"})
        if player_cell is None:
            continue
        link = player_cell.find("a")
        href = link.get("href", "") if link else ""
        player_key = Path(href).stem if href else ""
        birth_text = _cell_text(row, "birth_date")
        parsed_birth = pd.to_datetime(birth_text, errors="coerce")
        birth_date = None if pd.isna(parsed_birth) else parsed_birth.date()
        weight_text = _cell_text(row, "weight")

        rows.append({
            "team_abbr": team_abbr,
            "team_name": team_name,
            "season": season,
            "basketball_reference_id": player_key,
            "jersey_number": _cell_text(row, "number"),
            "player_name": player_cell.get_text(" ", strip=True),
            "position": _cell_text(row, "pos"),
            "height": _cell_text(row, "height"),
            "weight": int(weight_text) if weight_text.isdigit() else None,
            "birth_date": birth_date,
            "nationality": _cell_text(row, "flag"),
            "experience": _cell_text(row, "years_experience"),
            "college": _cell_text(row, "college"),
        })

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError(f"Roster table for {team_abbr} contained no player rows")
    return frame


def fetch_roster(team_abbr, session=None, timeout=30):
    """Fetch and parse one live Basketball Reference team page."""
    team_abbr = team_abbr.upper()
    if team_abbr not in PLAYOFF_TEAMS_2025:
        raise ValueError(f"Unknown configured team: {team_abbr}")
    client = session or requests.Session()
    url = BASE_URL.format(team=team_abbr, season=SEASON)
    response = client.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return parse_roster(response.text, team_abbr, PLAYOFF_TEAMS_2025[team_abbr])


def scrape_rosters(team_abbrs, delay=5.0, timeout=30):
    """Fetch configured teams and combine their roster rows."""
    frames = []
    with requests.Session() as session:
        for index, team_abbr in enumerate(team_abbrs):
            frame = fetch_roster(team_abbr, session=session, timeout=timeout)
            frames.append(frame)
            print(f"Parsed {len(frame)} player rows for {team_abbr}.")
            if index < len(team_abbrs) - 1 and delay > 0:
                time.sleep(delay)
    return pd.concat(frames, ignore_index=True)


def _mysql_config(database=None):
    return {
        "host": os.getenv("NBA_DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("NBA_DB_PORT", "3306")),
        "user": os.environ["NBA_DB_USER"],
        "password": os.environ["NBA_DB_PASSWORD"],
        "database": database or os.getenv("NBA_DB_NAME", "nba_playoff_rosters"),
    }


def load_mysql(frame, database=None):
    """Create the normalized schema and upsert a roster DataFrame into MySQL."""
    import mysql.connector

    config = _mysql_config(database)
    database_name = config.pop("database")
    if not DATABASE_NAME.fullmatch(database_name):
        raise ValueError("Database name may contain only letters, numbers, and underscores")

    admin = mysql.connector.connect(**config)
    try:
        cursor = admin.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.close()
    finally:
        admin.close()

    connection = mysql.connector.connect(database=database_name, **config)
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id INT AUTO_INCREMENT PRIMARY KEY,
                abbr CHAR(3) NOT NULL,
                name VARCHAR(80) NOT NULL,
                season SMALLINT NOT NULL,
                UNIQUE KEY uq_team_season (abbr, season)
            ) ENGINE=InnoDB
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                player_id INT AUTO_INCREMENT PRIMARY KEY,
                team_id INT NOT NULL,
                basketball_reference_id VARCHAR(20) NOT NULL,
                jersey_number VARCHAR(5),
                name VARCHAR(100) NOT NULL,
                position VARCHAR(10),
                height VARCHAR(10),
                weight SMALLINT,
                birth_date DATE,
                nationality VARCHAR(20),
                experience VARCHAR(10),
                college VARCHAR(120),
                UNIQUE KEY uq_team_player (team_id, basketball_reference_id),
                CONSTRAINT fk_players_team FOREIGN KEY (team_id)
                    REFERENCES teams(team_id) ON DELETE CASCADE
            ) ENGINE=InnoDB
        """)

        team_ids = {}
        team_columns = frame[["team_abbr", "team_name", "season"]].drop_duplicates()
        for team in team_columns.itertuples(index=False):
            cursor.execute("""
                INSERT INTO teams (abbr, name, season)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE name = VALUES(name)
            """, (team.team_abbr, team.team_name, int(team.season)))
            cursor.execute(
                "SELECT team_id FROM teams WHERE abbr = %s AND season = %s",
                (team.team_abbr, int(team.season)),
            )
            team_ids[(team.team_abbr, int(team.season))] = cursor.fetchone()[0]

        player_rows = []
        for player in frame.itertuples(index=False):
            player_rows.append((
                team_ids[(player.team_abbr, int(player.season))],
                player.basketball_reference_id,
                player.jersey_number or None,
                player.player_name,
                player.position or None,
                player.height or None,
                player.weight,
                player.birth_date if isinstance(player.birth_date, date) else None,
                player.nationality or None,
                player.experience or None,
                player.college or None,
            ))

        cursor.executemany("""
            INSERT INTO players (
                team_id, basketball_reference_id, jersey_number, name, position,
                height, weight, birth_date, nationality, experience, college
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                jersey_number = VALUES(jersey_number),
                name = VALUES(name),
                position = VALUES(position),
                height = VALUES(height),
                weight = VALUES(weight),
                birth_date = VALUES(birth_date),
                nationality = VALUES(nationality),
                experience = VALUES(experience),
                college = VALUES(college)
        """, player_rows)
        connection.commit()

        cursor.execute("SELECT COUNT(*) FROM teams")
        team_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM players")
        player_count = cursor.fetchone()[0]
        cursor.close()
        return database_name, team_count, player_count
    finally:
        connection.close()


def popDataFrame():
    """Compatibility wrapper that returns all configured rosters as a DataFrame."""
    return scrape_rosters(list(PLAYOFF_TEAMS_2025))


def main():
    parser = argparse.ArgumentParser(
        description="Parse 2025 NBA playoff rosters and load a normalized MySQL database."
    )
    parser.add_argument(
        "--teams",
        default=",".join(PLAYOFF_TEAMS_2025),
        help="Comma-separated team abbreviations. Defaults to all configured playoff teams.",
    )
    parser.add_argument("--delay", type=float, default=5.0, help="Seconds between live requests.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    parser.add_argument("--html-file", type=Path, help="Parse one previously saved team page.")
    parser.add_argument("--database", help="Override NBA_DB_NAME.")
    parser.add_argument("--no-load", action="store_true", help="Parse without loading MySQL.")
    args = parser.parse_args()

    teams = [team.strip().upper() for team in args.teams.split(",") if team.strip()]
    if args.html_file:
        if len(teams) != 1:
            parser.error("--html-file requires exactly one team in --teams")
        html = args.html_file.read_text(encoding="utf-8")
        team = teams[0]
        frame = parse_roster(html, team, PLAYOFF_TEAMS_2025.get(team, team))
        print(f"Parsed {len(frame)} player rows for {team} from {args.html_file}.")
    else:
        frame = scrape_rosters(teams, delay=args.delay, timeout=args.timeout)

    if args.no_load:
        print(frame.to_string(index=False))
        return

    database_name, team_count, player_count = load_mysql(frame, args.database)
    print(f"Loaded roster data into MySQL database {database_name}.")
    print(f"teams: {team_count}")
    print(f"players: {player_count}")


if __name__ == "__main__":
    main()
