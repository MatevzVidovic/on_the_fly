# Frontni model določa VO in lokalna številka verzije

Kopiranje starega VM ustvari najvišjo globalno številko njegovega tipa, vendar ga pusti na zgodovinski VO, zato globalno »latest« ni primerna oznaka aktivnega modela. Frontni VM je VM z najvišjo številko svojega tipa na frontnem VO; ob kopiranju frontne VO se naprej premaknejo ti lokalno izbrani VM, prejšnja VO pa postane ne-frontna in zaklenjena. Samodejno izbiro po številki ohranimo namesto uvedbe ročnega izbora aktivnega VM; uporabnik je odgovoren za namerno promocijo nove verzije.

## Posledice

- Tip modela lahko nastopa na največ enem frontnem VO, čeprav lahko ta VO vsebuje več njegovih verzij.
- Frontnost VO določa `delovna_geo_coniranje`; oznake uporabnik ne spreminja ročno.
- Kopiranje VO je v začetnem obsegu dovoljeno samo za frontni VO. Začetno stanje verig je že vzpostavljeno; nov postopek za ustanavljanje verig ni potreben.
- Zaklenjenost VO varuje območja; zaklenjenost oziroma pripisnost VM varuje podatke in hierarhijo VM. Zaklenjen VO sam po sebi ne preprečuje spreminjanja hierarhije nezaklenjenega VM.
- Sprememba frontnega VO zunaj običajnega kopiranja ostane poseg ekipe na bazi.
- Filtri območij in delovnega VM na karti lahko ostanejo neusklajeni; avtomatska uskladitev ni del tega obsega.

Dogovor: 2026-10-10. Vir: [latest_ideja.md](../../latest_ideja.md) in zaključeni pogovor o zasnovi. Opisuje načrtovano delovanje, ne potrjene implementacije.
