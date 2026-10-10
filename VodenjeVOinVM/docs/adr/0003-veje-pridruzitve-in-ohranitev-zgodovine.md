# Pridružitev uporablja različne veje glede na frontnost VO

Neposredno premikanje med frontnimi VO mora odstraniti tip modela z izvorne VO, da isti tip ne dobi dveh frontnih VM na različnih VO. Zato se VM med frontnima VO premakne neposredno le, če je edini VM svojega tipa na izvorni VO in ni zaklenjen ali pripisen; med ne-frontnima VO se najprej ustvari njegova kopija in premakne ta. Premiki med VO z različno frontnostjo so zavrnjeni.

## Veje

1. **VM brez VO:** lahko se pridruži ne-frontni VO ali frontni VO, ki že vsebuje njegov tip modela. Izvede pridružitev in ponastavitev ter zaključi brez primerjave izvorne in ciljne VO.
2. **Dve ne-frontni VO:** ustvari kopijo izvornega VM, zagotovi njeno urejanje, nato jo pridruži ciljni VO in ponastavi. Izvorni VM ostane na izvorni VO.
3. **Dve frontni VO:** zavrne zaklenjen ali pripisen VM in VM, ki ni edini svojega tipa na izvorni VO. Sicer neposredno izvede pridružitev in ponastavitev.
4. **Različna frontnost:** zavrne pridružitev.

## Posledice

- Kopija VM dobi globalno `MAX(verzija)` za svoj tip + 1 in sprva ostane na isti VO kot izvorni VM.
- Kopija za zgodovinsko pridružitev mora biti urejiva: `pripisna=false`, `zaklenjena_verzija=false` in brez podedovanih omejitev `__readonly` na podatkih, ki jih naslednji workflow spreminja.
- Obstoječi copy workflow eksplicitno ponastavi `pripisna`, ne pa `zaklenjena_verzija`; zagotavljanje urejivosti je zahteva za implementacijo, ne že potrjena lastnost trenutne kode.
- Pred frontnim premikom priporočamo **kopija VM → kopija izvorne VO → pridružitev kopiranega VM**. Kopija VO ob tem prestavi naprej tudi frontne VM drugih tipov; to je namerno.
- Predhodno varovanje hierarhije pri frontnem premiku je priporočilo, ne obveznost. Uporabnik lahko neposredno premakne dovoljen VM in izgubi njegovo prejšnjo hierarhijo.

Dogovor: 2026-10-10. Vir: [latest_ideja.md](../../latest_ideja.md) in zaključeni pogovor o zasnovi.
