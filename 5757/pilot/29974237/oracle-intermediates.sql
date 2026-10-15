SELECT j.id,j.dst_sid,j.id_model,j.jn_rev_num,j.jn_rev_num_to,j.jn_status,
rf.created AS valid_from,rt.created AS valid_to,
j.error_msg,j.raven,j.cona_ime,j.d_dst,j.izmera,j.leto_izg_sta,j.vt_dst,
j.pov_leto_obn,j.f_obn,j.t_last,j.f_last,j.f_nk,j.povr_zps,j.f_d_dst,j.vt_zps_m2
FROM EV.JN_DST_PRIPIS_PODATKI j
JOIN EV.REVISION rf ON rf.rev_num=j.jn_rev_num
LEFT JOIN EV.REVISION rt ON rt.rev_num=j.jn_rev_num_to
WHERE j.id='29974237.IND' AND j.dst_sid=29974237 AND j.id_model='IND'
AND j.jn_status<>'X' AND rf.created<=TIMESTAMP '2026-01-01 00:00:00'
AND (rt.created>TIMESTAMP '2026-01-01 00:00:00' OR j.jn_rev_num_to IS NULL)
FETCH FIRST 3 ROWS ONLY
