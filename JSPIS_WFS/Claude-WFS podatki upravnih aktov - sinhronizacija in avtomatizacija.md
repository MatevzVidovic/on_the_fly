# WFS podatki upravnih aktov - sinhronizacija in avtomatizacija

**Created:** 7/23/2026 8:59:30  
**Updated:** 7/23/2026 9:04:23  
**Exported:** 7/23/2026 9:15:53  
**Link:** [https://claude.ai/chat/98f9e7ca-7270-4e34-b054-6a1184489421](https://claude.ai/chat/98f9e7ca-7270-4e34-b054-6a1184489421)  

## User:

> 7/23/2026 8:59:31

https://eprostor.gov.si/imps/srv/api/records/ff907852-18ca-426f-a100-5631ca5fa95c

Iz WFS je potrebno prenašati podatke upravnih aktov za točke in parcele. Za to se naredi dva sloja.
https://eprostor.gov.si/imps/srv/api/records/ff907852-18ca-426f-a100-5631ca5fa95c 
Preveri, če so kakšni optimalni načini, da prenašamo te podatek. Preko python skripte je izvedljivo in se lahko poveže na workflow ter nastavi avtomatsko posodabljanje npr. enkrat na teden.
Nevem, če je kakšen atribut, da bi lahko delali delto. Če ni naredimo popolno sinhronizacijo.

what am i supposed to do with this

## Assistant:

> 7/23/2026 9:00:11

> Dekodiral zahtevo za GIS podatkovni pipeline.
>
> - Deciphering WFS data transfer methods and synchronization strategies.
> - [Javne storitve Prostorskega informacijskega sistema - upravni akti s področja graditve objektov (WFS) (gov.si)](https://eprostor.gov.si/imps/srv/api/records/ff907852-18ca-426f-a100-5631ca5fa95c)
> - Dekodiral zahtevo za GIS podatkovni pipeline.
> - **Done**

That link is a metadata record from Slovenia's national spatial data catalog (eProstor / the INSPIRE system), and the text pasted above it is a work assignment written in Slovenian. So what's happened is: someone handed you a task, and you're being asked to build a data pipeline. Here's what it actually says and means.

**The dataset.** The record describes a public WFS (Web Feature Service) run by the Ministry for Natural Resources and Spatial Planning. It serves "upravni akti s področja graditve objektov" — administrative acts related to construction (building permits, occupancy permits, etc.). The service exposes two feature layers:
- **Upravni akti (točke)** — the acts as *points* (locations of issued permits)
- **Upravni akti (parcele/območja)** — the acts linked to *land parcels* (polygons)

The actual service endpoint is `https://storitve.eprostor.gov.si/ows-pub-wfs/wfs`, data comes out as GML 3.2.1, and the coordinate system is EPSG:3794 (Slovenia's national grid, D96/TM).

**What the assignment is asking you to do**, in plain terms:

1. Pull the administrative-acts data from that WFS — both the points layer and the parcels layer (hence "make two layers").
2. Figure out the best way to download it. The note already suggests the answer: do it with a **Python script**.
3. Wire that script into a **workflow** so it runs on a schedule — e.g. **once a week**, automatically.
4. Check whether the data has some attribute (like a "last modified" / date-of-change field) that would let you fetch **only what changed since last time** (a *delta* / incremental update). If such an attribute exists, use it. If not, just **re-download everything each run** (a *full sync*).

So it's not really an open-ended puzzle — it's a fairly standard "scheduled WFS harvester" task. The one genuine investigation item is step 4: whether incremental updates are possible depends on the fields the layers expose, which you'd find by calling `GetCapabilities` and then `DescribeFeatureType` on the service.

If it'd help, I can do a couple of concrete things next:
- Query that WFS's `GetCapabilities`/`DescribeFeatureType` and tell you the exact layer names and available attributes (so we can answer the delta-vs-full-sync question for real), and
- Write the Python harvester script (e.g. using `owslib`/`requests` + `geopandas`, output to GeoPackage/PostGIS) plus a simple weekly scheduler setup.

Want me to start with the capabilities check so we know what we're working with?

## User:

> 7/23/2026 9:02:20

https://storitve.eprostor.gov.si/ows-pub-wfs/wfs

How do i get data from this? where did ypu get this link - i didnt find much on the website

Research what endpoints exist on it and what i can do with it

## Assistant:

> 7/23/2026 9:04:23

> Excavated WFS endpoint metadata and encountered network constraints.
>
> - Excavated WFS endpoint metadata and encountered network constraints.
> - **Done**

First, to answer your question: I got that link from the metadata record you sent in your last message. Buried in it, under "OnLine resource," it lists the service endpoint `https://storitve.eprostor.gov.si/ows-pub-wfs/wfs`. That's the actual data service; the eprostor.gov.si page you were looking at is just the *catalog description* of it, which is why you didn't find much — the data lives on a different host (`storitve.eprostor.gov.si`).

Let me query the service directly to see what it offers.

> Grappled with XML parsing issues and explored alternative extraction methods.
>
> - [https://storitve.eprostor.gov.si/ows-pub-wfs/wfs (gov.si)](https://storitve.eprostor.gov.si/ows-pub-wfs/wfs)
> - Grappled with XML parsing issues and explored alternative extraction methods.
> - **Done**

The capabilities document came back as raw XML that the fetcher treated as binary. Let me try pulling it as text.

> Encountered technical barriers; pivoted toward documentation research strategy.
>
> - [https://storitve.eprostor.gov.si/ows-pub-wfs/wfs (gov.si)](https://storitve.eprostor.gov.si/ows-pub-wfs/wfs)
> - Encountered technical barriers; pivoted toward documentation research strategy.
> - **Done**

The fetcher won't render the XML (it keeps flagging it as binary), and I can't curl it directly from my sandbox because that government host isn't on my sandbox's network allowlist. Let me search for documentation on the service and its layers instead.

> Excavated WFS capabilities and devised JSON sampling strategy.
>
> - eprostor ows-pub-wfs upravni akti WFS layers
> - Excavated WFS capabilities and devised JSON sampling strategy.
> - **Done**

Good — that surfaced the two layer names. Now let me try pulling a single sample feature as JSON, which will also reveal the attribute schema (important for the delta-vs-full-sync question).

> Investigated WFS service capabilities and formulated practical data access strategy.
>
> - [https://storitve.eprostor.gov.si/ows-pub-wfs/wfs (gov.si)](https://storitve.eprostor.gov.si/ows-pub-wfs/wfs)
> - Investigated WFS service capabilities and formulated practical data access strategy.
> - **Done**

The fetcher on my end refuses to render anything from that host (it flags all their XML/JSON as "binary"), and I can't reach the server from my sandbox either, so I can't dump the raw capabilities for you directly. But between the metadata record and the WMS/WFS capabilities I found, I've got enough to explain the service concretely. Let me do one more check on how the service is built, since that decides the best download strategy.

> Investigated GeoServer capabilities and architected comprehensive WFS query guide.
>
> - storitve.eprostor.gov.si ows-pub-wfs GeoServer paging outputFormat json
> - Investigated GeoServer capabilities and architected comprehensive WFS query guide.
> - **Done**

Good — that first result gives it away. The error string it returns (`Could not determine geoserver request...AdvancedDispatchFilter`) is a **GeoServer** signature. So this service runs GeoServer, which tells us exactly what it can do. That's the key finding, because GeoServer WFS supports GeoJSON output, paging, sorting, and attribute filtering — everything you'd want for an automated harvester.

Here's the picture.

## What the service is

A standard OGC **WFS** at `https://storitve.eprostor.gov.si/ows-pub-wfs/wfs`, backed by GeoServer, publishing two free/public layers:

- `SI.MOP.GRAD:UPRAVNI_AKTI` — administrative acts as **points** (permit centroids)
- `SI.MOP.GRAD:UPRAVNI_AKTI_PARCELE` — administrative acts joined to **parcels** (polygons)

Native CRS is **EPSG:3794** (Slovenia D96/TM); it also advertises CRS:84 (WGS84 lon/lat). Default output is GML 3.2.1, but as GeoServer it also does GeoJSON, CSV, and shapefile.

## WFS isn't a file — it's a query API

A WFS has only three operations you care about. You call them by changing the `request=` parameter on that same base URL:

**1. GetCapabilities** — the "menu." Lists layers, supported CRSs, output formats, and max feature limits.
```
.../wfs?service=WFS&version=2.0.0&request=GetCapabilities
```

**2. DescribeFeatureType** — the schema of one layer, i.e. its **attribute/column names and types**. This is the one that answers your delta question.
```
.../wfs?service=WFS&version=2.0.0&request=DescribeFeatureType&typeNames=SI.MOP.GRAD:UPRAVNI_AKTI
```

**3. GetFeature** — the actual data. Examples:
```
# how many features exist (cheap, returns just a count):
.../wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=SI.MOP.GRAD:UPRAVNI_AKTI&resultType=hits

# first 10 rows as GeoJSON:
.../wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=SI.MOP.GRAD:UPRAVNI_AKTI&count=10&outputFormat=application/json

# paging through everything in 5000-row chunks:
.../wfs?...&request=GetFeature&typeNames=SI.MOP.GRAD:UPRAVNI_AKTI&count=5000&startIndex=0
.../wfs?...&count=5000&startIndex=5000   ... and so on
```

Paste any of these into a browser — XML/JSON renders fine there. (My fetch tool here insists on treating their responses as binary, and I can't reach the host from my sandbox, which is why I can't paste the raw capabilities back to you. If you open GetCapabilities and DescribeFeatureType and paste the output to me, I'll read it and pull out the exact limits and column names.)

## Your delta question

Whether incremental sync is possible comes down to one thing: **does DescribeFeatureType show a timestamp column** (something like a `DATUM_SPREMEMBE`, `DATUM_UA`, `LAST_UPDATE`, etc.)?

- If yes → you do delta with a filter, only pulling rows newer than your last run:
  ```
  &CQL_FILTER=DATUM_SPREMEMBE > '2026-07-16T00:00:00'
  ```
  GeoServer supports `CQL_FILTER` (easy) and standard OGC filters. You'd store the max timestamp each run and use it as the lower bound next time.
- If there's no such column → full sync each week, as your task note anticipated. Given this is national permit data (likely tens of thousands of features, not millions), a weekly full pull of two layers is completely reasonable and much simpler to keep correct.

## The download strategy that fits

Because it's GeoServer, the clean Python approach is: request `outputFormat=application/json`, page with `count` + `startIndex`, and load straight into GeoPandas → write to GeoPackage or PostGIS. No GML parsing headaches. Schedule it weekly (cron, systemd timer, or whatever your workflow orchestrator is — Airflow/Windows Task Scheduler/GitLab CI all work).

Two things worth confirming from GetCapabilities before committing: the server's **max feature count per request** (GeoServer often caps around 1M or less, hence paging), and whether `application/json` is actually in its advertised output format list (almost always yes for GeoServer, but worth verifying).

Want me to write the Python harvester now (GeoJSON + paging + optional CQL delta + GeoPackage/PostGIS output), so you'd only need to drop in the timestamp column name once you've checked DescribeFeatureType? Or would you rather paste me the DescribeFeatureType output first so I can wire the delta in directly?

---

**Sources:**

- [https://storitve.eprostor.gov.si/ows-pub-wms/ ...](https://storitve.eprostor.gov.si/ows-pub-wms/wms?request=getCapabilities)
- [Javno dostopna storitev WMS GURS](https://eprostor.gov.si/imps-test/srv/api/records/691e6bbd-6baa-4365-ac4c-2b8564158313/formatters/xsl-view?portalLink=&view=inspire)
- [https://storitve.eprostor.gov.si/ows-pub-wms/SI.GURS.DK/ ...](https://storitve.eprostor.gov.si/ows-pub-wms/SI.GURS.DK/ows?service=wms&request=GetCapabilities&version=1.3.0)
- [https://storitve.eprostor.gov.si/ows-pub-wms/SI.GURS. ...](https://storitve.eprostor.gov.si/ows-pub-wms/SI.GURS.ZPDZ/ows?service=wms&request=GetCapabilities&version=1.3.0)
- [Spatial Information System - Public Web Feature Service (WFS)](https://eprostor.gov.si/imps/srv/api/records/89a4954f-8118-4220-b73d-2b961afdfea5)
- [Javni spletni servisi Web Feature Service (WFS) - Spatineo Directory](https://directory.spatineo.com/service/37103/)
- [WMS/WFS - Getting Started | data-publication](https://bcgov.github.io/data-publication/pages/map_wms_wfs_getting_started.html)
- [Gov](https://eprostor.gov.si/imps/srv/api/records/1541149/formatters/xml)
- [Storitve WFS - E-prostor](https://www.e-prostor.gov.si/inspire/seznam-omreznih-storitev/storitve-wfs/)
- [https://storitve.eprostor.gov.si/ows-pub-wms/wms](https://storitve.eprostor.gov.si/ows-pub-wms/wms)
- [WMS/WFS - Tips & Tricks | data-publication](https://bcgov.github.io/data-publication/pages/tips_tricks_webservices.html)
- [WFS output formats — GeoServer 2.28.0 User Manual](https://docs.geoserver.org/main/en/user/services/wfs/outputformats.html)
- [GeoServer](https://en.wikipedia.org/wiki/GeoServer)
- [services.geodata.state.gov](https://services.geodata.state.gov/geoserver/web/wicket/bookmarkable/org.geoserver.wps.web.WPSRequestBuilder)
- [[OSM-dev] Is there any API to get data from OSM as geoJson?](https://lists.openstreetmap.org/pipermail/dev/2013-February/026513.html)
- [GeoServer 2.22.4](https://maps.dartmoor.gov.uk/geoserver/web/wicket/bookmarkable/org.geoserver.wps.web.WPSRequestBuilder;jsessionid=9A64ED6416CFD22DCF093FBD26721BEC)
- [maps.dartmoor.gov.uk](https://maps.dartmoor.gov.uk/geoserver/web)
- [GeoServer Web Map Service](https://emodnet.ec.europa.eu/geonetwork/srv/api/records/dc9b6360-f546-4767-b415-39b6dc9b6e06)

Powered by Claude Exporter (https://www.ai-chat-exporter.net)
