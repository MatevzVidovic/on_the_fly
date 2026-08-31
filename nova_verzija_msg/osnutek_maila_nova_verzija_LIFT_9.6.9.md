Zadeva: Nova verzija LIFT-a 9.6.9

Pozdravljeni,

danes bomo na produkcijsko in testno okolje naložili novo verzijo LIFT-a 9.6.9.

V verziji so vključeni popravki prijavljenih napak, optimizacije in dogovorjene nadgradnje za projekt ISAM ter splošne izboljšave LIFT-a. Manjši popravki so vodeni na Jiri.

Opravljena razvojna dela (D – dorazvoj, B – napaka):

- MD – B – Odpravljene so napake pri rezanju območij, shranjevanju imena območja ter posodabljanju geometrije con in križne tabele »MD – Območja x Cone«.
- MD – B/D – Odpravljene so napake pri množičnem niveliranju, vrednostnih tabelah, faktorjih in kopiranju verzij modelov oziroma območij. Izboljšana je tudi hitrost preračunov faktorja obnove in množičnega niveliranja.
- MD – D – V informacijski prikaz je prestavljen zavihek vrednostnih tabel; dodani so podatki fonda v cone ter usklajene spremembe podatkovnega modela in dokumentacije.
- PEV – B – Odpravljene so napake pri izpisu informacij o obsegu, prikazu oznak na karti in v GIS pogledu, funkcijah verzij modelov ter pri izračunu vrednosti.
- PEV – D – Produkti so po novem vezani na verzijo modela. Temu so prilagojene funkcionalnosti za kopiranje in brisanje verzij modela, generiranje parametrov, izračun vrednosti in izvoz XML. Pri izračunu se v primeru podvojenih poslovnih podatkov uporabi ustrezen zapis, uporabnik pa je o tem obveščen.
- POSLI – D – Pri dodajanju enote v posel ali podposel se lahko prevzamejo podatki iz katastra nepremičnin. V funkcionalnost za polnjenje historiata najemov je dodan atribut `vrsta_posla_etn`, dopolnjeno pa je tudi avtomatsko razvrščanje poslov.
- POSLI – D – Dodana sta sloja s podatki upravnih aktov za točke in parcele. Podatki se pridobivajo iz storitve WFS in se bodo samodejno posodabljali.
- LIFT – B – Odpravljene so napake pri prikazu zavihka rezultatov in atributnih polj, prikazu vrednosti iz lookupov, osveževanju atributne tabele v administraciji ter pravicah za hitro urejanje.
- LIFT – D – Dodan je uvoz začasnih slojev v LIFT. Uporabnik lahko sloj uvozi prek orodja na karti in ga uporablja v okviru svoje prijave oziroma seje.

Večje nadgradnje:

- Prenovljene so vnosne forme in nastavitve atributnih polj. Podprto je centralno nastavljanje privzetih vrednosti in urejanje nastavitev polj prek obrazca.
- Pravila za zaklepanje atributnih polj so prenovljena na princip dovoljenih polj (whitelist), kar omogoča jasnejše upravljanje urejanja podatkov.
- Poročila se lahko obdelujejo tudi s procesorjem Quarto. Nadaljuje se tudi prenova oblikovalnika poročil, ki bo na voljo kot administrativno orodje.
- Dodana je osnova za upravljanje geofence območij in pripadajočih pravic.

V primeru nepravilnosti nas prosimo obvestite prek Jire, da jih lahko čim prej preverimo in odpravimo.


Best regards / Lep pozdrav

[podpis]
