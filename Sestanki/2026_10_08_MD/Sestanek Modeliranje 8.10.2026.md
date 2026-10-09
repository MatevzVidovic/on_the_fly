
# Sestanek Modeliranje 8.10.2026

Zahtevke v povezavi z vodenjem verzij območij ter kopiranjem geometrij med verzijami modela na danih verzijah območij še dodatno dopolnjujemo in v kratkem pošljemo v potrditev. 

## 1. Dokumentacija zapisa enačb v LaTeX-u

- Preverili smo, ali dokumentacija pojasnjuje, kako sistem obravnava zapis enačb v LaTeX-u in katere dele zapisa upošteva oziroma ignorira.
  - **Status:** Pojasnilo je že vključeno v dokument **Modeliranje.docx**, v razdelku **5.2 → 5.2.1 Postopek pisanja enačb → Kako sistem interpretira zapis**.

## 2. Podpora za »Parametre izjeme«

- Ugotovili smo, da sta funkcionalnost »Parametri izjeme« in pripadajoči atribut trenutno nastavljena samo za model HIS.
  - **Status:** Za uporabo izjem pri drugih modelih oziroma spremenljivkah smo ustvarili zahtevek.
  - 
## 2. Izrecno odštevanje izjem v enačbi

- Izražena je bila zahteva, da je odštevanje modelov, navedenih v »Parametrih izjeme«, izrecno zapisano v enačbi.
  - **Dogovor:** Trenutno implicitno programsko določeno odštevanje v ozadju se nadomesti z eksplicitnim izračunanim faktorjem **v_izjema** (ki sicer ne bo prisoten med običajnimi faktorji). Za upoštevanje odštevanja mora enačba vsebovati člen **− v_izjema**. Za rešitev je bil ustvarjen zahtevek ISAM-1226.  
  - **Nadaljnji ukrep:** Za opisano spremembo se ustvari zahtevek ISAM-1223.

## 3. Izpolnjevanje modela in verzije ob dodajanju spremenljivke

- Pri dodajanju nove spremenljivke pod verzijo modela v drevesnem prikazu se polji **Model** in **Verzija** ne izpolnita vedno samodejno. Težava se pojavi, če je stranski panel pred tem že odprt za drugo vsebino. Če je panel pred dodajanjem zaprt, se polji pravilno izpolnita.
  - **Status:** Napako je že rešena in bo odpravljena v naslednji verziji LIFT-a.

## 4. Izbira faktorja pri dodajanju definicije TVR

- Pri dodajanju zapisa v **md_tvr_definicija** izbor faktorja ne deluje. Pri urejanju že dodanega zapisa se faktorji pravilno prikažejo.
  - **Status:** Napaka je evidentirana v zahtevku ISAM-1217 in bo odpravljena.

## 5. Dopolnitev navodil za definiranje TVR

- Obravnavali smo potrebo po jasnejših navodilih za celotno definicijo TVR, zlasti za uporabo vrstice brez faktorja (`null`). Ta vrstica je namenjena nastavitvi zadnjih treh logičnih stolpcev, ki se pri vrsticah s faktorjem ne nastavljajo.
  - **Dogovor:** Navodila se dopolnijo s celotnim postopkom definiranja TVR, vključno z namenom in uporabo vrstice brez faktorja. Za vrstico brez faktorja pri urejanju skrijemo 3 polja, ki se navezujejo le na vrstice s faktorji, in obratno:
	  - **Vrstica brez faktorja (`null`):** Polja **Vrednost**, **Ambicija** in **Delitev** se skrijejo, saj se v tej vrstici ne urejajo.
	  - **Vrstica s faktorjem:** Polja **Št. rel. tab.**, **Št. tab. obn.** in **Ref. vrednost m2** se skrijejo.

## 7. Izračun referenčnih vrednosti iz enačbe

- Polji **ref_vrednost** in **ref_m2** se trenutno preračunavata le ob spremembi md_referencni_objekti. Preračunavati se morata tudi ob spremembi definicije enačbe in ob spremembi **md_tvr_vrednosti.vrednost**.
  - **Status:** Izdelujemo podroben opis rešitve.

## 8. Izračun ref_vrednost in delitve

- Obravnavali smo način izračuna in posodabljanja delitve: **delitev = vrednost faktorja / ref_vrednost**.
  - **Dogovor:** Uporabnik ureja vrednosti faktorjev, referenčne vrednosti pa se izračunajo na njihovi podlagi. Polja **ref_vrednost**, **ref_vrednost_m2** in **delitev** se zaklenejo za ročno urejanje.
  - **Status:** Ustvarili smo zahtevek ISAM-1219 za uporabniški vmesnik (FE), s katerim se onemogoči ročno urejanje referenčnih vrednosti in delitve.


