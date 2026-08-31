Zadeva: Nova verzija LIFT-a 9.6.9

Pozdravljeni,

danes bomo na produkcijsko in testno okolje naložili novo verzijo LIFT-a 9.6.9.

V verziji so vključeni popravki prijavljenih napak, optimizacije in dogovorjene nadgradnje za projekt ISAM ter splošne izboljšave LIFT-a. V nadaljevanju so navedena dela, zaključena oziroma posodobljena od 18. 8. 2026 dalje. Manjši popravki so vodeni na Jiri.

Opravljena razvojna dela (D – dorazvoj, B – napaka):

- MD – B – Odpravljena je napaka pri rezanju območij in dodajanju zapisa v križno tabelo `md_geo_obmxcone`.
- MD – B – Odpravljena je napaka pri shranjevanju imena območja.
- MD – B – Odpravljena je napaka pri posodabljanju geometrije cone po spremembi križne tabele.
- MD – B – Odpravljena je napaka pri posodobitvi stare cone v tabeli »MD – Območja x Cone«.
- MD – D – Izboljšana je hitrost kontrole faktorja obnove.
- MD – D – Zavihek vrednostnih tabel je prestavljen v informacijski prikaz.
- MD – D – V cone so dodani podatki fonda.
- MD – D – Posodobljena je tabela novogradenj in pripadajoča migracija.
- PEV – B – Odpravljena je napaka pri izpisu »Informacije o obsegu«.
- PEV – B – Odpravljena je napaka pri relativnem položaju oznak zapisov na karti.
- PEV – B – Odpravljen je nekonsistenten prikaz oznak PEV v GIS pogledu.
- PEV – B – Odpravljene so napake pri funkcijah verzij modelov PEV.
- PEV – B – Pri izračunu se v primeru podvojenih poslovnih podatkov uporabi ustrezen zapis, uporabnik pa je o tem obveščen.
- PEV – D – Produkti so po novem vezani na verzijo modela.
- POSLI – D – Pri dodajanju enote v posel ali podposel se lahko prevzamejo podatki iz katastra nepremičnin.
- POSLI – D – Dopolnjena je sestava poslov.
- LIFT – B – Odpravljena je napaka pri prikazu zavihka rezultatov in atributnih polj.
- LIFT – B – Odpravljena je napaka pri prikazu vrednosti iz lookupov v atributni tabeli.
- LIFT – B – Odpravljena je napaka pri osveževanju atributne tabele v administraciji.
- LIFT – D – Dodan je uvoz začasnih slojev v LIFT. Uporabnik lahko sloj uvozi prek orodja na karti in ga uporablja v okviru svoje prijave oziroma seje.

Večje nadgradnje:

- Podprto je centralno nastavljanje privzetih vrednosti atributnih polj.
- Dodano je urejanje nastavitev atributnih polj prek obrazca.
- Pravila za zaklepanje atributnih polj so prenovljena na princip dovoljenih polj (whitelist), kar omogoča jasnejše upravljanje urejanja podatkov.
- Poročila se lahko obdelujejo tudi s procesorjem Quarto.
- Oblikovalnik poročil se nadalje razvija kot administrativno orodje.
- Odpravljena je napaka pri prikazu komponent oblikovalnika poročil brez podatkov.
- Pripravljen je uporabniški vmesnik za geofence območja.
- V orodju »Pomoč« je dostopna uporabniška dokumentacija, urejena po modulih in datotekah. Posamezno datoteko oziroma dokumentacijo posameznega modula je mogoče prenesti.

V primeru nepravilnosti nas prosimo obvestite prek Jire, da jih lahko čim prej preverimo in odpravimo.


Best regards / Lep pozdrav

[podpis]
