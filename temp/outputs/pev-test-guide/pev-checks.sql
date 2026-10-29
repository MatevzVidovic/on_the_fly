-- PEV: READ-ONLY checks based on supplied SQL; not live-database verified.
-- Run one numbered block at a time; replace REPLACE_SEQ_ID.

-- 1 · Preveri povezavo
-- pgAdmin → Servers → izbrano TESTNO okolje → Databases → fmp_data_gurs → desni klik → Query Tool. SQL prilepi v urejevalnik in izvedi izbrani blok z Execute. Ne izvajaj priložene migracijske skripte.
SELECT current_database() AS baza,
       current_user AS uporabnik,
       inet_server_addr() AS streznik,
       inet_server_port() AS vrata;
-- LOOK: Baza mora biti fmp_data_gurs. Strežnik primerjaj z nastavitvami povezave za izbrano testno okolje; samo ime baze ne potrjuje okolja.

-- 2 · Poišči zapis
-- V LIFT odpri PEV PNB 10683 → parcelo 2100 267/47 → atribute. Prepiši seq_id_parc. V naslednjih blokih zamenjaj REPLACE_SEQ_ID z dejansko vrednostjo. Številka 10683 NI seq_id_parc.
SELECT p.id, p.seq_id_parc, p.id_rel_fo, p.parcela_id,
       p.upostevan, p.delez, p.delez_bzps,
       f.id_rel_pe, pe.valid_to
FROM public.pev_parcele p
LEFT JOIN public.pev_fo f ON f.id = p.id_rel_fo
LEFT JOIN public.pev_posebne_enote pe ON pe.id = f.id_rel_pe
WHERE p.seq_id_parc::text = 'REPLACE_SEQ_ID';
-- LOOK: Pričakuj točno 1 vrstico in v aplikaciji potrdi identiteto parcele. Pred vsakim testom shrani rezultat (CSV ali posnetek): delez, delez_bzps, FO in upoštevanost. 0 ali več vrstic → najprej razreši izbor.

-- 3 · Neodvisno preveri izračun
-- Po uspešnem shranjevanju v LIFT ponovno izvedi ta SELECT. Ne kliče stare računske funkcije in ne spreminja podatkov. Oznaka MATCH potrdi numerično stanje, ne izvora ali števila izvajanj.
WITH target AS (
    SELECT p.*, f.id_rel_pe,
           CASE WHEN pe.id IS NOT NULL
                THEN COALESCE(pe.valid_to, DATE '2100-01-01')
           END AS effective_valid_to
    FROM public.pev_parcele p
    LEFT JOIN public.pev_fo f ON f.id = p.id_rel_fo
    LEFT JOIN public.pev_posebne_enote pe ON pe.id = f.id_rel_pe
    WHERE p.seq_id_parc::text = 'REPLACE_SEQ_ID'
), latest AS (
    SELECT DISTINCT ON (stavba_parcela_id, datum_od, datum_do)
           stavba_parcela_id, datum_od, datum_do,
           parcela_id, stavba_id, povrsina_zps
    FROM public.kn_nep_stavbe_parcele_h
    ORDER BY stavba_parcela_id, datum_od, datum_do, datum_sys DESC
), measured AS (
    SELECT p.*, (
        SELECT SUM(kn.povrsina_zps)
        FROM latest kn
        WHERE kn.parcela_id = p.parcela_id
          AND p.effective_valid_to <= kn.datum_do
          AND EXISTS (
              SELECT 1 FROM public.pev_stavbe st
              WHERE st.id_rel_fo = p.id_rel_fo
                AND st.stavba_id = kn.stavba_id
                AND EXISTS (
                    SELECT 1 FROM public.pev_deli_stavb d
                    WHERE d.id_rel_sta = st.id
                      AND d.upostevan IS TRUE
                )
          )
    ) AS vsota_zps
    FROM target p
), expected AS (
    SELECT m.*,
           CASE WHEN upostevan IS TRUE
                     AND id_rel_pe IS NOT NULL
                     AND vsota_zps IS NOT NULL
                THEN CASE WHEN delez IS NULL THEN NULL::numeric
                          ELSE GREATEST(delez - vsota_zps, 0) END
           END AS izracunana_vrednost
    FROM measured m
)
SELECT seq_id_parc, id_rel_fo, delez, delez_bzps AS shranjeno,
       vsota_zps, izracunana_vrednost,
       CASE
         WHEN upostevan IS NOT TRUE
           THEN 'CHECK BEFORE: neupostevana; ohrani vrednost'
         WHEN id_rel_pe IS NULL
           THEN CASE WHEN delez_bzps IS NULL THEN 'MATCH: brez FO-PEV, NULL'
                     ELSE 'MISMATCH: pricakovan NULL' END
         WHEN vsota_zps IS NULL
           THEN 'CHECK BEFORE: UPDATE ohrani; INSERT NULL'
         WHEN delez_bzps IS NOT DISTINCT FROM izracunana_vrednost
           THEN 'MATCH'
         ELSE 'MISMATCH'
       END AS preverjanje
FROM expected;
-- LOOK: Za osnovni primer: vsota_zps = 52; delez = 300 → shranjeno = izracunana_vrednost = 248. Nato 320 → 268. CHECK BEFORE zahteva primerjavo s posnetkom pred dogodkom; ni avtomatski PASS. Rezultat brez dogodka ne dokazuje, da se je workflow sprožil.

-- 4 · Preveri obseg FO in dele
-- Iz istega seq_id_parc izpiši vse parcele tega FO in njegove stavbe. Pri premiku uporabi še seq_id_parc parcele drugega FO in ponovi blok 3 za vse prizadete parcele.
SELECT p.seq_id_parc, p.id_rel_fo, p.parcela_id,
       p.upostevan, p.delez, p.delez_bzps
FROM public.pev_parcele p
WHERE p.id_rel_fo IN (
    SELECT id_rel_fo FROM public.pev_parcele
    WHERE seq_id_parc::text = 'REPLACE_SEQ_ID'
)
ORDER BY p.id;

SELECT st.id AS pev_stavba_id, st.id_rel_fo, st.stavba_id,
       COUNT(d.id) FILTER (WHERE d.upostevan IS TRUE) AS upostevani_deli
FROM public.pev_stavbe st
LEFT JOIN public.pev_deli_stavb d ON d.id_rel_sta = st.id
WHERE st.id_rel_fo IN (
    SELECT id_rel_fo FROM public.pev_parcele
    WHERE seq_id_parc::text = 'REPLACE_SEQ_ID'
)
GROUP BY st.id, st.id_rel_fo, st.stavba_id
ORDER BY st.id;
-- LOOK: 1 → 2 upoštevana dela iste stavbe: ZPS in rezultat ostaneta enaka. 2 → 1: isto. 1 → 0 brez drugih ustreznih ZPS: prejšnji delez_bzps se ohrani. Pri premiku preveri oba FO; izvorni FO brez ZPS ohrani prejšnjo vrednost.

-- 5 · Preveri odstranitev prožilcev
-- Po uvedbi workflowa, v Query Tool istega okolja. To je preverjanje, ne odstranitev. Pred uvedbo je prisotnost starih prožilcev pričakovana.
SELECT n.nspname AS shema, c.relname AS tabela,
       t.tgname AS prozilec, t.tgenabled AS omogocen,
       pg_get_triggerdef(t.oid) AS definicija
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE NOT t.tgisinternal
  AND n.nspname = 'public'
  AND t.tgname IN (
    'tr_pev_parcele_delez_bzps',
    'tr_pev_stavbe_delez_bzps',
    'tr_pev_deli_stavb_delez_bzps'
  );
-- LOOK: Po uvedbi: 0 vrstic. Onemogočen prožilec še vedno ni odstranjen. Nato sproži novo spremembo v LIFT in potrdi rezultat ter dnevnik workflowa; ta SELECT sam ne dokazuje odsotnosti drugih računskih poti.

