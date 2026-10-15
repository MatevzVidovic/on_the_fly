SELECT id_model_ver,DBMS_LOB.GETLENGTH(xml) AS xml_length,
DBMS_LOB.SUBSTR(xml,3500,1) AS xml_start,
DBMS_LOB.SUBSTR(xml_originalni,3500,1) AS original_start
FROM EV.MODELI_XML WHERE id_model_ver IN (1150,1173)
