# Pridružitev ponastavi hierarhijo, kopiranje hierarhije je ločeno

Ročna sprememba VO pusti povezave obmxcona na območjih prejšnje VO, zato se pridružitev izvede prek workflowa in vedno ponastavi hierarhijo VM. Ponastavitev odstrani obmxcona, cone, LAO in TAO ter ustvari eno cono na ravni 1 s povezavo za vsako območje ciljne VO; LAO in TAO ne ustvari. Namesto geometrijskega uparjanja v prvi izvedbi uporabnik po pridružitvi po želji sproži ločeno kopiranje hierarhije iz drugega VM na isti VO.

## Posledice

- Pridružitev ne kopira ciljne VO ali njenih območij.
- Ponastavitev in kopiranje hierarhije sta uporabna tudi samostojno znotraj VO.
- Kopiranje hierarhije zamenja ciljno hierarhijo, ustvari lastne cone, LAO in TAO ter povezave na ista območja; izvorni VM ostane nespremenjen.
- Če ima ciljni VM vsaj toliko vrednostnih ravni kot izvorni, se ravni con kopirajo. Sicer se vsem kopiranim conam ciljnega VM nastavi raven 1.
- Hierarhije ni dovoljeno spreminjati na zaklenjenem ali pripisnem ciljnem VM. Branje zaščitenega izvornega VM za kopiranje je dovoljeno.
- Pridružitev na isto VO je dovoljena in sledi istim pravilom kot ostale pridružitve, vključno s ponastavitvijo oziroma predhodnim kopiranjem.
- Geometrijsko uparjanje ob premiku in kopiranje hierarhije med različnima VO sta dorazvoj.

Dogovor: 2026-10-10. Vir: [latest_ideja.md](../../latest_ideja.md) in zaključeni pogovor o zasnovi.
