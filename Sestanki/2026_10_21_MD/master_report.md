# Skupno poročilo sestankov MD – 13., 20. in 21. oktober 2026


## 13. oktober 2026 – pregled zadev s prejšnjega sestanka

### 1. Potrditev zadev z VO

*Izvor: 13.md – »Potrditev zadev z VO«.*

- **Naš odgovor:** Obravnavana je bila potrditev zadev z VO. Podrobnejši sklep oziroma status posameznih zadev v zapiskih ni naveden.

### 2. Posplošitev izjeme za model HIS

*Izvor: 13.md – »Generaliziranje izjeme HIS (opis)«.*

- **Naš odgovor:** Posplošitev izjeme za model HIS je potrjena.

### 3. Pregled funkcionalnosti v TVR in dopolnitev dokumentacije

*Izvor: 13.md – »Pregled funkcionalnosti v TVR«.*

- **Naš odgovor:** Pregledali smo funkcionalnosti v TVR. Dokumentacijo je treba uskladiti z obravnavanimi funkcionalnostmi.
  - **Ticket – ustvariti: Posodobiti dokumentacijo funkcionalnosti v TVR na podlagi opravljenega pregleda.**

## 13. oktober 2026 – obravnavane teme

### 4. Pretvorba sestavljenih poslov v običajne podposle

*Izvor: 13.md – »Predlog pretvorbe sestavljenih poslov v običajne podposle«.*

- **Naš odgovor:** Predlog se obravnava kot možna poznejša nadgradnja po zagonu produkcije. Podrobnosti izvedbe v zapiskih niso opredeljene.

### 5. Uporaba pasivnih modelov in obravnava STZ

*Izvor: 13.md – »Pregled uporabe pasivnih modelov in obravnave STZ«.*

- **Naš odgovor:** Pregledali smo uporabo pasivnih modelov in obravnavo STZ. Dodatne spremembe ali naloge v zapiskih niso navedene.

### 6. Prikaz modela in verzije v obvestilu ob zagonu uvoza transakcij

*Izvor: 13.md – »Pri uvozu transakcij … na obvestilu za zagon … verzijo in model«.*

- **Naš odgovor:** Obvestilo ob zagonu uvoza transakcij je treba dopolniti s podatkoma o modelu in njegovi verziji, da bo jasno, na kateri uvoz se nanaša.
  - **Ticket – ustvariti: V obvestilo ob zagonu uvoza transakcij dodati model in verzijo modela.**

### 7. Posodabljanje statistik transakcij pri sprotnem niveliranju

*Izvor: 13.md – »Sprotno niveliranje«.*

- **Naš odgovor:** Ob spremembi številke vrednostne ravni na coni se statistike transakcij na tej coni ne posodobijo. Napako je treba odpraviti.
  - **Ticket – ustvariti: Zagotoviti posodobitev statistik transakcij na coni ob spremembi številke vrednostne ravni pri sprotnem niveliranju.**

### 8. Filtriranje po polju »Modeli« z regularnimi izrazi

*Izvor: 13.md – »Polje Modeli«; dopolnitev: 21.md – »Filtriranje transakcij v sql_filter glede na ‘Modeli’ na podlagi RegEx«.*

- **Naš odgovor:** Pregledali smo filtriranje različnih kombinacij modelov podposlov z regularnimi izrazi, obravnavo polja »Modeli« pri migraciji poslov in vrstni red zapisa modelov. Za model HIS smo pripravili naslednji primer regularnega izraza:

  ```regex
  /^HIS[(]1[)](, (STZ|KME|GAR|GOZ|KDS)[(][0-9]+[)])*$/gm
  ```

  - **Ticket – ustvariti: Dokumentacijo za `sql_filter` dopolniti z opisom filtriranja po polju »Modeli« in pripravljenim primerom regularnega izraza za HIS.**

### 9. Obravnava manjkajoče vrednosti spremenljivke `tip_stavbe` pri poslih TUR

*Izvor: 13.md – »Dodajanje logike na spremenljivkah namesto na faktorjih«.*

- **Naš odgovor:** Obravnavali smo možnost vključitve dodatne logike na ravni spremenljivk namesto na ravni faktorjev. Pri poslu TUR, ki se obravnava po modelu HIS, izvorna vrednost `tip_stavbe` ni na voljo, zato je treba opredeliti njeno obravnavo v vrednostni enačbi. Končna rešitev v zapiskih še ni določena.

### 10. Dostop do podatkovne baze samo za branje

*Izvor: 13.md – »Readonly dostop do baze … preverjanje filtriranja ‘KP Trans’«; dopolnitev: 21.md – povezovanje na predprodukcijsko in produkcijsko bazo prek pgAdmin 4.*

- **Naš odgovor:** Obravnavali smo dostop do baze samo za branje za preverjanje filtriranja »KP Trans«. Na sestanku 21. oktobra smo izvedli povezovanje s predprodukcijsko in produkcijsko bazo z uporabniki, ki imajo pravice samo za branje. V pgAdmin 4, različica 9.18, je treba med parametri povezave nastaviti:
  - `GSS encryption mode (gssencmode): disabled`.

## 20. oktober 2026 – obravnavane teme

### 11. Iskanje transakcij po vrednostih vmesnega izračuna in prikaz na karti

*Izvor: 20.md – poizvedovanje po vrednostih spremenljivk v »MD vmesni izračun (JSON)«; dopolnitvi: 21.md – materializirani pogled za prikaz faktorjev in spremenljivk ter zadnja točka o drevesnem prikazu in filtriranju JSON.*

GURS želi poiskati transakcije glede na nabor vrednosti spremenljivk iz vmesnega izračuna ter jih prikazati na karti.

- **Naš odgovor:** Za iskanje in prikaz so bile obravnavane naslednje možnosti:
  - Za začetni pristop uporabimo poizvedbo SQL z dostopom samo za branje, pridobimo nabor ID-jev zapisov v »MD Trans« in ta nabor uporabimo v filtru na splošnem sloju »MD Trans«.
  - V drevesnem prikazu vmesnega izračuna JSON je mogoče pregledati nadrejeno transakcijo. Pri filtriranju vmesnega izračuna lahko uporabimo filter vsebovanja, pri čemer ime spremenljivke prekopiramo iz obstoječega zapisa. Za filtriranje po naboru vrednosti posamezne spremenljivke je treba pripraviti poizvedbo na bazi s filtriranjem JSON ali z regularnim izrazom.
  - Za preglednejše delo pripravimo primer materializiranega pogleda (MV) za eno verzijo modela. Pogled poveže polje vrednosti v vmesnem izračunu s poljem ključev v `md_verzije_modeli`, tako da so faktorji in spremenljivke prikazani kot stolpci. Pogled se uporabi tudi kot sloj na karti, kar omogoča filtriranje po vrednostih stolpcev in prostorski prikaz izbranih transakcij.
  - Pripravljeni primer bo GURS uporabil kot zgled za pripravo pogledov za druge verzije modelov.
  - **Ticket – ustvariti: Dopolniti dokumentacijo s postopkom filtriranja transakcij po vrednostih vmesnega izračuna ter prikaza izbranega nabora na splošnem sloju »MD Trans«.**
  - **Ticket – ustvariti: Pripraviti primer materializiranega pogleda za eno verzijo modela, ki faktorje in spremenljivke prikaže kot stolpce ter omogoča uporabo pogleda kot sloja na karti.**

### 12. Rezanje območij in prenos povezav na cone

*Izvor: 20.md – »Pregled sprememb v izvedbi rezanja območij«; dopolnitev: 21.md – »Naredit ticket za clipping … povezave na vse cone«.*

- **Naš odgovor:** Pregledali smo spremembe pri rezanju območij. Dodatno je treba omogočiti, da novo območje prevzame povezave na vse cone, ki jih je imelo izbrano obstoječe območje. Predlagana rešitev je delovni postopek, v katerem uporabnik po zapolnitvi vrzeli z novim območjem na karti izbere referenčno območje, iz katerega se prekopirajo povezave območje–cona (`obmxcone`). Podrobnosti izvedbe je treba še opredeliti.
  - **Ticket – ustvariti: Omogočiti kopiranje povezav `obmxcone` z izbranega referenčnega območja na novo območje v postopku rezanja oziroma zapolnjevanja vrzeli; pri pripravi rešitve preveriti opisani delovni postopek z izbiro območja na karti.**

### 13. Zagotavljanje oglišč na tromejah območij

*Izvor: 20.md – »Sprotno zagotavljanje ogljišč na tromejah območij«.*

- **Naš odgovor:** Obravnavali smo potrebo po sprotnem zagotavljanju oglišč na tromejah območij. Območje je lahko topološko pravilno tudi brez izrecnega oglišča na tromeji, če ta leži na daljici med njegovima obstoječima ogliščema. Po izkušnjah GURS lahko pri prenosu v Oracle zaradi zaokroževanja ali spremembe številskega zapisa nastanejo topološke napake. Zahteva je zato, da se na takih mestih zagotovi izrecno oglišče.
  - Ticket: Pri GURS je že ustvarjen; oznaka v zapiskih ni navedena.

### 14. Dodatni sloji con in transakcij na karti modeliranja

*Izvor: 20.md – »Dodatni sloji con in transakcij za vsak model na karti modeliranje«.*

GURS želi dodatne sloje, na katerih bi modelar za posamezen model določil začasne filtre, predvsem za starejše verzije modela.

- **Naš odgovor:** Predlagali smo uporabo obstoječih splošnih slojev za nastavljanje začasnih filtrov. GURS je kljub temu izrazil potrebo po dodatnih slojih; zahteva ni nujna. Dokončna odločitev o izvedbi v zapiskih ni navedena.
  - Ticket: Pri GURS je že ustvarjen; oznaka v zapiskih ni navedena.

## 21. oktober 2026 – dodatne teme

Povezovanje z bazo je vključeno v točko 10, dopolnitev primera regularnega izraza v točko 8, prenos povezav na cone v točko 12, materializirani pogled in filtriranje vmesnega izračuna pa v točko 11. Preostale teme sledijo izvornemu vrstnemu redu.

### 15. Pravila filtriranja transakcij iz `pp_kp_trans`

*Izvor: 21.md – »Pregled filtriranja pp_kp_trans … na podlagi sql_filter«.*

- **Naš odgovor:** Pregledali smo filtriranje transakcij iz `pp_kp_trans` na podlagi pogoja `sql_filter`, zapisanega v `md_verzije_modeli`. Pri tem je treba upoštevati tudi naslednji pravili:
  - Poleg pogoja `sql_filter` se izločijo transakcije s podposli, katerih tip ni opredeljen med pasivnimi modeli.
  - Določiti je treba enoten presečni datum. V nasprotnem primeru postopek prenosa (`lift`) za isti ID posla prevzame eno transakcijo, preostale pa izloči.
  - **Ticket – ustvariti: Dokumentacijo filtriranja iz `pp_kp_trans` dopolniti s pravilom izločanja transakcij glede na tipe podposlov v pasivnih modelih ter z zahtevo po enotnem presečnem datumu in opisom posledic neustreznega filtra.**

### 16. Materializirani pogled za primerjavo razlik

*Izvor: 21.md – »MV za diff mi ne delamo«.*

- **Naš odgovor:** Materializiranega pogleda za primerjavo razlik ne bomo pripravljali. GURS ga lahko pripravi samostojno.

### 17. Privzeto sočasno urejanje več geometrij

*Izvor: 21.md – »Privzeto urejanje več geometrij hkrati«.*

- **Naš odgovor:** Privzetega sočasnega urejanja več geometrij ne omogočimo.

### 18. Prikaz oglišč

*Izvor: 21.md – »Ogljišča prikazovanje«.*

- **Naš odgovor:** Funkcionalnost prikaza oglišč trenutno ni na voljo. Nadaljnja izvedba v zapiskih ni dogovorjena.
