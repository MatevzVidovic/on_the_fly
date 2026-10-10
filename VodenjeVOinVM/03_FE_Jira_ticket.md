# FE: SFC akcije za pridružitev VM in upravljanje hierarhije

## Cilj in odvisnost

Dodati tri SFC akcije nad verzijo modela ter omejiti običajno ročno spreminjanje povezave VM–VO in frontnosti VO. Akcije uporabljajo workflowe iz [BE ticketa](02_BE_Jira_ticket.md). Domenski potek je opisan v [pojasnilu za naročnika](01_Pojasnilo_za_narocnika.md).

Frontend ne izvaja kopiranja ali prevezovanja sam; odda vhodne ID v BE workflow in prikaže njegov rezultat.

## Nove SFC akcije

| Akcija na VM | Uporabniški vhod | Workflow |
|---|---|---|
| **Pridruži na VO** | Izbira ciljnega VO. | `JoinModelToGeoVersionWorkflow(vm_id, target_vo_id)` |
| **Ponastavi hierarhijo** | Brez dodatnega modela ali VO; uporablja VO izbranega VM. | `ResetModelGeoHierarchyWorkflow(vm_id)` |
| **Prekopiraj hierarhijo iz VM** | Izbira izvornega VM na istem VO; trenutni VM je cilj. | `CopyModelGeoHierarchyWorkflow(source_vm_id, target_vm_id)` |

## 1. Pridruži na VO

V izboru VO prikazati najmanj številko oziroma naziv VO, frontnost in prisotne tipe modelov. Zaklenjenost VO ni razlog za izključitev cilja; akcija ne spreminja območij.

### Dovoljene izbire

| Stanje izbranega VM | Cilji in delovanje |
|---|---|
| Brez VO, spremenljiv VM | Vsi zgodovinski VO; frontni VO samo, če že vsebujejo njegov tip modela. Pridruži se isti VM. |
| Na zgodovinskem VO | Samo zgodovinski VO. BE najprej ustvari spremenljivo kopijo in pridruži kopijo. Zaklenjenost/pripisnost izvornega VM ne onemogoči branja za kopijo. |
| Na frontnem VO, spremenljiv VM, edini svojega tipa na izvoru | Samo frontni VO. Premakne se isti VM. |
| Na frontnem VO, zaklenjen/pripisen ali več VM njegovega tipa na izvoru | Akcija ni omogočena; prikazati razlog. |

Enakega VO kot ciljnega ni treba izključiti. Akcija tudi v tem primeru ponastavi hierarhijo oziroma v zgodovinski veji ustvari kopijo.

### Besedilo pred zagonom

Vedno prikazati: **»Pridružitev nadomesti hierarhijo modela z eno cono na vrednostni ravni 1, povezano z vsemi območji izbrane VO. Obstoječe cone, LAO in TAO modela, ki se pridružuje, se odstranijo.«**

Za zgodovinski izvor dopolniti: **»Najprej bo ustvarjena kopija modela. Izvorni model in njegova hierarhija ostaneta nespremenjena.«**

Za neposredni frontni premik dopolniti: **»Za ohranitev prejšnje hierarhije priporočamo, da pred pridružitvijo kopirate model in nato njegov izvorni VO. Ta korak ni obvezen.«**

FE ne ponuja samodejnega paketa kopiraj VM → kopiraj VO → pridruži. Uporabnik po potrebi izvede obstoječe akcije ločeno.

## 2. Ponastavi hierarhijo

Omogočiti za VM, ki ima VO in ni zaklenjen ali pripisen. Frontnost in zaklenjenost njegove VO nista pogoja.

Besedilo: **»Obstoječe cone, LAO, TAO in povezave z območji bodo odstranjene. Nastala bo ena cona na vrednostni ravni 1 z vsemi območji trenutne VO. LAO in TAO ne bosta ustvarjena.«**

Po uspehu osvežiti prikaz VM in njegove hierarhije.

## 3. Prekopiraj hierarhijo iz VM

Omogočiti za ciljni VM, ki ima VO in ni zaklenjen ali pripisen. Izbor izvora vsebuje samo druge VM na isti VO. Zaklenjen/pripisen izvor je dovoljen, saj se ne spreminja.

V izboru prikazati tip modela, verzijo in naziv. Trenutnega ciljnega VM izključiti iz izbora izvora.

Besedilo: **»Hierarhija ciljnega modela bo nadomeščena s kopijo con, LAO, TAO in povezav z območji iz izbranega modela. Izvorni model ostane nespremenjen.«**

Dodati pravilo ravni: **»Če ciljni model podpira manj vrednostnih ravni kot izvorni, bodo vse kopirane cone nastavljene na raven 1. Sicer se ravni ohranijo.«**

Po uspešni pridružitvi naj bo ta akcija na voljo nad dejanskim rezultatskim VM. Ne zagnati je samodejno kot drugi korak pridružitve.

## Omejitve obstoječih akcij in obrazcev

- Na obstoječem SFC **kopiranja VO** prikazati gumb samo za `delovna_geo_coniranje=true`. Zaklenjen frontni VO je lahko kopiran; ne filtrirati po `zaklenjena=false`.
- Onemogočiti običajno ročno nastavljanje `delovna_geo_coniranje`, tudi v administrativnem obrazcu. Uporabniške akcije ne prestavljajo frontnosti ročno.
- Onemogočiti običajno ročno spreminjanje VM → VO (`id_rel_geo_verzija`), tudi v administrativnem obrazcu. Pri VM iz nič VO ostane prazen do pridružitve. Pri obstoječem VM se VO prikazuje kot podatek, za spremembo se uporabi SFC.
- Ohraniti obstoječi akciji kopiranja VM in VO. Ne uvajati globalnega »latest« filtra za izbiro izvornega VM ali novih akcij.
- Ne omejiti ponastavitve oziroma kopiranja hierarhije na frontne VM; odločilna je spremenljivost ciljnega VM.

## Zagon, rezultat in obvestila

- Med izvajanjem trenutne oddane akcije prikazati stanje izvajanja; uspeh prikazati šele po zaključku BE workflowa.
- Po pridružitvi uporabiti `result_vm_id`. Pri zgodovinski veji odpreti oziroma ponuditi odprtje nove kopije, ne osvežiti samo izvora.
- Prikazati ciljni VO in podatek, ali je nastala kopija.
- Po uspehu osvežiti relevantne prikaze podatkov; ne spreminjati samodejno izbire delovnega modela ali filtrov območij na karti.
- BE napako prikazati z razumljivim razlogom. FE izbor in omogočenost akcij sta pomoč uporabniku; končno odločitev sprejme BE.
- Po ponastavitvi/kopiranju ne sprožiti avtomatskega transakcijskega preračuna. Ostane obstoječa ločena uporabniška akcija.

## Sprejemni kriteriji

1. Vsak SFC odda pravilne ID v ustrezen workflow; kopiranje hierarhije uporablja trenutni VM kot cilj.
2. Izbori in onemogočene akcije sledijo zgornjim pravilom, vključno z VM brez VO in zaklenjenim zgodovinskim izvorom.
3. Uporabnik pred pridružitvijo ali ponastavitvijo razume, da bo hierarhija nadomeščena z eno cono.
4. Pri zgodovinski pridružitvi je rezultat nova kopija, ki jo uporabnik lahko odpre in na njej nadaljuje delo.
5. Kopiranje VO je prikazano samo na frontnih VO, tudi kadar so zaklenjeni.
6. Povezave VM–VO in frontnosti ni mogoče spreminjati v običajnih uporabniških obrazcih.
7. Geometrijsko uparjanje, kopiranje hierarhije med različnimi VO in kopiranje zgodovinskih VO niso ponujeni.
