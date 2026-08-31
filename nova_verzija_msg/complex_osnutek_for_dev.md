# Kontrolni seznam za osnutek e-maila LIFT 9.6.9

Ta dokument povezuje posamezne vnose v `osnutek_maila_nova_verzija_LIFT_9.6.9.md` z Jira nalogami. Vključene so **samo naloge, posodobljene 18. 8. 2026 ali pozneje**. Namenjen je preverjanju besedila pred pošiljanjem.

## Opravljena razvojna dela

| Vnos v e-mailu | Povezane Jira naloge | Kaj preveriti |
| --- | --- | --- |
| MD – rezanje območij in zapis v `md_geo_obmxcone` | [GMS-5715](https://flycomtech.atlassian.net/browse/GMS-5715) – 31. 8. | — |
| merged MD – shranjevanje imena območja | [GMS-5713](https://flycomtech.atlassian.net/browse/GMS-5713) – 31. 8. | — |
| merged MD – geometrija cone po spremembi križne tabele | [GMS-5710](https://flycomtech.atlassian.net/browse/GMS-5710) – 27. 8. | — |
| merged MD – posodobitev stare cone | [GMS-5708](https://flycomtech.atlassian.net/browse/GMS-5708) – 27. 8. | — |
| MD – hitrost kontrole faktorja obnove | [GMS-5679](https://flycomtech.atlassian.net/browse/GMS-5679) – 26. 8. | — |
| skipped MD – vrednostne tabele v info prikazu | [GMS-5633](https://flycomtech.atlassian.net/browse/GMS-5633) – 26. 8. | — |
| skipped MD – fond v conah | [GMS-5415](https://flycomtech.atlassian.net/browse/GMS-5415) – 25. 8. | Potrdi nalaganje v ciljna okolja. |
| MD – tabela novogradenj in migracija | [GMS-5536](https://flycomtech.atlassian.net/browse/GMS-5536) – 26. 8. | Potrdi izvedbo migracije. |
| PEV – izpis informacij o obsegu | [GMS-5675](https://flycomtech.atlassian.net/browse/GMS-5675) – 26. 8. | — |
| PEV – relativni položaj oznak na karti | [GMS-5212](https://flycomtech.atlassian.net/browse/GMS-5212) – 26. 8. | — |
| merged PEV – oznake v GIS pogledu | [GMS-5192](https://flycomtech.atlassian.net/browse/GMS-5192) – 26. 8. | — |
| PEV – funkcije verzij modelov | [GMS-5535](https://flycomtech.atlassian.net/browse/GMS-5535) – 18. 8. | — |
| PEV – podvojeni poslovni podatki pri izračunu | [GMS-5225](https://flycomtech.atlassian.net/browse/GMS-5225) – 20. 8. | Potrdi logiko izbire zapisa. |
| in prev release already PEV – produkti po verziji modela | [GMS-5185](https://flycomtech.atlassian.net/browse/GMS-5185) – produkti so vezani na verzijo modela (18. 8.) | Ali je sprememba za uporabnike že vidna oziroma zahteva navodilo. |
| POSLI – prevzem podatkov enote iz KN | [GMS-5727](https://flycomtech.atlassian.net/browse/GMS-5727) – 26. 8. | — |
| prev release POSLI – sestava poslov | [GMS-5393](https://flycomtech.atlassian.net/browse/GMS-5393) – 18. 8. | Ali vključiti podrobnosti spremembe. |
| irrelevant for gurs LIFT – zavihek rezultatov in atributna polja | [GMS-5747](https://flycomtech.atlassian.net/browse/GMS-5747) – 26. 8. | — |
| irrelevant for gurs LIFT – lookupi v atributni tabeli | [GMS-5104](https://flycomtech.atlassian.net/browse/GMS-5104) – 26. 8. | — |
| LIFT – osveževanje atributne tabele v administraciji | [GMS-5602](https://flycomtech.atlassian.net/browse/GMS-5602) – 26. 8. | — |

## Večje nadgradnje

| Vnos v e-mailu | Povezane Jira naloge | Kaj preveriti |
| --- | --- | --- |
| Procesor Quarto za poročila | [GMS-5031](https://flycomtech.atlassian.net/browse/GMS-5031) – 26. 8. | Ali je pripravljen za splošno uporabo ali le za administracijo/testiranje. |
| Dokumentacija v orodju »Pomoč« | [GMS-5629](https://flycomtech.atlassian.net/browse/GMS-5629) – dokumentacija po modulih ter prenos datoteke/modula (31. 8.) | Potrdi, katere datoteke so naložene in ali je omogočen prenos celotnega modula. |

## Zaključene naloge po 18. 8., ki niso izrecno omenjene

Naslednje naloge so v priloženih izvozih posodobljene v izbranem obdobju, vendar jih osnutek ne izpostavlja, ker so tehnične, testne ali preveč podrobne za obvestilo uporabnikom:
 [GMS-5698](https://flycomtech.atlassian.net/browse/GMS-5698) – omejitev virov roadrunnerja; 
 [GMS-5724](https://flycomtech.atlassian.net/browse/GMS-5724) – vnos neporočanj; 
 [GMS-5594](https://flycomtech.atlassian.net/browse/GMS-5594), 
 [GMS-5438](https://flycomtech.atlassian.net/browse/GMS-5438), 
 [GMS-5717](https://flycomtech.atlassian.net/browse/GMS-5717) – testiranje; 
 [GMS-5437](https://flycomtech.atlassian.net/browse/GMS-5437) – analiza prekinjene poizvedbe; 
 [GMS-5725](https://flycomtech.atlassian.net/browse/GMS-5725) – dostopnost S3 za poročila; 
 [GMS-5695](https://flycomtech.atlassian.net/browse/GMS-5695) – optimizacija preračuna m² v RT; 
 [GMS-5726](https://flycomtech.atlassian.net/browse/GMS-5726) – vizualni popravki modala; 
 [GMS-5501](https://flycomtech.atlassian.net/browse/GMS-5501) – preverjanje arhiviranja Temporal; 
 [GMS-5557](https://flycomtech.atlassian.net/browse/GMS-5557) – šifriranje Barman varnostnih kopij.
