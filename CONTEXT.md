# AppHub 4.0 — Copilot Context Map
**Last Updated:** July 2026  
**App URL (dev):** `http://localhost:5000` — start via `py -u run_dev.py`  
**Python command:** always `py` (not `python`)  
**DB connections:** always `SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)` — never tunnel/mirror

---

## Architecture Overview

Flask 3.x app using blueprint-per-module pattern. Each module has a `.py` backend, a `.html` Jinja2 template, and shares a common `shell.html` base layout.

```
app.py           → Flask app factory, blueprint registration, usage logging hook
run_dev.py       → Dev server entry point (sets DEV_BYPASS=true)
config.py        → App config (Azure AD creds, secret key, version)
auth.py          → Entra ID (Azure AD) auth, login_required decorator, DEV_BYPASS mode
routes.py        → Main blueprint: dashboard, module routing, impersonation, theme-settings API
security.py      → Access resolution: MODULE_AUDIENCE + EMPLOYEE_F → user module list
modules.py       → MODULES list + APP_ID_MAP (int DB id ↔ string module id)
usage_log.py     → Fire-and-forget daemon thread usage writer → dbo.APPHUB_USAGE_LOG
```

---

## Shell / UI Infrastructure

| File | Purpose |
|------|---------|
| `templates/shell.html` | Base template — nav, theme toggle, Theme Studio, collapsible nav, impersonation bar |
| `static/css/apphub.css` | All styles. **Current version: v=29** (bump on every CSS change) |
| `static/css/fontawesome.min.css` | Icons |

### Theme System
- Three themes: **dark** (default), **medium**, **light** — set via `data-theme` on `<html>`
- CSS custom properties per theme block in `apphub.css`
- Key vars: `--nav-bg`, `--content-bg`, `--content-header`, `--card-bg`, `--surface-raised`, `--section-hd-bg`, `--section-hd-border`, `--text-primary`, `--text-secondary`, `--accent-cyan`, `--accent-blue`, `--accent-gold`
- `--section-hd-bg / --section-hd-border` control dark section header bars (used by RFS2 topbar, left panel, section headers, comps/stakeholder headers)
- Theme overrides stored in `localStorage` key `apphub_theme_overrides` (dev preview only)
- Published overrides stored server-side in `dbo.APPHUB_THEME_SETTINGS` (per app_id, per theme) — apply to all users

### Theme Studio (developer-only floating panel)
- Launch button at nav footer bottom — only visible when `is_developer=True`
- **Preview** button → saves current tab's colors to localStorage, applies to this browser only
- **Publish** button → POSTs to `POST /api/theme-settings` → writes to DB, applies to all users
- **Reset** button → clears localStorage + publishes empty overrides to server (restores CSS defaults)
- Color groups: Navigation, Content, Section Headers & Panels, Text, Accents
- JS in `shell.html` inside `{% if is_developer %}` block (~line 336–532)

### Collapsible Nav
- 260px expanded / 64px collapsed, persists in `localStorage` key `apphub_nav_collapsed`
- Toggle button: `#navToggleBtn`, icon: `#navToggleIcon`
- CSS classes: `.nav-collapsed` on `.apphub-nav`

---

## Modules — Backend + Template Map

### AppHub Maintenance (`/maintenance/`)
- **Backend:** `maintenance.py` — `maintenance_bp`
- **Template:** `templates/maintenance.html`
- **Tabs:** Module Registry, Audience Manager, User Lookup, Usage Log
- **Key APIs:**
  - `GET /maintenance/api/modules` — module list from DB
  - `PATCH /maintenance/api/modules/<app_id>` — toggle enabled/disabled
  - `GET/POST/PATCH/DELETE /maintenance/api/audience/<module_id>` — audience grants
  - `GET /maintenance/api/user-search` — employee search for audience grants
  - `GET /maintenance/api/usage-log` — analytics: rows, summary, daily, top_users (filters: days, module, email)
- **Usage Log UI** (in `maintenance.html`): CS App-style analytics layout — 4 KPI cards, daily activity bar chart, hits-by-module bars, top users table, recent requests. Dynamic user filter dropdown (`#ulUser`). Module display names via JS `MODULE_NAMES` map + `modName()` helper.
- **DB tables:** `dbo.APP_LIST`, `dbo.MODULE_AUDIENCE`, `dbo.APPHUB_USAGE_LOG`
- **Admin guard:** `_require_admin()` checks `is_developer` session flag

### Rent Forecasting 2.0 (`/rfs2/`)
- **Backend:** `rent_forecast2.py` — `rfs2_bp`, `_APP_ID = 35`
- **Template:** `templates/rent_forecast2.html` — self-contained CSS/JS (no shell.html inheritance — full-page app)
- **Uses global theme vars:** `--section-hd-bg`, `--section-hd-border` (wired in July 2026, previously `--lpanel-bg/border`)
- **Key APIs:**
  - `GET /rfs2/api/properties` — property list for AY
  - `GET /rfs2/api/floorplans` — floorplans for property
  - `GET /rfs2/api/forecasts` — RFC plan list for property
  - `GET /rfs2/api/budget-tiers` — budgeted tiers by floorplan
  - `GET /rfs2/api/actuals` — actuals YTD by floorplan
  - `GET /rfs2/api/forecast-tiers` — RFC editable tiers
  - `POST /rfs2/api/forecast-tiers/save` — save tier row edits
  - `POST /rfs2/api/forecast-tiers/add` — add new tier
  - `POST /rfs2/api/forecast-tiers/delete` — delete tier
  - `GET /rfs2/api/comps` — market comps data
  - `POST /rfs2/api/comps/toggle` — include/exclude a comp
  - `GET /rfs2/api/left-to-budget` — left-to-budget KPI
  - `GET /rfs2/api/property-summary` — prelease/rate/NER summary
  - `GET /rfs2/api/rate-trends` — weekly rate trend data
  - `GET /rfs2/api/leasing-trend` — cumulative leasing trend
  - `GET /rfs2/api/fp-inducements` — floorplan inducements
  - `POST /rfs2/api/forecasts/approve` — approve RFC plan
  - `POST /rfs2/api/forecasts/create` — create new RFC plan
  - `POST /rfs2/api/forecasts/clone` — clone existing plan
- **DB:** `DB_APP_SUPPORT` (direct), tables prefixed `RFS2_*` and `GEOCENTRAL_*`
- **UI sections:** Topbar (property/AY/plan selectors), Left Panel (property summary + floor plans), Renewals & New Leases (collapsible, `.coll-sec-hdr`), Market Comps & Stakeholder Summary (collapsible)
- **Current AY:** `_CURRENT_AY = 2026`

### Rent Forecasting System v1 (`/rfs/`)
- **Backend:** `rent_forecast.py` — `rfs_bp`
- **Template:** `templates/rent_forecast.html`
- Older version — maintained but RFS2 is the active development target

### Employee Data Manager (`/edm/`)
- **Backend:** `edm.py` — `edm_bp`
- **Template:** `templates/edm.html`
- **Tabs:** Employees, Title Assignments, Entrata Mapping, Soft Terminations
- **Key APIs:**
  - `GET /edm/api/employees/search` — employee search (WH_STAGING, EMPLOYEE_F)
  - `GET /edm/api/employees/filter-options` — dropdown options (departments, title groups, etc.)
  - `GET/POST/PATCH/DELETE /edm/api/title-assignments` — `dbo.EMP_TITLE_GROUP_MGMT`
  - `GET/POST/PATCH/DELETE /edm/api/entrata-mapping` — `dbo.EMP_ENTRATA_TITLE_GROUP_MAPPING`
  - `GET/POST /edm/api/soft-terminations` — `dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES`
- **DB tables:** `DB_APP_SUPPORT` for writes (direct=True); `WH_STAGING` for employee reads
- **Validation warnings:** orange `.validation-warnings` box — checks for title groups missing Entrata mapping. Orange styling has mid/light theme overrides at bottom of `edm.html` `<style>` block.
- **Schema fix (July 2026):** Tables moved from `sync_tables.*` → `dbo.*`; `OVERRIDES_STG` → `OVERRIDES`

### Property Data Manager (`/pdm/`)
- **Backend:** `pdm.py` — `pdm_bp`
- **Template:** `templates/pdm.html`
- **Key APIs:**
  - `GET /pdm/api/properties/search` — property search with filters
  - `GET /pdm/api/properties/filter-options` — markets, groups, property managers
  - `PATCH /pdm/api/properties/<key>` — update property fields
  - `GET/POST/PATCH /pdm/api/property-groups` — manage property groups
  - `GET/POST/PATCH /pdm/api/markets` — manage markets
  - `GET /pdm/api/employees` — employee list for PM assignment
  - `GET/POST /pdm/api/overrides/<key>` — field-level override management
  - `POST /pdm/api/properties/create` — create new property

### Other Flask Modules
| Module | Backend | Template | Route |
|--------|---------|----------|-------|
| Cultivate Nomination | `cultivate.py` | `cultivate.html` | `/cultivate/` |
| FastTrack Recommendation | `fasttrack.py` | `fasttrack.html` | `/fasttrack/` |
| Mentor Certification | `mentor_cert.py` | `mentor_cert.html` | `/mentor-cert/` |
| Mindset Award Nomination | `mindset.py` | `mindset.html` | `/mindset/` |
| New Hire Alert | `new_hire.py` | `new_hire.html` | `/new-hire/` |
| Peak Link (Ideas) | `peak_link.py` | `peak_link.html` | `/peak-link/` |

### PowerApps Modules (launch page only — no Flask template)
Canada Market Survey, Market Benchmark, Milestones, Promotion/Transfer Alert, Rush Check Request, SAM Ad Spend Planning, SAM Contract Manager, Special Handling Form, Support Data Manager, The Pitch Workflow, Vendor Setup Form, ACH Request, Prepaid Visa Compliance, RM Inspections

---

## Authentication & Access Control

- **Auth flow:** `auth.py` — Microsoft Entra ID (Azure AD) via MSAL, `/auth/login` → `/auth/callback`
- **DEV_BYPASS:** `os.environ["DEV_BYPASS"] = "true"` skips auth in `run_dev.py`; auto-sets `is_developer=True`
- **Session keys:** `user` (dict: email, name), `user_modules` (list of {id, name, access}), `is_developer`, `is_dev_mode`, `is_impersonating`, `impersonating_user`
- **Access resolution** (`security.py`): reads `dbo.MODULE_AUDIENCE` (grants by email, title_group, prefix `*`) + `WH_STAGING.dbo.EMPLOYEE_F` → returns allowed module list
- **Impersonation** (developer-only, dev mode required): `POST /api/impersonate` + `POST /api/stop-impersonation` — swaps user session to another employee's access profile

---

## Database Connections

| Name | Type | Used For |
|------|------|---------|
| `DB_APP_SUPPORT` | SQL Server (direct) | Writes: usage log, EDM, PDM, RFS2 data, theme settings, audience |
| `WH_STAGING` | SQL Server (tunnel) | Reads only: employee data (EMPLOYEE_F), property data |
| Azure Key Vault / Managed Identity | Production only | Fabric connections via `fabric_db.py` |

**Connection pattern:**
```python
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
rows = conn.fetchall("SELECT ...", (param,))
conn.execute("INSERT ...", (param,))
```

**Critical:** Never use `WH_STAGING` for writes. Never use `direct=False` for `DB_APP_SUPPORT`.

---

## Key DB Tables (DB_APP_SUPPORT)

| Table | Used By |
|-------|---------|
| `dbo.APP_LIST` | Module registry — app IDs, names, enabled flag |
| `dbo.MODULE_AUDIENCE` | Access grants per module (email/title_group/prefix/baseline) |
| `dbo.APPHUB_USAGE_LOG` | Page hit logging (email, module_id, route, timestamp) |
| `dbo.APPHUB_THEME_SETTINGS` | Published theme overrides per app_id per theme (created on first Publish) |
| `dbo.EMP_TITLE_GROUP_MGMT` | Title → Title Group + Type assignments (EDM tab) |
| `dbo.EMP_ENTRATA_TITLE_GROUP_MAPPING` | Title Group → Entrata permission group (EDM tab) |
| `dbo.EMPLOYEE_SOFT_TERMINATION_OVERRIDES` | Soft termination flag overrides (EDM tab) |
| `RFS2_*` tables | Rent Forecasting 2.0 data (plans, tiers, inducements) |

---

## Routes Reference (Global)

| Endpoint | File | Description |
|----------|------|-------------|
| `GET /api/theme-settings/<app_id>` | `routes.py` | Fetch published theme overrides for an app |
| `POST /api/theme-settings` | `routes.py` | Save/publish theme overrides (developer only) |
| `POST /api/toggle-dev-mode` | `routes.py` | Toggle dev mode (developer only) |
| `POST /api/impersonate` | `routes.py` | Start impersonation session |
| `POST /api/stop-impersonation` | `routes.py` | End impersonation session |
| `GET /api/employees` | `routes.py` | Employee list for impersonation picker |

---

## Developer Workflow Notes

- **Run server:** `py -u run_dev.py` from `APPHUB_4/` directory
- **Bump CSS version:** Update `?v=XX` in `shell.html` `<link>` tag on every `apphub.css` change
- **Template edits:** Flask auto-reloads templates (no restart needed)
- **Python file edits:** Flask debug mode auto-restarts on save
- **Theme Studio:** Only visible when logged in as developer. Preview = localStorage (this browser). Publish = DB (all users).
- **Per-app theme identity:** `active_module` string (e.g., `rent_forecasting_2`, `edm`, `pdm`) is baked into Theme Studio JS as `APP_ID` — so each app can have independent published colors per theme.

---

## Active Development Status (July 2026)

### Completed This Month
- **RFS2:** Full rebuild of Rent Forecasting 2.0 (new template, all APIs, collapsible sections)
- **AppHub nav:** Collapsible left nav (64px/260px, localStorage persistence)
- **Theme system:** Full Dark/Mid/Light CSS var system; Theme Studio dev panel with Preview/Publish/Reset
- **Theme Studio:** Extended with Section Headers & Panels group (`--section-hd-bg/border`); Publish to DB (per-app, per-theme, all users); server-side `APPHUB_THEME_SETTINGS` table auto-created
- **Maintenance Usage Log:** Rebuilt with CS App-style analytics (KPI cards, bar charts, top users, recent requests); dynamic user filter; favicon excluded; module display names
- **EDM:** Fixed broken tabs after DB schema migration (`sync_tables.*` → `dbo.*`); orange styling contrast for mid/light themes
- **RFS2 theme:** `--lpanel-bg/border` replaced by global `--section-hd-*` vars so Theme Studio controls section headers

### Known Limitations / Next Items
- RFS v1 (`/rfs/`) is older generation — no active dev planned unless bugs reported
- PowerApps modules show a "launch in Power Apps" placeholder page — not rebuilt natively yet
- Theme Studio tooltip behavior in Chrome: `data-tooltip` shows native browser tooltip under cursor (deprioritized)
