"""Parse the export without database writes.
Run: uv --cache-dir /tmp/5757-uv-cache run --no-project --with pglast python 5757/assets/verify_mv_export.py
"""
from pathlib import Path
import json
from pglast import parse_sql,Error
ROOT=Path(__file__).resolve().parents[1]
script=(ROOT/'mv-backup/recreate_pripis_standardne_statistike_napak.sql').read_text()
creation=script[script.index('CREATE MATERIALIZED'):script.index('WITH NO DATA;')+len('WITH NO DATA;')]
prefix=creation[:creation.index('SELECT')].rstrip()
try:
    parse_sql(prefix)
except Error as error:
    assert 'syntax error at end of input' in str(error)
    symptom=str(error)
else:
    raise AssertionError('Expected truncated CREATE statement to fail')
statements=parse_sql(script)
assert len(parse_sql(creation))==1
(ROOT/'mv-backup/01_create_pripis_standardne_statistike_napak.sql').write_text(creation+'\n')
report={'validation':'PostgreSQL grammar via pglast; no database writes','full_script_parses':True,'statement_count':len(statements),'create_only_statement_count':1,'prefix_length_before_select':len(prefix),'end_of_input_position':len(prefix)+1,'prefix_error':symptom,'limitation':'Grammar validation, not execution against staging. Procedural-body execution and permissions are not validated.'}
(ROOT/'mv-backup/verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
