# BE: pridružitev VM na VO, ponastavitev in kopiranje hierarhije

## Cilj

Uvesti tri namenske workflowe: pridružitev VM na VO, ponastavitev hierarhije VM in nadomestitev hierarhije s kopijo drugega VM na istem VO. Pridružitev vedno konča s ponastavitvijo na eno cono na ravni 1. Kopiranje hierarhije je ločena uporabniška akcija.

Ta ticket uporablja potrjeni koncept **frontnega VO in lokalno frontnega VM**, ne globalnega »latest VM«. Domenske odločitve so povzete v [pojasnilu za naročnika](01_Pojasnilo_za_narocnika.md).

## Obseg

### Novi workflowi

Predlagana imena so del tega ticketa; v obstoječem FMP jih še ni.

| Workflow | Vhod | Namen |
|---|---|---|
| `JoinModelToGeoVersionWorkflow` | `vm_id`, `target_vo_id` | Izbere vejo pridružitve, po potrebi kopira VM, prestavi VM in počaka na ponastavitev. |
| `ResetModelGeoHierarchyWorkflow` | `vm_id` | Nadomesti hierarhijo z eno cono na ravni 1 in povezavami do vseh območij njegove VO. |
| `CopyModelGeoHierarchyWorkflow` | `source_vm_id`, `target_vm_id` | Nadomesti ciljno hierarhijo s kopijo hierarhije drugega VM na istem VO. |

Skupne aktivnosti za brisanje in ustvarjanje hierarhije naj se ponovno uporabijo. Za brisanje naj ne bo potrebna dodatna uporabniška akcija.

### Obstoječi workflowi in integracije

- Ponovno uporabiti `CloneModelVersionWorkflow` za vejo zgodovinski → zgodovinski, z zagotovitvijo odklenjene kopije.
- Ohraniti `GeoObmCopyWorkflow`: kopira območja, premakne lokalno najvišjo verzijo vsakega tipa iz izvorne VO in preveže `obmxcona`. Omejiti kopiranje na frontni VO.
- Podpreti ustvarjanje VM brez VO: ustvarjanje številke verzije deluje, VO-locking workflow pa se za tak VM ne sme zagnati oziroma mora varno zaključiti brez VO.
- Preprečiti običajno ročno spreminjanje `md_verzije_modeli.id_rel_geo_verzija`. Namenski workflowi, vključno z obstoječim kopiranjem VO, morajo ohraniti možnost nadzorovane spremembe.

## Definicije in pravila

| Pojem | Pravilo |
|---|---|
| Frontni VO | `md_geo_obm_verzije.delovna_geo_coniranje = true`. |
| Frontni VM | VM z največjim `verzija` za svoj `model` znotraj posameznega frontnega VO. |
| Zgodovinski VO | `delovna_geo_coniranje = false`; območja so zaklenjena. |
| Spremenljiv VM | `zaklenjena_verzija = false` in `pripisna = false`. Če je katerakoli od teh vrednosti true, se VM ne spreminja. |
| Zaklenjen VO | Varuje VO/območja; sam po sebi ne preprečuje spreminjanja hierarhije spremenljivega VM. |

Izhodiščno stanje sistema že zagotavlja razporeditev tipov po frontnih VO. Pridružitev ohranja to razporeditev z omejitvami spodaj. Ne uvajamo nove izbire frontnega VM; frontnost se še naprej določa z lokalno najvišjo številko.

Izvorni zaklenjeni oziroma pripisni VM se lahko bere za kopiranje. Omejitev spreminjanja velja za dejanski VM, ki se premika, ponastavlja ali prejema kopirano hierarhijo.

## 1. JoinModelToGeoVersionWorkflow

### Vhod in rezultat

Vhod: obstoječi `vm_id` in obstoječi `target_vo_id`.

Rezultat naj vsebuje najmanj `requested_vm_id`, `result_vm_id`, `target_vo_id` in `copied_before_join`. FE mora vedeti, ali je delal z istim VM ali z novo kopijo.

### Psevdokoda

```text
join(vm_id, target_vo_id):
    vm = fetchVM(vm_id)
    targetVO = fetchVO(target_vo_id)
    reject if either record does not exist

    if vm.id_rel_geo_verzija is null:
        requireEditable(vm)
        if targetVO.delovna_geo_coniranje is true:
            require targetVO contains at least one VM with model = vm.model
        # Na zgodovinskem ciljnem VO ni zahteve po obstoju istega tipa.
        moveAndReset(vm.id, targetVO.id)
        return result(vm.id, copied_before_join = false)

    sourceVO = fetchVO(vm.id_rel_geo_verzija)
    reject if sourceVO does not exist

    if sourceVO.delovna_geo_coniranje != targetVO.delovna_geo_coniranje:
        reject MIXED_FRONT_STATUS

    if sourceVO.delovna_geo_coniranje is false:
        # Izvor se samo bere; lahko je zaklenjen ali pripisen.
        new_vm_id = await CloneModelVersionWorkflow(vm.id)
        makeCopyEditable(new_vm_id)
        requireEditable(fetchVM(new_vm_id))
        moveAndReset(new_vm_id, targetVO.id)
        return result(new_vm_id, copied_before_join = true)

    # Oba VO sta frontna.
    requireEditable(vm)
    count = countVMs(sourceVO.id, model = vm.model)
    require count == 1
    # Štejemo vse verzije tega tipa, ne samo odklenjenih ali frontnih.
    moveAndReset(vm.id, targetVO.id)
    return result(vm.id, copied_before_join = false)

moveAndReset(actual_vm_id, target_vo_id):
    update actualVM.id_rel_geo_verzija = target_vo_id
    await ResetModelGeoHierarchyWorkflow(actual_vm_id)

requireEditable(vm):
    reject if vm.zaklenjena_verzija is true OR vm.pripisna is true
```

`makeCopyEditable` ni nov javni workflow. To je del zagotovitve rezultata obstoječega kopiranja oziroma interna aktivnost pridružitve. Kopija mora imeti `pripisna=false`, `zaklenjena_verzija=false` in odklenjene pripadajoče zapise (`__readonly=false` tam, kjer je ta atribut prisoten). Izvorni VM in njegovi zapisi ostanejo nespremenjeni.

### Pomembni primeri

- Frontni A vsebuje PPP v5 in v6: premik PPP iz A ni dovoljen, tudi če v6 predstavlja frontni VM. Najprej je treba kopirati VO.
- Frontni A vsebuje samo PPP v6: premik v frontni B je dovoljen, če PPP v6 ni zaklenjen ali pripisen. B lahko vsebuje druge tipe; ne zahtevamo, da že vsebuje PPP.
- Zgodovinski A → zgodovinski B: izvor ostane na A; na B se premakne nova kopija z naslednjo globalno številko verzije za tip.
- VM brez VO → frontni B: B mora že vsebovati isti tip. Pri zgodovinskem B tega pogoja ni.
- Enak izvorni in ciljni VO ni posebej zavrnjen. Veljajo ista pravila veje; akcija še vedno izvede ponastavitev.

Pridružitev ne kopira VO ali območij, ne spreminja `delovna_geo_coniranje` in ne premika drugih VM. Ne ohranja stare hierarhije premaknjenega VM; uporabnik jo po želji predhodno ohrani s kopiranjem VM in VO.

## 2. ResetModelGeoHierarchyWorkflow

### Predpogoji

- VM obstaja, je spremenljiv in ima obstoječ VO.
- Frontnost in zaklenjenost VO nista dodatna pogoja. Workflow spreminja hierarhijo VM, ne območij.

### Koraki

1. Zbere vse cone, LAO in TAO, ki pripadajo temu VM, ter njihove `md_geo_obmxcona` povezave.
2. Odstrani povezave `obmxcona`, nato cone, LAO in TAO v vrstnem redu, ki spoštuje reference med temi zapisi.
3. Ustvari natanko eno novo `md_geo_cona` z novim ID, `id_rel_verzije_modeli=vm_id` in `st_ravni=1`. Cona nima LAO; ne ustvarja se LAO ali TAO.
4. Za vsako `md_geo_obm` na trenutnem VO ustvari natanko eno novo `md_geo_obmxcona`, ki povezuje to območje z novo cono.
5. Geometrijo nove cone sestavi iz povezanih območij po obstoječih pravilih sestavljanja geometrij. Če VO nima območij, ostane ena cona brez povezav in brez sestavljene geometrije.

Rezultat: `vm_id`, `new_cona_id`, število ustvarjenih povezav.

Ne spreminja območij, drugih VM, modelskih nastavitev ali številke verzije. Po pridružitvi nobena povezava nove hierarhije ne kaže na območje prejšnje VO.

## 3. CopyModelGeoHierarchyWorkflow

### Predpogoji

- Oba VM obstajata in sta različna.
- Oba imata isti, obstoječi VO.
- Ciljni VM je spremenljiv. Izvorni VM je lahko zaklenjen ali pripisen, saj se samo bere.
- Frontnost in zaklenjenost VO nista dodatna pogoja.

### Koraki

1. Prebere izvorne cone, LAO, TAO, njihove medsebojne reference in `obmxcona` povezave. Prebere število vrednostnih ravni obeh VM po obstoječi definiciji v modelu.
2. Odstrani celotno obstoječo hierarhijo ciljnega VM. Ponovno uporabi interno brisanje iz ponastavitve; **ne kliče ponastavitve tako, da bi za kopijo ostala dodatna privzeta cona**.
3. Kopira vse izvorne zapise cone/LAO/TAO z novimi ID in `id_rel_verzije_modeli=target_vm_id`. Kopirani zapisi so spremenljivi, brez podedovanega `__readonly=true`.
4. Preveže vse reference znotraj kopirane hierarhije na nove ID: cona → LAO, tudi dodatne povezave LAO, kjer jih podatkovni model vsebuje; LAO → TAO. Ciljna hierarhija ne sme kazati na izvorne LAO/TAO.
5. Kopira izvorne `obmxcona`: novo območje se ne ustvarja; `id_rel_geo_obm` ostane isti, `id_rel_geo_cona` pa kaže na novo ciljno cono. Ohranijo se tudi cone brez območij in deli hierarhije brez podrejenih zapisov.
6. Nastavi ravni:
   - `target_level_count >= source_level_count`: ohrani izvorni `st_ravni`.
   - Sicer: vsem kopiranim conam nastavi `st_ravni=1`.
7. Zagotovi geometrije kopirane hierarhije, skladne s kopiranimi povezavami. Kopira strukturo, opisne podatke hierarhije in geometrije; ne prenaša modelskih nastavitev ali transakcijskih rezultatov iz izvornega VM.

Če je izvorna hierarhija prazna, je po nadomestitvi prazna tudi ciljna; ne ustvarja se privzeta cona. Rezultat vsebuje ID obeh VM in število kopiranih con, LAO, TAO ter povezav.

## Obstoječa implementacija: mesta za ponovno uporabo in prilagoditev

- [CloneModelVersionWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/CloneModelVersionWorkflow.php:19) že kopira model in njegove podatke. [archiveModel](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Activities/CloneModelVersionActivity.php:30) ohrani VO izvora, določi `MAX(verzija)+1`, nastavi `kopija_verzije` in `pripisna=false`; trenutno ne nastavi izrecno `zaklenjena_verzija=false`. Ne predpostaviti, da je obstoječa kopija že odklenjena.
- Ista aktivnost vsebuje kopiranje con, LAO, TAO in `obmxcona`. Logiko preslikav je smiselno ponovno uporabiti za kopiranje hierarhije, brez kopiranja ostalih modelskih tabel.
- [GeoObmCopyWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/GeoObmCopyWorkflow.php:20) že izbere lokalno najvišje verzije na izvornem VO. Ne zamenjati tega z globalnim filtrom latest.
- [LockGeoObmVerzijaWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/LockGeoObmVerzijaWorkflow.php:14) se sproži po ustvarjanju VM. Trenutno pri manjkajočem VO vrže izjemo; to prilagoditi za VM iz nič. Ta ticket ne uvaja avtomatskega odklepanja VO po premiku.
- [RecalculateGeoHierarchyWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/RecalculateGeoHierarchyWorkflow.php:23) poleg geometrij preračunava tudi podatke transakcij. Zato ga ne uporabiti brez prilagoditve kot celoten avtomatski zaključek novih workflowov: potrebujemo geometrije, transakcijski preračun pa ostane ločena uporabniška zahteva.

## Napake in rezultat za FE

Pred začetkom spreminjanja vrniti razumljivo napako za: manjkajoč zapis; VM brez VO pri ponastavitvi/kopiranju; različna VO pri kopiranju hierarhije; isti VM kot izvor in cilj kopiranja; zaklenjen ali pripisen spreminjani VM; različna frontnost pri premiku; več VM istega tipa na izvornem frontnem VO; manjkajoč isti tip na frontnem cilju pri VM brez VO.

Workflow pridružitve počaka na konec kopiranja in ponastavitve. Uspeh ne pomeni samo spremenjenega `id_rel_geo_verzija`, ampak tudi dokončano začetno hierarhijo. Obvestilo in rezultat morata omogočiti odprtje dejanskega rezultatskega VM.

## Sprejemni kriteriji

| Scenarij | Pričakovani rezultat |
|---|---|
| VM brez VO → zgodovinski VO | Isti VM, ena cona na ravni 1, povezave do vseh ciljnih območij. |
| VM brez VO → frontni VO z istim tipom | Enak rezultat; novi VM je lokalno najvišja verzija svojega tipa. |
| VM brez VO → frontni VO brez istega tipa | Zavrnitev brez sprememb. |
| Zgodovinski → zgodovinski, tudi zaklenjen izvor | Nova spremenljiva kopija na cilju; izvorni VM in hierarhija ostaneta nespremenjena. |
| Frontni → frontni, en VM tega tipa na izvoru | Isti VM se prestavi in ponastavi; ostali VM ostanejo na izvoru. |
| Frontni → frontni, več VM tega tipa na izvoru | Zavrnitev brez sprememb. |
| Različna frontnost izvora in cilja | Zavrnitev brez sprememb. |
| Zaklenjen ALI pripisen neposredno spreminjani VM | Zavrnitev; za zavrnitev zadostuje katerakoli zastavica. |
| Samostojna ponastavitev, tudi ponovljena | Natanko ena cona; natanko ena povezava za vsako območje; brez LAO/TAO. |
| Kopiranje hierarhije na isti VO | Ciljna struktura in povezave nadomeščene; novi ID; izvor nespremenjen. |
| Cilj podpira manj ravni kot izvor | Vse kopirane cone imajo raven 1. |
| Cilj podpira vsaj toliko ravni kot izvor | Ravni izvornih con se ohranijo. |
| Kopiranje med različnimi VO | Zavrnitev. |
| Kopiranje frontnega VO | Nova VO postane frontna; prenesejo se lokalno najvišje verzije po tipu. |
| Kopiranje zgodovinskega VO | Ni na voljo v tej izvedbi. |

Pri preverjanju izvedbe posebej pokriti tudi naslednje integracije:

- VM iz nič dobi številko verzije brez neuspelega VO-locking workflowa zaradi praznega `id_rel_geo_verzija`.
- Nova kopija zaklenjenega/pripisnega zgodovinskega VM je spremenljiva, vključno s pripadajočimi zapisi; izvor ohrani svoje zastavice.
- Ponovljeno kopiranje hierarhije nadomesti cilj, ne dodaja nove hierarhije poleg prejšnje.
- Kopiranje ohrani tudi dodatne povezave con z LAO in ne pušča referenc na izvorno hierarhijo.
- Nobeden od treh novih workflowov samodejno ne sproži transakcijskega preračuna; geometrije nove hierarhije so vseeno sestavljene.
- Obstoječe kopiranje VO lahko še naprej nadzorovano spremeni povezavo VM–VO, čeprav je običajna ročna sprememba prepovedana.

## Izven obsega

- Geometrijsko uparjanje pri premikanju ali kopiranju med različnimi VO.
- Kopiranje zgodovinskih VO, prazne kopije VO in uporabniško spreminjanje frontnosti.
- Samodejna uskladitev delovnega modela s filtri slojev območij.
- Samodejno ohranjanje kopije pred neposrednim frontnim premikom.
- Transakcijske povezave in preračuni po zamenjavi hierarhije: sprožijo se kasneje na zahtevo uporabnika.
- Dodatni nadzor sočasnih operacij, serializacija in posebna obnova/kompenzacija delno neuspelega postopka.
- Celovita prenova obstoječega zaklepanja VO.
