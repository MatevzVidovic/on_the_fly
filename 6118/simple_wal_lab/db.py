"""Load this directory's .env and connect using its PG* settings."""
import os
import argparse
import sys
from pathlib import Path
import psycopg
from psycopg import sql
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))
parser = argparse.ArgumentParser()
parser.add_argument('--table', default=os.getenv('TARGET_TABLE'))
parser.add_argument('--schema', default=os.getenv('TARGET_SCHEMA', 'public'))
parser.add_argument('--date-column', '--utc-column', default=os.getenv('DATE_COLUMN', 'date_change_utc'),
                    help='Destination UTC column')
parser.add_argument('--source-date-column', default=os.getenv('SOURCE_DATE_COLUMN', 'date_change'))
if Path(sys.argv[0]).name in ('batched_copy_backfill.py', 'compare_copy.py'):
    parser.add_argument('--copy-target', help='Destination table; default: source name + _org2810')
if Path(sys.argv[0]).name == 'batched_copy_backfill.py':
    parser.add_argument('--batch-size', type=int, default=500000)
    parser.add_argument('--pause', type=float, default=1)
if Path(sys.argv[0]).name == 'db_tracker.py':
    parser.add_argument('sqlite_file', nargs='?', default=str(Path(__file__).with_name('full.sqlite')))
ARGS = parser.parse_args()
if not ARGS.table:
    parser.error('Set TARGET_TABLE in .env or pass --table')
schema, table = ARGS.table.split('.', 1) if '.' in ARGS.table else (ARGS.schema, ARGS.table)
TABLE = sql.Identifier(schema, table)
DATE_COLUMN = sql.Identifier(ARGS.date_column)
SOURCE_DATE_COLUMN = sql.Identifier(ARGS.source_date_column)


def connect():
    return psycopg.connect(autocommit=True, connect_timeout=5,
                           application_name="simple_wal_lab")
