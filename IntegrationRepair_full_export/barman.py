"""Pause writes while the Barman replication slot retains too much WAL."""
import time


def wait_for_barman(db):
    paused = False
    while True:
        slot = db.execute('''SELECT active,
            pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
            FROM pg_replication_slots WHERE slot_name='barman' ''').fetchone()
        # Apply calls this only at committed batch boundaries; do not hold a
        # PostgreSQL read transaction open while waiting for the receiver.
        db.commit()
        if slot is None or slot[1] is None:
            raise RuntimeError('Cannot measure WAL retention for the barman slot')
        if not slot[0]:
            raise RuntimeError('Barman slot is inactive; stopping apply')
        retained = slot[1]
        if not paused and retained <= 5 * 1024**3:
            return
        if paused and retained < 2 * 1024**3:
            print('Barman retained WAL is below 2 GiB; resuming.', flush=True)
            return
        paused = True
        print(f'Barman retained {retained / 1024**3:.2f} GiB; waiting for below 2 GiB...', flush=True)
        time.sleep(5)
