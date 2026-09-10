
this is the current report


Sestanek MD – 10.09.2026 - interni zapisnik 
 
Prisotni: 
FCT: Gašper Oder, Matevž Vidovič 
GURS: Melita Ulbl, Rok Štembal, Andrej Glavica 
 
Zadeve iz prejšnjega sestanka: 
Avtomatsko odštevanje vrednosti pasivnih modelov tudi takrat ko v modelu posla niso dodani. Ko se v poslu ne upošteva pasivni model, naj v vmesnem izračunu dobi vrednost 0, ne null, kar trenutno vodi do null leve strani. Želja je, da se lahko doda poljuben nabor pasivnih modelov. 
v_gar kot faktor vrednostne tabele garaž je potrebno preimenovati, saj ima namespace clash s pasivnim modelom GAR, ki je v enačbi tudi predstavljen kot v_gar. 
 
Na novo odprte zadeve: 
Na modelu PPL_NAJ, se ne dodajo in izračunajo transakcije: 
ODG: V model ni bilo vključenih nobenih transakcij, ker filter na modelu ne vključuje nobenih transkacij v matični tabeli (pp_np_trans). Če filter prilagodimo na:  
dat_pri >= '2020-01-01' AND dat_pri <= '2025-01-01' AND model_posla = 'PPL' AND vrsta_posla IN (1) AND sestava = 1 AND ef_najem > 0 AND (obrat_str = FALSE OR obrat_str IS NULL) AND (cas_najema = 2 OR (cas_najema = 1 AND trajanje >= 6)) AND status_pregleda = 1, 
dobimo nekaj transakcij. Prosim, da preverite pravilnost filtrov za _NAJ in _MN modele, ter nam jih sporočite, da jih lahko popravimo.  
Zapis DATE ni potreben. Če je v filtru dodano datumsko polje se lahko zapiše kot: dat_pri > ‘2020-01-01'.  
Vir transakcij v MD verzije modeli: 
ODG: Vir transakcij se v skripti določi na podlagi končnice imena modela. *_NAJ -> pp_np_trans; *_MN -> md_trans_mn; ostalo -> pp_kp_trans 
Doda se atribut kjer je to jasno prikazano. Za odgovor glede črpanja podatkov za fiktivne prodaje počakamo Primoža. Prav tako Primož pove na podlagi česa se polni atribut md_verzije_modeli.skupina. 
Posel z id_posla = 894728 ima v ISAMu dodan napačen prostor.  
ODG: Pogledamo kje pride do težave. 
Pri modelu PPP je veliko transakcij z desno vrednostjo enačbe null. 
ODG: Vrednost se ne izračuna ker je atribut velikost na transakciji prazen. Pogledamo ali je to napaka. 
Velikost label naj se prilagaja merilu 
ODG:  
Dodati obvestilo ob začetku in koncu procesa izdelave poročila o modelu 
Poročila o modelu naj bodo v DOCX obliki, ne PDF 
ODG: Gre za večjo spremembo. O odločitvi vas obvestimo naknadno. 
Prikaz transakcij na karti naj se ne reducira tudi pri manjšem merilu. Transakcije naj se prikažejo pri vseh verzijah modelov, ki transakcije vključujejo 
ODG: Model PPL ne prikazuje transakcij ker zapisi za ta model v md_trans nimajo geometrije. Napako bomo odpravili. Pri pregledu transakcij na karti je potrebno pazit in upoštevat filter “Delovna coniranje” = True in ustrezno nastavit atribut md_verzije_modeli.delovna za določeno verzijo modela 
Na 3D tabeli gradnikov faktorja obratovalnih stroškov, se prikažejo napačne vrednosti (v bazi so prave vrednosti) 
Pri testiranju je težava odkriti transakcijo, ki vsebuje vse vrednosti iz enačbe. Ali obstaja možnost filtriranja transakcij, ki imajo določene vrednosti v osnovi izpolnjene? 
V kopiranje med verzijami modelov se doda atribut barvne sheme 
 
Teme za naslednjič: 
- kaj je drugi TAO, kako funkcionira 
- črpanje podatkov za MN in fiktivne trans 
- odločitev o prepisu poročila o modelu v DOCX obliko 







Does it include everything said here:




SQL filtri na MD verzije modeli: Uporaba besede DATE pri dat_pri. Je to smiselno? To je načeloma Oracle sintaksa.


Vir transakcij v MD verzije modeli:
Katera tabela je vir transakcij za izbrano verzijo modela? pp_kp_trans, pp_np_trans? Kako vemo, iz katere tabele se zgodi osvežeitev transakcij za dan model? Je hardcoded na modele z *_NAJ, da gredo na najeme?
To mora biti na vrstici gumb, kjer se pove, od kje se črpa.
Je to tisti gumb Skupina?
Kaj pa Množitelji?
Kaj pa fiktivne prodaje? Nastavi to črpanje tisti boolean field Fiktivne?



PPP_NAJ in PPP_MN sta imela 0 transakcij kjub uspešnemu uvozu.




Posel s posel_id 894728 ima prostor 99, ampak v GV ima prostor: 3 - Poslovni prostor.
Melita ima v migraciji, da ok.
Nekje pri nas je težava.

V modelu PPP ima ogromno transakcij po preračunu desna 0. Povsod ta velikost null. To je s tem id prostora 99 povezano.




Prikaz transakcij na karti:
Ne sme biti redukcije na sloju. Treba je videti, kje se nahajajo vse tranakcije, tudi na višjem zoom-u.
Je točkovni sloj in načeloma ne bi smel biti problem, da bi crashalo aplikacijo.
Skalabilnost pikic na karti - da ima vedno v merilu velikost. Tako da ko zoom in/ zoom out delaš, da se velikost glede na objekte na karti ne spreminja.



Kako deluje flag Drugi TAO? Bosta 2 vnosa na tem sloju? Z Gašperjem niti ne veva, kaj so želje naročnika.


Obratovalni stroški so povsem našačne številke v tej tabeli v sidepanel-u. Posnetek na prbl. 1h 20min pokazano


Problem testiranja:
Kako naj se preverja, če je npr. v_gar ali povrsina_dp pravilna v enačbi, če se ne da filtrirat na transakcije, ki imajo to vrednost v osnovi izplonjeno.
Ker na vmesni?izr je samo JSON prisoten in po tistem ne moreš filtrirat. Nekako tako opisan problem.







Create a .md file where one col will have things from the main doc, and the other col will have stuff from my notes and we will see the pairings and where the other col has a null val