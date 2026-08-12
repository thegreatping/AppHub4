# Market Benchmark — Project Context
> **Update this file at the end of each month.** It is the first thing to read when resuming work on this project.
> Last updated: 2026-07-31

---

## What This App Is

A standalone Flask app (port **5055**) that replicates and extends the Market Benchmark module from the legacy Power Apps AppHub. It lets analysts select a **subject property**, manage its **assigned comp properties**, and view/edit detailed benchmark data across six tabs.

It runs independently of AppHub 4.0 for now. Future plan: integrate it as a Flask blueprint inside the main AppHub shell (change type from `"powerapps"` to `"flask"` in `modules.py` and register the blueprint in `routes.py`).

---

## How to Start the App

```powershell
Set-Location "C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\APPHUB_4\Market Benchmark"
$python = "C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\.venv\Scripts\python.exe"
& $python -u app.py
# Opens on http://localhost:5055  (debug mode, auto-reloads on save)
```

---

## File Map

```
APPHUB_4/Market Benchmark/
├── app.py                  ← Flask backend: ALL API routes + DB logic
├── templates/
│   └── index.html          ← Single-page app shell: tab HTML, slide-out HTML, cache bust versions
├── static/
│   ├── css/style.css       ← All styling (dark theme, grid, slide-out, fp section, badges)
│   └── js/app.js           ← All frontend JS (IIFE, ~1600 lines)
├── CONTEXT.md              ← This file
├── SESSION_LOG.md          ← Detailed session-by-session log
└── mockup_redesign.html    ← Static HTML mockup of proposed AppHub 4.0 redesign
```

---

## Database

- **Connection**: `SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)` — Fabric SQL Database (transactional endpoint)
- **Helper path**: `C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts`
- `load_env()` reads `C:\helpdesk\.env` (no arguments)
- **NEVER** use the analytics/datawarehouse endpoint for write operations

### Key Tables

| Table | Purpose |
|---|---|
| `COMP_ASSIGNMENTS` | Legacy weekly snapshot — stale, read for `subjectID` lookup only |
| `MktSrv_CompMap` | Live assign-comps source of truth. `compID` = `LEGACY_MARKETPROPERTYID` (NOT PROPERTY_KEY) |
| `COMP_FACT` | Comps tab data — per-comp benchmark fields |
| `FLOORPLAN_FACT` | Comps tab floorplan rows (per-comp, per-week) |
| `FLOORPLAN_WORKSPACE` | Floor Plans tab — comp property floor plan configs |
| `MktSrv_Schools` | Schools tab data |
| `MktSrv_Markets` | Markets tab data |
| `COMP_PROPERTY` | Comp property master (name, market, active flag) |
| `PROPERTY` | Authoritative property status/flags (source of truth) |

### Key Data Facts

- `MktSrv_CompMap.compID` = `LEGACY_MARKETPROPERTYID` (not `PROPERTY_KEY`) — critical for Assign Comps JOIN
- `MktSrv_CompMap.subjectID` = legacy subject ID — resolve via `_get_subject_id(conn, parent_key)` helper (`app.py` line ~595)
- `marketCompMapID` is **NOT** an identity column — always compute `MAX(marketCompMapID)+1` on INSERT
- `FLOORPLAN_ASSIGNMENT_KEY` is **NOT** an identity column — always compute `MAX()+1` on INSERT
- New-system properties (no legacy ID) fall back to using `PROPERTY_KEY` directly as `compID`

---

## Backend: app.py — Route Map

### Core / Shell
| Route | Function | Notes |
|---|---|---|
| `GET /` | `index()` | Renders `index.html` |
| `GET /api/parent-properties` | `api_parent_properties()` | Loads subject property dropdown |
| `GET /api/weeks` | `api_weeks()` | AY weeks for the selected parent |

### Markets Tab
| Route | Function |
|---|---|
| `GET /api/markets` | `api_markets()` |
| `GET /api/markets/all` | `api_markets_all()` |
| `POST /api/markets/update` | `api_markets_update()` |
| `POST /api/markets/create` | `api_markets_create()` |
| `POST /api/markets/delete` | `api_markets_delete()` |

### Comps Tab
| Route | Function |
|---|---|
| `GET /api/comp-properties` | `api_comp_properties()` — left nav list + FP comp search |
| `POST /api/comp-properties/update` | `api_comp_properties_update()` |
| `GET /api/comp-properties/detail` | `api_comp_properties_detail()` — slide-out data |
| `POST /api/comp-properties/create` | `api_comp_properties_create()` |
| `GET /api/comp-assignments` | `api_comp_assignments()` |
| `GET /api/comp-fact` | `api_comp_fact()` |
| `POST /api/comp-fact/update` | `api_comp_fact_update()` |
| `GET /api/floorplan-fact` | `api_floorplan_fact()` |
| `POST /api/floorplan-fact/update` | `api_floorplan_fact_update()` |

### Schools Tab
| Route | Function |
|---|---|
| `GET /api/schools` | `api_schools()` |
| `POST /api/schools/update` | `api_schools_update()` |
| `POST /api/schools/create` | `api_schools_create()` |

### Floor Plans Tab
| Route | Function | Notes |
|---|---|---|
| `GET /api/floorplans` | `api_floorplans()` | `?property_key=&show_inactive=0/1` — reads `FLOORPLAN_WORKSPACE` |
| `POST /api/floorplans/update` | `api_floorplans_update()` | Field whitelist: `_FP_ALLOWED_FIELDS`. Sets `MODIFIED_BY`, `DATE_MODIFIED` |
| `POST /api/floorplans/create` | `api_floorplans_create()` | Computes `MAX(FLOORPLAN_ASSIGNMENT_KEY)+1` |
| `POST /api/floorplans/activate` | `api_floorplans_activate()` | Toggles `FLAG_ACTIVE` |

### Assign Comps Tab
| Route | Function | Notes |
|---|---|---|
| `GET /api/assign-comps` | `api_assign_comps()` | Reads `MktSrv_CompMap`; JOIN uses `LEGACY_MARKETPROPERTYID = m.compID OR (LEGACY_MARKETPROPERTYID IS NULL AND PROPERTY_KEY = m.compID)` |
| `POST /api/assign-comps/add` | `api_assign_comps_add()` | Resolves `LEGACY_MARKETPROPERTYID` from `PROPERTY_KEY`; duplicate guard; `MAX(marketCompMapID)+1` |
| `POST /api/assign-comps/remove` | `api_assign_comps_remove()` | Soft-delete: sets `endCompDate = yesterday` |
| `POST /api/assign-comps/reorder` | `api_assign_comps_reorder()` | Bulk `orderID` update |

### Private Helpers
| Function | Location | Purpose |
|---|---|---|
| `_get_subject_id(conn, parent_key)` | `app.py` line ~595 | Resolves legacy `subjectID` from `COMP_ASSIGNMENTS` for a given `PROPERTY_KEY` |

---

## Frontend: app.js — Function Map

All code lives in one IIFE. Sections are marked with `// ──` banners.

### Core / Init (lines 1–180)
| Function | Purpose |
|---|---|
| `init()` | Entry point — calls `loadParentProperties()`, `loadWeeks()`, `setupTabs()`, etc. |
| `setupTabs()` | Wires tab click → panel switch; on `floorplans` tab switch calls `loadFloorplans()` |
| `setupTheme()` | Dark/medium/light theme toggle via `data-theme` |
| `setupCollapse()` | Info blurb collapse toggles |
| `checkReadonly()` | Disables all inputs if URL has `?readonly=1` |
| `loadParentProperties()` | Fetches `/api/parent-properties`, populates parent dropdown |
| `loadWeeks()` | Fetches `/api/weeks`, populates week dropdown |
| `onParentChange()` | Fires when subject property changes; reloads comps + active tab data; if FP tab active calls `loadFloorplans()` |
| `onWeekChange()` | Fires on week select change |
| `onAYChange()` | Fires on AY year change |

### Comp List / State (lines 141–282)
| Function | Purpose |
|---|---|
| `loadComps()` | Fetches `/api/comp-assignments` → populates left nav comp list |
| `selectComp(el)` | Activates a comp in left nav; loads `loadCompFact()`, `loadFloorplanFact()`; if FP tab active calls `loadFloorplans(key, name, true)` |
| `getParentMarketKey()` | Returns current `PARENT_MARKET_KEY` from dropdown |
| `loadCompFact()` | Fetches `/api/comp-fact` → populates Comps tab data entry fields |
| `loadFloorplanFact()` | Fetches `/api/floorplan-fact` → populates Comps tab floorplan rows |
| `trackModified(compKey, fieldId)` | Tracks which fields have been edited per comp (in-memory) |
| `reapplyModified(compKey)` | Re-highlights modified fields when switching comps |

### Schools Tab (lines 362–494)
| Function | Purpose |
|---|---|
| `loadSchools()` | Fetches `/api/schools` |
| `renderSchools(data)` | Renders school rows; wires auto-save on blur |
| `addSchool()` | POSTs to `/api/schools/create` |

### Markets Tab (lines 496–610)
| Function | Purpose |
|---|---|
| `loadMarkets()` | Fetches `/api/markets` |
| `renderMarkets(data)` | Renders market rows; wires auto-save on blur |
| `addMarket()` | POSTs to `/api/markets/create` |

### Comps Tab (lines 612–1022)
| Function | Purpose |
|---|---|
| `loadCompProperties()` | Fetches `/api/comp-properties` |
| `renderCompProperties(data)` | Renders comp property rows; row click → `openCompDetail()` |
| `addCompProperty()` | POSTs to `/api/comp-properties/create` |
| `openCompDetail(pk)` | Opens comp detail slide-out, fetches `/api/comp-properties/detail` |
| `closeCompDetail()` | Hides slide-out |
| `renderCompDetail()` | Renders all fields in slide-out; wires auto-save |
| `renderDetailRow(field, value, compact)` | Helper — renders a single field row in the slide-out |
| `openCompSettings()` | Opens gear/settings modal (column show/hide) |
| `closeCompSettings()` / `renderCompSettings()` | Modal management |
| `saveFieldSettings()` | Persists column visibility to `localStorage` key `mrb_comp_fields` |

### Assign Comps Tab (lines 1023–1196)
| Function | Purpose |
|---|---|
| `loadAssignComps()` | Fetches `/api/assign-comps`; populates assigned list + available search panel |
| `renderAssignAvailable()` | Renders left panel: available comps to add; wires add button |
| `renderAssignComps()` | Renders right panel: assigned comps with drag-to-reorder and remove |
| `debounce(fn, ms)` | Utility used by assign-comps search input |

### Floor Plans Tab (lines 1198–end)
| Function | Purpose |
|---|---|
| `loadFloorplans(overrideCompKey, overrideCompName, keepSearch)` | Main loader. `keepSearch=true` = don't overwrite search input (use for left-nav clicks, activate/create reloads). Fetches `/api/floorplans` |
| `ensureFpAllComps()` | Lazy-loads all active comp properties into `fpAllComps` (for search dropdown) |
| `renderFpCompDropdown(q)` | Filters `fpAllComps` by query, renders dropdown; mousedown → `loadFloorplans(key, name)` |
| `fixFpNameColumnWidth()` | After render: measures widest `.fp-cell-name`, applies uniform px width to all rows and header |
| `renderFpGrid()` | Renders header + rows; row click → `openFpDetail(key)` |
| `positionFpOverlay()` | Calculates overlay width = `window.innerWidth - fpGrid.getBoundingClientRect().right - 100` |
| `openFpDetail(key)` | Adds `.open` to overlay, calls `positionFpOverlay()` + `renderFpDetail()` |
| `closeFpDetail()` | Removes `.open`, clears `fpSelectedKey` |
| `renderFpDetail(fp)` | Renders 6 collapsible sections (Identity, Counts, Flags, Financials, Unit Premiums, Notes); wires auto-save on blur/change; wires Activate/Deactivate button |
| `fpSection(title, bodyHtml)` | Helper — returns HTML for a collapsible section |

### Key State Variables
```js
selectedCompKey    // PROPERTY_KEY of active left-nav comp
selectedCompLegacyId // legacy ID of active comp (from COMP_ASSIGNMENTS)
compList           // DOM element: left nav comp list container
fpData             // current Floor Plans data array
fpSelectedKey      // FLOORPLAN_ASSIGNMENT_KEY of open slide-out row
fpCompKey          // PROPERTY_KEY of the comp being viewed in Floor Plans
fpCompName         // display name of the comp being viewed
fpAllComps         // full list of active comp properties (lazy-loaded for FP search)
```

---

## index.html Notes

- All tab panels: `<div class="tab-panel" id="panel-{tabname}">`
- Floor Plans HTML includes: toolbar with `#fpCompSearch` + `#fpCompDropdown` + `#fpTitle` (active property label), `#fpGrid`, and the `#fpDetailOverlay` slide-out with `#fpDetailBody`, `#fpDetailCompName`, `#fpDetailName`, `#fpActivateBtn`, `#fpModifiedBy`
- Cache bust versions: CSS `?v=6`, JS `?v=11` (increment on every edit)

---

## style.css Notes

- All Floor Plans styles are in a dedicated `/* ── Floor Plans ── */` section at the bottom
- Key classes: `.fp-toolbar`, `.fp-grid`, `.fp-grid-header`, `.fp-row`, `.fp-cell-name`, `.fp-detail-overlay`, `.fp-detail-overlay.open`, `.fp-section-header`, `.fp-field-row`, `.fp-badge`
- `.fp-grid` has `width: fit-content; min-width: 100%` — required so `positionFpOverlay()` gets the real table right-edge
- Grid column template: `minmax(180px, max-content) 90px 120px 65px 65px 85px 80px` (JS overrides with exact px after render via `fixFpNameColumnWidth()`)
- Base font sizes: grid header `1.08rem`, grid rows `1.32rem`, slide-out labels/inputs `1.32rem`

---

## Current Status (July 2026)

### Completed Tabs
- ✅ **Data Entry** — subject property fields, auto-save
- ✅ **Schools** — add/edit/delete, auto-save
- ✅ **Markets** — add/edit/delete, auto-save
- ✅ **Comps** — comp property list, comp fact data entry, floorplan fact rows, detail slide-out with gear column selector
- ✅ **Assign Comps** — add, remove (soft-delete), drag-to-reorder; legacy ID mapping fully resolved
- ✅ **Floor Plans** — grid, detail slide-out, create, activate/deactivate, comp search dropdown, dynamic overlay width, uniform column widths

### Known Issues / Deferred Work
- Floor Plans comp search toolbar (search box + title label) is currently in the Floor Plans tab header. The redesign mockup (`mockup_redesign.html`) proposes moving this to a permanent left panel.
- Two "2 Bed Standard" records exist in `FLOORPLAN_WORKSPACE` for 48 West — real data issue, not an app bug. Consider adding a deduplication/delete function.
- No delete function for floor plans yet (only deactivate).

### Next Major Work
- **AppHub integration**: Register Market Benchmark as a Flask blueprint inside the main AppHub 4.0 shell. Change type in `modules.py` from `"powerapps"` to `"flask"`.
- **UX redesign**: Implement the left-panel-always-visible comp selector from `mockup_redesign.html`. See the design notes in that file for the full breakdown.

---

## Redesign Mockup

`mockup_redesign.html` — open with:
```powershell
Start-Process chrome "`"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\APPHUB_4\Market Benchmark\mockup_redesign.html`""
```

Key proposals documented in it:
1. Left comp panel always visible (no per-tab toolbar search)
2. Subject property shown in module header pill
3. Floor Plans + Comps use AppHub standard `data-table` pattern
4. Slide-out follows PDM exactly (resize handle, collapsible sections, pinned footer)
5. Assign Comps as PDM-style drag list with grip handles
6. Markets tab gets KPI summary cards above the table
