# Pridružitev modela na VO ter ponastavitev in kopiranje hierarhije

Definicije:
- **VO:** verzija območij.
- **VM:** verzija modela.
- **Hierarhija geometrij VM:** cone, LAO, TAO in povezave con z območji.

## 1. Pridružitev VM drugemu VO

VM lahko pridružite drugemu VO, če:

- imata **izvorni in ciljni VO oba »Delovna geo coniranje« nastavljeno na true**;
- je izbrani VM **edini VM svojega tipa na izvornem VO** (npr. edini PPP);
- izbrani VM ni zaklenjen ali pripisen.

**Če željeni VM ni edini svojega tipa na VO, lahko pred pridružitvijo najprej naredite kopijo izvornega VO.** Na novi VO se prenese samo najvišja verzija VM posameznega tipa. Prejšnji VO dobi »Delovna geo coniranje = false«, novi pa »Delovna geo coniranje = true«.

Na primer: če izvorni VO vsebuje PPP v5 in PPP v6, premik nobenega od njiju ni dovoljen. Po kopiranju VO je na novi VO samo PPP v6, zato ga lahko pridružite drugemu VO z »Delovna geo coniranje = true«.

Omejitev na en VM istega tipa na izvoru zagotavlja, da po premiku tam ne ostane drug VM tega tipa. Tako isti tip modela ne ostane na dveh VO z »Delovna geo coniranje = true«, ampak le na enem.

### Kaj se zgodi ob pridružitvi?

Izberete VM in ciljni VO. Izbrani VM se premakne na ciljni VO, njegova hierarhija pa se **samodejno ponastavi**:

1. Prejšnje cone, LAO, TAO in povezave z območji se odstranijo.
2. Ustvari se ena cona na vrednostni ravni 1, povezana z vsemi območji ciljnega VO, brez LAO in TAO.

Prejšnje geometrije VM se ne ohranijo. Območja obeh VO in drugi VM se ne spremenijo. Povezavo VM–VO spreminjate s to akcijo, ne z ročnim prevezovanjem.

Po pridružitvi lahko začnete coniranje iz te začetne cone. Če želite uporabiti hierarhijo drugega VM na ciljnem VO, sprožite **kopiranje hierarhije**, opisano spodaj.




## 2. Dva workflowa za hierarhijo na istem VO

### Ponastavitev hierarhije

Za izbrani VM odstranimo obstoječe cone, LAO, TAO in njihove povezave z območji. Ustvarimo **eno cono na vrednostni ravni 1**, povezano z vsemi območji njegove VO, brez LAO in TAO. Če VO nima območij, je cona brez povezav in geometrije.

To je ista ponastavitev, ki se samodejno izvede ob pridružitvi. Lahko jo sprožite tudi pozneje, kadar želite coniranje začeti znova.

### Kopiranje hierarhije iz drugega VM

Izberete izvorni in ciljni VM, ki sta na **istem VO**. Celotno hierarhijo ciljnega VM nadomestimo s kopijo con, LAO, TAO in povezav z območji izvornega VM. Izvorni VM ostane nespremenjen.

- Če ciljni VM podpira vsaj toliko vrednostnih ravni kot izvorni, se ravni con ohranijo.
- Če jih podpira manj, se vsem kopiranim conam nastavi raven 1.

Pri obeh workflowih VM, ki ga spreminjamo, **ne sme biti zaklenjen ali pripisen**. Območja VO in hierarhije drugih VM ostanejo nespremenjeni.


## 3. Kasnejša izboljšava: pridružitev z geometrijskim uparjanjem

Ob pridružitvi bi lahko namesto osnovne ponastavitve **ohranili cone, LAO in TAO premaknjenega VM** ter njegove cone povezali z območji ciljnega VO glede na geometrijsko ujemanje.

Uporabili bi eno od strategij uparjanja:

- cona v celoti vsebuje območje;
- cona in območje se prekrivata;
- cona pokriva vsaj izbrani delež območja (98%, 80%, 51%).

Tako bi lahko na ciljnem VO nadaljevali z obstoječo hierarhijo premaknjenega VM. Ta možnost bo implementirana kasneje. V trenutni izvedbi pridružitev vedno izvede osnovno ponastavitev, kopiranje hierarhije drugega VM pa je ločena akcija.
