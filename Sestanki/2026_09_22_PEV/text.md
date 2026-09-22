




- Geometrija deleža parcele za FO
Uporaba geometrije deleža parcele, ki se uporablja za FO, ne zahteva podvojenega vnosa uradne KN geometrije v zmanjšani obliki. Ker je takšnih FO razmeroma malo, bo zanje polje »Generiraj nov geom« nastavljeno na vrednost False, FO pa se bodo urejali ročno.

- Prožilci za posodabljanje FO
Predstavili smo prožilce, ki se izvajajo z namenom posodabljanja FO. Njihovo razlago bomo dodali v dokumentacijo, ki je dostopna v okolju LIFT.

- Reaktivacija arhiviranih PEV
Napačno zastavljen aktivni PEV je mogoče arhivirati, pri čemer predhodno aktiviranemu PEV nastavimo polje »Veljaven do« na prazno vrednost, s čimer ta ponovno postane aktiven. Če želimo napačni zapis kljub temu ohraniti kot arhiviran PEV, zanj ponovno izvedemo postopek arhiviranja in tako pridobimo arhivirano ter aktivno kopijo.

- Vpogled v arhivirane PEV
Aktivni PEV imajo polje »Veljaven do« prazno oziroma nastavljeno na datum, ki je poznejši od trenutnega. Arhivirani PEV imajo v tem polju datum, ki je zgodnejši od današnjega, kar predstavlja tudi merilo za njihovo filtriranje.

- Odložišče geometrij
Ob označeni geometriji v spodnjem desnem kotu karte izberemo možnost »Dodaj v geometrijsko odložišče«. Shranjeno geometrijo je mogoče pozneje uporabiti tudi pri določanju geometrije novim zapisom.

- Vrstni red stolpcev v tabeli
Vrstni red stolpcev v tabeli je v celoti odvisen od zaporedja atributnih polj v pogledu »Atributna polja« posamezne tabele. V pogledu tabele rezultatov je mogoče nastaviti zgolj privzeto širino stolpcev in privzeto zaporedje vrstic.

- Dodajanje zapisov v tabelo pev_pos_vnos
Nezmožnost urejanja, dodajanja in masovnega urejanja tabele pev_pos_vnos izhaja iz iste napake, ki je povezana z neizpolnjevanjem lookup polj. Težavo bomo podrobneje raziskali in odpravili.

- Kontrole neupoštevanih parcel
Parcele PEV, pri katerih je polje »Upoštevan« nastavljeno na vrednost False, ne smejo biti vključene v kontrole. Te izjeme trenutno ne izvajamo, zato jo bomo dodali.

- Kontrola na parceli PNP (ID PEV 30001)
Raziskali smo problematično kontrolo na parceli PNP z ID PEV 30001, pri kateri se izpiše naslednje sporočilo: »Vsota deležev na 1 PEV za 767 m2 presega atr. površino«. Podrobnosti te kontrole morajo vključevati ID parcele ter ID-je vseh PEV, ki v kontroli sodelujejo.