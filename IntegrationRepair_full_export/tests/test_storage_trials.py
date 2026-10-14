"""All strategies receive the same batches and produce the same durable diff."""
import pytest
import storage_trials

DATE='2025-01-02 00:00:00.000000'
OLD='2025-01-01 00:00:00.000000'
FUTURE='2099-01-01 00:00:00.000000'


@pytest.mark.parametrize('engine,algorithm,commit_rows',[
    ('sqlite','row_loop',2),('sqlite','row_loop',0),('sqlite','bulk',2),('sqlite','bulk',0),
    ('duckdb','bulk',2),('duckdb','bulk',0),('ram','bulk',2),('ram','bulk',0)])
def test_trial(tmp_path,monkeypatch,engine,algorithm,commit_rows):
    monkeypatch.setattr(storage_trials,'BATCH',2)
    source=[('a',DATE),('b',OLD),('c',FUTURE),('d',DATE),('z',DATE)]
    # Deliberately unsorted target input: no matching sort-order assumption.
    target=[('id-b','b',DATE),('id-c','c',OLD),('id-a','a',OLD),('id-extra','extra',OLD)]
    result=storage_trials.trial(tmp_path,source,target,DATE,engine,algorithm,commit_rows)
    assert result['diff_counts']==dict(insert=2,update=1,remove=1,ahead=1)
    assert result['reopened_source_rows']==5 and result['reopened_prepared']
    assert result['file_bytes']>0


def test_duck_insert_array_and_csv_are_equal(tmp_path):
    import duckdb
    with duckdb.connect() as db:
        for method in ('arrays','csv'):
            db.execute(f'CREATE TABLE {method}(key VARCHAR,date VARCHAR)')
            storage_trials.duck_insert(db,method,['key','date'],[('001',DATE),('x-y',OLD)],tmp_path/'input.csv',method)
        assert db.execute('SELECT * FROM arrays').fetchall()==db.execute('SELECT * FROM csv').fetchall()


def test_failure_trials(tmp_path):
    result=storage_trials.failure_trials(tmp_path)
    assert result[0]['persisted_keys']==[]
    assert result[1]['persisted_keys']==[1,2]
    modes={r['mode']:r for r in result}
    assert modes['ram_one_transaction']['persisted_keys']==[]
    assert modes['controlled_fetch_failure_commit_healthy_transaction']['persisted_keys']==[1,2]
    assert modes['reload_ram_snapshot_and_continue']['persisted_keys']==[1,2,3]
    assert not modes['abrupt_process_exit']['snapshot_created']
    assert modes['abrupt_exit_with_previous_file_commit']['persisted_keys']==[1,2]
