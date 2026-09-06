


Vprašanja za gurs:

- "Oznaka PEV naj se pojavi samo enkrat v dokumentu, čeprav se je prej ponavljala." - torej samo pri npr. "Posebna enota vrednotenja: PNB-10552 MOL BS MESTINJE"

- To je mišljeno kot glava, ki se pojavlja na vseh straneh, tudi teh s prikazom slojev?
![alt text](<imgs/Screenshot 2026-09-05 at 19.13.38.png>)

- kako to naslovimo (»PNE_21380_20251212.pdf«) in ne tako, kot je sedaj (primer »45a7ce34-a12b-11f1-9912-02420a0001b0.pdf«.)
Bi bilo fajn na backendu, ker je pogost problem.
Morda vemo, ;e se kdaj to masovno izvaža? Ker sicer lahko naredim temporary fix s SFCjem, kjer ob downloadu preimenujem.

- luknje so mi pomoje jasne - dajmo še preverit, če mislimo isto. AMPAK POMEMBNEJE - kaj mislite s slepimi poligoni?




Za naslovit interno:

- to imamo zdaj narobe zapeljano "(parcele in stavbe se morajo prikazovati v celoti); delež parcele v grafični obliki informativno prikazuje zgolj FO)". 

Potencialna rešitev: podrejen zapis na PEV parcele in PEV stavbe, ki so clipped na parent-a (trigger). Če podrejenega zapisa ni, se gleda celotna parcela/stavba, ko se preračunava FO.

Drug način (jim mogoče ne bo všeč, ker oni kaj prestavljajo stavbe zraven, in potem bi rabli na novo rezat FO):
Namesto avtomatskega preračuna FO, damo SFC, ki požene preračun.
Kasneje oni na roke urejajo samo FO.

Če prav razumem: deli stavb nimajo geometrije. Ampak ne vem kako se potem tam delež računa npr. Kaj potem delež pomeni? V m2 je pomoje. To oni na roke nastavljajo za dele stavb?



- labele se lahko naredi v liftu, da so vedno prisotne? Pa da se ne porežejo pa da se ne prekrivajo?
Od kje jih Timotej jemlje?

- smo zdaj sploh že dobili glavo in nogo? Kakor vem, je bil problem, da smo že doglo nazaj prosili zanje pa jih ne dobili.
Je naslov dokumenta in celjavnost, kot je v docx, v bistvu glava?

- težje zadeve: odmik od roba, takoj pod tabelami brez razmaka kaj pomenijo okrajšave, pa da bi vse strani imele iste checkboxe, pa labele da KO labela ziher prisotna, pa da druge tabele ne prekrivajo in ziher prisotne


- poimenovanje datotek - lahko naredim SFC na fieldu, kjer za download overrideam ime. Ampak za masovne izvoze to lahko problem, če jih ne bomo reševali s SFC, ampak na backendu (kar bo doti bolje - glej 5239 - sicer ne vem če se bodo tako izvažali kot vprašalniki, ampak je za considerat. Also, v splošnem bi bilo nicer, da bi uploadi na S3 imeli:   /<uuid>/lepo_ime  na splo[no na document fieldu - tudi na isam_dokumentacija je tako, in tam hackam s SFCjem)

- obvestilo o končanju: lahko na SFCju ni async, ampak traja 50 sek, in nih;e ne bo čakal z odprtim SFC za to. Po drugi strani je na backendu tako, da če damo notif, ga vsi dobijo. Kaj naredit?

