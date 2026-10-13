



We need to make an integration-repair system (like we tried to do with EV_integ but never ran. But we want to make it more tied to existing Oracle integrations in LIFT and make it very all simple).

vzamemo podatke integracije, kot to počne backend

Vzamemo id in date_changed polje iz remote-a
Naredimo do nekega date_time_changed
Ugotovimo, katere id imamo pri sebi premalo in jih gremo dodajat
Ugotovimo, katere id imamo preveč in jih odstranimo

Stvar deluje za neko splošno integracijo na KN Orcale v LIFT-u - pač iz naše baze potegne sql za to integracijo


Koda mora bit res maksimalno preprosta
SQLite naj ima:
- integracija-prenos tabela (tu initamo prenašanje za neko integracijo, na ta UUID se potem navezujemo, ob initu definiramo uuid integracije, date_changed do katerega delamo prenos - ta se vzame iz integracije kot to kar je trenuten high-water mark)
- child tabele: 
    - remote_ids_and_date_changed
    - removal_diff
    - addition_diff
