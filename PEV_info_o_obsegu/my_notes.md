


We are working on PEV_info_o_obsegu


We have to prepare a few things:

- a deduplicated list of problems/topics from the many sources we have
- take that list and add how we are addressing it and what the state is for each of those points

We have access to the main repo over fmp symlink, where i did fetc and prune, so hopefully we can see the latest state of progress for everything - tell me if you cant.

The same goes for lift-temporal-python where some of the used workflows live (although i think not much of the useful code lives there).

Also, you have access to the test DB by reading /Users/matevzvidovic/on_the_fly/test_nas_access/README_ACCESSIBILITY.md
And in there you can also look at SFCs that exist if that helps you, but this stuff mostly doesnt concern that.






Vprašanja za gurs:

- "Oznaka PEV naj se pojavi samo enkrat v dokumentu, čeprav se je prej ponavljala." - torej samo pri npr. "Posebna enota vrednotenja: PNB-10552 MOL BS MESTINJE"

- To je mišljeno kot glava, ki se pojavlja na vseh straneh, tudi teh s prikazom slojev?
![alt text](<imgs/Screenshot 2026-09-05 at 19.13.38.png>)

- kako to naslovimo (»PNE_21380_20251212.pdf«) in ne tako, kot je sedaj (primer »45a7ce34-a12b-11f1-9912-02420a0001b0.pdf«.)
Bi bilo fajn na backendu, ker je pogost problem.
Morda vemo, ;e se kdaj to masovno izvaža? Ker sicer lahko naredim temporary fix s SFCjem, kjer ob downloadu preimenujem.

- luknje so mi pomoje jasne - dajmo še preverit, če mislimo isto. AMPAK POMEMBNEJE - kaj mislite s slepimi poligoni?




Za naslovit interno:

- to imamo zdaj narobe zapeljano "(parcele in stavbe se morajo prikazovati v celoti); delež parcele v grafični obliki informativno prikazuje zgolj FO)". Potencialna rešitev: podrejen zapis na pev parcele in deli stavb, ki so clipped na parent-a. Če podrejenega zapisa ni, se gleda celotna parcela, ko se preračunava FO.
Če prav razumem: deli stavb nimajo geometrije. Ampak ne vem kako se potem tam delež računa npr. Kaj potem delež pomeni? V m2 je pomoje.
Drug način (jim mogoče ne bo všeč, ker oni kaj prestavljajo stavbe zraven, in potem bi rabli na novo rezat FO):
Namesto avtomatskega preračuna FO, damo SFC, ki požene preračun.
Kasneje oni na roke urejajo samo FO.


- labele se lahko naredi v liftu, da so vedno prisotne? Pa da se ne porežejo pa da se ne prekrivajo?
Od kje jih Timotej jemlje?

- smo zdaj sploh že dobili glavo in nogo? Kakor vem, je bil problem, da smo že doglo nazaj prosili zanje pa jih ne dobili.
Je naslov dokumenta in celjavnost, kot je v docx, v bistvu glava?

- težje zadeve: odmik od roba, takoj pod tabelami brez razmaka kaj pomenijo okrajšave, pa da bi vse strani imele iste checkboxe, pa labele da KO labela ziher prisotna, pa da druge tabele ne prekrivajo in ziher prisotne



- poimenovanje datotek - lahko naredim SFC na fieldu, kjer za download overrideam ime. Ampak za masovne izvoze to lahko problem, če jih ne bomo reševali s SFC, ampak na backendu (kar bo doti bolje - glej 5239 - sicer ne vem če se bodo tako izvažali kot vprašalniki, ampak je za considerat. Also, v splošnem bi bilo nicer, da bi uploadi na S3 imeli:   /<uuid>/lepo_ime  na splo[no na document fieldu - tudi na isam_dokumentacija je tako, in tam hackam s SFCjem)

- obvestilo o končanju: lahko na SFCju ni async, ampak traja 50 sek, in nih;e ne bo čakal z odprtim SFC za to. Po drugi strani je na backendu tako, da če damo notif, ga vsi dobijo. Kaj naredit?





My notes:





- po mailu poslat sporočila Timoteju in Gašperju:

Timotej:
Zdravo,
ne vem, če ti je Matija že kej razlagal o komunikaciji z GURSom glede PDFov informacije o obsegu.
So sklicali sestanek glede določenih problemov (opisani v enem docx dokumentu + v 2 mailih + verbalno na enem sestanku).
Sem te težave zbral v tem mailu, kjer sem te CCjal.
Sestanek je v torek.
V ponedeljek pride Gašper z dopusta in bova najprej skupaj šla čez seznam in stanja,
potem bi te pa lepo prosil če te lahko rezerviram za en sestanek, kjer bomo še skupaj šli čez in boš dal BE perspektivo, kaj je z lahkoto izvedljivo, kaj je izvedljivo če je res pomembno, pa kaj res raje ne.
Bi to šlo?

Imam pa nekaj vprašanj, ki mi jih lahko že zdaj odgovoriš, ali pa si mogoče vmes pogledaš, pa jih potem naslovimo:
- Kako delujejo labele? Ti delaš dobeseden screenshot LIFT-a, če bi viewport karte prilagodil strani v PDFu? Da vem, kako z Gašperjem poskušava matchat to, kar oni želijo, pa se potem posvetujemo, če je kaj treba specifično za dokument, če bi bilo neizvedljivo v LIFTu.
- Matija mi je pravil, da smo jih enkrat prosili za glavo in nogo in ne dobili odgovora. Mogoče veš, če smo to že dobili?
- (najbolje kar na sestanku) Mi boš znal povedat, kaj je z legendami. V dokumentih je SSL error v rdečem napisan. Matija je v interni dokumentaciji nekaj omenil, da ne znamo nasloviti. Nimam nič ozadja o tem - za kaj se tu sploh gre?
Tole je error v dokumentu v rdečem:
Opozorilo: Legenda KN parcele ni bila dostopna — HTTPSConnectionPool(host=’lift.gurs.sigov.si’,
port=443): Max retries exceeded with url:
/geoserver/wms?REQUEST=GetLegendGraphic&VERSION=1.0.0&FORMAT=image%2Fpng&WIDTH=31&HEIGHT=31&(Caused by SSLError(SSLCertVerificationError(1, ’[SSL: CERTIFICATE_VERIFY_FAILED] certificate
verify failed: unable to get local issuer certificate (_ssl.c:1010)’)))






Gašper:
Zdravo,
ne vem če si kaj spremljal sago informacije o PEVu z gursom (upam da nisi in si užival na dopustu).
V torek imava z njimi sestanek o tem.
Sem zbral težave in kar trenutno vem o njihovi naslovljivosti.
Prosim če v ponedeljek greš čez njih in že raziščeš, če imam kje narobe, pa če veš kaj, kjer imam jaz nejasnosti.
Potem bi imela sestanek, kjer še skupaj vse pogledava in se uskladiva,
potem pa še en sestanek s Timotejem, kjer njega glede BE strani tega preizprašava.

Tule je dokument s tem, kako sem do zdaj našel, da se naslevlja te težave:









