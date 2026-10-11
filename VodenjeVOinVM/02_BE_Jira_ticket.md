# BE: pridružitev VM na VO, ponastavitev in kopiranje hierarhije

## Cilj

Uvesti tri namenske BE workflowe: pridružitev VM na VO, ponastavitev hierarhije geometrij VM in nadomestitev hierarhije geometrij s kopijo drugega VM na istem VO. Pridružitev je ena operacija: BE sam izbere ustrezno vejo, po potrebi kopira VM, spremeni njegovo povezavo na VO in počaka na ponastavitev hierarhije.

### Definicije

- VO: verzija območij.
- VM: verzija modela.
- Hierarhija geometrij: vsi pripadajoči vnosi nekega VM v `md_geo_obmxcona`, `md_geo_cona`, `md_geo_lao` in `md_geo_tao`. Vnosi v `md_geo_obm` niso del hierarhije geometrij VM.
- Editabilen VM: ima `zaklenjena_verzija = false` in `pripisna = false`. 
- Delovni VO: ima `delovna_geo_coniranje = true`.
- Nedelovni VO: ima `delovna_geo_coniranje = false`.
- Tip modela: vrednost polja `model` na VM.

Zaklenjenost VO ni pogoj za spreminjanje hierarhije geometrij editabilnega VM. Ti workflowi ne spreminjajo območij v `md_geo_obm`. Zaklenjen ali pripisen izvorni VM se lahko bere za kopiranje; editabilen mora biti VM, ki ga dejansko spreminjamo.

## Obseg

### Novi workflowi

| Workflow | Vhod | Namen |
|---|---|---|
| `JoinModelToGeoVersionWorkflow` | `vm_id`, `target_vo_id` | BE izbere vejo, po potrebi kopira VM, prestavi VM in počaka na ponastavitev. |
| `ResetModelGeoHierarchyWorkflow` | `vm_id` | Nadomesti hierarhijo geometrij z eno cono na ravni 1, povezano z vsemi območji njegove VO. |
| `CopyModelGeoHierarchyWorkflow` | `source_vm_id`, `target_vm_id` | Nadomesti ciljno hierarhijo geometrij s kopijo drugega VM na istem VO. |

## 1. JoinModelToGeoVersionWorkflow

### Vhod in upravljanje izvedbe

Vhod: obstoječi `vm_id` in obstoječi `target_vo_id`.

Celoten postopek vodi BE. Klicatelj ne izbira veje, ne zaganja kopiranja kot vmesnega koraka in ne nadaljuje postopka nad kopijo. Če je potrebna kopija, BE pridobi njen ID iz obstoječega workflowa kopiranja in ta ID uporabi za premik ter ponastavitev. Operacija je zaključena šele, ko je končana ponastavitev.

### Psevdokoda

`fetchVM` bere `md_verzije_modeli`, `fetchVO` pa `md_geo_obm_verzije`. Prisotnost oziroma število VM istega tipa se preveri v `md_verzije_modeli` s filtroma `id_rel_geo_verzija = vo_id` in `model = vm.model`. Pri štetju se ne filtrira po številki verzije, zaklenjenosti ali pripisnosti.

```text
join(vm_id, target_vo_id):
    vm = fetchVM(vm_id)
    targetVO = fetchVO(target_vo_id)
    reject if either record does not exist

    if vm.id_rel_geo_verzija is null:
        requireEditable(vm)
        if targetVO.delovna_geo_coniranje is true:
            require targetVO contains at least one VM with model = vm.model
        # Pri ciljnem VO z delovna_geo_coniranje=false tega pogoja ni.
        moveAndReset(vm.id, targetVO.id)
        return  # Pridružen in ponastavljen je podani VM.

    sourceVO = fetchVO(vm.id_rel_geo_verzija)
    reject if sourceVO does not exist

    if sourceVO.delovna_geo_coniranje != targetVO.delovna_geo_coniranje:
        reject DIFFERENT_WORKING_VO_STATUS

    if sourceVO.delovna_geo_coniranje is false:
        # Izvor se samo bere; lahko je zaklenjen ali pripisen.
        new_vm_id = await CloneModelVersionWorkflow(vm.id)
        makeCopyEditable(new_vm_id)
        requireEditable(fetchVM(new_vm_id))
        moveAndReset(new_vm_id, targetVO.id)
        return  # Pridružena in ponastavljena je nova kopija; izvor ostane nespremenjen.

    # Oba VO imata delovna_geo_coniranje=true.
    requireEditable(vm)
    count = countVMs(sourceVO.id, model = vm.model)
    require count == 1
    # Štejemo vse VM tega tipa na izvornem VO, ne glede na verzijo ali editabilnost.
    moveAndReset(vm.id, targetVO.id)
    return  # Pridružen in ponastavljen je podani VM.

moveAndReset(actual_vm_id, target_vo_id):
    update VM(actual_vm_id).id_rel_geo_verzija = target_vo_id
    await ResetModelGeoHierarchyWorkflow(actual_vm_id)

requireEditable(vm):
    reject if vm.zaklenjena_verzija is true OR vm.pripisna is true
```

`makeCopyEditable` ni nov javni workflow. To je del zagotovitve rezultata obstoječega kopiranja oziroma interna aktivnost pridružitve. Kopija mora imeti `pripisna=false`, `zaklenjena_verzija=false` in odklenjene pripadajoče zapise (`__readonly=false` tam, kjer je ta atribut prisoten). Izvorni VM in njegovi zapisi ostanejo nespremenjeni.

### Pravila po vejah

V stolpcih za izvorni in ciljni VO sta `true` in `false` vrednosti polja `delovna_geo_coniranje`.

| Izvorni VO delovna_geo_coniranje | Ciljni VO delovna_geo_coniranje | Pogoj                                                               | Izvedba BE                                                                              |
| -------------------------------- | ------------------------------- | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| VM nima VO                       | `false`                         | VM je editabilen.                                                   | Prestavi podani VM in ponastavi njegovo hierarhijo.                                     |
| VM nima VO                       | `true`                          | VM je editabilen; ciljni VO že vsebuje VM istega tipa.              | Prestavi podani VM in ponastavi njegovo hierarhijo.                                     |
| `false`                          | `false`                         | Izvorni VM se lahko bere tudi, če ni editabilen.                    | Kopira VM, zagotovi editabilnost kopije, prestavi kopijo in ponastavi njeno hierarhijo. |
| `true`                           | `true`                          | Podani VM je editabilen in je edini VM svojega tipa na izvornem VO. | Prestavi podani VM brez predhodne kopije in ponastavi njegovo hierarhijo.               |
| `false`                          | `true`                          | —                                                                   | Zavrne.                                                                                 |
| `true`                           | `false`                         | —                                                                   | Zavrne.                                                                                 |

Pri že povezanem VM se editabilnost preveri na VM, ki se dejansko premika: pri obeh nedelovnih VO je to nova kopija, pri obeh delovnih VO pa podani VM.

### Pomembni primeri

- Delovni VO A vsebuje PPP v5 in PPP v6: premik kateregakoli od teh VM ni dovoljen, ker sta na izvornem VO dva VM istega tipa. Uporabnik lahko najprej izvede obstoječe kopiranje VO, ki na novi delovni VO prenese samo PPP v6.
- Delovni VO A vsebuje samo PPP v6: premik v delovni VO B je dovoljen, če je PPP v6 editabilen. V tej veji ni zahteve, da B že vsebuje PPP.
- Oba VO sta nedelovna: izvorni VM ostane na A; BE na B premakne novo kopijo z naslednjo številko verzije za tip modela.
- VM brez VO: delovni cilj mora že vsebovati isti tip modela; za nedelovni cilj tega pogoja ni.
- Enak izvorni in ciljni VO ni posebej zavrnjen. Veljajo ista pravila veje; postopek še vedno izvede ponastavitev.

Pridružitev ne kopira VO ali območij, ne spreminja `delovna_geo_coniranje` in ne premika drugih VM. Ne ohranja stare hierarhije premaknjenega VM; uporabnik jo po želji predhodno ohrani s kopiranjem VM in VO.

## 2. ResetModelGeoHierarchyWorkflow

### Predpogoji

- VM obstaja, je editabilen in ima obstoječ VO.
- Vrednosti `delovna_geo_coniranje` in `zaklenjena` na VO nista pogoja. Workflow spreminja hierarhijo geometrij VM, ne območij.

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
- Ciljni VM je editabilen. Izvorni VM je lahko zaklenjen ali pripisen, saj se samo bere.
- Vrednosti `delovna_geo_coniranje` in `zaklenjena` na VO nista pogoja.

### Koraki

1. Prebere izvorne cone, LAO, TAO, njihove medsebojne reference in `obmxcona` povezave. Prebere število vrednostnih ravni obeh VM po obstoječi definiciji v modelu.
2. Odstrani celotno obstoječo hierarhijo ciljnega VM. Ponovno uporabi interno brisanje iz ponastavitve; **ne kliče ponastavitve tako, da bi za kopijo ostala dodatna privzeta cona**.
3. Kopira vse izvorne zapise cone/LAO/TAO z novimi ID in `id_rel_verzije_modeli=target_vm_id`. Kopirani zapisi so editabilni, brez podedovanega `__readonly=true`.
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

## Validacije in zaključek BE operacije

Pred začetkom spreminjanja BE preveri pogoje ustrezne veje. Zavrnitev naj ima razumljiv razlog:

- VM ali VO ne obstaja.
- VM pri ponastavitvi oziroma kopiranju hierarhije nima VO.
- Izvorni in ciljni VM pri kopiranju hierarhije nimata istega VO ali sta isti VM.
- VM, ki ga spreminjamo, ni editabilen.
- Izvorni in ciljni VO pri pridružitvi nimata enake vrednosti `delovna_geo_coniranje`.
- Na izvornem delovnem VO obstaja več VM istega tipa kot podani VM.
- VM brez VO se pridružuje delovnemu VO, ki še nima VM istega tipa.

Pridružitev v BE počaka na konec morebitnega kopiranja in nato na konec ponastavitve. Uspeh pomeni spremenjeno povezavo VM–VO in dokončano začetno hierarhijo. Med koraki ni nadaljnjih zahtev ali odločitev klicatelja.

## Sprejemni kriteriji

| Scenarij | Pričakovani rezultat |
|---|---|
| VM brez VO → nedelovni VO | Isti VM, ena cona na ravni 1, povezave do vseh ciljnih območij. |
| VM brez VO → delovni VO z istim tipom | Isti VM se pridruži in ponastavi; ne ustvari se dodatna kopija. |
| VM brez VO → delovni VO brez istega tipa | Zavrnitev brez sprememb. |
| Nedelovni → nedelovni VO, tudi zaklenjen izvor | Nova editabilna kopija na cilju; izvorni VM in hierarhija ostaneta nespremenjena. |
| Delovni → delovni VO, en VM tega tipa na izvoru | Isti VM se prestavi in ponastavi; ostali VM ostanejo na izvoru. |
| Delovni → delovni VO, več VM tega tipa na izvoru | Zavrnitev brez sprememb. |
| Različni vrednosti `delovna_geo_coniranje` izvora in cilja | Zavrnitev brez sprememb. |
| Zaklenjen ALI pripisen neposredno spreminjani VM | Zavrnitev; za zavrnitev zadostuje katerakoli zastavica. |
| Samostojna ponastavitev, tudi ponovljena | Natanko ena cona; natanko ena povezava za vsako območje; brez LAO/TAO. |
| Kopiranje hierarhije na isti VO | Ciljna struktura in povezave nadomeščene; novi ID; izvor nespremenjen. |
| Cilj podpira manj ravni kot izvor | Vse kopirane cone imajo raven 1. |
| Cilj podpira vsaj toliko ravni kot izvor | Ravni izvornih con se ohranijo. |
| Kopiranje med različnimi VO | Zavrnitev. |
| Kopiranje delovnega VO | Nova VO dobi `delovna_geo_coniranje=true`, izvorna pa `false`; prenesejo se VM z najvišjo verzijo po tipu na izvornem VO. |
| Kopiranje nedelovnega VO | Ni na voljo v tej izvedbi. |

Pri preverjanju izvedbe posebej pokriti tudi naslednje integracije:

- VM iz nič dobi številko verzije brez neuspelega VO-locking workflowa zaradi praznega `id_rel_geo_verzija`.
- Nova kopija zaklenjenega/pripisnega VM na nedelovnem VO je editabilna, vključno s pripadajočimi zapisi; izvor ohrani svoje zastavice.
- Ponovljeno kopiranje hierarhije nadomesti cilj, ne dodaja nove hierarhije poleg prejšnje.
- Kopiranje ohrani tudi dodatne povezave con z LAO in ne pušča referenc na izvorno hierarhijo.
- Nobeden od treh novih workflowov samodejno ne sproži transakcijskega preračuna; geometrije nove hierarhije so vseeno sestavljene.
- Obstoječe kopiranje VO lahko še naprej nadzorovano spremeni povezavo VM–VO, čeprav je običajna ročna sprememba prepovedana.

## Izven obsega

- Geometrijsko uparjanje pri premikanju ali kopiranju med različnimi VO.
- Kopiranje nedelovnih VO, prazne kopije VO in uporabniško spreminjanje `delovna_geo_coniranje`.
- Samodejna uskladitev delovnega modela s filtri slojev območij.
- Samodejno ohranjanje kopije pred neposrednim premikom med delovnima VO.
- Transakcijske povezave in preračuni po zamenjavi hierarhije: sprožijo se kasneje na zahtevo uporabnika.
- Dodatni nadzor sočasnih operacij, serializacija in posebna obnova/kompenzacija delno neuspelega postopka.
- Celovita prenova obstoječega zaklepanja VO.
