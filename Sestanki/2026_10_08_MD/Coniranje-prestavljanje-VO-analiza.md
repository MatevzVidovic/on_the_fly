%%%%# Coniranje: prestavljanje verzij območij in kopiranje geometrij med verzijami modelov

Analiza obstoječe kode v modulu `app/_Company/Gurs` (workflowi, aktivnosti in event listenerji nad tabelami `md_*`) in primerjava z zapiski s sestanka.

**Okrajšave:** VO = verzija območja (`md_geo_obm_verzije`), VM = verzija modela (`md_verzije_modeli`).

---

## 1. Trenutno stanje (koda)

### Podatkovni model

```
md_geo_obm_verzije (VO)          verzija_obmocja, zaklenjena, delovna_geo_coniranje, modeli
 └─ md_geo_obm                    območja (poligoni) VO: id_rel_geo_verzija, kopiran_id, split_group_id

md_verzije_modeli (VM)           model (tip), verzija, id_rel_geo_verzija → VO,
                                  zaklenjena_verzija, pripisna, kopija_verzije, delovna_coniranje
 ├─ md_geo_tao  ← md_geo_lao  ← md_geo_cona     (vse imajo id_rel_verzije_modeli)
 ├─ md_geo_obmxcona               povezava cona ↔ obm (cona = unija svojih območij)
 ├─ md_tvr (st_ravni)             vrednostne ravni modela
 └─ md_trans (id_rel_geo_cona, st_ravni), faktorji, razredi …
```

- Geometrija cone se izračuna kot unija območij (`md_geo_obm`), na katera je cona vezana prek `md_geo_obmxcona`. LAO in TAO se izračunata iz con (`RecalculateGeoHierarchyActivity`). Cone torej ne nosijo lastne geometrije, ampak so vezane na območja VO.
- **Polja »latest« ni.** Najnovejša verzija modela je implicitno tista z `MAX(verzija)` za isti `model` (tako jo določata `GeoObmCopyActivity::relinkVerzijeModeli` in `SetMdVerzijaModelaEventListener`).
- Vrednostne ravni so v `md_tvr.st_ravni` (na VM), dodelitev ravni posamezne cone pa v `md_geo_cona.ravan` / `st_ravni`.

### Obstoječe funkcionalnosti

| Funkcionalnost                     | Kje                                                                          | Kaj naredi                                                                                                                                                                                                                                                                                        |
| ---------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Nov VM**                         | `SetMdVerzijaModelaEventListener`                                            | `verzija = MAX(verzija) + 1` za isti `model`.                                                                                                                                                                                                                                                     |
| **Zaklepanje VO ob novem VM**      | `LockGeoObmVerzijaWorkflow` / `LockGeoObmVerzijaActivity::checkIfShouldLock` | Ko se ustvari VM in sta na isti VO **več kot ena verzija istega modela**, se VO zaklene (`zaklenjena = true`, vsi `md_geo_obm` dobijo `__readonly`). Sproži se samo ob ustvarjanju VM, odklepanja ni.                                                                                             |
| **Zaščita zaklenjene VO**%%%%      | `PreventLockedGeoObmVersionMutationEventListener`%%%%                        | Prepreči create/delete na `md_geo_obm` zaklenjene VO. Posledično na zaklenjeni VO ne gre deliti ali združevati območij.                                                                                                                                                                           |
| **Kopiranje VM**                   | `CloneModelVersionWorkflow`                                                  | Nova verzija (`MAX + 1`, `kopija_verzije`), **ista VO**. Kopira vse: faktorje, TVR, trans, cone, LAO, TAO in `obmxcona` (vezane na ista območja). Ker sta potem na VO dve verziji istega modela, se VO zaklene.                                                                                   |
| **Kopiranje VO**                   | `GeoObmCopyWorkflow`                                                         | Ustvari novo VO (`MAX + 1`, odklenjena, delovna) in staro zaklene. Kopira območja (`kopiran_id` kaže na izvor). Na novo VO **prestavi samo najnovejšo verzijo vsakega modela**, `obmxcona` prevzame prek `kopiran_id` in preračuna hierarhijo. Starejše verzije ostanejo na stari, zaklenjeni VO. |
| **Delitev in združevanje območij** | `GeoObmSplitWorkflow`                                                        | Znotraj iste VO.                                                                                                                                                                                                                                                                                  |
| **Zaklepanje VM**                  | `LockVerzijaModelaWorkflow`                                                  | Na vseh `md_*` zapisih VM nastavi `__readonly` (ob `zaklenjena_verzija` ali `pripisna`).                                                                                                                                                                                                          |

### Pomembne ugotovitve

1. **Prestavljanje VM na poljubno VO danes ne obstaja.** Edini način za menjavo VO je kopiranje VO. Ta deluje samo zato, ker so območja na novi VO kopije starih (`kopiran_id`). Za tujo VO takšne preslikave ni.
2. **Ročna sprememba `id_rel_geo_verzija` na VM ne sproži ničesar.** Listener `MdVerzijaObmocjaChangedEventListener` je bil odstranjen (GMS-4723, opomba v `relinkVerzijeModeli`). Če je polje v UI urejljivo, se VO zamenja, cone pa ostanejo vezane na območja stare VO, kar pusti podatke v nekonsistentnem stanju.
3. **Kopiranja geometrij iz drugega modela ni.** `CloneModelVersion` kopira samo geometrije lastnega modela.
4. **Primerjave vrednostnih ravni med modeli ni.**
5. Pravilo zaklepanja danes je »več kot ena verzija istega modela na VO«. To je približno enako »vsaj en ne-latest model na VO«, ni pa povsem isto (glej 4. poglavje).
6. Kje v UI se kopiranje VO in kopiranje VM sprožita, iz kode ni razvidno (ni neposrednega klica). Najverjetneje prek SFC ali gumba, konfiguriranega v bazi.

---

## 2. Kaj želijo (iz zapiskov)

1. **Nov model iz nule:** Nov prazen latest VM, brez vseh geometrij, se poveže z obstoječo VO (kjer je bil prejšnji latest model te vrste modela), in nato se lahko z območji povezujejo cone.
	1. To je že mogoče s preprostim prestavljanjem VM na pravo VO. Bolje bi bilo, da se v splošnem prestavljanje onemogoči in za to naredi preprost workflow.
	
2. **Pridružitev na VO:** Nek latest model (npr. latest PPP) lahko pridružimo na VO, ki je odklenjena (ima same latest modele). Imamo 3 scenarije za to, kaj se zgodi z geometrijami:
	1. izberemo VM na ciljnem VO. Celotna veriga geometrij (cone, LAO, TAO) izbranega VM se kopira na geometrije VM, ki ga prestavljamo.
		1. Če je število vrednostnih ravni ciljnega VM večje ali enako od števila vrednostnih ravni premikajočega VM, se številka vrednostne ravni na conah prav tako kopira.
		2. Če ni, potem se na premikajočem VM vsem conam št. vrednostne ravni nastavi na 1.
	2. Dorazvoj: Ni potrebna izbira VM na VO. Važno le, da smo izbrali odklenjen VO (s samimi latest modeli). Ohranimo cone, LAO, TAO premikajočega modela. Povezave obmxcona se ustvarijo glede na geometrijski presek novih območij in premaknjenih con (opcije so ST_Contains, ST_Intersects, ali pa npr. da cona pokriva več kot npr. 51% ali 98% območja.)

3. **Kopiranje znotraj VO:** V odklenjenem VO lahko med 2 prisotnima VM kopiramo geometrija na enaka opisana načina, kot se zgodi pri združevanju. 


---

## 3. Predlagana rešitev (iz zapiskov, preslikana na kodo)

**Potek:**
1. Uporabnik izbere izvorni VM in **ciljni VM** (nov atribut na `md_verzije_modeli` ali parameter SFC akcije).
2. Izvorni VM se **kopira** (obstoječi `CloneModelVersionWorkflow`). Original ostane nespremenjen.
3. Kopiji se VO nastavi na VO ciljnega VM. To sproži nov workflow (npr. `RelinkModelToGeoVerzijaWorkflow`), ki:
   - pobriše `md_geo_cona`, `md_geo_lao`, `md_geo_tao` in `md_geo_obmxcona` kopije,
   - podvoji cone, LAO, TAO in `obmxcona` ciljnega VM ter jim nastavi `id_rel_verzije_modeli` na kopijo (preslikava ID-jev kot v `CloneModelVersionActivity::duplicateGeo*`, `updateGeo*References`),
   - `obmxcona` kaže na **ista območja** ciljne VO, zato območij ni treba kopirati,
   - primerja število vrednostnih ravni (`md_tvr.st_ravni` izvora in cilja). Ob ujemanju prenese `ravan`/`m2_ravan` in ostale vrednosti con, sicer samo geometrije in hierarhijo, ravni pa ostanejo prazne (podrobnosti so na posnetku),
   - **preveže transakcije** kopije na nove cone (`md_trans.id_rel_geo_cona`, `RecalculateGeoHierarchyActivity::updateTransactionsForCona`) in sproži preračune con (`RecalculateMdGeoConaFromTrans`, števila transakcij, ravni).

Večino gradnikov (podvajanje con, LAO in TAO s preslikavo, bulk insert, saga kompenzacije, preračun hierarhije) že imamo v `CloneModelVersionActivity` in `RecalculateGeoHierarchyActivity`. Na novo je treba napisati predvsem orkestracijo, brisanje starih geometrij in pogoj glede vrednostnih ravni.

---

## 4. Omejitve in kako se ujemajo s kodo

| Omejitev (sestanek) | Stanje v kodi | Kaj je treba narediti |
|---|---|---|
| Na VO, kjer je vsaj en latest model, mora imeti vsak prisoten tip modela svoj latest model. | Ni preverjanja, »latest« je implicitno `MAX(verzija)`. | Dodati preverjanje (validacija pred prestavljanjem ali povezovanjem). Pojem »latest« je treba uradno definirati, mogoče kot izračunano polje. |
| Kjer je vsaj en ne-latest model, je VO zaklenjena, zato je potrebno kopiranje. | Delno: `LockGeoObmVerzija` zaklene, ko sta na VO **2+ verziji istega modela**, a samo ob ustvarjanju VM. Ne ujame primera, ko na VO ostane **samo** stara verzija (najnovejša je drugje), razen pri `GeoObmCopy`, ki staro VO zaklene eksplicitno. | Pravilo preračunati tudi ob prestavljanju VM in ob novi verziji modela na drugi VO, ne samo ob ustvarjanju VM na isti VO. |
| Združevanje ali povezovanje VM na VO je dovoljeno samo na VO, kjer so samo latest modeli. | Delitev in združevanje območij sta na zaklenjeni VO že blokirana (`PreventLocked…`). Povezovanja VM na VO (`id_rel_geo_verzija`) ne preverja nič. | Preverjanje pred prestavljanjem: ciljna VO ne sme biti zaklenjena, izvorni VM pa mora biti latest (ali pa ga najprej kopiramo, kar predlog tudi predvideva). |

### Pasti pri implementaciji

1. **Kopiranje VM in nato prestavljanje** začasno pusti dve verziji istega modela na izvorni VO. Obstoječi `LockGeoObmVerzijaEventListener` bo ob ustvarjanju kopije **zaklenil izvorno VO**. Odločiti se je treba, ali je to želeno (stari model na njej postane ne-latest, torej verjetno da) ali pa se ustvarjanje kopije in prestavljanje izvedeta v enem workflowu brez vmesnega zaklepanja.
2. **Ročno urejanje `id_rel_geo_verzija`** je treba v UI onemogočiti oziroma ga preusmeriti na novi workflow, sicer ostanejo podatki nekonsistentni (2. ugotovitev v 1. poglavju).
3. **Kateri podatek pomeni »število vrednostnih ravni«?** `md_tvr.st_ravni` (lahko je več TVR na VM) ali `md_geo_cona.st_ravni`? In kaj točno pomeni »ne kopiraj povezav med vrednostnimi ravnmi«: `ravan`/`m2_ravan` na coni na `NULL`, ali še kaj na `md_trans`/`md_vt`? To je treba potrditi glede na posnetek.
4. **Zaklenjen ciljni VM** (`zaklenjena_verzija`/`pripisna`): iz njega se lahko kopira, nove cone pa ne smejo podedovati `__readonly`. To je treba upoštevati pri kopiranju (`(array) $record` kopira vse stolpce).
5. **Transakcije in preračuni:** brez prevezave `md_trans` na nove cone ostanejo transakcije kopije vezane na pobrisane cone.
