
Namen sestanka PEV naslednji teden (usklajeno z GURS) je:

pregled word dokumenta in nejasnosti (povejte iskreno... npr. najbrž ne veste ali bomo legende lahko zagotovili ali ne... odgovor je "Ne moremo odgovoriti, ker ne vemo do katere mere je izvedljivo. Bomo posredovali naprej razvojni ekipi in pripravili predlog izvedve". 
Prikaz nalog, ki niso delovale (nekatere že odpravljene; želijo prikaz): 
Arhiviranje podatkov posamezne PEV še ne deluje. Sistem ISAM deluje tako, da najprej podatke posamezne PEV arhiviraš, aktualno stanje pa popravljaš in uvajaš spremembe. To še ne deluje pravilno, ker je podatkov o enem PEV veliko in se vsi še ne arhivirajo. Težava je, da na FCTju razvojnem okolju nekaj deluje, v okolju UMVN pa ne. [Naš komentar: Že rešeno; naslednji deploy.]
format izrisa mora podpirati formate od A0 do A4 – pričakujemo izris kot GIS orodje izriše grafiko, upošteva scale besedila, okvir, merilo,…  [Naš komentar: Formati že rešeno. Ostale reči stvar pregelda dokuemnta]
Masovni uvoz atributnih podatkov PEV (ko dobimo od upravljavca podatke v datoteki za več PEV hkrati). Če gremo po navodilih izvajalca step-by-step, postopek ne deluje in uvoza ne izvedemo. To je v JIRI že dolgo časa. [Naš komentar: Dogovorjeno he bilo, da bo tule enostavneje izvesti uvoz preko baze; Postopek se prikaže]
Pri risanju funkcionalnih območij (FO) PEV se v določenih primerih pojavljajo luknje in slepi poligoni [@Matevž Vidovič tole boš ti vedel naš komenatr ... status]
Prikaz parcel in FO na informacijah PEV – zgolj informativne narave. Takrat, ko FO prečka parcelo, mora biti geometrija parcele nespremenjena, spremeniti je potrebno zgolj obliko FO, ki je izvedena iz geometrije sekane parcele, oblika vključene parcele pa mora biti izvorna, takšna kot v KN [@Primož dodaj komentar za sestanek prosim]
Pogojno prikazovanje atributov na vnosni maski v odvisnosti od modela [Naš komentar: To so sicer že videli, ampak je bil v eni verziji bug s prikazom. Sedaj je to rešeno.]

(edited)
[9:48 AM]Prosim preberite in javite če kaj ni jasno (to je za sestanek nasledni torek). Prosim, da se za sestanek pripravite (to velja nasplošno), in sicer:

(ko mi uskladimo zgornje teme) stranki napišimo mail (@Matevž Vidovič, ker je @Gašper Oder še odsoten) s predlaganimi temami in če bi še kaj dodali glede na podan spisek
točke pregledamo in delovanje preverimo na njihovem okolju
zapišeš si opažanja; neznanke, ki jih mora podati stranka; ostalo

rezultat VSEH TEH KLICEV (@Primož @Matevž Vidovič @Gašper Oder) NAJ BO ZAPISNIK UGOTOVITEV. Dajem primer - danes sva z Matevžem šla preko včerajšnega klica in hitro našla rešitve za 2 nujni točki in našla dogovor za naprej za preostale zadeve (ki pa niso tako nujne)
Na osonovi teh dokumentov se potem usedete in predlagate rešitev: 
rešitev najdete ker je vzrok neznanja tistega, ki je bil na klicu, kar je čist OK! in to jemlite kot prenos znanja / učenje
rešitev najdete z uporabo drugega načina / orodja / ... 
rešitev je dodaten razvoj (gre v grooming; predstavite objektivno zahteve; bodite en drugemo the devil's advocat! - to pišem ker ne želim, da pridejo naloge v smislu to tukaj rabimo in ne pomislimo, da poderevmo 30 drugih caseov)
rešitev je odprava buga (torej zares gre za bug; tu potem probate ugotovit ali BE ali FE)