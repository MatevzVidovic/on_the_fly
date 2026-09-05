# Povzetek problemov iz dokumenta »Seznam pomanjkljivosti Informacija PEV«

Vir: [izvirni DOCX](wants/Seznam_pomanjkljivosti_Informacija_PEV.docx); [Markdown prepis](wants/Seznam_pomanjkljivosti_Informacija_PEV.md). Pregled: 5. 9. 2026.

Spodaj je **23 združenih problemov oziroma zahtev iz tega dokumenta**. Ponavljajoče se navedbe iste težave so združene. To je povzetek zahtev, ne preverjanje, kaj je že rešeno. Podrobnosti iz drugih treh virov tu niso dodane.

DOCX je bil prebran neposredno iz vsebine datoteke in preverjenih je bilo vseh 12 vstavljenih slik. Prepis MD je služil za primerjavo. Izris celotnega Wordovega dokumenta ni uspel (LibreOffice se je prekinil), zato se sklici nanašajo na razdelke in začetke navedb, ne na številke strani. V DOCX ni komentarjev, sledenih vstavitev/izbrisov ali vsebinskih opomb pod črto/na koncu.

## Splošno in atributni del

| ID  | Problem / zahtevano stanje                                                                                                                                                                                                                                                                                                           | Mesto v izvirniku                                                                                 |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| D01 | **Celostno oblikovanje uradnega dokumenta je nedodelano.** Atributni del je uraden seznam sestavin PEV, grafični del je informativen, vendar mora prikazovati uradne geometrije parcel in stavb ter ustrezati osnovnim geodetskim standardom. Predloženi izrisi GURS so oblikovalski zgled. Podrobnejše zahteve so razdelane spodaj. | Uvod: »Splošna pomanjkljivost« in »Gre za dokument Republike Slovenije«; primeri GURS/Flycom.     |
| D02 | **Začetni naslov:** manjša pisava, sredinska poravnava, ena vrstica in bistveno manjši razmik pod naslovom; predlagana je ločilna črta.                                                                                                                                                                                              | Atributni del, »Začetni napis«.                                                                   |
| D03 | **Odstraniti sivo polnilo iz napisov:** datum veljavnosti, oznaka PEV, seznam parcel in delov stavb ter »Informativni pregled posebne …«. Zahteva se nanaša na napise, ne na odstranitev polnila iz glav tabel.                                                                                                                      | Atributni del, »Napisi z datumom veljavnosti …«; slikovni zgledi.                                 |
| D04 | **Oznaka PEV naj se pojavi samo enkrat** v dokumentu, čeprav se je prej ponavljala.                                                                                                                                                                                                                                                  | Atributni del, »Oznaka posebne enote vrednotenja …«.                                              |
| D05 | **Tabeli morata ostati tudi brez sestavin:** tako seznam parcel kot seznam delov stavb se izrišeta z glavo in vsaj eno vrstico, tudi ko teh sestavin ni. Na slikah je v vrstici »Nima parcel« oziroma »Nima delov stavb«.                                                                                                            | Atributni del, »Tabeli Seznam parcel …«; sliki »Seznam brez parcel« in »Seznam brez delov stavb«. |
| D06 | **Poravnava obeh tabel:** isti levi rob in navpične ločilne črte na istih mestih.                                                                                                                                                                                                                                                    | Atributni del, »Obe zgoraj navedeni tabeli …«.                                                    |
| D07 | **Pomen okrajšav:** manjša pisava in manjši odmik od zadnje vrstice tabele; razlaga DST naj bo zamaknjena desno pod K.O.                                                                                                                                                                                                             | Atributni del, »Pomen okrajšav«.                                                                  |
| D08 | **Enotna debelina črt tabel:** vse obrobne črte enako debele; notranje ne smejo biti debelejše od obrobnih.                                                                                                                                                                                                                          | Atributni del, »Debelina črt tabel …«.                                                            |
| D09 | **Zapis števil:** števila nad 1.000 s pikami za tisočice in brez decimalnih mest; primer `1668 → 1.668`.                                                                                                                                                                                                                             | Atributni del, »Števila, večja od 1.000 …«.                                                       |
| D10 | **Legenda še ni dokončna:** dopolniti jo po uskladitvi dokončne oblike informativnega grafičnega izrisa.                                                                                                                                                                                                                             | Zadnja navedba atributnega dela, »Legendo dopolnimo …«.                                           |

## Sloji in upravljanje plasti GeoPDF

| ID | Problem / zahtevano stanje | Mesto v izvirniku |
| --- | --- | --- |
| D11 | **Nabor in vrstni red slojev pri grafičnem izrisu:** od zgoraj navzdol: (1) parcele, delno ali v celoti vključene v PEV; (2) parcele zunaj PEV; (3) stavbe/deli stavb PEV, z obrisom stavb; (4) stavbe zunaj PEV; (5) zaris FO; (6) zaris in številka KO. Trenutni vrstni red je napačen. | Grafični del, »V tem delu dokumenta …«, šest postavk in odstavek o vrstnem redu. |
| D12 | **Skupno upravljanje slojev vseh grafičnih listov:** pri več okvirjih se nabor plasti ponavlja za vsak list. Če je mogoče, naj bo en nabor, ki velja za vse liste, da slojev ni treba izklapljati na vsakem posebej. | Grafični del, »Na tej sliki je viden primer …«. |
| D13 | **Odstraniti odvečne skupine plasti:** če je mogoče, naj bodo sloji na enem nivoju, brez skupin »PEV«, »Informacija o obsegu (GeoPDF)« in »Podlage«, v vrstnem redu iz D11. | Grafični del, »Odveč so skupine slojev …«. |
| D14 | **Brez podvojenega izrisa PEV in KN:** sestavine PEV naj se ne rišejo še enkrat v drugih slojih KN; za dele stavb naj bi bilo to že urejeno, enako je zahtevano za parcele. | Grafični del, »Prikaz sestavin, ki so vključene v PEV …«. |
| D15 | **Razumljiva imena slojev:** odstraniti nepojasnjene kratice in tehnična poimenovanja; ohranjenih je vseh sedem predlaganih preimenovanj v spodnji tabeli. | Grafični del, »Naslednja težava so imena slojev …« in tabela imen. |

### D15 — vsa predlagana preimenovanja

| Zdajšnje ime | Predlagano ime |
| --- | --- |
| PEV – Parcele | Parcele PEV |
| KN NEP A Parcele (GeoPDF) | Parcele katastra nepremičnin |
| PEV – Stavbe | Stavbe/deli stavb PEV |
| KN NEP A Stavbe obrisi (GeoPDF) | Stavbe/deli stavb katastra nepremičnin |
| PEV – FO | Funkcionalno območje PEV |
| KN NEP A Katastrske občine (GeoPDF) | Katastrska občina |
| Ortofoto SLO (zadnje stanje) | Ortofoto posnetek |

## Grafični list, geometrije in datoteka

| ID | Problem / zahtevano stanje | Mesto v izvirniku |
| --- | --- | --- |
| D16 | **Odmik karte od roba papirja:** slika je zdaj od roba do roba. DOCX ne določa širine odmika. | Grafični del, »izris slojev in podlog se zdi kot zajem zaslona …«. |
| D17 | **Prilagoditev izrisa papirju/merilu:** velikosti pisav in debeline črt niso ustrezno prilagojene; izris deluje kot zajem zaslona. | Ista sestavljena navedba kot D16. |
| D18 | **Obroba, glava in noga grafičnega lista manjkajo.** | Ista sestavljena navedba kot D16; zgled grafičnega izrisa GURS. |
| D19 | **Merilo ni prikazano.** | Grafični del, »ni merila«. |
| D20 | **Oznake parcel in stavb:** prikazati vse oznake; osrediniti jih na vidni del objekta, preprečiti prekrivanje in zagotoviti celoten izpis brez odrezanih delov. | Grafični del, »ni vidnih vseh oznak grafičnih objektov« in »nezadovoljiv prikaz oznak parcel in stavb …«. |
| D21 | **Manjka oznaka katastrske občine.** Prikazati številko KO skupaj z njenim zarisom (povezano tudi z D11). | Grafični del, šesta postavka slojev in »ni prikaza oznake katastrske občine«. |
| D22 | **Ohranitev uradne geometrije pri delni vključitvi v PEV:** parcela in stavba se na izrisu prikažeta v celoti po uradni geometriji. Delež oziroma vključeni grafični del informativno prikazuje FO. Rezanje parcele ali spreminjanje verteksov pri izdelavi FO v ISAM/LIFT ne sme nadomestiti izvorne geometrije parcele, ki se uporabi na izrisu. Združuje napako prikaza in njen opisani vzrok v vodenju/vzdrževanju sestavin. | Grafični del, »nepravilen prikaz geometrij parcel PEV …«; celoten razdelek »Vodenje parcel, ki so delno vključene v PEV, v orodju ISAM« in zadnje tri slike. |
| D23 | **Ime PDF po pravilih uvoza v EV:** `model PEV_id_nep_datum izdelave.pdf`, primer `PNE_21380_20251212.pdf`; sedanje ime z UUID ni ustrezno. | »Poimenovanje datotek«, oba odstavka. |

## Opombe za pravilno razumevanje

- Slike podpirajo besedilne zahteve, niso dodatne samostojne zahteve. Stari zgledi ponavljajo oznako PEV in kažejo decimalke; izrecni besedilni zahtevi D04 in D09 zahtevata spremembo tega. Tega neskladja ne obravnavamo kot dve različni želji.
- DOCX pri praznih tabelah kaže obstoječa stolpca in obvestilo v prvi celici. Ne predpisuje izrecno združene vrstice čez celotno širino.
- DOCX **ne določa** odmika 1 cm, formatov A0–A4, obvestila o končani izdelavi ali prikaza/prevezovanja ID-jev v obrazcih. Ti podatki sodijo v primerjavo drugih virov.
- Številke na označenih slikah in podvojeni napisi slik niso dodatni problemi. Primerjave GURS/Flycom ne pretvarjamo v nove zahteve, ki v dokumentu niso izražene.
