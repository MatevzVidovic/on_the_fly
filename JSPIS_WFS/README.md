# eProstor WFS – upravni akti

Tedenska popolna sinhronizacija dveh javnih slojev upravnih aktov v en
GeoPackage:

- `SI.MOP.GRAD:UPRAVNI_AKTI` → `upravni_akti_tocke`
- `SI.MOP.GRAD:UPRAVNI_AKTI_PARCELE` → `upravni_akti_parcele`

Izhodni CRS je `EPSG:3794`. Sinhronizacija je namenoma popolna. Atribut
`ZAD_SPR` sicer opisuje spremembo zapisa, vendar WFS ne ponuja izbrisanih
zapisov oziroma tombstonov. Delta zato ne more pravilno zaznati brisanj.

## Lokalni zagon

Potreben je Python 3.12 ali novejši in sistemske knjižnice GDAL, ki jih
uporabljata GeoPandas in pyogrio.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install .

# Hiter pregled shem in števila zapisov, brez prenosa geometrij
python -m wfs_sync discover --report build/wfs-discovery.json

# Celoten prenos (trenutno približno 864.000 geometrij)
python -m wfs_sync sync --output data/upravni_akti.gpkg
```

Globalne možnosti morajo biti pred ukazom:

```bash
python -m wfs_sync --page-size 2000 --timeout 180 sync \
  --output data/upravni_akti.gpkg
```

Enake nastavitve so na voljo prek `WFS_ENDPOINT`, `WFS_PAGE_SIZE`,
`WFS_TIMEOUT`, `WFS_RETRIES`, `WFS_LOG_LEVEL`, `WFS_OUTPUT` in `WFS_REPORT`.

## Varnost sinhronizacije

- WFS 2.0 keyset strani po `ID_UA` in `CQL_FILTER`; zadnja skupina z enakim
  `ID_UA` se vedno ponovno prenese v celoti, zato neunikatna meja strani ne
  more izpustiti zapisa
- preverjanje vsake strani: schema, tipi, CRS, geometrije in WFS ID-ji
- v pomnilniku je samo trenutna stran in množica vseh že videnih WFS ID-jev;
  poraba za ID-je zato raste s številom zapisov, ne pa z velikostjo geometrij
- ponovna primerjava `numberMatched` po prenosu
- oba sloja se najprej zapišeta v začasni GeoPackage
- star rezultat se zamenja z `os.replace` šele po vseh preverjanjih
- lock datoteka prepreči dva sočasna zagona

Če prenos pade, ostane prejšnji GeoPackage nespremenjen. Začasna datoteka se
odstrani. Parcelni vir vsebuje tudi zapise brez geometrije; ti se ohranijo z
`NULL` geometrijo, ker so njihovi atributi še vedno veljavni.

WFS strani niso transakcijski posnetek. Keyset pomikanje brez offsetov,
unikatni WFS ID-ji in primerjava števila vseh slojev tik pred objavo so
najboljša praktična zaščita, vendar ne morejo zaznati vsake sočasne spremembe,
če skupno število ostane enako.

`DescribeFeatureType` se najprej pošlje kot en WFS 2.0 klic s
singularnim parametrom `typeName`. Ker je storitev 23. julija 2026 za ta klic
občasno vračala `ArrayIndexOutOfBoundsException`, klient v tem konkretnem
primeru ponovi shemi posamično prek WFS 1.1. Prenos podatkov ostane WFS 2.0.

## Avtomatizacija

Workflow [`.github/workflows/wfs-sync.yml`](.github/workflows/wfs-sync.yml)
teče vsak ponedeljek ob 03:17 UTC in tudi ročno. Objavi:

- `upravni_akti.gpkg`
- poročilo odkrivanja
- SHA-256 kontrolne vsote

GitHub artifact je začetna dostava z omejeno hrambo, ne trajna podatkovna
shramba. Če ima uporabnik trajni objektni prostor ali podatkovno bazo, naj se
po uspešnem ukazu `sync` doda korak za objavo z začasnimi poverilnicami.

Primer za strežnik s cron:

```cron
17 4 * * 1 cd /opt/jspis-wfs && .venv/bin/python -m wfs_sync sync --output /srv/data/upravni_akti.gpkg >> /var/log/wfs-sync.log 2>&1
```

Čas cron je lokalni čas strežnika. Najprej preverite prostor na disku:
za atomsko zamenjavo morata med prenosom obstajati stara in nova datoteka.

## Testi

```bash
python -m pip install -e '.[dev]'
pytest
```

Avtomatski testi ne kličejo žive storitve. Za ročni omejeni pregled uporabite
`discover`; popolna sinhronizacija prenese približno 1 GB in ni smoke test.
