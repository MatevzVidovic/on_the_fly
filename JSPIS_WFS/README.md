# eProstor WFS – upravni akti

Orodje podpira dva načina prenosa javnih podatkov upravnih aktov:

- checkpointiran popoln prenos v GeoPackage za začetni zajem, arhiv ali obnovo;
- redno delta usklajevanje v PostgreSQL/PostGIS.

Vir vsebuje:

- `SI.MOP.GRAD:UPRAVNI_AKTI` → `upravni_akti_tocke`;
- `SI.MOP.GRAD:UPRAVNI_AKTI_PARCELE` → `upravni_akti_parcele`.

Izhodni koordinatni sistem je `EPSG:3794`.

## Namestitev

Potreben je Python 3.12 ali novejši. GeoPackage uporablja GDAL prek
GeoPandas/pyogrio; podatkovna baza potrebuje PostgreSQL 14+ in PostGIS 3+.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install .
```

## Checkpointiran prenos na disk

```bash
# Preverjanje shem in trenutnih števil zapisov
python -m wfs_sync discover --report build/wfs-discovery.json

# Nov prenos ali samodejno nadaljevanje obstoječega checkpointa
python -m wfs_sync sync --output data/upravni_akti.gpkg

# Lokalno stanje brez klica WFS
python -m wfs_sync status --output data/upravni_akti.gpkg

# Zavrnitev starega checkpointa in nov začetek
python -m wfs_sync sync --output data/upravni_akti.gpkg --restart
```

Med prenosom ostaneta na disku:

- `.upravni_akti.partial.gpkg`;
- `.upravni_akti.gpkg.checkpoint.json`.

Checkpoint se posodobi po vsaki zaključeni keyset meji `ID_UA`. Ob prekinitvi
se isti ukaz nadaljuje za zadnjim zaključenim ID-jem. Sprememba endpointa,
CRS-a, pogodbe slojev ali izvornega števila zapisov zahteva `--restart`.

Po uspehu nastanejo:

- `upravni_akti.gpkg`;
- `upravni_akti.gpkg.manifest.json`;
- `upravni_akti.gpkg.sha256`.

Prejšnji dokončan GeoPackage ostane nespremenjen do atomske objave novega.

## PostGIS

Povezava se podaja samo prek okoljske spremenljivke:

```bash
export DATABASE_URL='postgresql://user:password@db.example/jspis'
```

Orodje upravlja namensko shemo `eprostor`:

```bash
# Idempotentna izdelava sheme, tabel in indeksov
python -m wfs_sync db-init

# Začetno polnjenje iz že prenesenega GeoPackage
python -m wfs_sync db-bootstrap --input data/upravni_akti.gpkg

# Redna delta sinhronizacija
python -m wfs_sync db-sync

# Ročni popoln pregled vseh geometrij
python -m wfs_sync db-sync --full-refresh
```

`db-bootstrap` sprejme samo dokončano objavo skupaj z datotekama
`.manifest.json` in `.sha256`; pred zamenjavo preveri kontrolno vsoto, sloje,
števila zapisov, shemo, CRS in geometrije.

### Delta postopek

Za vsak sloj skripta:

1. prenese celoten lahek CSV inventar `FID + ID_UA + ZAD_SPR` brez geometrije;
2. primerja inventar s PostGIS zrcalom;
3. prek WFS `resourceId` prenese samo nove ali spremenjene zapise;
4. zapise z `ZAD_SPR IS NULL` osveži ob vsakem zagonu;
5. vstavi oziroma posodobi spremembe;
6. izbriše lokalne WFS ID-je, ki jih ni več v izvornem inventarju;
7. stanje obeh slojev in `sync_state` potrdi v eni transakciji.

To odpravi problem brisanj, ki ga sam časovni filter ne more rešiti. Za točke
in parcele je ključ `wfs_id`; `ID_UA` pri parcelah ni unikaten. Če vir spremeni
WFS ID, se nov zapis vstavi, stari pa v istem ciklu izbriše.

Javni točkovni sloj trenutno vsebuje tudi identične podvojene vrstice z istim
`wfs_id`. Surovi GeoPackage jih ohrani, PostGIS pa identične dvojnike
kanonizira v eno vrstico; konfliktne dvojnike zavrne. Vsak DB cikel preveri
tudi živi fingerprint WFS sheme in se ob nenapovedani spremembi varno ustavi.

Inventar uporablja boundary-safe keyset paging po `ID_UA`. Pred transakcijo se
število obeh izvornih slojev ponovno preveri. WFS ne ponuja transakcijskega
snapshot-a, zato se redka sočasna sprememba z nespremenjenim skupnim številom
lahko dokončno uskladi šele pri naslednjem zagonu.

CSV čas brez odmika se interpretira v `Europe/Ljubljana` in shrani v UTC, kar
ustreza GeoJSON zapisu istega vira. Če GeoServer izpusti posamezen ID iz
večvrednostnega `resourceId` odgovora, ga skripta še enkrat zahteva samostojno
in nato še vedno zahteva natančno ujemanje vseh zahtevanih ID-jev.

## Cron na lastnem strežniku

GitHub Actions ni produkcijski scheduler. Prejšnja lokalna YAML datoteka ni
bila potisnjena ali aktivirana in je iz rešitve odstranjena.

Primer tedenskega crona:

```cron
17 4 * * 1 cd /opt/jspis-wfs && . /etc/jspis-wfs.env && /opt/jspis-wfs/.venv/bin/python -m wfs_sync db-sync >> /var/log/jspis-wfs-sync.log 2>&1
```

Datoteka `/etc/jspis-wfs.env` naj bo dostopna samo izvajalnemu uporabniku in
naj vsebuje `export DATABASE_URL='postgresql://...'`. Alternativi sta zaščiten
cron wrapper ali systemd `EnvironmentFile`; skrivnosti ne vpisujte neposredno
v crontab. Postgres advisory lock zavrne prekrivajoča se zagona.

## Nastavitve

Globalne CLI možnosti morajo biti pred podukazom:

```bash
python -m wfs_sync --page-size 2000 --timeout 180 sync \
  --output data/upravni_akti.gpkg
```

Podprte okoljske spremenljivke:

- `DATABASE_URL`;
- `WFS_ENDPOINT`;
- `WFS_PAGE_SIZE` (privzeto `5000`);
- `WFS_RESOURCE_BATCH_SIZE` (privzeto `100`);
- `WFS_TIMEOUT` (privzeto `120`);
- `WFS_RETRIES` (privzeto `4`);
- `WFS_LOG_LEVEL`;
- `WFS_OUTPUT`;
- `WFS_REPORT`.

## Testi

```bash
python -m pip install -e '.[dev]'
pytest
```

Offline testi ne kličejo javne storitve. Test z resničnim začasnim PostGIS se
vključi z:

```bash
WFS_SYNC_TEST_DATABASE_URL='postgresql://...' pytest \
  Agents/AgentTests/wfs-sync/implementers-tests/test_postgis.py
```
