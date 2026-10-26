"""Load this directory's .env and connect using its PG* settings."""
import os
from pathlib import Path
import psycopg
from psycopg import sql
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))
TABLE = sql.Identifier(os.getenv('TARGET_SCHEMA', 'public'), os.environ['TARGET_TABLE'])


def connect():
    return psycopg.connect(autocommit=True, connect_timeout=5,
                           application_name="simple_wal_lab")
