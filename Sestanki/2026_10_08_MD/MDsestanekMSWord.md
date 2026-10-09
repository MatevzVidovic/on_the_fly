ZAPISNIK SESTANKA – MODELIRANJE
8. oktober 2026

Zahtevke za vodenje verzij območij in kopiranje geometrij med verzijami modela na posameznih verzijah območij še dopolnjujemo. V kratkem jih bomo poslali v potrditev.

1. Dokumentacija zapisa enačb v LaTeX-u

Preverili smo, ali dokumentacija pojasnjuje, kako sistem obravnava zapis enačb v LaTeX-u in katere dele zapisa upošteva oziroma ignorira.

Status: Pojasnilo je že vključeno v dokument Modeliranje.docx, v razdelku 5.2 → 5.2.1 Postopek pisanja enačb → Kako sistem interpretira zapis.

2. Podpora za »Parametre izjeme«

Ugotovili smo, da sta funkcionalnost »Parametri izjeme« in pripadajoči atribut trenutno nastavljena samo za model HIS.

Status: Za podporo izjemam pri drugih modelih oziroma spremenljivkah smo ustvarili zahtevek.

3. Izrecno odštevanje izjem v enačbi

Obravnavali smo zahtevo, da je odštevanje modelov, navedenih v »Parametrih izjeme«, izrecno zapisano v enačbi.

Dogovor: Trenutno implicitno odštevanje v ozadju se nadomesti z izračunanim faktorjem v_izjema. Ta ne bo prikazan med običajnimi faktorji. Za upoštevanje odštevanja mora enačba vsebovati člen − v_izjema.

Status: Za rešitev je bil ustvarjen zahtevek ISAM-1226.

Nadaljnji ukrep: Za opisano spremembo je predvidena tudi priprava zahtevka ISAM-1223.

4. Izpolnjevanje modela in verzije ob dodajanju spremenljivke

Pri dodajanju nove spremenljivke pod verzijo modela v drevesnem prikazu se polji Model in Verzija ne izpolnita vedno samodejno. Težava se pojavi, če je stranski panel pred tem že odprt za drugo vsebino. Če je panel pred dodajanjem zaprt, se polji pravilno izpolnita.

Status: Napaka je že odpravljena. Popravek bo vključen v naslednjo različico sistema LIFT.

5. Izbira faktorja pri dodajanju definicije TVR

Pri dodajanju zapisa v md_tvr_definicija izbira faktorja ne deluje. Pri urejanju že dodanega zapisa se faktorji pravilno prikažejo.

Status: Napaka je evidentirana v zahtevku ISAM-1217 in bo odpravljena.

6. Navodila in prikaz polj pri definiranju TVR

Obravnavali smo potrebo po jasnejših navodilih za celotno definicijo TVR, zlasti za uporabo vrstice brez faktorja (null). Ta vrstica je namenjena nastavitvi zadnjih treh logičnih stolpcev, ki se pri vrsticah s faktorjem ne nastavljajo.

Dogovor: Navodila se dopolnijo s celotnim postopkom definiranja TVR, vključno z namenom in uporabo vrstice brez faktorja. Prikaz polj pri urejanju se prilagodi vrsti vrstice:

• Vrstica brez faktorja (null): skrijejo se polja Vrednost, Ambicija in Delitev, saj se v tej vrstici ne urejajo.
• Vrstica s faktorjem: skrijejo se polja Št. rel. tab., Št. tab. obn. in Ref. vrednost m2.

7. Preračun referenčnih vrednosti

Polji ref_vrednost in ref_m2 se trenutno preračunavata samo ob spremembi md_referencni_objekti. Preračun mora biti izveden tudi ob spremembi definicije enačbe in ob spremembi md_tvr_vrednosti.vrednost.

Status: Pripravljamo podroben opis rešitve.

8. Izračun referenčnih vrednosti in delitve

Obravnavali smo način izračuna in posodabljanja delitve po naslednji formuli:

delitev = vrednost faktorja / ref_vrednost

Dogovor: Uporabnik ureja vrednosti faktorjev, referenčne vrednosti pa se izračunajo na njihovi podlagi. Polja ref_vrednost, ref_vrednost_m2 in delitev se zaklenejo za ročno urejanje.

Status: Ustvarili smo zahtevek ISAM-1219 za prilagoditev uporabniškega vmesnika, s katero se onemogoči ročno urejanje referenčnih vrednosti in delitve.
