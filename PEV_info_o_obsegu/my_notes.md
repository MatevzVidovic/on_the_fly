


We are working on PEV_info_o_obsegu


We have to prepare a few things:

- a deduplicated list of problems/topics from the many sources we have
- take that list and add how we are addressing it and what the state is for each of those points

We have access to the main repo over fmp symlink, where i did fetc and prune, so hopefully we can see the latest state of progress for everything - tell me if you cant.

The same goes for lift-temporal-python where some of the used workflows live (although i think not much of the useful code lives there).

Also, you have access to the test DB by reading /Users/matevzvidovic/on_the_fly/test_nas_access/README_ACCESSIBILITY.md
And in there you can also look at SFCs that exist if that helps you, but this stuff mostly doesnt concern that.







My notes:



- dodat probleme omenjene verbalno  na sestanku

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

P.S Tule ti še pošiljam vmesni dokument, kaj trenutno vem o rešitvah teh problemov in kje imam še nejasnosti.


Gašper:
Zdravo,
ne vem če si kaj spremljal sago informacije o PEVu z gursom (upam da nisi in si užival na dopustu).
V torek imava z njimi sestanek o tem.
Sem zbral težave in kar trenutno vem o njihovi naslovljivosti.
Prosim če v ponedeljek greš čez njih in že raziščeš, če imam kje narobe, pa če veš kaj, kjer imam jaz nejasnosti.
Potem bi imela sestanek, kjer še skupaj vse pogledava in se uskladiva,
potem pa še en sestanek s Timotejem, kjer njega glede BE strani tega preizprašava.

Tule je dokument s tem, kako sem do zdaj našel, da se naslevlja te težave:










- luknje so mi pomoje jasne - dajmo še preverit, če mislimo isto. AMPAK POMEMBNEJE - kaj mislite s slepimi poligoni?

- smo zdaj sploh že dobili glavo in nogo? Kakor vem, je bil problem, da smo že doglo nazaj prosili zanje pa jih ne dobili.

- odmik od roba

-  A0-A4 pogledat DELA NA NJIHOVEM TESTU IN PROD

- SSL problemi, da ne dobi legende - kaj so te problemi v rde;em z SSL certificate ni valid (vidno na posnetku sestanka)
Opozorilo: Legenda KN parcele ni bila dostopna — HTTPSConnectionPool(host=’lift.gurs.sigov.si’,
port=443): Max retries exceeded with url:
/geoserver/wms?REQUEST=GetLegendGraphic&VERSION=1.0.0&FORMAT=image%2Fpng&WIDTH=31&HEIGHT=31&(Caused by SSLError(SSLCertVerificationError(1, ’[SSL: CERTIFICATE_VERIFY_FAILED] certificate
verify failed: unable to get local issuer certificate (_ssl.c:1010)’)))

- labele se lahko naredi v liftu, da so vedno prisotne? Pa da se ne pore\ejo pa da se ne prekrivajo?


- poimenovanje datotek - lahko naredim SFC na fieldu, kjer za download overrideam ime. Ampak za masovne izvoze to lahko problem, če jih ne bomo reševali s SFC, ampak na backendu (kar bo doti bolje - glej 5239 - sicer ne vem če se bodo tako izvažali kot vprašalniki, ampak je za considerat. Also, v splošnem bi bilo nicer, da bi uploadi na S3 imeli:   /<uuid>/lepo_ime  na splo[no na document fieldu - tudi na isam_dokumentacija je tako, in tam hackam s SFCjem)
- A0-A4 že deluje? Je na workflowu? Je kje deployed? Je dodano v podatkovni model?
- obvestilo o končanju: lahko na SFCju ni async, ampak traja 50 sek, in nih;e ne bo čakal z odprtim SFC za to. Po drugi strani je na backendu tako, da če damo notif, ga vsi dobijo. Kaj naredit?
