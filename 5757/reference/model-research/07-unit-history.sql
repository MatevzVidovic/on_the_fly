SELECT j.dst_sid,j.id_model,j.id_model_ver,j.vrednost,j.posplosena_vrednost,j.jn_status,
j.jn_rev_num,j.jn_rev_num_to,rf.created AS valid_from,rt.created AS valid_to,
SUBSTR(rf.description,1,160) AS revision_description
FROM EV.JN_DEL_STAVBE_ENOTA j
LEFT JOIN EV.REVISION rf ON rf.rev_num=j.jn_rev_num
LEFT JOIN EV.REVISION rt ON rt.rev_num=j.jn_rev_num_to
WHERE j.dst_sid=29974237 AND j.id_model='IND'
ORDER BY j.jn_rev_num
FETCH FIRST 30 ROWS ONLY
