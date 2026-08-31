Zadeva: Nova verzija LIFT-a 9.6.9

Pozdravljeni,

danes bomo na testno okolje naložili novo verzijo LIFT-a 9.6.9.

Prosili bi vas, da omenjene spremembe potestirate in potrdite njihovo ustreznost, nato pa jih bomo naložili tudi na produkcijo.
Po omenjenem postopku morajo potekati naložitve novih verzij, ko je sistem v produkcijski uporabi, zato bi s tem pristopom začeli že zdaj, da bomo na obeh straneh vanj utečeni.

V verziji so vključeni popravki prijavljenih napak, optimizacije in dogovorjene nadgradnje za projekt ISAM ter splošne izboljšave LIFT-a. V nadaljevanju so navedena dela, zaključena oziroma posodobljena od 18. 8. 2026 dalje. Manjši popravki so vodeni na Jiri.

Opravljena razvojna dela (D – dorazvoj, B – napaka):

- MD – B – Odpravljene so napake pri rezanju območij in spreminjanju zapisov v križni tabeli `md_geo_obmxcone` (pravilno shranjevanje imena območja in posodobitev geometrije cone). ([GMS-5715](https://flycomtech.atlassian.net/browse/GMS-5715), [GMS-5713](https://flycomtech.atlassian.net/browse/GMS-5713), [GMS-5710](https://flycomtech.atlassian.net/browse/GMS-5710), [GMS-5708](https://flycomtech.atlassian.net/browse/GMS-5708))
- MD – D – Izboljšana je hitrost kontrole faktorja obnove. ([GMS-5679](https://flycomtech.atlassian.net/browse/GMS-5679))
- MD – D – Posodobljena je tabela novogradenj in pripadajoča migracija. ([GMS-5536](https://flycomtech.atlassian.net/browse/GMS-5536))
- MD – B – Odpravljena je napaka pri izdelavi poročila analize napake in nedostopnosti poročil. ([GMS-5437](https://flycomtech.atlassian.net/browse/GMS-5437), [GMS-5725](https://flycomtech.atlassian.net/browse/GMS-5725))
- MD – D – Pohitritev preračuna dodatnega m2 in kontrol ob vnosu osnove v relacijsko tabelo. ([GMS-5695](https://flycomtech.atlassian.net/browse/GMS-5695))
- MD – D – Zaključeno je testiranje izračuna in zapisa ČPT (7. in 8. poglavje). ([GMS-5594](https://flycomtech.atlassian.net/browse/GMS-5594))
- PEV – B – Odpravljena je napaka ob generiranju izpisa »Informacija o obsegu«. ([GMS-5675](https://flycomtech.atlassian.net/browse/GMS-5675))
- PEV – B – Odpravljena je napaka pri relativnem položaju oznak PEV na karti. ([GMS-5212](https://flycomtech.atlassian.net/browse/GMS-5212))
- POSLI – D – Pri dodajanju enote v posel ali podposel se lahko prevzamejo podatki iz katastra nepremičnin. ([GMS-5727](https://flycomtech.atlassian.net/browse/GMS-5727))
- LIFT – B – Ob kliku na vrstico atributne tabele v administraciji ne pride do nepotrebnega osveževanja. ([GMS-5602](https://flycomtech.atlassian.net/browse/GMS-5602))
- LIFT – D – Dodana je možnost izdelave Quarto poročil znotraj sistema LIFT. ([GMS-5031](https://flycomtech.atlassian.net/browse/GMS-5031))

V primeru nepravilnosti nas prosimo obvestite prek Jire, da jih lahko čim prej preverimo in odpravimo.

