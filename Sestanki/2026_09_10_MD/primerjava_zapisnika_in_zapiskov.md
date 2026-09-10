# Primerjava zapisnika in zapiskov – sestanek MD, 10. 9. 2026

Vir: `task.md`. Levi stolpec povzema glavni zapisnik, desni osebne zapiske. `null` pomeni, da v posameznem viru ni ustrezne navedbe. Sorodne navedbe so poravnane; razlike so izrecno označene. Vsebina je primerjana, ne tehnično preverjena.

| Glavni zapisnik | Osebni zapiski |
| --- | --- |
| **Sestanek:** MD, 10. 9. 2026, interni zapisnik. Prisotni: FCT – Gašper Oder, Matevž Vidovič; GURS – Melita Ulbl, Rok Štembal, Andrej Glavica. | null |
| **Pasivni modeli:** avtomatsko odštevanje tudi, kadar niso dodani v model posla; neupoštevani pasivni model naj v vmesnem izračunu dobi `0` namesto `null`, da leva stran ne postane `null`. Omogočiti poljuben nabor pasivnih modelov. | null |
| **Ime `v_gar`:** preimenovati faktor vrednostne tabele garaž zaradi kolizije s pasivnim modelom GAR, ki je v enačbi prav tako `v_gar`. | null |
| **SQL datumi:** zapis `DATE` ni potreben; zadostuje npr. `dat_pri > '2020-01-01'`. | **SQL datumi:** vprašanje, ali je uporaba `DATE` pri `dat_pri` smiselna; opomba, da gre načeloma za sintakso Oracle. Zapisnik vsebuje odgovor na vprašanje. |
| **Model brez transakcij – razlika v imenih:** naveden je **PPL_NAJ**; transakcije se ne dodajo in izračunajo. | **Modela brez transakcij – razlika v imenih:** navedena sta **PPP_NAJ in PPP_MN**, ki imata kljub uspešnemu uvozu `0` transakcij. Preveriti, kateri modeli so bili predmet težave; uspešen uvoz v zapisniku ni omenjen. |
| **Vzrok in popravek filtra:** filter PPL_NAJ ne zajame nobene transakcije iz `pp_np_trans`. Predlagani filter vrne nekaj transakcij: `dat_pri >= '2020-01-01' AND dat_pri <= '2025-01-01' AND model_posla = 'PPL' AND vrsta_posla IN (1) AND sestava = 1 AND ef_najem > 0 AND (obrat_str = FALSE OR obrat_str IS NULL) AND (cas_najema = 2 OR (cas_najema = 1 AND trajanje >= 6)) AND status_pregleda = 1`. Preveriti in sporočiti pravilne filtre za modele `_NAJ` in `_MN`. | null |
| **Vir transakcij:** skripta izbira tabelo po končnici imena modela: `*_NAJ` → `pp_np_trans`; `*_MN` → `md_trans_mn`; ostalo → `pp_kp_trans`. | **Vir transakcij:** katera tabela je vir za izbrano verzijo modela (`pp_kp_trans`, `pp_np_trans`)? Kako vemo, od kod se izvede osvežitev? Ali je izbira za `*_NAJ` vnaprej določena? Kaj velja za množitelje? Zapisnik vsebuje odgovore. |
| **Prikaz vira:** dodati atribut, ki jasno prikazuje vir transakcij. | **Prikaz vira – razlika v predlogu izvedbe:** na vrstici naj bo **gumb**, ki pove, od kod se podatki črpajo. Zapisnik predvideva atribut. |
| **Skupina:** Primož naj pojasni, na podlagi česa se polni `md_verzije_modeli.skupina`. | **Skupina:** ali je »Skupina« tisti gumb, ki pove vir transakcij? Vprašanje o povezavi med skupino in virom v zapisniku ni izrecno ohranjeno. |
| **Fiktivne prodaje:** za odgovor o črpanju podatkov počakati Primoža; črpanje podatkov za MN in fiktivne transakcije je tema za naslednjič. | **Fiktivne prodaje:** kako se določa njihov vir oziroma črpanje? |
| null | **Atribut Fiktivne:** ali črpanje fiktivnih prodaj določa logični atribut »Fiktivne«? To konkretno vprašanje v zapisniku manjka. |
| **Posel 894728:** v ISAM-u ima napačen prostor; preveriti, kje nastane težava. | **Posel 894728:** ima prostor **99**, v GV pa **3 – Poslovni prostor**. Zapisnik povzema težavo, vendar ne vključuje konkretnih kod in primerjave z GV. |
| null | **Migracija posla 894728:** pri Meliti je v migraciji pravilno; po zapiskih je težava nekje pri nas. |
| **PPP, desna stran enačbe – razlika v vrednosti:** veliko transakcij ima desno vrednost **`null`**. Vrednost se ne izračuna, ker je atribut `velikost` prazen; preveriti, ali gre za napako. | **PPP, desna stran enačbe – razlika v vrednosti:** po preračunu ima veliko transakcij desno vrednost **`0`**; povsod je `velikost` enaka `null`. Preveriti razliko med navedbama `0` in `null`. |
| null | **Povezava težav:** manjkajoča `velikost` oziroma desna vrednost v modelu PPP je po zapiskih povezana z ID prostora **99**. Zapisnik te povezave ne navaja. |
| **Karta, redukcija:** prikaz transakcij naj se ne reducira tudi pri manjšem merilu. | **Karta, redukcija:** na sloju ne sme biti redukcije; vidne naj bodo vse transakcije, tudi pri »višjem zoom-u«. Obe navedbi zahtevata prikaz vseh transakcij; izraz za merilo oziroma zoom ni enak. |
| null | **Utemeljitev prikaza vseh transakcij:** gre za točkovni sloj, zato po zapiskih načeloma ne bi smelo prihajati do sesutja aplikacije. |
| **Merilo – drugačen predmet:** velikost **label** naj se prilagaja merilu; odgovor ni zapisan. | **Merilo – drugačen predmet:** prilagajanje velikosti **pikic na karti**, da se pri približevanju in oddaljevanju njihova velikost glede na objekte na karti ne spreminja. Zapisnik ne navaja izrecno te zahteve za točkovne simbole. |
| **Karta, verzije modelov:** transakcije naj se prikažejo pri vseh verzijah modelov, ki jih vključujejo. | null |
| **Karta, manjkajoča geometrija:** PPL ne prikazuje transakcij, ker zapisi v `md_trans` nimajo geometrije; napako bodo odpravili. | null |
| **Karta, delovno coniranje:** upoštevati filter »Delovna coniranje« = `True` in ustrezno nastaviti `md_verzije_modeli.delovna` za verzijo modela. | null |
| **Drugi TAO:** tema za naslednjič – kaj je in kako deluje. | **Drugi TAO:** kako deluje ta zastavica? Splošno vprašanje je vključeno v zapisnik. |
| null | **Drugi TAO, podrobnosti:** ali bosta na tem sloju dva vnosa? Z Gašperjem ne vesta, kakšne so želje naročnika. |
| **Obratovalni stroški:** v 3D tabeli gradnikov faktorja obratovalnih stroškov so prikazane napačne vrednosti; v bazi so vrednosti pravilne. | **Obratovalni stroški:** povsem napačne številke v tabeli v stranskem panelu. Zapisi se vsebinsko ujemajo; zapiski ne potrjujejo pravilnosti vrednosti v bazi. |
| null | **Lokacija prikaza napake:** težava z obratovalnimi stroški je na posnetku prikazana približno pri **1 h 20 min**. |
| **Testiranje in filtriranje:** težko je najti transakcijo z vsemi vrednostmi iz enačbe; ali je mogoče filtrirati transakcije, ki imajo določene vrednosti že v osnovi izpolnjene? | **Testiranje in filtriranje:** kako preveriti pravilnost npr. `v_gar` ali `povrsina_dp` v enačbi, če ni mogoče filtrirati transakcij, ki imajo ti vrednosti v osnovi izpolnjeni? Splošna zahteva je vključena, konkretna primera manjkata. |
| null | **Omejitev filtriranja:** na »vmesni?izr« je po zapiskih samo JSON, po katerem ni mogoče filtrirati. Ime mesta oziroma atributa je v zapiskih negotovo; zapisnik te razlage ne vključuje. |
| **Poročilo o modelu:** dodati obvestilo ob začetku in koncu izdelave poročila. | null |
| **Format poročila:** DOCX namesto PDF; gre za večjo spremembo, odločitev bo sporočena naknadno. Odločitev je tudi tema za naslednjič. | null |
| **Kopiranje med verzijami modelov:** vključiti atribut barvne sheme. | null |

Glavni zapisnik **ne vključuje vseh podrobnosti iz zapiskov**. Pred dopolnitvijo je treba razjasniti predvsem imena modelov (**PPL_NAJ / PPP_NAJ in PPP_MN**), desno vrednost enačbe (**null / 0**) ter predmet prilagajanja merilu (**labele / pikice**). Vrstice z `null` na levi kažejo manjkajoče navedbe; dodatne razlike in izpuščene podrobnosti so opisane tudi znotraj povezanih vrstic.
