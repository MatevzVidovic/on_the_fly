
Testiranje modeliranja: 

Pregleda se dokumentacija, če je zapisano kako se obravnava latex zapis enačb (kaj se ignorira in kaj ne) 

Je prisotno. Dokumentacija za modul Modeliranje.docx: Razdelek: 5.2 → 5.2.1 Postopek pisanja enačb → Kako sistem interpretira zapis 

Polje "Parametri izjeme": Dodatne izjeme za druge modele oz. spremenljivke se morajo sprogramirati (trenutno je nastavljeno samo za HIS) - tudi atribut je nastavljen samo pri HIS 

Pri dodajnju nove spremenljivke v tree-view pod verzijo modela se polja za model ne izpolnejo vedno 

Odkrit bug: če je side-panel prej odprt za nekaj drugega, in potem damo dodajanje, se ne izpolnita polji Model in Verzija. Če je side-panel predhodno zaprt, se izpolnita. 

Bug je mogoče reproducirati na staging, na našem testu pa že vse deluje pravilno. Predvidevamo, da je bug že odpravljen. 

Ne deluje lookup na md_tvr_definicija za izbiro faktorja (bug in ko rešimo sporočimo -> ko urejamo na že dodanem polju se faktorji pokažejo). 

Lookup deluje pri urejanju, ne pa pri dodajanju. 

Ticket napisan https://flycomtech.atlassian.net/browse/GMS-6088 

Kako definirat TVR -> naj se doda v navodila. Morda manjka samo uporaba vrstice z null faktorjem z namenom nastavitve zadnjih treh boolean stolpcev, ki pa se na fakotrjih ne nastavljajo. 

Doda se v navodila celotna definicija TVR 

Naj se tudi naredi pogojno prikazovanje atributov pri definiranju TVR: za vrstico z null faktorjem, so Vrednost, Ambicija, Delitev skrita polja, saj se ne urejajo. In obratno – za vstico, ki ima faktor, so Št. rel. tab., Št. tab. obn., Ref. vrednost m2 skrita polja. 

Na prod se nastavi zgoraj opisan pravilnejši prikaz 

Izračun ref_vrednosti in ref_m2 bi se moralo poračunati iz enačbe 

Ticket v reševanju https://flycomtech.atlassian.net/browse/GMS-5554 

Kako se računa delitev (ali se sploh računa/posodablja) delitev = vrednost faktorja / ref_vrednost 

ref_vrednost se ne bo nikoli urejala. Vedno se samo ta vrednost na faktorjih, in se posledično ref_vrednost izračunava (ref_vrednost, ref_vrednost_m2 in delitev se zaklenejo) 

delitev je smiselno, da je samo za 2 od 4, ker npr. pri HIS je delitev za v_dst in v_z true, za v_zps in pribitek pa ni: fora je pa, da se v_z izra;unava na podlagi v_zps in pribitek, torej imata samo posredno vpliv 

Napiše se ticket FE da se zaklene ref_* in delitev 

 

Željena je eksplicitna prisotnost odštevanja modelov, opisanih v "Parametri izjeme", znotraj enačbe. 

Naredi ticket: Namesto hardcoded skritega odštevanja "Parametri izjeme", naj se v ozadju del z izjemo doda v nabor faktorjev kot v_izjema. Oni morajo potem v enačbi imeti definirano - v_izjema, da se bo res odštevalo. 

 