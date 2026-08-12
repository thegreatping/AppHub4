# Market Benchmark — Session Log

## 2026-07-26 — Assign Comps Tab: Full Implementation + Data Model Fixes

### What Was Built
Complete "Assign Comps" tab in the standalone Market Benchmark Flask app (port 5055).
- Two-panel layout: Available Comps (left) + Assigned Comps (right)
- Left panel: shows all market comps, ghosts already-assigned ones
- Right panel: rank-ordered list, drag-to-reorder, ← remove buttons, parent at rank-0 (no remove)
- All backed by `MktSrv_CompMap` as live source (not the stale `COMP_ASSIGNMENTS` snapshot)

### Critical Data Model Discoveries

**1. subjectID ≠ PROPERTY_KEY**
`MktSrv_CompMap.subjectID` is a legacy internal ID, not the modern `PROPERTY_KEY`.
- Resolved via: `SELECT TOP 1 SUBJECTID FROM dbo.COMP_ASSIGNMENTS WHERE PARENT_PROPERTY_KEY = ? AND SUBJECTID IS NOT NULL ORDER BY DATE_KEY DESC`
- 48 WEST: PROPERTY_KEY=9797 → subjectID=3888

**2. compID ≠ PROPERTY_KEY**
`MktSrv_CompMap.compID` stores `COMP_PROPERTY.LEGACY_MARKETPROPERTYID`, not PROPERTY_KEY.
- Read JOIN must be: `JOIN dbo.COMP_PROPERTY cp ON (cp.LEGACY_MARKETPROPERTYID = m.compID OR (cp.LEGACY_MARKETPROPERTYID IS NULL AND cp.PROPERTY_KEY = m.compID))`
- On INSERT: look up `LEGACY_MARKETPROPERTYID` from COMP_PROPERTY; fall back to PROPERTY_KEY for new-system properties

**3. marketCompMapID is NOT an identity column**
Silent NULL writes on every INSERT until this was discovered. Fix: `SELECT ISNULL(MAX(marketCompMapID), 0) + 1 FROM dbo.MktSrv_CompMap` and include in INSERT explicitly.

### Data Cleanup Done
- Deleted 9 NULL-map-id garbage test rows for subjectID=3888 via `_tmp_cleanup2.py`
- Clean state confirmed: 7 rows, max marketCompMapID=33967

### Files Modified
- `app.py` — `_get_subject_id()`, `api_assign_comps()`, `api_assign_comps_add()`, `api_assign_comps_remove()`, `api_assign_comps_reorder()`
- `templates/index.html` — two-panel assign comps HTML, script cache-bust
- `static/css/style.css` — assign comps styles
- `static/js/app.js` — `loadAssignComps()`, `renderAssignAvailable()`, `renderAssignComps()`

### Current Tab Status
| Tab | Status |
|-----|--------|
| Data Entry | ✅ Complete |
| Schools | ✅ Complete |
| Markets | ✅ Complete |
| Comps | ✅ Complete |
| Assign Comps | ✅ Complete (add, remove, drag-reorder) |
| Floor Plans | ❌ Not started |

### Next Session
1. Build Floor Plans tab — manage `FLOORPLAN_WORKSPACE` table
   - Fields: FLOORPLAN_NAME, FLOORPLAN_TYPE, COMPARE_AS_FLOORPLAN_TYPE, APARTMENT_COUNT, BED_COUNT, rent/concession fields, FLAG_SOLD_OUT, FLAG_NO_PRICING_ONLINE, FLAG_ACTIVE
   - Per-property, per-week like Data Entry
2. Consider integrating into AppHub shell (currently standalone)

### Resume Command
```powershell
Set-Location "C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\APPHUB_4\Market Benchmark"
$python = "C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\.venv\Scripts\python.exe"
& $python -u app.py
# then: Start-Process chrome "`"http://localhost:5055`""
```
