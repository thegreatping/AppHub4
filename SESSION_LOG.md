# AppHub 4.0 — Session Log

Newest entries at the top.

---

## 2026-10-07 — Peak Academy LMS integrated as a native AppHub module (App_ID 38)

**Status:** Done locally. NOT committed, NOT deployed. Rule honored: no existing module
changed without authorization (only the 4 pre-approved shared files were edited).

### Source
Standalone Peak Academy LMS Flask app from Ryan Mahaffey —
`Peak Academy/PeakAcademy_LMS_TestDeploy_2026-10-07.zip`, extracted to
`Peak Academy/PeakAcademy_LMS_TestDeploy_2026-10-07_extracted/`.

### New package: `APPHUB_4/peak_academy/`
Copied from the delivered `lms_app` and adapted:
- `data.py` — reads the 4 WH_PROD2 LMS tables via AppHub `SafeConnection(..., "WH_PROD2")`
  (dropped the msi/sp/pyodbc host paths). In-memory TTL cache + pickle kept.
- `views/__init__.py` — blueprint kept named `lms` (so `url_for('lms.*')` stays valid),
  mounted at `/peak-academy`, `static_url_path="/static"`. Identity = AppHub session email
  (honours View-As). Admins = `APP_ADMINS` App_ID 38 + developers. Login gate mirrors
  `auth.login_required` (incl. dev bypass). Context processor also injects the shell.html
  context (modules, user, version, impersonation flags). Legacy `/dev/view-as` disabled.
- `__init__.py` — `init_peak_academy(app)` wires the store + blueprint + jinja filters/globals.
- `config.py` — cache at `_pa_cache/snapshot.pkl`.
- `templates/base.html` — rewritten to `{% extends "shell.html" %}` with a content-header +
  in-module tab bar; all 15 tab templates had `{% block content %}` → `{% block pa_main %}`.
- `static/peak_academy.css` — new; restyles every component (tabs, KPIs, cards, bars,
  donuts, tiles, status pills, reports, filters) to AppHub theme tokens.
- Tables conform to the shared `table_menu.js` (add `data-table`, drop LMS click-sort) via a
  small script in base.html; LMS `app.js` kept only for its type-to-filter search boxes.

### Approved shared-file edits (backed up to `_backups/peak_academy_integration_*`)
- `app.py` (import + `init_peak_academy(app)`), `modules.py` (MODULES entry + APP_ID_MAP 38),
  `nav.py` (`peak_academy_lms` in `_BETA_ALLOWED_MODULES`), `requirements.txt` (pandas, openpyxl).

### DB (DB_APP_SUPPORT; snapshot backup `_backups/peak_academy_db_snapshot_*.json`)
- `APP_LIST` App_ID 38 'Peak Academy' Flag_Active=1 Testing_Status=PENDING (IDENTITY_INSERT).
- `APP_ADMINS` cpell baseline admin.
- `MODULE_AUDIENCE` empty on purpose — visibility = devs + AppHub Maintenance grants.
- Identity: route `/peak-academy/`, icon `fa-graduation-cap`, color teal `#13a2c4`.

### Verified (localhost:5001)
- Appears in nav; `/module/peak_academy_lms` → `/peak-academy/overview`.
- All 9 tabs 200 with real WH_PROD2 data; location + course drilldowns 200.
- Shared column sort/filter menu works on the grids; dark-theme styling conforms.
- Only the 4 approved shared files changed outside the new package.

### Follow-ups
- Pre-existing (delivered app): "Unassigned" row → `/compliance/location/-1` 404s (Flask
  `<int:key>` rejects negatives). Admin-only; left as delivered.
- Add Sarah Sugerman + BI team to `APP_ADMINS(38)` via Maintenance once emails confirmed.
- Not committed / not deployed.


## 2026-10-07 — Shared unified column header menu for all module tables

**Status:** Done locally. NOT deployed to Azure (awaiting user approval).

### What was built
A reusable, self-contained component that gives every module data table the same
unified header menu the Leadership Scorecard has — click any column header to open
one popover with **Sort A→Z / Z→A** and an **Excel-style multi-select value filter**.
The **"Show Data" drilldown is intentionally omitted** (module tables have no
underlying data table to drill into).

### New / changed files
- `static/js/table_menu.js` (new) — the component.
- `static/css/table_menu.css` (new) — styling (`tm-*` classes, uses global theme vars).
- `templates/shell.html` — loads the CSS in `<head>` and the JS before `</body>`
  (cache-busted). No other templates were edited.

### How it attaches
Auto-enhances tables matching this class selector (opt-in by class):
`table.data-table, table.scm-table, table.paf-table, table.vs-table,
table.ms-table, table.qad-table, table.qas-table, table.spr-steps`.

Excluded on purpose:
- **Leadership Scorecard** (`sc-table`, `sc-dd-table`) — left 100% untouched (user req).
- **Table Manager** (`stm-table`) — already has its own full sort/filter system.
- **RFS + pivot/metric/tooltip tables** (`rfs-*`, `ttbl`, `ctbl`, `sam-table`,
  `market-prop-table`) — not row grids; RFS is locked.

### Key design decisions (why it's robust)
- Operates on **rendered DOM rows**, so it's independent of each module's JS data
  pipeline (most modules do `tbody.innerHTML = ...` on sort/filter).
- A **table-level MutationObserver** (childList+subtree) re-applies the active
  sort/filter after a tbody re-render AND re-decorates **late JS-built theads**
  (e.g., EDM's dynamic tables, milestones, QA tables).
- **Detail/colspan rows are grouped** with their primary row, so sorting keeps an
  expandable detail row attached to its parent and filtering hides them together.
- Header clicks are intercepted in the **capture phase** to override any existing
  `onclick="sortX(this)"` native sort (no double behavior).
- Reapply debounce uses **setTimeout** (not requestAnimationFrame) so it still fires
  in background/non-visible tabs.
- Auto-skips non-sortable headers: empty, "Actions", and columns whose header holds a
  checkbox/button/select.

### Verified in dev (localhost:5001)
- **Peak Link `#subTable`** (hardest case — 6 interleaved detail rows): sort asc/desc
  keeps each detail row paired with its parent; plain-click isolate, Ctrl+click
  multi-select, (Select all), Clear, and the filter dot all correct.
- **Employee Data Manager** (`/edm/`): all 35 tables enhanced; visible headers
  decorated with Actions/checkbox columns correctly skipped; a late-rendered thead
  auto-decorates and sorts (Alpha/Beta/Gamma).
- **Leadership Scorecard**: 0 tables enhanced, 0 `tm-th` decorations, its own
  `openHeadMenu` intact — confirmed untouched.

### Not done / next
- Deployment to Azure App Service (AppHub40) — **awaiting explicit user approval.**
