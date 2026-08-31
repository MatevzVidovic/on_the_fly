Zadeva: Nova verzija LIFT-a 9.6.9

Pozdravljeni,

danes bomo na produkcijsko in testno okolje naložili novo verzijo LIFT-a 9.6.9.

V verziji so vključeni popravki prijavljenih napak, optimizacije in dogovorjene nadgradnje za projekt ISAM ter splošne izboljšave LIFT-a. V nadaljevanju so navedena dela, zaključena oziroma posodobljena od 18. 8. 2026 dalje. Manjši popravki so vodeni na Jiri.

Opravljena razvojna dela (D – dorazvoj, B – napaka):

- MD – B – Odpravljene so napake pri rezanju območij in spreminjanju zapisov v križni tabeli `md_geo_obmxcone` (pravilno shranjevanje imena območja in posodobitev geometrije cone).
- MD – D – Izboljšana je hitrost kontrole faktorja obnove.
- MD – D – Posodobljena je tabela novogradenj in pripadajoča migracija.
- MD - D / B - Pohitritev izdelave poročila analize napake za večje modele, odprava napake nedostopnosti poročil.
- MD - D - Pohitritev preračuna dodatnega m2 in kontrol ob vnosu osnove v relacijsko tabelo.
- MD - D - Razvojno okolje za izvajanje umerjanja ČPT je prilagojeno vzporedni uporabi.
- PEV – B – Odpravljena je napaka ob generiranju izpisa »Informacija o obsegu«.
- PEV – B – Odpravljena je napaka pri relativnem položaju oznak PEV na karti.
- PEV – B – Odpravljene so napake pri funkcijah verzij modelov PEV.
- PEV – B – Pri izračunu vrednosti PEV se v primeru podvojenih poslovnih podatkov uporabi ustrezen zapis, uporabnik pa je o tem obveščen.
- POSLI – D – Pri dodajanju enote v posel ali podposel se lahko prevzamejo podatki iz katastra nepremičnin.
- POSLI – D – Avtomatska nastavitev sestave poslov je ob sprotnem posodabljanju prilagojena upoštevanju preglednikove nastavitve.
- LIFT – B – Ob kliku na vrstico atributne tabele v administraciji ne pride do nepotrebnega osveževanja.
- LIFT - D - Dodana je možnost izdelave Quarto poročil znotraj sistema LIFT s splošnimi bralnimi SQL poizvedbami. 

V primeru nepravilnosti nas prosimo obvestite prek Jire, da jih lahko čim prej preverimo in odpravimo.


Best regards / Lep pozdrav

[podpis]
