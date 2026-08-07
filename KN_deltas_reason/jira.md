
V KN podatkih se pojavljajo razlike med original podatki iz Oracle baze in podatki iz ISAM2 produkcije, kjer se ti sinhronizirajo.

Primer tabele delov stavb

Tabela kn_nep_deli_stavb_h v ISAM2 je ciljna kopija Oracle tabele nep.DELI_STAVB_H. Gre za historično tabelo delov stavb.
Pomen ključnih datumov:

datum_sys pomeni sistemski datum spremembe zapisa v izvorni KN Oracle bazi. Ta datum se uporablja za delta sinhronizacijo, ker pove, kdaj je bil zapis v izvoru dodan ali spremenjen.

datum_od in datum_do pomenita obdobje veljavnosti historičnega zapisa. Pri poslovnih poizvedbah se aktualen/veljaven zapis za določen referenčni datum izbira z logiko:

Ključi:

del_stavbe_h_id je unikaten identifikator posameznega historičnega zapisa in se uporablja kot poslovni ključ pri sinhronizaciji.

del_stavbe_id ni unikaten, ker ima lahko en del stavbe več historičnih zapisov.



Potek sinhronizacije:

Iz Oracle tabele nep.DELI_STAVB_H se berejo zapisi, ki imajo datum_sys novejši od zadnje uspešno prenesene vrednosti.

V ciljni Postgres tabeli kn_nep_deli_stavb_h se zapis identificira po del_stavbe_h_id.

Če del_stavbe_h_id v Postgresu še ne obstaja, se zapis vstavi.

Če del_stavbe_h_id že obstaja in se je zapis v Oracle spremenil, se mora obstoječi zapis v Postgresu posodobiti.

Ciljna tabela mora biti zrcalo Oracle tabele glede na del_stavbe_h_id.

Ugotovljeno stanje kontrole:

V Oracle obstaja 604 ključev, ki jih ni v Postgresu.

V Postgresu obstaja 11 ključev, ki jih ni v Oracle.

Pri 7880 zapisih isti del_stavbe_h_id obstaja v obeh bazah, vendar ima različen datum_sys.

Pri 2282 zapisih je datum_sys v Oracle že >= 2026-07-01, v Postgresu pa je isti zapis še vedno < 2026-07-01.


To pomeni, da ciljna tabela trenutno ni popolnoma sinhronizirana z izvorno Oracle tabelo. Problem ni v samem count(*), ampak v tem, da obstoječi zapisi v Postgresu niso bili posodobljeni oziroma so bili nekateri novi zapisi izpuščeni.

Potrebno je ugotoviti zakaj pride do teh razlik.

Te razlike se pojavijo na vseh KN podatkih, ki se sinhronizirajo z delto preko Oracle baze.

Vedno primerjaj razlike do določenega datuma. V Oracle se lahko zapisi dodajajo med dnevom ni primeren samo count po celotni tabeli.