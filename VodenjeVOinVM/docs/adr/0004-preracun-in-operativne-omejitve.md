# Preračun ostane ročen, dodatno operativno varovanje je zunaj obsega

Ponastavitev in zamenjava hierarhije lahko vplivata na povezave transakcij na cone, vendar se njihova ponovna določitev in povezani preračuni sprožijo pozneje na zahtevo uporabnika. Za ta obseg zavestno ne uvajamo dodatnih preverjanj sočasnih operacij ali zahtev za povrnitev stanja po delni napaki. Predhodna kopija ohranja uporabnikovo zgodovino, vendar ni nadomestilo za avtomatsko obnovitev neuspešne operacije.

## Posledice

- Dokončan workflow hierarhije ne pomeni, da so transakcijske povezave in izračuni že osveženi.
- Sočasne operacije lahko povzročijo konflikte; zasnova njihovega preprečevanja ni zahtevana v tem obsegu.
- Po delni napaki lahko ostane delno spremenjeno stanje; avtomatska povrnitev ali odstranjevanje neuspešne kopije nista zahtevana.
- To so sprejete omejitve obsega, ne trditev, da težave niso mogoče, in ne zahteva za odstranitev obstoječih zaščit.

Dogovor: 2026-10-10. Vir: zaključeni pogovor o zasnovi, odgovori Q14, Q16, Q19 in Q21.
