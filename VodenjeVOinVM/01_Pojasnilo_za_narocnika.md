# Kopiranje in pridruževanje modelov verzijam območij

Predlog delovanja za potrditev naročnika. Dokument opisuje osnovno izvedbo; geometrijsko uparjanje med različnimi verzijami območij ni vključeno.

## Kaj sta frontni VO in frontni VM?

**Verzija območij (VO)** vsebuje območja, na katerih se izdeluje coniranje modelov. Več verzij modelov (VM) lahko uporablja isto VO. Cone, LAO in TAO pripadajo posameznemu VM.

**Frontni VO** je trenutna verzija v svoji verigi kopij območij. Ko jo kopiramo, nova VO postane frontna, prejšnja pa zgodovinska. Hkrati lahko obstaja več frontnih VO za različne tipe modelov.

**Frontni VM** je VM z najvišjo številko verzije svojega tipa na frontnem VO. Najvišja številka med vsemi verzijami tega tipa v sistemu sama po sebi ne pomeni, da je VM frontni.

| Primer | Kaj je frontno? |
|---|---|
| Frontni VO A vsebuje PPP v5, PPP v6 in STA v3. | Frontna VM sta PPP v6 in STA v3. PPP v5 ni frontni. |
| Na zgodovinskem VO B naredimo kopijo PPP v2 in nastane PPP v7. | PPP v7 ni frontni, čeprav ima višjo številko kot PPP v6 na VO A. |
| Kopiramo frontni VO A. | Nova VO postane frontna; nanjo se premakneta PPP v6 in STA v3. PPP v5 ostane na stari VO. |

En tip modela ne sme imeti frontnih VM na dveh različnih frontnih VO. Pravila pridruževanja ohranjajo to razporeditev.

Frontnost in zaklenjenost sta različni lastnosti. Zgodovinski VO ima zaklenjena območja. Tudi frontni VO je lahko zaklenjen. Zaklenjenost VO varuje območja, zaklenjenost oziroma pripisnost VM pa varuje podatke in hierarhijo tega VM. Pridruževanje in kopiranje hierarhije ne spreminjata območij VO.

## Ustvarjanje in kopiranje

### Nova verzija modela

- **Kopija VM:** dobi naslednjo številko verzije za svoj tip modela in ostane na istem VO kot izvorni VM. Kopira se tudi njegova hierarhija. Kopiranje VM ne ustvari nove VO.
- **VM iz nič:** dobi naslednjo številko verzije za svoj tip modela, vendar še nima VO. Na VO ga uporabnik priključi z akcijo »Pridruži na VO«.

Kopiranje starega modela ustvari novo številko verzije, vendar ga ne prestavi samodejno na frontni VO. Če kopija nastane na frontnem VO, postane frontni VM svojega tipa na tem VO. Uporabnik mora pri izbiri izvora kopiranja upoštevati ta učinek.

### Nova verzija območij

Kopirati je mogoče samo frontni VO. Kopiranje:

1. Ustvari novo VO s kopiranimi območji.
2. Novo VO označi kot frontno, prejšnjo pa kot zgodovinsko in zaklenjeno.
3. Na novo VO premakne samo frontne VM prejšnje VO: po enega z najvišjo številko verzije za vsak prisotni tip modela.
4. Ohrani njihove hierarhije in jih poveže s kopiranimi območji nove VO.

Starejši VM ostanejo na prejšnji VO. Kopiranje VO ne ustvarja novih številk verzij modelov. Frontnosti VO uporabnik ne more spreminjati ročno; izjemne spremembe izvede izvajalec.

## Pridružitev VM na VO

Uporabnik izbere VM in ciljni VO ter sproži namensko akcijo. Neposredno ročno spreminjanje povezave med VM in VO ni omogočeno.

**Vsaka uspešna pridružitev ponastavi hierarhijo VM:** obstoječe cone, LAO, TAO in povezave z območji se odstranijo. Nastane ena cona na vrednostni ravni 1, ki vsebuje vsa območja ciljnega VO. LAO in TAO se pri ponastavitvi ne ustvarita.

Po pridružitvi lahko uporabnik nadaljuje coniranje ali prekopira hierarhijo drugega VM na istem VO.

| Izvor VM | Ciljni VO | Dovoljeno delovanje |
|---|---|---|
| VM še nima VO. | Zgodovinski VO. | Pridruži se isti VM in ponastavi njegova hierarhija. |
| VM še nima VO. | Frontni VO, ki že vsebuje njegov tip modela. | Pridruži se isti VM; kot nova verzija postane frontni VM tega tipa. Hierarhija se ponastavi. |
| VM še nima VO. | Frontni VO, ki ne vsebuje njegovega tipa modela. | Pridružitev ni dovoljena. |
| Zgodovinski VO. | Zgodovinski VO. | Najprej se ustvari odklenjena, nepripisna kopija VM. Pridruži in ponastavi se kopija; izvorni VM ostane nespremenjen. |
| Frontni VO. | Frontni VO. | Neposredno se premakne izbrani VM, če je edini VM svojega tipa na izvornem VO ter ni zaklenjen ali pripisen. Hierarhija se ponastavi. |
| Zgodovinski VO. | Frontni VO. | Ni dovoljeno. |
| Frontni VO. | Zgodovinski VO. | Ni dovoljeno. |

Zaklenjen ali pripisen VM se ne spreminja. Lahko pa se uporabi kot izvor kopije v postopku zgodovinski → zgodovinski, ker se tam spreminja nova, odklenjena kopija.

Izbira istega VO kot ciljnega ni posebej prepovedana. Tudi takšna akcija izvede zgornji postopek: na zgodovinskem VO ustvari in ponastavi kopijo; na frontnem VO ponastavi izbrani VM, če izpolnjuje pogoj edinega VM svojega tipa.

### Priporočen postopek za ohranitev stare hierarhije

Pred premikom med frontnima VO priporočamo:

1. Naredite kopijo VM na izvornem VO.
2. Naredite kopijo izvornega VO. Nova kopija VM se skupaj z drugimi frontnimi VM premakne na novo frontno VO; starejši VM ostane na zgodovinski VO.
3. Novo kopijo VM pridružite ciljnemu frontnemu VO. Na njenem izvornem frontnem VO je zdaj edini VM svojega tipa, zato je premik dovoljen.

**Primer:** VO A vsebuje PPP v6 in STA v3. Kopiramo PPP v6 → v7, nato kopiramo VO A → A2. PPP v6 ostane na zgodovinskem A, PPP v7 in STA v3 se premakneta na frontni A2. PPP v7 lahko zdaj pridružimo frontnemu VO B. Njegova hierarhija se ponastavi, hierarhija PPP v6 pa ostane ohranjena.

Ta predhodna kopija je priporočilo, ne obveznost. Pri neposrednem premiku brez ohranjene kopije uporabnik izgubi prejšnjo hierarhijo premaknjenega VM.

## Delo s hierarhijo na istem VO

### Ponastavitev hierarhije

Uporabnik lahko ločeno ponastavi hierarhijo odklenjenega, nepripisnega VM, ki že ima VO. Rezultat je enak kot pri pridružitvi: ena cona na ravni 1 z vsemi območji njegove VO, brez LAO in TAO. Podatki drugih VM in območja VO se ne spremenijo.

### Prekopiranje hierarhije iz drugega VM

Uporabnik izbere izvorni in ciljni VM na istem VO. Ciljna hierarhija se nadomesti s kopijo izvornih con, LAO, TAO in njihovih povezav z območji. Izvorni VM ostane nespremenjen. Ciljni VM ne sme biti zaklenjen ali pripisen.

- Če ciljni model podpira vsaj toliko vrednostnih ravni kot izvorni, se ravni con ohranijo.
- Če jih podpira manj, se vsem kopiranim conam nastavi raven 1.

**Primer:** kopiranje iz modela z 10 ravnmi v model s 15 ravnmi ohrani ravni. Kopiranje iz modela s 15 ravnmi v model z 10 ravnmi vse kopirane cone nastavi na raven 1.

Kopiranje hierarhije ne spremeni verzije ali tipa ciljnega modela in ne prenese njegovih modelskih nastavitev iz izvora. Kopiranje hierarhij med različnimi VO v tej izvedbi ni omogočeno.

## Prikaz na karti in nadaljnji izračuni

Privzeti prikaz območij uporablja frontni VO, prikaz con, LAO in TAO pa izbiro delovnega modela. Ti izbiri nista samodejno usklajeni. Pri delu z drugim VM uporabnik prilagodi filter območij, da prikazuje njegovo VO.

Preračun podatkov, vezanih na transakcije, se po spremembi hierarhije sproži posebej na zahtevo uporabnika.

## Kaj potrjuje naročnik?

Potrditev tega predloga pomeni potrditev definicije frontnosti, pravil v tabeli pridruževanja, ponastavitve na eno cono, ločenega kopiranja hierarhije ter priporočila za ohranitev starega stanja pred premikom. Geometrijsko uparjanje med različnimi VO, kopiranje zgodovinskih VO in ročno izbiranje novega frontnega VO niso del te izvedbe.
