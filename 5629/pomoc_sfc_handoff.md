# Pomoč: dynamic documentation catalogue

## What we want

- In **Pomoč**, show documents from `isam_dokumentacija`, grouped by `modul`.
- Show document name, type, and `updated_at` as a date.
- Allow an individual download and one ZIP download per module.

## What we found

- `general/help` stores a static rich-text HTML component at `PROFILE → TOOLS_EXTRA`.
- The editor strips scripts; Help renders with Vue `v-html`, so scripts/Vue directives would not run even if stored.
- SFC is the supported runtime for administrator-authored HTML/CSS/JS.

## What to do

1. Create SFC `Pomoč – dokumentacija` with position `SFC_TOOL`.
2. Bind it with `sfc_tool_position = PROFILE` and `sfc_tool_content_position = TOOLS_EXTRA`.
3. Its **Button code** is the Pomoč button; its **Content code** is the dynamic catalogue.
4. Disable the old `general/help` entry for this company to avoid two Pomoč buttons.
5. Add authorised backend endpoints:
   - `GET /api/help/documents` → allowed document metadata + download URLs.
   - `GET /api/help/modules/{module}/download` → authorised ZIP stream.

Do not expose database/S3 credentials in the SFC. Use `isam_dokumentacija.updated_at::date`; use S3 `LastModified` only through the backend if explicitly required.
