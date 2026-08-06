

Potrebno je uvoziti EV podatke iz EV Oracle baze in nastaviti ustrezno sinhronizacijo.

Tako kot za KN potrebujemo tudi tukaj historične podatke, vendar se vodijo na drugačen način. Trenutno imamo uvožene te podatke:


Zaradi velikosti tabell in sestave podatkov je bilo možno razdeliti tabeli enot delov stavb in enot parcel na več tabel, ker bi bile drugače prevelike. Zraven imajo letnico, preko katere se vidijo iz katerega leta so podatki. Kjer je napisano do danes je potrebno nastaviti integracijo, če ta še ni nastavljena.



Branje historičnih vrednosti

V tabeli ev.revision imamo zapise, da lahko preberemo historične podatke. To tabelo povežemo in dobimo atribute valid_from in valid_to ter date_change, ki ga uporabimo pri delta integraciji. Identifikator moramo sestaviti, ker v večini primerov ga ni. V spodnjem primeru je to atribut jn_parcela_enota_pk. Če neveš kateri je enolični identifikator poglej kako je setavljen primarni ključ v bazi.

SELECT
        to_char(j."ID_PARC_ENOTA") || '-' || to_char(j."JN_REV_NUM") as jn_parcela_enota_pk,
        j.ID_PARC_ENOTA,
        j.PC_MID,
        j.ID_MODEL,
        j.DELEZ_POVRSINE,
        j.VREDNOST,
        j.RAVEN,
        j.VPLIV,
        j.CONA_IME,
        j.FAKTOR_PO,
        j.POSPLOSENA_VREDNOST,
        j.ID_MODEL_VER,
        CAST(TRIM(j.JN_STATUS) AS VARCHAR2(1)) AS JN_STATUS,
        from_tz(cast(RF.CREATED as TIMESTAMP), 'Europe/Ljubljana')                       valid_from,
        from_tz(cast(RT.CREATED as TIMESTAMP), 'Europe/Ljubljana')                       valid_to,
        from_tz(cast(COALESCE(RT.CREATED, RF.CREATED) as TIMESTAMP), 'Europe/Ljubljana') date_change,
        ROW_NUMBER() OVER (
            ORDER BY rf.created, j.id_parc_enota, j.jn_rev_num
        ) AS rn
    FROM EV.JN_PARC_ENOTA j
    JOIN ev.revision rf ON (j.jn_rev_num = rf.rev_num)
    LEFT JOIN ev.revision rt ON (j.jn_rev_num_to = rt.rev_num)
    WHERE rf.created >= TIMESTAMP '2025-01-01 00:00:00'

Vse historične tabele v EV so zapisane z začetnico JN_*. Tudi tabeli *_podatki imata jn_rev_num, preko katerega delamo delta integracijo.

Seznam tabel, ki jih potrebujemo v liftu

dst_pripis_podatki

jn_del_stavbe

JN_DEL_STAVBE_ENOTA (deljena, spusti atribut podatki).  (že v liftu - to sta te 2025 dalje)

jn_parc_del

jn_parc_enota (deljena, spusti atribut podatki).  (že v liftu - to sta te 2025 dalje)

jn_parcela 

jn_pe_dst (mala in lahko direktno)

jn_pe_parc (mala in lahko direktno)

jn_posebna_enota (mala in lahko direktno)

jn_prostor

jn_stavba

parc_pripis_podatki



Pazi - notes



where jn_status <> 'X'



Gej EV H DEL stavbe integracijo.



Vase razen malih tabel je treba: na roke povezava do baze in v programu postopno in retryable loadaš.



Na teh H tabelzah je že nekaj podatkov. Lahko preveriš njihovo pravilnost in jih kar uporabiš.