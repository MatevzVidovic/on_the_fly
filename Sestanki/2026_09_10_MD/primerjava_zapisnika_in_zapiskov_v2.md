# Primerjava posodobljenega zapisnika in vseh zapiskov – 10. 9. 2026

Primerjava temelji na obeh besedilih iz zadnjega sporočila. `null` pomeni, da v ustreznem viru ni navedbe. Sorodne vsebine so povezane tudi, kadar se podrobnosti razlikujejo; razlike so označene. Tehnična pravilnost navedb ni preverjena.

| Glavni dokument | Vsi osebni zapiski |
| --- | --- |
| **Sestanek in prisotni:** interni zapisnik MD, 10. 9. 2026. FCT: Gašper Oder, Matevž Vidovič. GURS: Melita Ulbl, Rok Štembal, Andrej Glavica. | null |
| **Pasivni modeli:** avtomatsko odštevanje tudi, kadar niso dodani v model posla; neupoštevani pasivni model naj dobi `0` namesto `null`, da leva stran ne postane `null`. Omogočiti poljuben nabor pasivnih modelov. | null |
| **Kolizija imena `v_gar`:** preimenovati faktor vrednostne tabele garaž, ker ima enako ime kot pasivni model GAR v enačbi. | null |
| **SQL datumi – pokrito z odgovorom:** `DATE` ni potreben; datum se lahko zapiše npr. `dat_pri > '2020-01-01'`. | **SQL datumi:** ali je uporaba `DATE` pri `dat_pri` smiselna? Opomba, da je to načeloma sintaksa Oracle. |
| **Vir transakcij – pokrito z odgovorom:** skripta izbira po končnici imena: `*_NAJ` → `pp_np_trans`; `*_MN` → `md_trans_mn`; ostalo → `pp_kp_trans`. | **Vir transakcij:** katera tabela je vir za izbrano verzijo modela in osvežitev? Ali je izbira za `*_NAJ` vnaprej določena? Kaj velja za množitelje? |
| **Prikaz vira – drugačen predlog izvedbe:** dodati atribut, ki jasno prikazuje vir. | **Prikaz vira:** na vrstici naj bo **gumb**, ki pove, od kod se podatki črpajo. Namen je pokrit, predlagana izvedba ni enaka. |
| **Skupina – delno pokrito:** Primož naj pojasni, na podlagi česa se polni `md_verzije_modeli.skupina`. | **Skupina:** ali je »Skupina« tisti gumb, ki pove vir transakcij? Dokument ne ohrani izrecnega vprašanja o povezavi skupine z virom. |
| **Fiktivne prodaje – splošno vprašanje pokrito:** za odgovor o črpanju počakati Primoža. Črpanje za MN in fiktivne transakcije je tudi tema za naslednjič. | **Fiktivne prodaje:** kako se določa njihovo črpanje? |
| null | **Atribut Fiktivne – manjka:** ali črpanje določa logični atribut »Fiktivne«? |
| **Model brez transakcij – neskladje:** naveden je **PPL_NAJ**, pri katerem se transakcije ne dodajo in izračunajo. | **Modela brez transakcij:** **PPP_NAJ in PPP_MN** imata `0` transakcij kljub uspešnemu uvozu. Imena modelov se razlikujejo; uspešen uvoz ni izrecno naveden v dokumentu. |
| **Filter:** PPL_NAJ nima transakcij, ker filter ne zajame zapisov v `pp_np_trans`. Predlagan je filter: `dat_pri >= '2020-01-01' AND dat_pri <= '2025-01-01' AND model_posla = 'PPL' AND vrsta_posla IN (1) AND sestava = 1 AND ef_najem > 0 AND (obrat_str = FALSE OR obrat_str IS NULL) AND (cas_najema = 2 OR (cas_najema = 1 AND trajanje >= 6)) AND status_pregleda = 1`. Ta vrne nekaj transakcij. Preveriti in sporočiti pravilne filtre za `_NAJ` in `_MN`. | null |
| **Posel 894728 – pokrito:** v ISAM-u prostor **99**, v GV **3 – Poslovni prostor**; v migraciji na strani GURS je vrednost pravilna. Preveriti, kje pride do težave. | **Posel 894728:** prostor 99 namesto 3 – Poslovni prostor v GV. Pri Meliti je v migraciji pravilno; težava je po zapiskih nekje pri nas. |
| **PPP, desna vrednost – neskladje:** veliko transakcij ima desno vrednost enačbe **`null`**, ker je `velikost` prazna; preveriti napako. | **PPP, desna vrednost:** po preračunu ima veliko transakcij desno vrednost **`0`**, povsod je `velikost` enaka `null`. Razlika `0` / `null` ostaja. |
| **Povezava s prostorom 99 – pokrito kot domneva:** težava bi lahko bila povezana s prostorom 99 oziroma migracijo podatka iz GV. | **Povezava s prostorom 99:** zapiski povezavo z manjkajočo velikostjo navajajo trdilno. Dokument jo ustrezno ločuje kot možnost, ki jo je treba preveriti. |
| **Redukcija na karti – pokrito:** prikaz transakcij se ne sme reducirati pri manjšem merilu; zmanjšanje števila oznak ni ustrezno, ker je pomembno videti, kje jih je največ. | **Redukcija na karti:** brez redukcije na sloju; videti je treba vse transakcije, tudi pri »višjem zoom-u«. |
| null | **Zmogljivost točkovnega sloja – manjka:** po zapiskih prikaz vseh točk načeloma ne bi smel povzročiti sesutja aplikacije. To je ocena iz zapiskov, ne preverjeno dejstvo. |
| **Velikost pik glede na merilo – prvotna želja je zdaj pokrita:** dokument izrecno navede prvotno željo, da se absolutna velikost pik/zvezd skalira z merilom, in pomislek, da na pogledu cele karte transakcije ne bi bile vidne. | **Velikost pik glede na merilo:** velikost naj bo vedno v merilu, tako da se glede na objekte na karti pri približevanju in oddaljevanju ne spreminja. |
| **Razdelan predlog prikaza:** oznake stalne velikosti se pri oddaljevanju zlijejo v ploskev. Predlagano je prilagajanje velikosti v pikslih stopnji približave, da ostanejo manjše, a vidne. Potrebna je uskladitev izvedljivosti z razvijalci in sprejemljive rešitve z GURS. | null |
| **Labele:** velikost label naj se prilagaja merilu; odgovor ni zapisan. | null – zapiski govorijo o pikah oziroma simbolih transakcij, ne izrecno o besedilnih labelah. |
| **PPL in geometrija:** sloj ne prikazuje transakcij, ker zapisi PPL v `md_trans` nimajo geometrije; napako bodo odpravili. Transakcije naj bodo prikazane pri vseh verzijah modelov, ki jih vključujejo. | null |
| **Delovno coniranje:** upoštevati filter »Delovna coniranje« = `True` in ustrezno nastaviti `md_verzije_modeli.delovna`. | null |
| null | **Drugi modeli – manjka:** »Pri drugih modelih baje transakcije ok.« Zapiski ne določajo, na kateri vidik delovanja se opomba nanaša. |
| **Drugi TAO – splošno vprašanje pokrito:** tema za naslednjič – kaj je in kako deluje. | **Drugi TAO:** kako deluje zastavica? |
| null | **Drugi TAO, podrobnosti – manjka:** ali bosta dva vnosa na tem sloju? Z Gašperjem ne vesta, kakšne so želje naročnika. |
| **Obratovalni stroški – pokrito:** napačne vrednosti v 3D tabeli gradnikov faktorja obratovalnih stroškov; v bazi so pravilne. Posnetek približno pri **1 h 20 min**. | **Obratovalni stroški:** napačne številke v tabeli v stranskem panelu; prikazano na posnetku približno pri **1 h 20 min**. Zapiski ne vsebujejo potrditve pravilnosti podatkov v bazi. |
| **Filtriranje za testiranje – delno pokrito:** možnost filtriranja transakcij, ki imajo določene vrednosti iz enačbe že v osnovi izpolnjene. | **Filtriranje za testiranje:** kako preveriti npr. **`v_gar` ali `povrsina_dp`**, če ni mogoče poiskati transakcij, ki imajo ti vrednosti izpolnjeni? Splošna zahteva je pokrita; konkretna primera manjkata. |
| null | **JSON in filtriranje – manjka:** na »vmesni?izr« je samo JSON, po katerem ni mogoče filtrirati. Poimenovanje je v zapiskih negotovo. |
| **Obvestili pri izdelavi poročila:** obvestilo ob začetku in koncu procesa. | null |
| **Zaklep gumba – pokrito:** zaklep ob kliku generiranja poročila o modelu. | **Poročilo o modelih:** zaklep gumba. |
| **DOCX – povezana tema:** poročila o modelu naj bodo DOCX namesto PDF; večja sprememba, odločitev naknadno in tema za naslednjič. | **DOCX:** ali se da s **Quartom neposredno v DOCX**? Želeni format je pokrit, konkretno vprašanje o orodju Quarto manjka. |
| **Kopiranje sheme – verjetno ujemanje, preveriti pomen:** v kopiranje med verzijami modelov dodati atribut **barvne sheme**. | **Kopiranje sheme:** »Analiza napake shema polje dodat v kopiranju modelov.« Ni izrecno navedeno, da gre za barvno shemo; preveriti, ali je mišljeno isto polje in ali je povezava z analizo napake dovolj jasno zapisana. |
| **PPL 192 – pokrito:** v poročilu o analizi napake za model PPL 192 je tabela dejanskih rab prazna. | **PPL 192:** ni dejanskih rab v analizi napake. |
| **Nejasna dodatna primerjava:** »Za PPL so pravilno navedene.« Ker je pred tem prav tako naveden PPL (192), ni jasno, s katerim modelom oziroma verzijo se primerja. | null |
| **Dokumentacija `f_cpt` – vsebina pokrita, umestitev se razlikuje:** za skripte umerjanja ČPT opisati deljenje s trenutnim `f_cpt`, da dobimo osnovne vrednosti leve strani transakcije. | **Dokumentacija `f_cpt`:** v dokumentaciji **gradnje enačb pri analizi napake** pojasniti, kako se `f_cpt` »odbije«. Dokument konkretizira operacijo kot deljenje, vendar ne ohrani izrecne umestitve v dokumentacijo gradnje enačb pri analizi napake. |
| **Izločanje osamelcev – pokrito:** dokumentirati, kako iz dataframe-a izločiti osamelce po razmerju `leva/desna` oziroma `index_c/index_v`. | **Izločanje osamelcev:** pokazati, kako iz dataframe-a odstraniti osamelce, npr. kadar je `leva/desna` večje od določenega praga. |
| null | **Interpolacija/ekstrapolacija ČPT in SFC – manjka:** »Interpolacija/ekstrapolacija ČPT? SFC ne dela?« Iz zapiskov ni jasno, kaj točno ne deluje; ohraniti kot odprto vprašanje. |

## Kaj še ostaja

Posodobljeni dokument pokriva bistveno več zapiskov: kode prostorov in pravilnost migracije na strani GURS, možno povezavo s prostorom 99, prvotno željo glede velikosti pik, čas na posnetku, zaklep gumba, manjkajoče dejanske rabe pri PPL 192 ter dokumentacijo `f_cpt` in izločanja osamelcev.

**Še vedno ne vsebuje vsega.** Za dopolnitev oziroma razjasnitev ostajajo:

- **Neskladji:** PPL_NAJ proti PPP_NAJ in PPP_MN; desna vrednost `null` proti `0`.
- **Manjkajoča vprašanja:** vpliv atributa Fiktivne na črpanje; dva vnosa pri Drugem TAO in nejasne želje naročnika; neposredni izvoz iz Quarta v DOCX; interpolacija/ekstrapolacija ČPT in težava s SFC.
- **Podrobnosti testiranja:** primera `v_gar` in `povrsina_dp` ter omejitev filtriranja po JSON-u.
- **Dodatne opombe:** transakcije pri drugih modelih naj bi bile v redu; ocena zmogljivosti točkovnega sloja.
- **Natančnost formulacij:** gumb proti atributu za prikaz vira; povezava Skupine z virom; ali je polje sheme pri analizi napake res barvna shema; kam sodi dokumentacija `f_cpt`; na kateri model/verzijo se nanaša »Za PPL so pravilno navedene«.

Navedbe, da GURS-ova migracija vsebuje pravilno vrednost, in domneve o napaki migracije iz GV ni treba razumeti kot neposredno protislovje: dokument pa naj jasno pove, da mesto napake v prenosu podatkov še ni ugotovljeno.
