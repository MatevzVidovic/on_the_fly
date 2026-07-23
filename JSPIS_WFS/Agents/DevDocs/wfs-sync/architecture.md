# WFS sync — architecture

## Layered DAG

Arrows mean module dependency or entrypoint invocation. Subgraph borders separate architectural layers; no dependency violates the downward DAG.

```mermaid
flowchart TB
    subgraph L4["Layer 4 — automation / entry"]
        direction LR
        WF["GitHub workflow<br/>.github/workflows/wfs-sync.yml"]
        MAIN["__main__.py"]
    end

    subgraph L3["Layer 3 — interface"]
        direction LR
        CLI["cli.py<br/>arguments, env, exit codes"]
    end

    subgraph L2["Layer 2 — application"]
        direction LR
        DISC["discovery.py<br/>schema and count report"]
        SYNC["sync.py<br/>two-layer orchestration"]
    end

    subgraph L1["Layer 1 — infrastructure"]
        direction LR
        WFS["wfs.py<br/>HTTP, XML, GeoJSON, keyset"]
        STORE["storage.py<br/>validation, staging, lock, publish"]
    end

    subgraph L0["Layer 0 — domain"]
        direction LR
        MODEL["model.py<br/>configuration, layer specs, results"]
    end

    WF --> CLI
    MAIN --> CLI
    CLI --> DISC
    CLI --> SYNC
    CLI --> WFS
    CLI --> STORE
    CLI --> MODEL
    DISC --> WFS
    DISC --> MODEL
    SYNC --> WFS
    SYNC --> STORE
    SYNC --> MODEL
    WFS --> MODEL
    STORE --> MODEL

    style L4 fill:#f8f9fa,stroke:#6c757d,stroke-width:2px
    style L3 fill:#f8f9fa,stroke:#6c757d,stroke-width:2px
    style L2 fill:#f8f9fa,stroke:#6c757d,stroke-width:2px
    style L1 fill:#f8f9fa,stroke:#6c757d,stroke-width:2px
    style L0 fill:#f8f9fa,stroke:#6c757d,stroke-width:2px
```

- `model.py`
  - fixed source/output mappings
  - field types
  - sort expressions
- `wfs.py`
  - bounded retries / timeout
  - WFS exceptions
  - WFS 2.0 hits and features
  - WFS 1.1 schema fallback for server defect
  - typed GeoDataFrames
- `storage.py`
  - frame checks
  - page append
  - exact layer-set inspection
  - SQLite integrity check
  - exclusive output lock
- `sync.py`
  - counts and unique IDs
  - both layers or no publication
- `discovery.py`
  - strict schema validation
  - full-sync rationale

## Sync sequence

Numbered messages form the synchronization pseudocode. The layer loop covers points, then parcels.

```mermaid
sequenceDiagram
    actor Run as CLI / workflow
    participant Sync as sync.py
    participant WFS as wfs.py
    participant Store as storage.py
    participant File as GeoPackage

    Run->>Sync: 1. sync_all()
    Sync->>Store: 2. acquire output lock
    Sync->>Store: 3. create sibling staging path
    loop 4. each layer
        Sync->>WFS: 4.1 initial numberMatched
        Sync->>WFS: 4.2 count ID_UA IS NULL
        opt 4.2.a nullable-key group exists
            Sync->>WFS: 4.2.a.1 fetch complete nullable-key group
            WFS-->>Sync: 4.2.a.2 typed nullable-key page
            Sync->>Sync: 4.2.a.3 reject repeated _wfs_id
            Sync->>Store: 4.2.a.4 validate and append page
            Store->>File: 4.2.a.5 write staging layer
        end
        loop 4.3 numeric keyset until expected count emitted
            Sync->>WFS: 4.3.1 ID_UA keyset CQL page
            WFS->>WFS: 4.3.2 split safe prefix / boundary ID_UA
            WFS->>WFS: 4.3.3 refetch complete boundary group
            WFS-->>Sync: 4.3.4 typed page, nullable geometry allowed
            Sync->>Sync: 4.3.5 reject repeated _wfs_id
            Sync->>Store: 4.3.6 validate and append page
            Store->>File: 4.3.7 write staging layer
        end
        Sync->>WFS: 4.4 final layer numberMatched
    end
    Sync->>Store: 5. inspect exact layers, counts, bounds
    loop 6. each layer
        Sync->>WFS: 6.1 pre-publication numberMatched
    end
    Sync->>Store: 7. publish staging file
    Store->>File: 7.1 SQLite integrity_check
    Store->>File: 7.2 atomic os.replace
    Store-->>Sync: 8. release lock
    Sync-->>Run: 9. layer results
```

- `1–3`
  - one run, one lock, one staging file
- `4.2–4.2.a`
  - count nullable keys once
  - fetch one complete `ID_UA IS NULL` group when present
- `4.3.1`
  - first numeric page: `ID_UA IS NOT NULL`
  - later pages: `ID_UA > cursor`
- `4.3.2–4.3.3`
  - boundary tie excluded from prefix
  - equality query retrieves the entire tied group
- `4.2.a.2`, `4.3.4`
  - source types normalized
  - parcel `NULL` geometry retained
- `4.4`, `6.1`
  - abort on count drift
- `7`
  - only fully verified two-layer file becomes visible
- failure path
  - staging removed
  - destination unchanged
  - lock released
