

Ustvarjanje VM je na 2 načina:
- kopiranje modela: dobi št. verzije MAX(številke tipa modela) + 1. Poveže se na isti VO kot izvoren model.
- ustvarjanje iz nule: tudi dobi št. verzije MAX(številke tipa modela) + 1. Povezan na noben VO.



(Latest VM ne obstaja več, ker ni smiselen, ker lahko delaš kopijo starega VM, ki bo potem dobil najvišjo številko VM možno, in bo na starem, zaklenjenem, ne-frontnem VO.)


Flaga na VO:

Delovna geo coniranje: se ne da nastavljat ročno (nastavlja ga kopiranje VO). 
Določa frontni VO (zadnja kopija v verigi).
VM znotraj frontenga VO, ki imajo najvišjo številko za nek tip modela ki je v tem VO, je frontni VM.
Samo za frontni VO se lahko dela kopija VO - izvorni VO dobi "Delovna geo coniranje" na false, novi pa na true. V nov VO se vzamejo samo frontni modeli.
Če je kdaj želja po ročni spremembi, kater VO je fronten, se mora kontaktirati nas, da to izvedemo na varen način na bazi.
(To omejitev kopiranja lahko naredimo na SFCju kopiranja, kjer tega gumba ni, kjer je "Delovna geo coniranje" false).
(Lahko bi dodali dvoje: 
- nefrontni VO se lahko kopira, in se vzamejo psevdo-frontni modeli, ampak ciljni VO ima vseeno "Delovna geo coniranje" na false, ker ni frontni.
- lahko delaš prazno kopijo VO, kejr se kopirajo le območja, ampak se ne prenese noben model. Ta ima tudi "Delovna geo coniranje" false, potem pa lahko vanj pridružuješ neke VM in morda enkrat nam rečeš, da je zdaj to fronten VO.)

Zaklenjen: Lahko false samo pri frontnih VO, torej teh, ki imajo delovna_geo_coniranje na true.


Sidenote vidnosti na slojih:
Po defaultu se delovna_geo_coniranje za nek tip modela to, kar določa vidnost območij.
Območja so lahko druga, kot to, katere cone, lao, tao so prikazani - te so za delovni model.
Da vidiš prava območja, ročno spremeniš filter.
(Lahko bi dodali tudi moj dodatek obstoječemu VM triggerju, kjer bi vodili, kateri VM so pri neki VO delovni in bi potem bilo to usklajeno na slojih in bi vedno videl pravi model. Sicer na zaklenjeni VO ne bi mogel urejat, lahko bi pa prevezoval. Ampak te stari VM so itak tudi načeloma zaklenjeni, tako da tudi prevezovat ne moreš.)


Premikanje med VM med VO je problematično, ker po premiku obmxcone kažejo na območja povsem drugega VO. Za to premikanje se mora uporabljat nek workflow.
Premikanje je lahko za nek VM na drugem VO (kot je kopiran model) ali pa za nek model, ki je bil ustvarjen iz nule (nima VO).

Kaj se zgodi ob premikanju bomo obravnavali po tem, ko pogledamo kopiranje geometrij znotraj VO.



Kopiranje se lahko izvaja tudi znotraj VO, in sicer na 3 načine:

   1. Prekopiranje hierarhij VM: izberemo izvorni VM in ciljni VM ki sta v istem VO. Celotna veriga geometrij (cone, LAO, TAO) izbranega VM se kopira na geometrije VM, ki ga prestavljamo.  
      
       1. Če je število vrednostnih ravni ciljnega VM večje ali enako od števila vrednostnih ravni premikajočega VM, se številka vrednostne ravni na conah prav tako kopira. 
          
       2. Če ni, potem se na premikajočem VM vsem conam št. vrednostne ravni nastavi na 1. 
          
   2. Ponastavitev hierarhij VM: izbrišejo se vsi TAO, LAO, cone, obmxcone. Potem se ustvari ena cona, in zanjo se ustvari vnose v obmxcone za vsa območja VO, in št. ravni se ji nastavi na 1. (tako je bilo rečeno na sestanku, da se naredi 1 cona.) (Če hočejo potem to cono izbrisati, lahko pogledajo obmxcone izven administracije, filtrirajo za verzijo modela, in pobrišejo vse vnose.)



!!!!!!!!!! Workflowi morajo tudi paziti: ne smejo ze zagnati, če je VM zaklenjen ali pripisen.







Za izvedbo smiselnega premikanja torej potrebujemo le eno stvar:
Ko se model pridruži na nek VO, se mora izvesti "Ponastavitev hierarhij VM".
Če želijo, lahko potem naredijo "Prekopiranje hierarhije VM"

Moramo pa paziti na nekaj:
- Če premikamo model iz frontnega VO (ima delovna_geo_coniranje True) potem mora to biti edini model tega tipa na VO (kar lahko zagotovimo tako, da prej naredimo kopijo VO).
Sicer se lahko zgodi, da 2 frontna VO vsebujeta isti tip modela, torej ima nek tip modela dva frontna VM, kar pa je problem.
- če prekimamo iz ne-frontnega VO na nek frontni VO, ki nima tega tipa modela, imamo problem - ker ima nek drug forntni VO že ta tip modela. Na koncu bi imeli 2 frontna VO s tem tipom modela, torej tudi 2 frontna VM za ta tip modela. Torej to ne sme biti omogočeno.
- če premikamo Vm iz frontnega VO na ne-frontni VO, potem smo frontni VM dali v mesto, kjer ne mroe več postati fronten (zaradi zgornjega pravila). Lahko bi dodatno omejili, da ni smel biti zadnji model tega tipa na tem VO, tako da bo ta tip na izvornem VO potem imel nek drug frontni model. Ampak predvidevaam, da jim ne bo všeč, da jim je omogočeno njihov ljubi frontni model poslati v stanje, kjer ne more več postati fronten, tako da bomo to celotno premikanje preprečili.

(Na sestanku smo dobili potrjeno še zožano verzijo: da se lahko premika samo "latest" modele, kar je praktično pomenilo samo frontne modele. Ampak lahko smo malo širši od tega.)

Torej premik mora biti doboljen le če:
- izvorni VO in ciljni VO imata enak delovna_geo_coniranje (oba frontna ali nefrontna)
- če imata VO delovna_geo_coniranje na true, potem mora biti na izvornem VO to edini VM s tem tipom modela (kar lahko naredimo s predhodno kopijo izvornega VO)
- VM, ki se premika, ni zaklenjen in ni pripisen


Želel bi tudi neko kopiranje pred premikanjem, da se ohrani stara hierarhija in se ne morejo grdo pokvarit zadeve.
Ampak premikanje med frontnimi VO ti na starem ne sme pustit modela, ker bi bila dva VM frontna. Tako da to je problem.
Morda, da ko se med nefrontnimi VO dogaja premikanje, da se najprej zgodi kopija?


Tako da zgornje omejitve morda predrugačim v 2 veji izvedb s to psevdokodo:
- izvorni VO in ciljni VO nimata enak delovna_geo_coniranje (nista oba frontna ali nefrontna) -> error
- če imata oba VO false, se naredi kopija VM, potem pa se izvede WF premika za to kopijo
- če imata oba true, potem:
    - Če VM, ki se premika, je zaklenjen in je pripisen, potem error
    - Če VM, ki se premika, na izvornem VO ni edini VM s tem tipom modela (kar lahko naredimo s predhodno kopijo izvornega VO), potem error.
    - Sicer se zgodi direktno premik WF, brez predhodne kopije.


TOPLO PRIPOROČAMO:
Preden premikate frontni VM na nek frontni VM, naredite kopijo izvornega VM, in potem naredite kopijo njegovega VO.
Tako boste ohranili stare hierarhije in je veliko lažje popraviti predhodno stanje, če si potem premislite.


Dorazvoj: geometrijski premik:

Obstaja pa kompleksnejša ideja premikanja z geometrijskim uparjanjem.
To pa je workflow, ki se ne more izvesti znotraj VO, ampak samo ob premikanju - ker so takrat cone še povezane z originalnimi območji in imajo še smiselne geometrije, ki jih lahko geometrijsko upoarjamo s ciljnimi območji.

Ohranimo cone, LAO, TAO premikajočega modela. Povezave obmxcona se ustvarijo glede na geometrijski presek novih območij in premaknjenih con (opcije so ST_Contains, ST_Intersects, ali pa npr. da cona pokriva več kot npr. 51% ali 98% območja.) 


Dorazvoj: kopija hierarhije med različnimi VO na podlagi geometrijskega uparjanja:
Primer uporabnosti: Ko smo iz frontnega VO premaknili frontni VM, smo izgubili hierarhijo, ki smo jo prej imeli. Lahko bi kopirali hiterarhijo za en model prej, kjer pa bi izvedli geometrijsko uprajanje na ciljno VO.










