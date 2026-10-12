# Pridružitev verzije modela verziji območij z geometrijskim uparjanjem con

## OPIS

Omogočiti pridružitev VM drugemu VO z ohranitvijo con, LAO in TAO. Namesto ponastavitve hierarhije se povezave con z območji nadomestijo na podlagi uparjanja obstoječih geometrij con z območji ciljnega VO.

**VM:** verzija modela. **VO:** verzija območij.

## WORKFLOW

Izdelati `JoinModelToGeoVersionByGeometryWorkflow`.

**Vhod:** `vm_id`, `target_vo_id`, `min_coverage_percent` (zahtevani odstotek pokritosti, npr. 98).

### Pogoji

- VM in oba VO obstajajo; izvorni in ciljni VO sta različna.
- Oba VO imata `delovna_geo_coniranje=true`.
- VM ima `zaklenjena_verzija=false` in `pripisna=false`.
- VM je edini svojega tipa (`model`) na izvornem VO. Štejejo vse VM tega tipa, ne glede na editabilnost.

### Uparjanje glede na odstotek pokritosti

Območje ciljnega VO povežemo s cono, če cona pokriva vsaj `min_coverage_percent` odstotkov njegove površine.

Odstotek pokritosti je `100 × površina preseka cone in območja / površina območja`.

Predlagamo, da se v postopku izvede for loop po conah, kjer se najprej s ST_Intersects preveri možna območja in pridobi omejen nabor, za katerega se izvede zahtevnejša operacija izračuna površin.


### Izvedba

1. Preveri pogoje in podani odstotek pokritosti.
2. **Pred odstranitvijo starih povezav** določi ujemanja med trenutnimi geometrijami con VM in območji ciljnega VO glede na podani odstotek pokritosti.
3. Odstrani stare povezave `md_geo_obmxcona` tega VM in nastavi njegov `id_rel_geo_verzija` na ciljni VO.
4. Za vsak ujemajoči se par ustvari povezavo med obstoječo cono in območjem ciljnega VO.
5. Osvežitev geometrije con, LAO in TAO se zgodi samodejno.

Cone, LAO in TAO ohranijo ID, medsebojne povezave in vrednostne ravni. Cona brez ujemanj ostane v hierarhiji brez povezav z območji.

## KRITERIJI SPREJETJA

- Pridružitev je dovoljena samo ob izpolnjenih pogojih.
- VM je povezan s ciljnim VO; njegove cone so povezane samo z območji ciljnega VO, ki izpolnjujejo podani prag pokritosti.
- Območja, drugi VM in nastavitve `delovna_geo_coniranje` ostanejo nespremenjeni.

## TESTIRANJE

- Preveriti primer, ko cona pokriva 80 % območja: pri pragu 80 % se poveže, pri 98 % ne.
- Preveriti cono brez ujemanj ter ohranitev hierarhije in odstranitev starih povezav.
- Preveriti zavrnitev pri nedelovnem ciljnem VO, zaklenjenem ali pripisnem VM ter več VM istega tipa na izvoru.
