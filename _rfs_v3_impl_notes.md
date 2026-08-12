# RFS v3 Mockup — Implementation Notes
**Backup:** `_mockup_rfs_v3_backup_20260728c.html` (stable state as of 2026-07-28)

---

## 1. Theme System

Three themes on `<html data-theme="dark|medium|light">`. All color vars live in CSS custom properties.

### Dark (default)
```css
:root,[data-theme="dark"]{
  --nav-bg:#0f1729; --accent-cyan:#67e8e0; --accent-blue:#64b5f6;
  --accent-gold:#fbbf24; --accent-orange:#fb923c; --accent-green:#4ade80;
  --accent-red:#f87171;
  --content-bg:#111b2e; --content-header:#162035; --surface:#162035;
  --card:#1c2d4a; --text:#f1f5f9; --text2:#94a3b8;
  --bm:rgba(255,255,255,.08); --bl:rgba(255,255,255,.05);
  --bi:rgba(255,255,255,.12); --ibg:rgba(255,255,255,.05);
  --lpanel-bg:#0a1120; --lpanel-border:rgba(103,232,224,.22); --lpanel-shadow:rgba(0,0,0,.5);
}
```

### Medium (dark slate)
```css
[data-theme="medium"]{
  --nav-bg:#1e293b; --accent-cyan:#2dd4bf; --accent-blue:#60a5fa;
  --accent-gold:#d4840a; --accent-orange:#fb923c; --accent-green:#4ade80;
  --accent-red:#f87171;
  --content-bg:#232f3e; --content-header:#1a2535;
  --surface:#1e2d3e; --card:#1a2535; --text:#e2e8f0; --text2:#94a3b8;
  --bm:rgba(255,255,255,.08); --bl:rgba(255,255,255,.05); --bi:rgba(255,255,255,.18);
  --ibg:#1a2535;
  --lpanel-bg:#151f2d; --lpanel-border:rgba(45,212,191,.5); --lpanel-shadow:rgba(0,0,0,.3);
}
```

### Light
```css
[data-theme="light"]{
  --nav-bg:#1e293b; --accent-cyan:#0d9488; --accent-blue:#2563eb;
  --accent-gold:#92400e; --accent-orange:#c2410c; --accent-green:#14532d;
  --accent-red:#dc2626;
  --content-bg:#c8d4e0; --content-header:#d8e2ec;
  --surface:#d8e2ec; --card:#ecf0f5; --text:#0f172a; --text2:#1e3a5f;
  --bm:rgba(0,0,0,.15); --bl:rgba(0,0,0,.08); --bi:rgba(0,0,0,.22);
  --ibg:#f2f5f8;
  --lpanel-bg:#8fa4bc; --lpanel-border:rgba(13,148,136,.55); --lpanel-shadow:rgba(0,0,0,.25);
}
```

---

## 2. Light Mode SVG Chart Overrides

The inline SVG uses hardcoded white fills/strokes (dark-theme defaults). These CSS rules override for light mode via `#viewTrend svg`:

```css
[data-theme="light"] #viewTrend svg text          { fill:#374151 !important; }
[data-theme="light"] #viewTrend svg line           { stroke:rgba(0,0,0,.18) !important; }
[data-theme="light"] #viewTrend svg .ser-py polyline{ stroke:#d97706 !important; }
[data-theme="light"] #viewTrend svg .ser-py circle  { fill:#d97706 !important; stroke:#d97706 !important; }
[data-theme="light"] #viewTrend svg .ser-bud polyline{ stroke:#2563eb !important; }
[data-theme="light"] #viewTrend svg .ser-bud circle  { fill:#2563eb !important; stroke:#2563eb !important; }
[data-theme="light"] #viewTrend svg .ser-bud text    { fill:#2563eb !important; }
[data-theme="light"] #viewTrend svg .ser-act polyline{ stroke:#16a34a !important; }
[data-theme="light"] #viewTrend svg .ser-act circle  { fill:#16a34a !important; stroke:#16a34a !important; }
[data-theme="light"] #viewTrend svg .ser-act text    { fill:#16a34a !important; }
```

**IMPORTANT:** The SVG series must be wrapped in `<g class="ser-py">`, `<g class="ser-bud">`, `<g class="ser-act">` for these rules to work. The axis/grid elements must NOT be inside those `<g>` tags.

---

## 3. Reforecast Plan Dropdown

Replace the native `<select>` with a custom JS-driven dropdown supporting archive/revive.

### HTML structure
```html
<div class="plan-wrap" id="planWrap">
  <div class="plan-trigger" id="planTrigger" onclick="togglePlanMenu()">
    <span class="plan-trigger-lbl" id="planTriggerLbl">RF-284 · June 2026</span>
    <span class="plan-chev">▼</span>
  </div>
  <div class="plan-menu" id="planMenu"><!-- rendered by JS --></div>
</div>
```

### Key CSS classes
- `.plan-wrap` — `position:relative`
- `.plan-menu` — `display:none; position:absolute; top:calc(100%+3px)` — add `.open` to show
- `.plan-item` — active plan row with `.active` state
- `.plan-item.archived` — ghosted/italic, shown below a `<div class="plan-divider">` separator
- `.plan-arch-btn` — ✕ button (archive action)
- `.plan-revive-btn` — ✚ button (restore archived plan)

### JS data model
```js
const planData = [
  {id:'RF-284', lbl:'RF-284 · June 2026',   archived:false},
  {id:'RF-275', lbl:'RF-275 · March 2026',  archived:false},
  // ...
];
let activePlan = 'RF-284';
```

Functions: `renderPlanMenu()`, `togglePlanMenu()`, `selectPlan(id)`, `archivePlan(id)`, `revivePlan(id)`.
Close-on-outside-click via `document.addEventListener('click', ...)`.

---

## 4. KPI Strip (sstrip)

- Removed `.ss-legend` block entirely
- Three KPI blocks: Prelease %, Avg Rate, NER — each with Budget/Actual/Fcst sub-columns
- KPI title, column headers, and values all **centered** (`text-align:center` / `justify-content:center`)
- Inducements panel: **Planned ($)** row uses same `smr` flex layout as other rows — no icon, label left, input right-aligned (72px wide)

---

## 5. Layout Key Settings

| Element | Value |
|---|---|
| `html` font-size | `17px` (30% smaller than original 24px) |
| `.nav` width | `200px` |
| `.lpanel` width | `237px` |
| Tier row | `display:flex` — Renewals + New Leases side-by-side, `16px` cyan divider |
| `.tc-forecast` flex | `1.3` (slightly wider than budget/actuals) |
| Bottom row | `display:grid; grid-template-columns:auto 1fr; align-items:stretch` |
| Comps scroll | `overflow-y:auto; min-height:160px` (no max-height cap) |

---

## 6. Topbar Controls

- **Clone Plan** button (cyan border/text)
- **New Plan** button
- **Export PDF** button (red tint: `background:rgba(248,113,113,.15); color:var(--accent-red)`)
- **Save All Tiers** button — REMOVED (autosave on `input` event → POST `/api/forecast-tiers/save`)
- **Approved** toggle — `.appr-btn.on` with checkmark / `.appr-btn` pending state

---

## 7. Files

| File | Purpose |
|---|---|
| `_mockup_rfs_v3.html` | Active mockup (current approved state) |
| `_mockup_rfs_v3_backup_20260728c.html` | Stable backup 2026-07-28 (this session final) |
| `_mockup_rfs_v3_backup_20260728b.html` | Earlier backup (pre-legend removal) |
| `_mockup_rfs_v3_backup_20260728.html` | Earliest backup (pre-compression) |
