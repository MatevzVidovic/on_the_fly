"""Original scattered-key fetch, retained only for performance comparisons."""

def fetch_models(oracle, keys):
    """Use Oracle's original composite index; retain NULL as a returned value."""
    result = {}
    with oracle.cursor() as cur:
        cur.arraysize = 1000
        for start in range(0, len(keys), 1000):
            batch = keys[start:start + 1000]
            binds = {}
            pairs = []
            for i, (sid, revision) in enumerate(batch):
                binds[f's{i}'], binds[f'r{i}'] = sid, revision
                pairs.append(f'(:s{i},:r{i})')
            # TO_CHAR avoids any floating-point conversion of Oracle NUMBER values.
            cur.execute('''SELECT TO_CHAR(DST_SID, 'TM9'), TO_CHAR(JN_REV_NUM, 'TM9'),
                TO_CHAR(ID_MODEL_VER, 'TM9') FROM EV.JN_DEL_STAVBE_ENOTA
                WHERE (DST_SID, JN_REV_NUM) IN (''' + ','.join(pairs) + ')', binds)
            for sid, revision, model in cur:
                result[int(sid), int(revision)] = None if model is None else int(model)
    return result


