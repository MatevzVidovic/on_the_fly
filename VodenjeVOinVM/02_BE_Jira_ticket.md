# Pridružitev modela območjem ter ponastavitev in kopiranje hierarhije

## OPIS

Omogočiti pridružitev različice modela različici območij, ponastavitev njene geometrijske hierarhije in kopiranje hierarhije med različicama modelov na isti različici območij. Operacije upoštevajo spodaj navedena podrobna pravila; območja in druge različice modelov ostanejo nespremenjeni.

## KRITERIJI SPREJETJA

- Pridružitev skladno s tabelo pravil premakne izbrano različico in ponastavi hierarhijo.
- Ponastavitev ustvari eno cono na ravni 1, povezano z vsemi trenutnimi območji, brez LAO/TAO. Če območij ni, je cona brez povezav in geometrije.
- Kopiranje nadomesti celotno ciljno hierarhijo; izvor ostane nespremenjen. Pri enakem ali večjem številu ciljnih ravni ohrani ravni con, sicer vse nastavi na 1.
- Spreminjana različica in kopirani zapisi omogočajo urejanje.

## TESTIRANJE

V okolju [test.gurs.lift.flycom.si](http://test.gurs.lift.flycom.si):

- Pridružitev → primeri iz tabele pravil → predviden premik in ponastavitev ali zavrnitev.
- Ponastavitev → model z območji in brez njih → ustrezna osnovna cona.
- Kopiranje → cilj z več, enako in manj ravnmi → ohranjene ravni oziroma raven 1.

Vsi WF se sprožijo na podlagi SFCjev, ki so vezani na vrstice v tabeli “MD Območja verzije”.
Za namen pridružitve v SFC izberemo verzijo modela, ki pripada vrstici verzije območja, ter ciljno verzijo območja. Izvorna verzija modela in ciljna verzija območij se pošljeta na WF.
Za namen ponastavitve hierarhije izberemo verzijo modela na tej vrstici verzije območij, ki se pošlje na WF.
Za namen kopiranja hierarhije izberemo izvorno in ciljno verzijo modela na tej verziji območij, ki se pošljeta na WF.

Izdelati tri workflowe. Pridružitev vedno ponastavi hierarhijo; kopiranje hierarhije je ločena akcija.

## Definicije

- **VO:** verzija območij (`md_geo_obm_verzije`).
- **VM:** verzija modela (`md_verzije_modeli`). Tip modela določa polje `model`.
- **Hierarhija geometrij VM:** pripadajoči zapisi v `md_geo_obmxcona`, `md_geo_cona`, `md_geo_lao` in `md_geo_tao`. Območja (`md_geo_obm`) niso del te hierarhije.
- **Editabilen VM:** `zaklenjena_verzija=false` in `pripisna=false`.
- **Delovni VO:** `delovna_geo_coniranje=true`; **nedelovni VO:** `false`.

Editabilen mora biti VM, ki ga spreminjamo. Zaklenjen ali pripisen izvor lahko beremo za kopiranje. Zaklenjenost VO ne preprečuje teh operacij, ker območij ne spreminjamo.

## 1. JoinModelToGeoVersionWorkflow

**Vhod:** `vm_id`, `target_vo_id`.

BE preveri pogoje spodaj, spremeni `id_rel_geo_verzija` izbranega VM in počaka na ponastavitev. Celoten postopek izvede en workflow.

### Pravila po vejah

V stolpcih za izvorni in ciljni VO sta `true` in `false` vrednosti polja `delovna_geo_coniranje`.

| Izvorni VO delovna_geo_coniranje | Ciljni VO delovna_geo_coniranje | Pogoj | Izvedba BE |
|---|---|---|---|
| VM nima VO | `false` | VM je editabilen. | Prestavi podani VM in ponastavi njegovo hierarhijo. |
| VM nima VO | `true` | VM je editabilen; ciljni VO že vsebuje VM istega tipa. | Prestavi podani VM in ponastavi njegovo hierarhijo. |
| `false` | `false` | — | Zavrne; pridružitev med nedelovnima VO ni del trenutnega obsega. |
| `true` | `true` | Podani VM je editabilen in je edini VM svojega tipa na izvornem VO. | Prestavi podani VM in ponastavi njegovo hierarhijo. |
| `false` | `true` | — | Zavrne. |
| `true` | `false` | — | Zavrne. |

Vedno se premakne podani VM, ki mora biti editabilen. Če VM že ima VO, je pridružitev dovoljena samo med dvema delovnima VO.

Pridružitev ne kopira območij, ne spreminja `delovna_geo_coniranje` in ne premika drugih VM.

Za štetje VM istega tipa uporabiti `md_verzije_modeli`, filtrirano po izvornem `id_rel_geo_verzija` in `model`. Štejejo vse verzije, ne glede na editabilnost.

### Psevdokoda

```text
vm = preberi VM(vm_id)
ciljni_vo = preberi VO(target_vo_id)
izvorni_vo = preberi VO(vm.id_rel_geo_verzija), če je povezan

preveri obstoj zapisov in pogoje iz tabele

nastavi vm.id_rel_geo_verzija = ciljni_vo.id
počakaj na ResetModelGeoHierarchyWorkflow(vm.id, create_base_cona=true)    // opisan kasneje
```

### Primer

Delovni VO A vsebuje PPP v5 in v6: premik katerega od njiju je zavrnjen. Po obstoječem kopiranju VO (že implementirano) je na novi delovni VO samo PPP v6, zato ga lahko premaknemo. Pogoj je število VM istega tipa na izvoru.

## 2. ResetModelGeoHierarchyWorkflow

**Vhod:** `vm_id`, `create_base_cona: bool`.

**Pogoji:** VM obstaja, je editabilen in ima obstoječ VO.

1. Izbriše celotno hierarhijo geometrij tega VM: `obmxcona`, cone, LAO in TAO, v ustreznem vrstnem redu. Če `create_base_cona == false`, se tu zaključi, sicer gre na naslednje korake.
2. Ustvari eno `md_geo_cona` z novim ID, `id_rel_verzije_modeli=vm_id` in `st_ravni=1`, brez LAO in TAO.
3. Za vsako območje trenutnega VO ustvari eno `md_geo_obmxcona` povezavo na novo cono.
4. Geometrijo cone se samodejno ustvari iz povezanih območij.

**Rezultat:** natanko ena cona na ravni 1, brez LAO/TAO. Če VO nima območij, je cona brez povezav in geometrije. Pri ponastavitvi po pridružitvi se uporabijo samo območja ciljnega VO.

## 3. CopyModelGeoHierarchyWorkflow

**Vhod:** `source_vm_id`, `target_vm_id`.

**Pogoji:** VM sta različna, obstajata in imata isti VO. Ciljni VM je editabilen.

1. Prebere izvorno hierarhijo in število vrednostnih ravni obeh modelov.
2. Izbriše ciljno hierarhijo, torej počaka na `ResetModelGeoHierarchyWorkflow(ciljni_vm.id, create_base_cona=false)`
3. Preveri številke ravni, ki jih verziji modelov ponujata: če ciljnji VM podpira vsaj toliko ravni kot izvor, ob kopiranju con ohrani `st_ravni`; sicer vsem kopiranim conam nastavi `st_ravni=1`.
4. Kopira izvorne cone (in obenem obmxcone, ki se navezujejo na trenutno kopirano cono), LAO in TAO z novimi ID in `id_rel_verzije_modeli=target_vm_id`. Ob kopiranju mora poskrbeti na pravilne reference zapisov, npr. kopirana cona kaže na ustrezan kopiran TAO. Zato predlagamo naslednji postopek:
   - najprej kopiramo TAO, kjer ohranimo preslikovalno tabelo iz starih TAO na kopirane nove TAO.
   - Nato LAO (da ob kopiranju že pravilno nastavimo parent TAO), kjer vodimo tabelo preslikav starih v nove LAO.
   - In nato cone, jer ob kreiranju posamezne cone ustvarimo tudi vnose v obmxcona, ki bodo novo cono povezovali z istimi območji, kot stara cona.

**Rezultat:** ciljna hierarhija je nadomeščena, izvor ostane nespremenjen. Kopirajo se tudi cone brez območij in nepovezani deli hierarhije.

## Obstoječa koda, ki jo lahko uporabimo

**[CloneModelVersionWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/CloneModelVersionWorkflow.php:19):** aktivnosti za kopiranje hierarhije geometrij lahko morda ponovno uporabimo v `CopyModelGeoHierarchyWorkflow`.
