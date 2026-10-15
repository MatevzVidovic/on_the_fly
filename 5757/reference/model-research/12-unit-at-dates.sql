SELECT d.cutoff,j.dst_sid,j.id_model,j.id_model_ver,j.vrednost,j.posplosena_vrednost,
rf.created AS valid_from,rt.created AS valid_to
FROM (SELECT TIMESTAMP '2020-01-01 00:00:00' AS cutoff FROM dual
UNION ALL SELECT TIMESTAMP '2025-01-01 00:00:00' FROM dual
UNION ALL SELECT TIMESTAMP '2026-01-01 00:00:00' FROM dual) d
LEFT JOIN EV.JN_DEL_STAVBE_ENOTA j ON j.dst_sid=29974237 AND j.id_model='IND' AND j.jn_status<>'X'
AND EXISTS (SELECT 1 FROM EV.REVISION rf WHERE rf.rev_num=j.jn_rev_num AND rf.created<=d.cutoff)
AND (j.jn_rev_num_to IS NULL OR EXISTS (SELECT 1 FROM EV.REVISION rt WHERE rt.rev_num=j.jn_rev_num_to AND rt.created>d.cutoff))
LEFT JOIN EV.REVISION rf ON rf.rev_num=j.jn_rev_num
LEFT JOIN EV.REVISION rt ON rt.rev_num=j.jn_rev_num_to
ORDER BY d.cutoff FETCH FIRST 12 ROWS ONLY
