# Ponastavitev, kopiranje in pridružitev modela na VO

Predlog možnosti za potrditev naročnika.

- **VO:** verzija območij.
- **VM:** verzija modela.
- **Hierarhija geometrij VM:** cone, LAO, TAO in povezave con z območji.

## 1. Dve možnosti na istem VO

### Ponastavitev hierarhije

Za izbrani VM odstranimo obstoječe cone, LAO, TAO in njihove povezave z območji. Ustvarimo **eno cono na vrednostni ravni 1**, povezano z vsemi območji njegove VO. LAO in TAO se ne ustvarita.

Ta možnost omogoča, da coniranje začnete znova.

### Kopiranje hierarhije iz drugega VM

Izberete izvorni in ciljni VM, ki sta na **istem VO**. Hierarhijo ciljnega VM nadomestimo s kopijo con, LAO, TAO in povezav z območji izvornega VM. Izvorni VM ostane nespremenjen.

- Če ciljni VM podpira vsaj toliko vrednostnih ravni kot izvorni, se ravni con ohranijo.
- Če jih podpira manj, se vsem kopiranim conam nastavi raven 1.

Pri obeh možnostih VM, ki ga spreminjamo, **ne sme biti zaklenjen ali pripisen**. Območja VO in hierarhije drugih VM ostanejo nespremenjeni.

## 2. Pridružitev VM drugemu VO

VM lahko pridružite drugemu VO, če:

- imata **izvorni in ciljni VO oba »Delovna geo coniranje« nastavljeno na true**;
- je izbrani VM **edini VM svojega tipa na izvornem VO**;
- izbrani VM ni zaklenjen ali pripisen.

Na primer: če izvorni VO vsebuje PPP v5 in PPP v6, premik nobenega od njiju ni dovoljen. Po kopiranju izvornega VO je na novi VO samo PPP v6, zato ga lahko pridružite drugemu VO z »Delovna geo coniranje = true«.

### Kaj se zgodi ob pridružitvi?

Izberete VM in ciljni VO. Izbrani VM se premakne na ciljni VO, njegova hierarhija pa se **samodejno ponastavi**:

1. Prejšnje cone, LAO, TAO in povezave z območji se odstranijo.
2. Ustvari se ena cona na vrednostni ravni 1, povezana z vsemi območji ciljnega VO, brez LAO in TAO.

Prejšnje geometrije VM se ne ohranijo. Območja obeh VO in drugi VM se ne spremenijo. Povezavo VM–VO spreminjate s to akcijo, ne z ročnim prevezovanjem.

### Kako nadaljujete?

Po pridružitvi lahko začnete coniranje iz ene začetne cone ali uporabite **kopiranje hierarhije drugega VM na ciljnem VO**. Pozneje lahko hierarhijo ponovno ponastavite ali nadomestite z drugo kopijo, po pravilih iz prvega poglavja.

### Kako ohranite prejšnjo hierarhijo?

Pred pridružitvijo priporočamo, da najprej kopirate VM in nato njegov izvorni VO. Na novi VO bo kopirani VM edini svojega tipa, zato ga boste lahko premaknili. Prejšnji VM s svojo hierarhijo ostane ohranjen na prejšnji VO.

To je priporočilo, ne obveznost. Pri neposredni pridružitvi brez predhodne kopije se prejšnja hierarhija premaknjenega VM izgubi.
