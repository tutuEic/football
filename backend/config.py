# -*- coding: utf-8 -*-
"""Global config file"""
import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

_ROOT_DIR = Path(BASE_DIR).resolve().parent
_ENV_FILE = _ROOT_DIR / ".env"
load_dotenv(_ENV_FILE)

# MySQL
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "football_app")
MYSQL_PASS = os.getenv("MYSQL_PASS", "")
MYSQL_DB_SOURCE = os.getenv("MYSQL_DB_SOURCE", "football_odds")
MYSQL_DB_PRED  = os.getenv("MYSQL_DB_PRED", "football_pred")

# Model storage
MODEL_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# SoFIFA cache
SOFIFA_CACHE = os.getenv(
    "SOFIFA_CACHE_PATH",
    os.path.join(os.path.dirname(BASE_DIR), "data", "sofifa_cache"),
)
os.makedirs(SOFIFA_CACHE, exist_ok=True)

# TheSportsDB API key (optional)
SPORTSDB_API_KEY = os.getenv("SPORTSDB_API_KEY", "")

# FIFA dataset (optional, used by squad_fifa fallback)
FIFA_PATH = os.getenv("FIFA_PATH", "")

# Current season derived from the calendar.
# Football seasons span two calendar years (e.g. 2025/2026).
# If we're in the second half of the year (July¨CDecember) the season started this year,
# otherwise it started last year.
now = datetime.now()
CURRENT_SEASON = now.year if now.month >= 7 else now.year - 1

# SoFIFA works with the most recent three completed/current seasons.
SO_FIFA_SEASONS = [
    CURRENT_SEASON - 2,
    CURRENT_SEASON - 1,
    CURRENT_SEASON,
]

# League name mapping (code -> English name)
LEAGUE_NAMES = {
    "E0": "Premier League", "E1": "Championship", "E2": "League One", "E3": "League Two",
    "D1": "Bundesliga", "D2": "2. Bundesliga",
    "I1": "Serie A", "I2": "Serie B",
    "SP1": "La Liga", "SP2": "La Liga 2",
    "F1": "Ligue 1", "F2": "Ligue 2",
    "N1": "Eredivisie", "B1": "Pro League", "P1": "Liga Portugal", "T1": "Super Lig",
    "SC0": "Scottish Premiership", "USA": "MLS", "JPN": "J1 League",
}

# SoFIFA league name mapping
SOFIFA_LEAGUES = {
    "E0": "ENG-Premier League",
    "SP1": "ESP-La Liga",
    "D1": "GER-Bundesliga",
    "I1": "ITA-Serie A",
    "F1": "FRA-Ligue 1",
    "N1": "NED-Eredivisie",
    "P1": "POR-Liga Portugal",
}
