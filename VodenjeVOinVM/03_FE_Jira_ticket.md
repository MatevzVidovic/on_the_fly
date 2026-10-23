# SFC akcije za pridružitev verzij modela in upravljanje hierarhije

## Cilj in odvisnost

Dodati tri SFC akcije nad verzijo modela ter omejiti običajno ročno spreminjanje povezave VM–VO.

## Nove SFC akcije

| Akcija na VM | Uporabniški vhod | Workflow |
|---|---|---|
| **Pridruži na VO** | Izbira ciljnega VO. | `JoinModelToGeoVersionWorkflow(vm_id, target_vo_id)` |
| **Ponastavi hierarhijo** | Brez dodatnega modela ali VO; uporablja VO izbranega VM. | `ResetModelGeoHierarchyWorkflow(vm_id)` |
| **Prekopiraj hierarhijo iz VM** | Izbira izvornega VM na istem VO; trenutni VM je cilj. | `CopyModelGeoHierarchyWorkflow(source_vm_id, target_vm_id)` |

Vsi WF se sprožijo na podlagi SFCjev, ki so vezani na vrstice v tabeli “MD Območja verzije”.  
Za namen pridružitve v SFC izberemo verzijo modela, ki pripada vrstici verzije območja, ter ciljno verzijo območja. Izvorna verzija modela in ciljna verzija območij se pošljeta na WF.  
Za namen ponastavitve hierarhije izberemo verzijo modela na tej vrstici verzije območij, ki se pošlje na WF.  
Za namen kopiranja hierarhije izberemo izvorno in ciljno verzijo modela na tej verziji območij, ki se pošljeta na WF.




## 1. Pridruži na VO

V izboru VO prikazati najmanj številko oziroma naziv VO in prisotne verzije modelov. Zaklenjenost VO ni razlog za izključitev cilja; akcija ne spreminja območij.

### Dovoljene izbire

| Stanje izbranega VM | Cilji in delovanje |
|---|---|
| Brez VO, spremenljiv VM | Vsi zgodovinski VO; frontni VO samo, če že vsebujejo njegov tip modela. Pridruži se isti VM. |
| Na zgodovinskem VO | Akcija ni omogočena; prikazati razlog. Pridružitev VM, ki že pripada zgodovinskemu VO, ni podprta. |
| Na frontnem VO, spremenljiv VM, edini svojega tipa na izvoru | Samo frontni VO. Premakne se isti VM. |
| Na frontnem VO, zaklenjen/pripisen ali več VM njegovega tipa na izvoru | Akcija ni omogočena; prikazati razlog. |

Enakega frontnega VO kot ciljnega ni treba izključiti. Akcija tudi v tem primeru ponastavi hierarhijo, če so izpolnjeni pogoji za pridružitev med frontnima VO.


## 2. Ponastavi hierarhijo


Omogočeno le za VM, ki ima VO in ni zaklenjen ali pripisen.

## 3. Prekopiraj hierarhijo iz VM

Omogočiti za ciljni VM, ki ima VO in ni zaklenjen ali pripisen. Izbor izvora vsebuje samo druge VM na isti VO. Zaklenjen/pripisen izvor je dovoljen, saj se ne spreminja.

V izboru prikazati tip modela, verzijo in naziv. Trenutnega ciljnega VM izključiti iz izbora izvora.


## Omejitve obstoječih akcij in obrazcev

- Na obstoječem SFC **kopiranja VO** prikazati gumb samo za `delovna_geo_coniranje=true`. Zaklenjen frontni VO je lahko kopiran; ne filtrirati po `zaklenjena=false`.
- Onemogočiti običajno ročno nastavljanje `delovna_geo_coniranje`, tudi v administrativnem obrazcu. Uporabniške akcije ne prestavljajo frontnosti ročno.
- Onemogočiti običajno ročno spreminjanje VM → VO (`id_rel_geo_verzija`), tudi v administrativnem obrazcu. Pri VM iz nič VO ostane prazen do pridružitve. Pri obstoječem VM se VO prikazuje kot podatek, za spremembo se uporabi SFC.
- Ohraniti obstoječi akciji kopiranja VM in VO. Ne uvajati globalnega »latest« filtra za izbiro izvornega VM ali novih akcij.
- Ne omejiti ponastavitve oziroma kopiranja hierarhije na frontne VM; odločilna je spremenljivost ciljnega VM.
