# Vodenje verzij območij in modelov

Pojmi za različice vrednostnih modelov, njihove prostorske hierarhije in pripadnost verzijam območij. Slovar opisuje dogovorjeni domenski model.

## Jezik

**Tip modela**:
Vrsta vrednostnega modela, na primer PPP. Več VM istega tipa predstavlja različne verzije tega tipa modela.

**VM — verzija modela**:
Posamezna verzija vrednostnega modela določenega tipa. Lahko pripada eni VO ali še ni pridružena nobeni VO.

**Številka verzije VM**:
Zaporedna številka VM znotraj njegovega tipa modela. Najvišja številka sama po sebi ne pomeni, da je VM frontni.
_Izogibaj se_: latest VM kot oznaki aktivnega modela

**VO — verzija območij**:
Skupna zbirka območij, ki jo lahko uporablja več VM različnih tipov ali več verzij istega tipa.

**Veriga VO**:
Zaporedje VO, nastalih s kopiranjem območij. Pripadnost VM verigi določa njegova trenutna VO.

**Frontni VO**:
VO, ki predstavlja trenutno nadaljevanje svoje verige. Več neodvisnih verig ima lahko svoje frontne VO.

**Frontni VM**:
VM z najvišjo številko verzije svojega tipa na frontnem VO. Isti tip modela ne sme imeti frontnih VM na dveh različnih VO.
_Izogibaj se_: globalno latest VM

**Delovna geo coniranje**:
Oznaka, ki določa, ali je VO frontni. Ni isto kot izbira delovnega VM za prikaz na karti.

**Zaklenjen VO**:
VO, katere območij ni dovoljeno urejati. Ne-frontni VO je vedno zaklenjen; frontni VO je lahko zaklenjen ali odklenjen.

**Zaklenjen VM**:
VM, katerega podatkov in hierarhije ni dovoljeno spreminjati. Zaklenjenost VM je ločena od zaklenjenosti VO.

**Pripisni VM**:
VM z oznako pripisna. Za premikanje in spreminjanje hierarhije se obravnava kot zaščiten VM.

**Območje**:
Prostorska enota, ki pripada eni VO. VM jo uporablja prek povezave s svojo cono.

**Hierarhija VM**:
Lastna struktura con, LAO in TAO posameznega VM skupaj s povezavami območij na cone.

**Cona**:
Del hierarhije VM, ki združuje dodeljena območja in ima številko vrednostne ravni.

**LAO in TAO**:
Višji ravni prostorske hierarhije VM nad conami. Po ponastavitvi hierarhije še ne obstajata.

**Obmxcona**:
Povezava med območjem VO in cono VM. Območje in VM cone morata pripadati isti VO.

**Izvorni VM in ciljni VM pri kopiranju hierarhije**:
Izvorni VM je predloga, ki ostane nespremenjena; ciljni VM prejme nadomestno hierarhijo. Oba pripadata isti VO.
_Izogibaj se_: premikajoči VM pri kopiranju znotraj VO

**Pridružitev VM**:
Pripis VM izbrani VO skupaj s ponastavitvijo njegove hierarhije. Pri pridružitvi med ne-frontnima VO se pridruži nova kopija VM.

**Ponastavitev hierarhije**:
Zamenjava obstoječe hierarhije z eno cono na ravni 1, povezano z vsemi območji trenutne VO, brez LAO in TAO.

**Prekopiranje hierarhije**:
Zamenjava hierarhije ciljnega VM z lastno kopijo hierarhije izvornega VM na isti VO. Kopija uporablja ista območja, vendar svoje cone, LAO in TAO.

**Delovni VM**:
VM, izbran za prikaz con, LAO in TAO na karti. Ni nujno frontni VM in njegov prikaz območij ni samodejno usklajen s filtrom frontnih VO.
