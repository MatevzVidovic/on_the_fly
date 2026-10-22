



Izvedba spremembe datuma na migracijah s CET in CEST namesto UTC




Na mnogih migracijah uporabljamo obliko:
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,

kjer DATUM_SYS uporabimo kot polje DATE_CHANGED na migraciji.

Backend pridobljeno polje s timezoneom shrani v high-water mark polje, ki je navaden timestamp in ne timestamptz. (pri tem datetime-a ne zamakne, ampak samo odvzame informacijo o timezone-u, ura pa ostane ista.)

Iz tega razloga pride do zamikov ob naslednjem zagonu migracije: ko backend ponovno zažene migracijo in prebere datum, ga oplemeniti s timezone-om UTC+0.

Tako v integracijah pride do izgube podatkov v časovnem pasu 1 ali 2 ure (odvisno od poletnega ali zimskega časa).



Kot začasno rešitev je potrebno uvesti naslednje na takšnih integracijah:

dodamo DATUM_SYS_SYNC

iz DATUM_SYS nardim vanj kopijo in conversion v UTC+0

na integraciji dodamo: SYS_EXTRACT_UTC(FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana')) AS DATUM_SYS_SYNC

in na integraciji nastavimo potem to polje kot DATE_CHANGED field

integracije ponovno zaženemo in preverimo, da ne izvedejo polne sinhronizacije zaradi spremembe polja, ki velja za DATE_CHANGED

