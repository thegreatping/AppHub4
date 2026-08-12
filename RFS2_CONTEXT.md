# Rent Forecasting 2.0 — Project Context Map

> **Last updated:** July 31, 2026
> **Purpose:** Living reference for Copilot. Updated at the end of each month.
> At the start of a new session, read this file first to orient on architecture, locations, and current state.

---

## Application Overview

**Rent Forecasting 2.0 (RFS 2.0)** is a Flask blueprint (`rfs2_bp`) registered in the Peak AppHub 4.0 framework.
It allows leasing teams to select a property + floorplan + reforecast plan and view/edit tier-based rate forecasts,
model planned concessions (Plan Use), and view market comps and leasing trend charts — all on a single screen.

- **URL prefix:** `/rfs2/`
- **Dev server:** `py run_dev.py` from `APPHUB_4/` → `localhost:5000`
- **Auth bypass in dev:** `$env:DEV_BYPASS="true"` before starting

---

## File Locations

| File | Purpose |
|---|---|
| `APPHUB_4/rent_forecast2.py` | Flask blueprint — all API endpoints |
| `APPHUB_4/templates/rent_forecast2.html` | Single-page HTML — all CSS, HTML layout, and JS in one file |
| `APPHUB_4/RFS2_CONTEXT.md` | This file |

---

## Backend — `rent_forecast2.py`

### Blueprint & Setup
- `rfs2_bp = Blueprint('rfs2', ...)` — registered in `app.py`
- `_require_access()` — checks MODULE_AUDIENCE for user permissions
- `_get_env()` / `SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)` — always use `direct=True`
- `_user_email()`, `_today_int()` — audit helpers

### API Endpoints (all prefixed `/rfs2/api/`)

| Endpoint | Method | What it does |
|---|---|---|
| `/properties` | GET | Property list with bed counts |
| `/forecasts` | GET | All reforecast plans for a property (all AYs) |
| `/forecasts/create` | POST | Create a new reforecast plan |
| `/forecasts/clone` | POST | Clone plan + copies FP inducement rows to new plan |
| `/forecasts/approve` | POST | Toggle approved/pending flag |
| `/forecasts/planned-use` | POST | Save property-level Plan Use (annual $) |
| `/forecasts/archive` | POST | Archive a plan |
| `/forecasts/revive` | POST | Un-archive a plan |
| `/floorplans` | GET | Floorplans for a property with bed counts |
| `/budget-tiers` | GET | Budget tier rows (read-only) by FP + AY + lease type |
| `/actuals` | GET | YTD actual lease data by FP + AY + lease type |
| `/forecast-tiers` | GET | Editable forecast tier rows |
| `/forecast-tiers/save` | POST | Save edited tier values |
| `/forecast-tiers/add` | POST | Add a new tier row |
| `/forecast-tiers/delete` | POST | Delete a tier row |
| `/property-summary` | GET | KPI rollup: prelease %, avg rate, NER (budget/actual/fcst), total beds, forecast_ner |
| `/left-to-budget` | GET | Left-to-budget row for a floorplan |
| `/comps` | GET | Market comps list |
| `/comps/toggle` | POST | Include/exclude a comp |
| `/rate-trends` | GET | Rate trend data for SVG chart |
| `/leasing-trend` | GET | Leasing trend data for SVG chart |
| `/fp-inducement` | GET | Single FP Plan Use value (forecast_key + floorplan_key) |
| `/fp-inducement` | POST | Upsert single FP Plan Use value to DB |
| `/fp-inducements` | GET | Bulk-load ALL FP Plan Use values for a forecast |

### Key Database Tables (all in `dbo.*`, DB_APP_SUPPORT)

| Table | Purpose |
|---|---|
| `FORECAST_PLAN` | Reforecast plan metadata (name, AY, approved flag, prop-level planned use) |
| `FORECAST_TIERS` | Editable tier rows per plan + FP + lease type |
| `FORECAST_FP_INDUCEMENT` | Per-FP planned concession values — keyed on `(FORECAST_KEY, FLOORPLAN_KEY)` |
| `FORECAST_COMP_ASSIGNMENTS` | Which market comps are included per forecast |

---

## Frontend — `rent_forecast2.html`

All CSS, HTML, and JavaScript live in this single file. No external JS libraries.

### Key State Variables (JS globals)

| Variable | Holds |
|---|---|
| `_prop` | Selected PROPERTY_KEY |
| `_propName` | Selected property display name |
| `_fp` | Selected FLOORPLAN_KEY |
| `_fpName`, `_fpCode`, `_compType` | Floorplan display metadata |
| `_fk` | Selected FORECAST_KEY (reforecast plan) |
| `_ay` | Selected academic year |
| `_plans` | Array of plan objects for current property |
| `_propData` | Array of all properties (loaded once) |
| `_fpData` | Array of floorplans for current property |
| `_summ` | Current property-summary API response |
| `_propPu` | Property-level Plan Use (annual $) |
| `_fpPu` | Current FP's Plan Use (annual $) |
| `_fpPuCache` | `{ floorplan_key: annual_val }` — persists across FP switches |
| `_tierState` | `'default'` or `'expanded'` — tier table toggle state |

### JS Function Map

#### Utilities & Infrastructure
| Function | Line | What it does |
|---|---|---|
| `_$()` | ~772 | `document.getElementById` shorthand |
| `_esc()` | 774 | HTML-escape for rendering |
| `_fc()` | ~776 | Currency formatter |
| `_get(url)` | 778 | Fetch GET with error logging |
| `_post(url, body)` | 785 | Fetch POST with JSON body |
| `flash()` | 794 | Brief save-confirmation flash on page header |

#### Layout & UI Controls
| Function | Line | What it does |
|---|---|---|
| `toggleCollSec(hdr)` | 807 | Expand/collapse any `.coll-sec` section |
| `cycleTierExpand()` | 818 | Toggle tier table between default/expanded height |
| `_applyTierState()` | 822 | Apply current `_tierState` to all `.tier-scroll` elements |
| `resetTierToDefault()` | 833 | Reset tier expand state; called on property change |
| `toggleChartFocus()` | 1480 | Toggle 67vh focus overlay on chart panel |
| `switchStkhTab(tab)` | 1493 | Switch between Summary / Leasing Trend / Rate Trends tabs |

#### Property Dropdown
| Function | Line | What it does |
|---|---|---|
| `loadProperties()` | 921 | Fetch all properties, build custom dropdown + hidden `<select>` |
| `togglePropMenu()` | 918 | Open/close property dropdown |
| `selectPropFromMenu(key)` | 945 | Select property → clears state, loads forecasts + FPs + inducements |
| `onPropChange()` | 961 | Legacy handler for hidden `<select>` |

#### Plan (Reforecast) Dropdown
| Function | Line | What it does |
|---|---|---|
| `loadForecasts()` | 981 | Fetch plans for current property; auto-selects best plan; bulk-loads FP inducements |
| `renderPlanMenu()` | 854 | Rebuild plan dropdown HTML (grouped by AY, with archived section) |
| `updatePlanLabel()` | 887 | Update plan trigger label + approved/pending button |
| `selectPlan(key)` | 897 | Switch to a different plan → clears FP cache, reloads inducements |
| `archivePlan(key)` | 905 | Archive a plan |
| `revivePlan(key)` | 911 | Un-archive a plan |
| `clonePlan()` | 1426 | Clone current plan (prompts for name) |
| `newPlan()` | 1434 | Create new blank plan |
| `toggleApproved()` | 1416 | Toggle approved/pending on current plan |

#### Floorplan Dropdown
| Function | Line | What it does |
|---|---|---|
| `loadFloorplans()` | 1005 | Fetch FPs, build custom dropdown + hidden `<select>` |
| `toggleFpMenu()` | 1054 | Open/close FP dropdown |
| `selectFpFromMenu(key)` | 1055 | Select FP from custom menu |
| `onFpSelChange()` | 1066 | Legacy handler for hidden `<select>` |
| `selectFloorplan(key, name, code, ct)` | 1074 | Core FP selection: updates state, loads FP inducement from cache, loads tier data |

#### Tier Data (Renewals & New Leases)
| Function | Line | What it does |
|---|---|---|
| `loadTierData()` | 1094 | Orchestrates loading budget + actuals + forecast tiers + summary + LTB + charts |
| `renderBudget(side, rows)` | 1123 | Render budget column for R or N side |
| `renderActuals(side, data)` | 1143 | Render actuals column |
| `renderForecast(side, rows)` | 1169 | Render editable forecast column |
| `saveTier(tk, lt)` | 1197 | Save edited tier row on blur |
| `addTier(lt)` | 1210 | Add a new tier row |
| `delTier(tk, lt)` | 1225 | Delete a tier row |

#### KPIs / Summary
| Function | Line | What it does |
|---|---|---|
| `renderSummary(s)` | 1237 | Populate all KPI cells (prelease, avg rate, NER columns) |
| `renderLtb(ltb)` | 1284 | Render left-to-budget row |
| `resetKpis()` | 1291 | Clear all KPI cells to `—` (called on property change) |

#### Plan Use / Concession Modeling
| Function | Line | What it does |
|---|---|---|
| `loadAllFpInducements()` | 1312 | Bulk-load all FP Plan Use values for current forecast into `_fpPuCache` |
| `loadFpInducement()` | 1321 | Load current FP's value from cache (or DB fallback); calls `_applyFpPuInput()` |
| `_applyFpPuInput()` | 1334 | Set FP Plan Use input value from `_fpPu`; triggers `_recalcAll()` |
| `calcFpPu(rawVal)` | 1341 | oninput handler — updates `_fpPu`, `_fpPuCache`, debounced save to DB |
| `calcPropPu(rawVal)` | 1356 | oninput handler — updates `_propPu`, triggers `_recalcAll()` |
| `_recalcAll()` | 1362 | Master recalc: computes FP NER w/plan and Property NER w/plan |
| `savePlannedUse(val)` | 1407 | Save property-level Plan Use to DB (from hidden `plannedInp` blur) |

**`_recalcAll()` math summary:**
- **FP NER w/plan:** `(FP actuals NER-ext + FP fcst NER-ext − (fpPu/12 × fcst_count)) / fp_total_leases`
- **Prop NER w/plan:** `forecast_ner − (sum of ALL _fpPuCache values / 12) − (propPu / 12)`
- Property NER w/plan only changes when a Plan Use value is edited — not when switching FPs.

#### Market Comps
| Function | Line | What it does |
|---|---|---|
| `renderComps(rows)` | 1443 | Render market comps table rows |
| `toggleComp(fak)` | 1473 | Include/exclude a comp; saves to DB |

#### Charts
| Function | Line | What it does |
|---|---|---|
| `loadRateTrends()` | 1529 | Fetch rate trend data |
| `drawRateChart(data)` | 1534 | Draw Rate Trends SVG (`#rateSvg`, viewBox 580×189) |
| `loadLeasingTrend()` | 1618 | Fetch leasing trend data |
| `drawTrendChart(data)` | 1623 | Draw Leasing Trend SVG (`#trendSvg`, viewBox 560×180) |
| `setRateType(t)` | 1516 | Toggle rate chart between NER / Avg Rate / Budget |
| `buildAndCopyStkMsg()` | 1500 | Build stakeholder message text and copy to clipboard |

---

## HTML Layout Structure (rent_forecast2.html)

```
.rfs2
  .topbar                        ← page title + Export PDF button
  .rfs2-body
    .lpanel (hidden)             ← legacy compat spans (lpNerAdjRow, lpIndTotal, etc.)
    .mcontent
      .pfhdr                     ← dual-row sticky header
        .pfhdr-row (Property)
          #propWrap              ← custom property dropdown
          #propSel (hidden)      ← legacy <select>
          #apprBtn               ← Pending / Approved toggle
          #planWrap              ← custom plan dropdown
          #aySel                 ← AY selector
        #propMetrics             ← KPI blocks: Prelease / Avg Rate / NER (Budget/Actual/Fcst/W-Plan) + Prop Plan Use input
        .pfhdr-row (Floorplan)
          #fpWrap                ← custom FP dropdown (with bed count)
          #fpSel (hidden)        ← legacy <select>
        #fpMetrics               ← KPI blocks: same layout + FP Plan Use input + Left to Budget
      .scroll                    ← flex column, fills remaining height
        #tierSec .coll-sec       ← Renewals & New Leases (collapsible)
          .tier-row
            .tier-inner (R)      ← Budget / Actuals / Renewal Reforecast (editable)
            .tier-divider
            .tier-inner (N)      ← Budget / Actuals / New Lease Reforecast (editable)
        .coll-sec.coll-sec-bottom ← Market Comps + Charts (collapsible)
          .bottom-row (flex-row)
            .comps-sec           ← Market comps table (scroll max-height 320px)
            .stkh-sec#stkhSec   ← Chart panel (tabs: Summary / Leasing Trend / Rate Trends)
              #focusBtn          ← Focus mode toggle
              #viewTrend         ← Leasing Trend SVG
              #viewRate          ← Rate Trends SVG
```

---

## CSS Key Classes

| Class | Purpose |
|---|---|
| `.apphub-content` | Outer shell content area — `overflow:hidden; height:calc(100vh - 52px)` |
| `.scroll` | Main scrollable column — `flex:1; overflow:hidden` |
| `.tier-scroll` | Tier table scroll container — `max-height:168px` (default) |
| `.tier-scroll.tier-expanded` | Expanded tier table — `max-height:none` |
| `.plan-wrap / .plan-trigger / .plan-menu` | Shared custom dropdown pattern (used for Property, Plan, FP) |
| `.stkh-sec.focus-mode` | Chart panel in focus mode — `position:fixed; bottom:0; height:67vh` |
| `.comps-scroll` | Comps list scroll — `max-height:320px` |
| `.chart-wrap` | SVG wrapper — `height:280px; overflow:hidden` |

---

## Data Flow Summary

```
selectPropFromMenu(key)
  → loadForecasts()          ← sets _fk
      → loadAllFpInducements() ← populates _fpPuCache
  → loadFloorplans()         ← builds FP dropdown

selectFpFromMenu(key)
  → selectFloorplan()
      → loadFpInducement()   ← reads _fpPuCache[_fp]
      → loadTierData()
          → budget + actuals + forecast-tiers + property-summary + LTB
          → renderSummary() + _recalcAll()
          → loadRateTrends() + loadLeasingTrend()

calcFpPu(val) / calcPropPu(val)
  → updates _fpPuCache / _propPu
  → _recalcAll()             ← recomputes both w/plan NER columns
```

---

## Known Patterns / Rules

- **DB connections:** Always `SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)` — never tunnel
- **Python execution:** Always write a `.py` file and run `py -u file.py` — never `py -c "..."`
- **Flask server:** `$env:DEV_BYPASS="true"` + `$env:PYTHONIOENCODING="utf-8"` before `py run_dev.py`
- **Chrome:** `Start-Process chrome '`"URL`"'` — never VS Code Simple Browser
- **Edits:** Use `replace_string_in_file` or `multi_replace_string_in_file` — never Set-Content/terminal writes

---

## Monthly Update Checklist

At end of each month, update:
- [ ] "Last updated" date at top
- [ ] Any new API endpoints added
- [ ] Any new JS functions (with line numbers — these shift as code grows)
- [ ] Any new DB tables
- [ ] Any changes to `_recalcAll()` math
- [ ] Current status / known issues / next priorities
