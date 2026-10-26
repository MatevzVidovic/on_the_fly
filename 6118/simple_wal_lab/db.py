"""Connection uses PGHOST, PGPORT, PGDATABASE, PGUSER and PGPASSWORD/.pgpass."""
import psycopg


def connect():
    return psycopg.connect(autocommit=True, connect_timeout=5,
                           application_name="simple_wal_lab")
