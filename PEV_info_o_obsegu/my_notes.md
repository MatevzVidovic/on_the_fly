


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

- odmik od roba in A0-A4 pogledat


- poimenovanje datotek - lahko naredim SFC na fieldu, kjer za download overrideam ime. Ampak za masovne izvoze to lahko problem, če jih ne bomo reševali s SFC, ampak na backendu (kar bo doti bolje - glej 5239 - sicer ne vem če se bodo tako izvažali kot vprašalniki, ampak je za considerat. Also, v splošnem bi bilo nicer, da bi uploadi na S3 imeli:   /<uuid>/lepo_ime  na splo[no na document fieldu - tudi na isam_dokumentacija je tako, in tam hackam s SFCjem)
- A0-A4 že deluje? Je na workflowu? Je kje deployed? Je dodano v podatkovni model?
- obvestilo o končanju: lahko na SFCju ni async, ampak traja 50 sek, in nih;e ne bo čakal z odprtim SFC za to. Po drugi strani je na backendu tako, da če damo notif, ga vsi dobijo. Kaj naredit?
