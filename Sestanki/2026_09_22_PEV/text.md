


Uporaba geometrije deleža parcele, ki se uporablja za FO, ne potrebuje podvojenega vnosa uradne KN geometrije, ki bi bila zmanjšana.
Ker takšnih FO ni veliko, se bo zanje namreč nastavilo "Generiraj nov geom" na False, ter FO urejalo na roke.


Predstavili smo prožilce, ki se izvajajo za posodabljanje FO in bomo njihovo razlago dodali v dokumentaciji, ki je dostopna v LIFT.

Reaktivacija arhiviranih PEV: Napačno zastavljen aktiven PEV se lahko ativira, nakar predhodno aktiviranemu PEVu nastavimo polje "Veljaven do" na prazno vrednost, ter tako postane ponovno aktiven. Če ga vseeno želimo ohraniti kot arhiviran PEV, lahko nato zanj ponovno zaženemo arhiviranje, ter tako pridobimo tako arhivirano kot aktivno kopijo.


Vpogled v arhivirane PEV: Aktivni PEV imajo polje "Veljaven do" prazno, oziroma višje od trenutnega datuma. Arhivirani PEV imajo torej "Veljaven do" manjši od današnjega datuma - na ta način jih tudi filtriramo. 


Odložišče geometrij: Ob označeni geometriji v spodnjem desnem kotu karte kliknemo na "Dodaj v geometrijsko odložišče". Shranjeno geometrijo lahko kasneje uporabimo tudi ob določanju geometrije novim dodajanim zapisom.


Vrstni red stolpcev v tabeli: Vrstni red stolpcev tabele je popolnoma odvisen od zaporedja atributnih polj v pogledu "Atributna polja" tabele. V pogledu tabele rezultatov je mogoče nastavljati le privzeto širino stolpcev ter privzeto zaporedje vrstic v tabeli.

Dodajanje tabeli pev_pos_vnos: nezmožnost urejanja, dodajanja, ter masovnega urejanja tabele pev_pos_vnos izhaja iz iste napake, ki je povezana z neizpolnjevanjem lookup polj. Težavo moramo podrobneje raziskati ter rešiti.

Kontrole neupoštevanih parcel: parcele PEV, ki imajo polje "Upoštevan" na false, ne smejo biti prisotne v kontrolah. Trenutno te izjeme ne izvajamo in jo moramo dodati.


Raziskali smo problematično kontrolo na parceli PNP z ID PEV 30001, kjer so podrobnosti naslendje: "Vsota deležev na 1 PEV za 767 m2 presega atr. površino".
Podrobnosti te kontrole morajo vsebovati id parcele ter id-je PEVov, ki sodelujejo v kontroli.

