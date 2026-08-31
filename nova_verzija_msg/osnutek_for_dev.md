# Kontrolni seznam za osnutek e-maila LIFT 9.6.9

Ta dokument povezuje posamezne vnose v `osnutek_maila_nova_verzija_LIFT_9.6.9.md` z Jira nalogami. Vključene so **samo naloge, posodobljene 18. 8. 2026 ali pozneje**. Namenjen je preverjanju besedila pred pošiljanjem.

## Opravljena razvojna dela

| Vnos v e-mailu | Povezane Jira naloge | Kaj preveriti |
| --- | --- | --- |
| MD – popravki rezanja območij in sinhronizacije con | [GMS-5715](https://flycomtech.atlassian.net/browse/GMS-5715) – rezanje območja in `md_geo_obmxcone` (31. 8.); [GMS-5713](https://flycomtech.atlassian.net/browse/GMS-5713) – shranjevanje imena območja (31. 8.); [GMS-5710](https://flycomtech.atlassian.net/browse/GMS-5710) – geometrija cone po spremembi križne tabele (27. 8.); [GMS-5708](https://flycomtech.atlassian.net/browse/GMS-5708) – posodobitev stare cone (27. 8.) | Ali so vsi štirje popravki v paketu 9.6.9. |
| MD – kontrole faktorja, informacijski prikaz, fond in novogradnje | [GMS-5679](https://flycomtech.atlassian.net/browse/GMS-5679) – hitrost kontrole faktorja obnove (26. 8.); [GMS-5633](https://flycomtech.atlassian.net/browse/GMS-5633) – vrednostne tabele v info prikazu (26. 8.); [GMS-5415](https://flycomtech.atlassian.net/browse/GMS-5415) – fond v conah (25. 8.); [GMS-5536](https://flycomtech.atlassian.net/browse/GMS-5536) – tabela novogradenj in migracije (26. 8.) | Ali so podatki fonda in migracija že naloženi v vseh ciljnih okoljih. |
| PEV – popravki prikaza, verzij modelov in izračuna | [GMS-5675](https://flycomtech.atlassian.net/browse/GMS-5675) – informacije o obsegu (26. 8.); [GMS-5212](https://flycomtech.atlassian.net/browse/GMS-5212), [GMS-5192](https://flycomtech.atlassian.net/browse/GMS-5192) – oznake PEV na karti (26. 8.); [GMS-5535](https://flycomtech.atlassian.net/browse/GMS-5535) – funkcije pri verzijah modelov (18. 8.); [GMS-5225](https://flycomtech.atlassian.net/browse/GMS-5225) – obravnava podvojenih poslovnih podatkov (20. 8.) | Potrdi logiko izbire zapisa pri podvojenih podatkih. |
| PEV – produkti po verziji modela | [GMS-5185](https://flycomtech.atlassian.net/browse/GMS-5185) – produkti so vezani na verzijo modela (18. 8.) | Ali je sprememba za uporabnike že vidna oziroma zahteva navodilo. |
| POSLI – dodajanje enot in sestava poslov | [GMS-5727](https://flycomtech.atlassian.net/browse/GMS-5727) – prevzem podatkov enote iz KN (26. 8.); [GMS-5393](https://flycomtech.atlassian.net/browse/GMS-5393) – sestava poslov (18. 8.) | Ali vključiti podrobnosti spremembe sestave poslov. |
| LIFT – rezultati, lookupi in administracija | [GMS-5747](https://flycomtech.atlassian.net/browse/GMS-5747) – zavihek rezultatov/atributna polja (26. 8.); [GMS-5104](https://flycomtech.atlassian.net/browse/GMS-5104) – lookup (26. 8.); [GMS-5602](https://flycomtech.atlassian.net/browse/GMS-5602) – osvežitev atributne tabele (26. 8.) | — |
| LIFT – uvoz začasnih slojev | [GMS-5325](https://flycomtech.atlassian.net/browse/GMS-5325) – uvoz začasnih slojev (31. 8.) | Potrdi podprte formate in omejitev na prijavo/sejo. |

## Večje nadgradnje

| Vnos v e-mailu | Povezane Jira naloge | Kaj preveriti |
| --- | --- | --- |
| Nastavitve atributnih polj | [GMS-5560](https://flycomtech.atlassian.net/browse/GMS-5560) – privzete vrednosti nad aplikacijskim slojem (31. 8.); [GMS-5549](https://flycomtech.atlassian.net/browse/GMS-5549) – add/edit forma za atributna polja (31. 8.) | Ali sta spremembi že dostopni GURS administratorjem. |
| Whitelist za zaklepanje atributnih polj | [GMS-5377](https://flycomtech.atlassian.net/browse/GMS-5377) – attribute field rules whitelisting (28. 8.) | Ali je potrebna prilagoditev obstoječih pravil. |
| Quarto in oblikovalnik poročil | [GMS-5031](https://flycomtech.atlassian.net/browse/GMS-5031) – Quarto processor (26. 8.); [GMS-5656](https://flycomtech.atlassian.net/browse/GMS-5656) – oblikovalnik poročil v administraciji (20. 8.); [GMS-4399](https://flycomtech.atlassian.net/browse/GMS-4399) – prikaz komponent brez podatkov (20. 8.) | Ali sta Quarto in oblikovalnik pripravljena za splošno uporabo ali le za administracijo/testiranje. |
| Uporabniški vmesnik za geofence območja | [GMS-5592](https://flycomtech.atlassian.net/browse/GMS-5592) – UI/UX geofence (19. 8.) | Ali je funkcionalnost uporabnikom že vidna; če ne, jo odstrani iz e-maila. |
| Dokumentacija v orodju »Pomoč« | [GMS-5629](https://flycomtech.atlassian.net/browse/GMS-5629) – dokumentacija po modulih ter prenos datoteke/modula (31. 8.) | Potrdi, katere datoteke so naložene in ali je omogočen prenos celotnega modula. |

## Zaključene naloge po 18. 8., ki niso izrecno omenjene

Naslednje naloge so v priloženih izvozih posodobljene v izbranem obdobju, vendar jih osnutek ne izpostavlja, ker so tehnične, testne ali preveč podrobne za obvestilo uporabnikom: [GMS-5698](https://flycomtech.atlassian.net/browse/GMS-5698) – omejitev virov roadrunnerja; [GMS-5724](https://flycomtech.atlassian.net/browse/GMS-5724) – vnos neporočanj; [GMS-5594](https://flycomtech.atlassian.net/browse/GMS-5594), [GMS-5438](https://flycomtech.atlassian.net/browse/GMS-5438), [GMS-5717](https://flycomtech.atlassian.net/browse/GMS-5717) – testiranje; [GMS-5437](https://flycomtech.atlassian.net/browse/GMS-5437) – analiza prekinjene poizvedbe; [GMS-5725](https://flycomtech.atlassian.net/browse/GMS-5725) – dostopnost S3 za poročila; [GMS-5695](https://flycomtech.atlassian.net/browse/GMS-5695) – optimizacija preračuna m² v RT; [GMS-5726](https://flycomtech.atlassian.net/browse/GMS-5726) – vizualni popravki modala; [GMS-5501](https://flycomtech.atlassian.net/browse/GMS-5501) – preverjanje arhiviranja Temporal; [GMS-5557](https://flycomtech.atlassian.net/browse/GMS-5557) – šifriranje Barman varnostnih kopij.
