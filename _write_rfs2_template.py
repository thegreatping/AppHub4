"""
Write the complete rent_forecast2.html template with pixel-perfect mockup fidelity.
Run from the APPHUB_4 directory: py _write_rfs2_template.py
"""
import os

TEMPLATE = r'''{% extends "shell.html" %}
{% block head %}
<style>
/* ── Make RFS2 fill the AppHub content area fully ── */
.apphub-content{padding:0!important;overflow:hidden!important;display:flex;flex-direction:column;height:calc(100vh - 52px);}

/* ===== THEME VARS — identical to mockup ===== */
:root,[data-theme="dark"]{
  --nav-bg:#0f1729;--accent-cyan:#67e8e0;--accent-blue:#64b5f6;
  --accent-gold:#fbbf24;--accent-orange:#fb923c;--accent-green:#4ade80;
  --accent-red:#f87171;--accent-purple:#c084fc;
  --content-bg:#111b2e;--content-header:#162035;--surface:#162035;
  --card:#1c2d4a;--text:#f1f5f9;--text2:#94a3b8;
  --bm:rgba(255,255,255,.08);--bl:rgba(255,255,255,.05);
  --bi:rgba(255,255,255,.12);--ibg:rgba(255,255,255,.05);
  --hov:rgba(255,255,255,.04);--hovs:rgba(255,255,255,.09);--shadow:rgba(0,0,0,.5);
  --lpanel-bg:#0a1120;--lpanel-border:rgba(103,232,224,.22);--lpanel-shadow:rgba(0,0,0,.5);
}
[data-theme="medium"]{
  --nav-bg:#1e293b;--accent-cyan:#2dd4bf;--accent-blue:#60a5fa;
  --accent-gold:#d4840a;--accent-orange:#fb923c;--accent-green:#4ade80;
  --accent-red:#f87171;--content-bg:#232f3e;--content-header:#1a2535;
  --surface:#1e2d3e;--card:#1a2535;--text:#e2e8f0;--text2:#94a3b8;
  --bm:rgba(255,255,255,.08);--bl:rgba(255,255,255,.05);--bi:rgba(255,255,255,.18);
  --ibg:#1a2535;--hov:rgba(255,255,255,.03);--hovs:rgba(255,255,255,.08);--shadow:rgba(0,0,0,.4);
  --lpanel-bg:#151f2d;--lpanel-border:rgba(45,212,191,.5);--lpanel-shadow:rgba(0,0,0,.3);
}
[data-theme="light"]{
  --nav-bg:#1e293b;--accent-cyan:#0d9488;--accent-blue:#2563eb;
  --accent-gold:#92400e;--accent-orange:#c2410c;--accent-green:#14532d;
  --accent-red:#dc2626;--content-bg:#c8d4e0;--content-header:#d8e2ec;
  --surface:#d8e2ec;--card:#ecf0f5;--text:#0f172a;--text2:#1e3a5f;
  --bm:rgba(0,0,0,.15);--bl:rgba(0,0,0,.08);--bi:rgba(0,0,0,.22);
  --ibg:#f2f5f8;--hov:rgba(0,0,0,.03);--hovs:rgba(0,0,0,.07);--shadow:rgba(0,0,0,.18);
  --lpanel-bg:#8fa4bc;--lpanel-border:rgba(13,148,136,.55);--lpanel-shadow:rgba(0,0,0,.25);
}

/* ===== BASE ===== */
.rfs2{
  font-family:'Segoe UI',system-ui,sans-serif;
  font-size:0.8125rem;
  background:var(--content-bg);
  color:var(--text);
  flex:1;
  display:flex;
  flex-direction:column;
  overflow:hidden;
}

/* ===== TOP BAR ===== */
.topbar{background:var(--lpanel-bg);border-bottom:3px solid var(--lpanel-border);padding:8px 16px;display:flex;align-items:center;gap:12px;flex-shrink:0;flex-wrap:wrap;box-shadow:0 3px 10px var(--lpanel-shadow);}
.page-icon{width:34px;height:34px;border-radius:7px;background:#1e4a6a;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0;}
.page-name{font-size:1.2rem;font-weight:700;color:var(--text);white-space:nowrap;}
.tsep{width:1px;height:26px;background:var(--bm);flex-shrink:0;}
.ctrl-grp{display:flex;align-items:center;gap:6px;}
.ctrl-lbl{font-size:.9rem;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.3px;white-space:nowrap;}
.ctrl-sel{background:var(--ibg);border:1px solid var(--bi);color:var(--text);padding:6px 10px;border-radius:5px;font-size:.95rem;cursor:pointer;}
.ctrl-sel option{background:var(--card);color:var(--text);}
.appr-btn{display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:5px;border:1px solid var(--bi);background:var(--ibg);color:var(--text2);cursor:pointer;font-size:.9rem;font-weight:700;white-space:nowrap;user-select:none;}
.appr-btn.on{background:rgba(74,222,128,.1);border-color:rgba(74,222,128,.3);color:var(--accent-green);}
.ml-auto{margin-left:auto;}
.btn{padding:6px 14px;border:none;border-radius:5px;font-size:.88rem;font-weight:700;cursor:pointer;display:flex;align-items:center;gap:5px;}
.btn-p{background:var(--accent-cyan);color:#0f1729;}
.btn-g{background:var(--ibg);color:var(--text2);border:1px solid var(--bi);}

/* Plan dropdown */
.plan-wrap{position:relative;}
.plan-trigger{display:flex;align-items:center;gap:6px;padding:3px 8px;background:var(--ibg);border:1px solid var(--bi);border-radius:4px;cursor:pointer;font-size:.77rem;color:var(--text);min-width:160px;}
.plan-trigger .plan-trigger-lbl{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.plan-trigger .plan-chev{font-size:.6rem;color:var(--text2);flex-shrink:0;}
.plan-menu{display:none;position:absolute;top:calc(100% + 3px);left:0;min-width:220px;background:var(--card);border:1px solid var(--bi);border-radius:6px;box-shadow:0 6px 20px var(--shadow);z-index:999;padding:4px 0;}
.plan-menu.open{display:block;}
.plan-item{display:flex;align-items:center;padding:5px 10px;cursor:pointer;font-size:.77rem;color:var(--text);}
.plan-item:hover{background:var(--hovs);}
.plan-item.active{font-weight:700;color:var(--accent-cyan);}
.plan-item.archived{color:var(--text2);font-style:italic;opacity:.7;}
.plan-item .plan-name{flex:1;}
.plan-arch-btn,.plan-revive-btn{margin-left:6px;flex-shrink:0;width:18px;height:18px;border-radius:3px;border:none;background:transparent;cursor:pointer;font-size:.72rem;display:flex;align-items:center;justify-content:center;color:var(--text2);}
.plan-arch-btn:hover{background:rgba(248,113,113,.18);color:var(--accent-red);}
.plan-revive-btn:hover{background:rgba(74,222,128,.18);color:var(--accent-green);}
.plan-divider{height:1px;background:var(--bm);margin:4px 0;}
.plan-arch-hdr{padding:3px 10px;font-size:.65rem;color:var(--text2);text-transform:uppercase;letter-spacing:.04em;}

/* Save flash dot */
.save-flash{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent-green);margin-left:4px;opacity:0;transition:opacity .3s;}
.save-flash.on{opacity:1;}

/* ===== BODY ===== */
.rfs2-body{flex:1;display:flex;overflow:hidden;}

/* ===== LEFT PANEL ===== */
.lpanel{width:237px;flex-shrink:0;border-right:3px solid var(--lpanel-border);display:flex;flex-direction:column;overflow:hidden;background:var(--lpanel-bg);box-shadow:3px 0 12px var(--lpanel-shadow);}

/* Side-card collapsibles */
.sc{border-bottom:1px solid var(--bm);flex-shrink:0;}
.sc-hdr{display:flex;align-items:center;padding:7px 10px;cursor:pointer;user-select:none;}
.sc-hdr:hover{background:var(--hov);}
.sc-title{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--accent-cyan);flex:1;}
.sc-chev{font-size:.62rem;color:var(--text2);transition:transform .2s;}
.sc-chev.c{transform:rotate(-90deg);}
.sc-body{padding:3px 0 8px;}
.sc-body.collapsed{display:none;}

/* Summary rows */
.smr{display:flex;align-items:center;padding:2px 10px;font-size:.77rem;}
.sml{color:var(--text2);flex:1;}
.smv{font-weight:700;color:var(--text);}
.smv.g{color:var(--accent-green);}
.smv.o{color:var(--accent-gold);}
.smv.r{color:var(--accent-red);}
.smcols{display:flex;gap:4px;}
.smc{min-width:44px;text-align:right;font-size:.77rem;font-weight:700;}
.smc.b{color:var(--accent-blue);}
.smc.g{color:var(--accent-green);}
.smc.o{color:var(--accent-gold);}
.sm-hdr{display:flex;padding:1px 10px 3px;gap:4px;}
.sm-hl{flex:1;}
.sm-hc{min-width:44px;text-align:right;font-size:.63rem;font-weight:700;text-transform:uppercase;color:var(--text2);}
.sdiv{border:none;border-top:1px solid var(--bl);margin:4px 10px;}

/* Planned use row */
.planned-row{display:flex;align-items:center;padding:2px 10px 3px;background:rgba(251,191,36,.08);border-radius:4px;margin:2px 0 4px;font-size:.77rem;}
.planned-lbl{color:var(--accent-gold);font-weight:700;flex:1;}
.planned-inp{background:rgba(251,191,36,.12);border:2px solid rgba(251,191,36,.4);color:var(--accent-gold);padding:3px 6px;border-radius:4px;font-size:.77rem;width:80px;text-align:right;font-weight:800;}
.planned-inp:focus{border-color:var(--accent-gold);outline:none;}

/* Floorplan list */
.fp-sec{display:flex;flex-direction:column;min-height:0;flex:1;overflow:hidden;}
.fp-sec-hdr{padding:7px 10px 5px;font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text2);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;border-top:1px solid var(--bm);}
.fp-list{overflow-y:auto;flex:1;}
.fpi{display:flex;align-items:center;padding:7px 10px;cursor:pointer;border-left:3px solid transparent;border-bottom:1px solid var(--bl);transition:background .1s;gap:8px;}
.fpi:hover{background:var(--hovs);}
.fpi.active{background:rgba(103,232,224,.07);border-left-color:var(--accent-cyan);}
.fpi-name{font-size:.82rem;font-weight:600;color:var(--text);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.fpi.active .fpi-name{color:var(--accent-cyan);}
.fpi-beds{font-size:.65rem;color:var(--text2);background:var(--bm);padding:1px 5px;border-radius:8px;white-space:nowrap;flex-shrink:0;}
.fpi.active .fpi-beds{background:rgba(103,232,224,.15);color:var(--accent-cyan);}

/* ===== MAIN CONTENT ===== */
.mcontent{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0;}

/* ===== SUMMARY STRIP ===== */
.sstrip{background:var(--content-header);border-bottom:2px solid var(--bm);padding:14px 22px;display:flex;align-items:stretch;gap:24px;flex-shrink:0;flex-wrap:wrap;}
.ss-fp{display:flex;flex-direction:column;justify-content:center;min-width:110px;}
.ss-fp-name{font-size:1.1rem;font-weight:800;color:var(--accent-cyan);}
.ss-fp-sub{font-size:.72rem;color:var(--text2);margin-top:2px;}
.ssep{width:1px;background:var(--bm);margin:4px 0;flex-shrink:0;}
.kpi-blk{display:flex;flex-direction:column;gap:6px;min-width:160px;background:rgba(100,181,246,.06);border:1px solid rgba(100,181,246,.18);border-radius:6px;padding:10px 14px;}
.kpi-blk-title{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--text2);text-align:center;}
.kpi-cols-hdr{display:flex;gap:6px;margin-top:2px;justify-content:center;}
.kpi-col-hdr{min-width:62px;text-align:right;font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.3px;}
.kpi-col-hdr.b{color:var(--accent-blue);}
.kpi-col-hdr.g{color:var(--accent-green);}
.kpi-col-hdr.f{color:var(--accent-gold);}
.kpi-vals{display:flex;gap:6px;justify-content:center;}
.kv{min-width:62px;text-align:right;font-size:.88rem;font-weight:700;}
.kv.b{color:var(--accent-blue);}
.kv.g{color:var(--accent-green);}
.kv.f{color:var(--accent-gold);}
.ltb-blk{background:rgba(251,191,36,.07);border:1px solid rgba(251,191,36,.2);border-radius:6px;padding:10px 18px;display:flex;flex-direction:column;gap:6px;}
.ltb-title{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--accent-gold);}
.ltb-nums{display:flex;gap:20px;margin-top:4px;}
.ltb-item{display:flex;flex-direction:column;align-items:center;gap:4px;}
.ltb-val{font-size:1rem;font-weight:800;}
.ltb-val.r{color:var(--accent-orange);}
.ltb-val.n{color:var(--accent-green);}
.ltb-val.t{color:var(--accent-gold);}
.ltb-lbl{font-size:.6rem;color:var(--text2);text-transform:uppercase;letter-spacing:.3px;}

/* ===== SCROLL AREA ===== */
.scroll{flex:1;overflow-y:auto;padding:10px 14px;display:flex;flex-direction:column;gap:10px;}

/* ===== COLLAPSIBLE SECTIONS ===== */
.coll-sec{border:1px solid var(--bm);border-radius:6px;overflow:visible;}
.coll-sec-hdr{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--lpanel-bg);border-bottom:3px solid var(--lpanel-border);cursor:pointer;user-select:none;border-radius:6px 6px 0 0;}
.coll-sec-hdr:hover{filter:brightness(1.08);}
.coll-sec-title{font-size:.78rem;font-weight:700;color:var(--text);flex:1;}
.coll-sec-chev{font-size:.65rem;color:var(--text2);transition:transform .2s;}
.coll-sec-chev.c{transform:rotate(-90deg);}
.coll-sec-body{padding-bottom:4px;}
.coll-sec-body.collapsed{display:none;}

/* ===== TIER ROW ===== */
.tier-row{display:flex;align-items:stretch;overflow:hidden;}
.tier-inner{flex:1;min-width:0;overflow:hidden;}
.tier-sec-hdr{display:flex;align-items:center;gap:8px;padding:7px 12px;background:rgba(255,255,255,.04);border-bottom:1px solid var(--bm);}
.tier-divider{width:16px;flex-shrink:0;background:rgba(103,232,224,.55);box-shadow:0 0 8px rgba(103,232,224,.4);}
.tcols{display:flex;width:100%;}
.tier-scroll{overflow-y:auto;overflow-x:hidden;max-height:240px;}
.tc-budget{flex:1;min-width:0;border-right:3px solid rgba(100,181,246,.35);background:rgba(100,181,246,.03);overflow:hidden;}
.tc-actuals{flex:1;min-width:0;border-right:3px solid rgba(74,222,128,.3);background:rgba(74,222,128,.03);overflow:hidden;}
.tc-forecast{flex:1.3;min-width:0;background:rgba(251,191,36,.04);overflow:hidden;}
.tc-hdr{padding:6px 8px;font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.4px;text-align:center;border-bottom:1px solid var(--bm);display:flex;align-items:center;justify-content:center;gap:6px;}
.tc-hdr.bgt{color:var(--accent-blue);}
.tc-hdr.act{color:var(--accent-green);}
.tc-hdr.fct{color:var(--accent-gold);}
.edit-badge{font-size:.6rem;padding:1px 6px;border-radius:8px;background:rgba(251,191,36,.15);color:var(--accent-gold);border:1px solid rgba(251,191,36,.25);font-weight:700;}
.fct-btns{display:flex;gap:4px;margin-left:auto;}
.btn-xs{padding:3px 8px;border:none;border-radius:3px;font-size:.68rem;font-weight:700;cursor:pointer;display:flex;align-items:center;gap:3px;}
.btn-xs.add{background:rgba(74,222,128,.12);color:var(--accent-green);border:1px solid rgba(74,222,128,.25);}
.btn-xs.add:hover{background:rgba(74,222,128,.22);}
.btn-xs.save{background:rgba(103,232,224,.12);color:var(--accent-cyan);border:1px solid rgba(103,232,224,.25);}
.btn-xs.save:hover{background:rgba(103,232,224,.22);}

/* Tier tables */
.ttbl{width:100%;border-collapse:collapse;font-size:.77rem;table-layout:fixed;}
.ttbl thead th{padding:3px 6px;background:var(--surface);color:var(--text2);font-weight:600;font-size:.65rem;text-align:right;border-bottom:1px solid var(--bm);}
.ttbl thead th:first-child{text-align:center;width:20px!important;max-width:20px;}
.ttbl col:first-child{width:20px;}
.ttbl tbody td{padding:3px 6px;border-bottom:1px solid var(--bl);text-align:right;color:var(--text);}
.ttbl tbody td:first-child{text-align:center;color:var(--text2);font-size:.63rem;}
.ttbl tbody td:last-child,.ttbl tfoot td:last-child{padding-right:10px;}
.ttbl tbody tr:last-child td{border-bottom:none;}
.ttbl tbody tr:hover td{background:var(--hov);}
.ttbl tfoot td{padding:5px 6px 6px;background:var(--surface);border-top:1px solid var(--bm);font-weight:700;font-size:.72rem;text-align:right;}
.ttbl tfoot td:first-child{text-align:center;color:var(--text2);}
.tner{color:var(--accent-cyan);font-weight:700;padding-right:10px!important;}
.tinp{background:transparent;border:1px solid transparent;color:var(--text);padding:2px 4px;border-radius:3px;font-size:.77rem;width:100%!important;text-align:right;box-sizing:border-box;}
.tinp:focus{border-color:var(--accent-cyan);outline:none;background:rgba(103,232,224,.05);}
.btn-del{background:none;border:none;color:var(--text2);cursor:pointer;font-size:.75rem;padding:0 3px;border-radius:3px;}
.btn-del:hover{color:var(--accent-red);background:rgba(248,113,113,.1);}

/* ===== BOTTOM ROW ===== */
.bottom-row{display:grid;grid-template-columns:auto 1fr;gap:10px;padding:10px;align-items:stretch;}

/* Comps */
.comps-sec{border:1px solid var(--bm);border-radius:6px;overflow:hidden;display:flex;flex-direction:column;}
.comps-hdr{display:flex;align-items:center;gap:8px;padding:7px 10px;background:var(--lpanel-bg);border-bottom:3px solid var(--lpanel-border);flex-shrink:0;}
.comps-hdr-t{font-size:.82rem;font-weight:700;color:var(--text);}
.ctype-pill{padding:2px 8px;border-radius:10px;font-size:.7rem;font-weight:700;background:rgba(251,191,36,.1);color:var(--accent-gold);border:1px solid rgba(251,191,36,.22);}
.comps-body{display:flex;flex-direction:column;flex:1;min-height:0;}
.comps-scroll{flex:1;overflow-y:auto;min-height:160px;}
.ctbl{width:auto;border-collapse:collapse;font-size:.77rem;table-layout:auto;}
.ctbl thead th{background:var(--surface);padding:4px 8px;text-align:left;font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.3px;color:var(--text2);border-bottom:1px solid var(--bm);position:sticky;top:0;}
.ctbl thead th.r{text-align:right;}
.ctbl thead th.c{text-align:center;}
.ctbl tbody td{padding:4px 8px;border-bottom:1px solid var(--bl);color:var(--text);}
.ctbl tbody td.r{text-align:right;font-weight:600;}
.ctbl tbody td.c{text-align:center;}
.ctbl tbody tr:hover td{background:var(--hov);}
.ctbl tbody tr.excl td{opacity:.38;}
.cfooter{border-top:2px solid var(--bm);background:var(--surface);flex-shrink:0;}
.cfooter td{padding:4px 8px;font-weight:700;font-size:.77rem;}
.cfooter td.r{text-align:right;}
.cfooter td.c{text-align:center;}
.toggle-btn{width:26px;height:20px;border-radius:3px;border:none;cursor:pointer;font-size:.78rem;font-weight:700;}
.ton{background:rgba(74,222,128,.15);color:var(--accent-green);border:1px solid rgba(74,222,128,.3);}
.toff{background:rgba(248,113,113,.15);color:var(--accent-red);border:1px solid rgba(248,113,113,.3);}
.bdg{display:inline-block;padding:1px 5px;border-radius:8px;font-size:.67rem;font-weight:700;}
.bdg-r{background:rgba(248,113,113,.15);color:var(--accent-red);}
.bdg-b{background:rgba(100,181,246,.12);color:var(--accent-blue);}

/* Stakeholder */
.stkh-sec{border:1px solid var(--bm);border-radius:6px;overflow:hidden;display:flex;flex-direction:column;}
.stkh-hdr{display:flex;align-items:center;gap:8px;padding:7px 10px;background:var(--lpanel-bg);border-bottom:3px solid var(--lpanel-border);flex-shrink:0;}
.stkh-title{font-size:.82rem;font-weight:700;color:var(--text);flex:1;}
.stkh-body{flex:1;display:flex;flex-direction:column;overflow:hidden;}
.stkh-tab.active-tab{background:rgba(103,232,224,.15)!important;color:var(--accent-cyan)!important;border-color:rgba(103,232,224,.35)!important;}

/* Trend legends */
.trend-legend{display:flex;gap:16px;margin-bottom:12px;}
.tleg-item{display:flex;align-items:center;gap:6px;font-size:.7rem;color:var(--text2);}
.tleg-dot{width:14px;height:5px;border-radius:2px;flex-shrink:0;}

/* Summary builder */
.stkh-controls{display:flex;gap:6px;padding:8px 10px;border-bottom:1px solid var(--bl);flex-wrap:wrap;flex-shrink:0;}
.stkh-ctrl-lbl{font-size:.7rem;color:var(--text2);display:flex;align-items:center;gap:5px;cursor:pointer;}
.stkh-ctrl-lbl input[type=checkbox]{accent-color:var(--accent-cyan);}
.stkh-ta-wrap{flex:1;padding:8px 10px;display:flex;flex-direction:column;gap:6px;overflow:hidden;}
.stkh-ta{flex:1;min-height:150px;background:var(--ibg);border:1px solid var(--bi);color:var(--text);border-radius:5px;padding:10px;font-size:.82rem;font-family:'Segoe UI',system-ui,sans-serif;resize:none;line-height:1.5;}
.stkh-ta:focus{border-color:var(--accent-cyan);outline:none;}
.stkh-actions{display:flex;gap:6px;flex-shrink:0;}
.stkh-note{font-size:.68rem;color:var(--text2);font-style:italic;}

/* Light-mode SVG overrides */
[data-theme="light"] #viewTrend svg text{fill:#374151!important;}
[data-theme="light"] #viewTrend svg line{stroke:rgba(0,0,0,.18)!important;}
[data-theme="light"] #viewTrend svg .ser-py polyline{stroke:#d97706!important;}
[data-theme="light"] #viewTrend svg .ser-bud polyline{stroke:#2563eb!important;}
[data-theme="light"] #viewTrend svg .ser-act polyline{stroke:#16a34a!important;}
[data-theme="light"] #viewRate svg text{fill:#374151!important;}
[data-theme="light"] #viewRate svg line{stroke:rgba(0,0,0,.18)!important;}
[data-theme="light"] #viewRate svg .rt-act polyline{stroke:#16a34a!important;}
[data-theme="light"] #viewRate svg .rt-fc polyline{stroke:#92400e!important;}
</style>
{% endblock %}

{% block content %}
<div class="rfs2">

  <!-- ══════════════════ TOP BAR ══════════════════ -->
  <div class="topbar">
    <div class="page-icon">&#128176;</div>
    <span class="page-name">Rent Forecasting 2.0</span>
    <div class="tsep"></div>

    <div class="ctrl-grp">
      <span class="ctrl-lbl">Property</span>
      <select class="ctrl-sel" id="propSel" onchange="onPropChange()">
        <option value="">Loading&hellip;</option>
      </select>
    </div>

    <div class="ctrl-grp">
      <span class="ctrl-lbl">AY</span>
      <select class="ctrl-sel" id="aySel" onchange="onAyChange()" style="min-width:80px">
        {% for ay in ay_options %}
        <option value="{{ ay }}"{% if ay == current_ay %} selected{% endif %}>{{ ay }}</option>
        {% endfor %}
      </select>
    </div>

    <div class="ctrl-grp">
      <span class="ctrl-lbl">Reforecast Plan</span>
      <div class="plan-wrap" id="planWrap">
        <div class="plan-trigger" id="planTrigger" onclick="togglePlanMenu()">
          <span class="plan-trigger-lbl" id="planTriggerLbl">&mdash; select property &mdash;</span>
          <span class="plan-chev">&#9660;</span>
        </div>
        <div class="plan-menu" id="planMenu"></div>
      </div>
    </div>

    <div class="tsep"></div>
    <div class="appr-btn" id="apprBtn" onclick="toggleApproved()">&#9675; Pending</div>
    <span class="save-flash" id="saveFlash" title="Saved"></span>

    <div class="ml-auto" style="display:flex;gap:8px;align-items:center">
      <button class="btn btn-g" onclick="clonePlan()" style="color:var(--accent-cyan);border-color:rgba(103,232,224,.3)">&#10697; Clone Plan</button>
      <button class="btn btn-g" onclick="newPlan()">&#65291; New Plan</button>
      <button class="btn" onclick="window.print()" style="background:rgba(248,113,113,.15);color:var(--accent-red);border:1px solid rgba(248,113,113,.35)">&#128196; Export PDF</button>
    </div>
  </div>

  <!-- ══════════════════ BODY ══════════════════ -->
  <div class="rfs2-body">

    <!-- LEFT PANEL ────────────────────────────── -->
    <div class="lpanel">

      <!-- Property Summary collapsible -->
      <div class="sc">
        <div class="sc-hdr" onclick="toggleSC(this)">
          <span class="sc-title">Property Summary</span>
          <span class="sc-chev">&#9660;</span>
        </div>
        <div class="sc-body">
          <div class="sm-hdr">
            <span class="sm-hl"></span>
            <span class="sm-hc b">Bud</span>
            <span class="sm-hc g">Act</span>
            <span class="sm-hc o">Fc</span>
          </div>
          <div class="smr"><span class="sml">Prelease</span><div class="smcols"><span class="smc b" id="lpPrelB">&mdash;</span><span class="smc g" id="lpPrelA">&mdash;</span><span class="smc o" id="lpPrelF">&mdash;</span></div></div>
          <div class="smr"><span class="sml">Rate</span><div class="smcols"><span class="smc b" id="lpRateB">&mdash;</span><span class="smc g" id="lpRateA">&mdash;</span><span class="smc o" id="lpRateF">&mdash;</span></div></div>
          <div class="smr"><span class="sml">NER</span><div class="smcols"><span class="smc b" id="lpNerB">&mdash;</span><span class="smc g" id="lpNerA">&mdash;</span><span class="smc o" id="lpNerF">&mdash;</span></div></div>
        </div>
      </div>

      <!-- Inducements collapsible -->
      <div class="sc">
        <div class="sc-hdr" onclick="toggleSC(this)">
          <span class="sc-title">Inducements</span>
          <span style="font-size:.7rem;color:var(--accent-gold);margin-right:6px" id="lpIndTotal">&mdash;</span>
          <span class="sc-chev">&#9660;</span>
        </div>
        <div class="sc-body">
          <div class="planned-row">
            <span class="planned-lbl">Planned ($)</span>
            <input class="planned-inp" id="plannedInp" type="number" min="0" step="100" placeholder="0" onblur="savePlannedUse(this.value)">
          </div>
          <div class="smr"><span class="sml">Used YTD</span><span class="smv" id="lpIndUsed">&mdash;</span></div>
          <div class="smr"><span class="sml">Forecasted</span><span class="smv" id="lpIndFc">&mdash;</span></div>
          <hr class="sdiv">
          <div class="smr"><span class="sml" style="font-weight:700;color:var(--text)">Total</span><span class="smv o" id="lpIndTot2">&mdash;</span></div>
        </div>
      </div>

      <!-- Floorplan list -->
      <div class="fp-sec">
        <div class="fp-sec-hdr">
          <span>Floor Plans</span>
          <span style="font-size:.65rem;color:var(--accent-cyan)" id="lpFpBeds"></span>
        </div>
        <div class="fp-list" id="fpList">
          <div style="padding:12px 10px;font-size:.72rem;color:var(--text2)">Select a property</div>
        </div>
      </div>

    </div><!-- /lpanel -->

    <!-- MAIN CONTENT ───────────────────────────── -->
    <div class="mcontent">

      <!-- SUMMARY STRIP -->
      <div class="sstrip">
        <div class="ss-fp">
          <div class="ss-fp-name" id="ssName">&mdash;</div>
          <div class="ss-fp-sub" id="ssSub">Select a property and floorplan</div>
        </div>
        <div class="ssep"></div>

        <div class="kpi-blk">
          <div class="kpi-blk-title">Prelease %</div>
          <div class="kpi-cols-hdr"><span class="kpi-col-hdr b">Budget</span><span class="kpi-col-hdr g">Actual</span><span class="kpi-col-hdr f">Fcst</span></div>
          <div class="kpi-vals"><span class="kv b" id="ssPrelB">&mdash;</span><span class="kv g" id="ssPrelA">&mdash;</span><span class="kv f" id="ssPrelF">&mdash;</span></div>
        </div>
        <div class="ssep"></div>

        <div class="kpi-blk">
          <div class="kpi-blk-title">Avg Rate</div>
          <div class="kpi-cols-hdr"><span class="kpi-col-hdr b">Budget</span><span class="kpi-col-hdr g">Actual</span><span class="kpi-col-hdr f">Fcst</span></div>
          <div class="kpi-vals"><span class="kv b" id="ssRateB">&mdash;</span><span class="kv g" id="ssRateA">&mdash;</span><span class="kv f" id="ssRateF">&mdash;</span></div>
        </div>
        <div class="ssep"></div>

        <div class="kpi-blk">
          <div class="kpi-blk-title">NER</div>
          <div class="kpi-cols-hdr"><span class="kpi-col-hdr b">Budget</span><span class="kpi-col-hdr g">Actual</span><span class="kpi-col-hdr f">Fcst</span></div>
          <div class="kpi-vals"><span class="kv b" id="ssNerB">&mdash;</span><span class="kv g" id="ssNerA">&mdash;</span><span class="kv f" id="ssNerF">&mdash;</span></div>
        </div>
        <div class="ssep"></div>

        <div class="ltb-blk">
          <div class="ltb-title">Left to Budget &middot; <span id="ssLtbFpName" style="color:var(--accent-cyan)">&mdash;</span></div>
          <div class="ltb-nums">
            <div class="ltb-item"><div class="ltb-val r" id="ltbAct">&mdash;</div><div class="ltb-lbl">Actuals</div></div>
            <div class="ltb-item"><div class="ltb-val n" id="ltbFc">&mdash;</div><div class="ltb-lbl">Forecast</div></div>
            <div class="ltb-item"><div class="ltb-val t" id="ltbRem">&mdash;</div><div class="ltb-lbl">Remaining</div></div>
          </div>
        </div>
      </div><!-- /sstrip -->

      <!-- SCROLL -->
      <div class="scroll">

        <!-- TIER SECTION (Renewals + New Leases) -->
        <div class="coll-sec">
          <div class="coll-sec-hdr" onclick="toggleCollSec(this)">
            <span class="coll-sec-title">Renewals &amp; New Leases</span>
            <span id="tierMeta" style="font-size:.72rem;color:var(--text2)"></span>
            <span class="coll-sec-chev" style="margin-left:8px">&#9660;</span>
          </div>
          <div class="coll-sec-body">
            <div class="tier-row">

              <!-- RENEWALS -->
              <div class="tier-inner">
                <div class="tier-sec-hdr">
                  <span style="color:var(--accent-orange);font-weight:700;font-size:.75rem">&#9654; Renewals</span>
                </div>
                <div class="tcols">
                  <!-- Budget -->
                  <div class="tc-budget">
                    <div class="tc-hdr bgt">Budgeted Tiers</div>
                    <div class="tier-scroll">
                      <table class="ttbl">
                        <colgroup><col style="width:20px"><col><col><col></colgroup>
                        <thead><tr><th>#</th><th>Ct</th><th>Rate</th><th>NER</th></tr></thead>
                        <tbody id="rBudBody"><tr><td colspan="4" style="text-align:center;color:var(--text2);padding:10px;font-style:italic">Select a floorplan</td></tr></tbody>
                        <tfoot><tr><td>&#8709;</td><td id="rBudTotCt">&mdash;</td><td id="rBudTotRate">&mdash;</td><td id="rBudTotNer" class="tner">&mdash;</td></tr></tfoot>
                      </table>
                    </div>
                  </div>
                  <!-- Actuals -->
                  <div class="tc-actuals">
                    <div class="tc-hdr act">Actuals YTD</div>
                    <div class="tier-scroll">
                      <table class="ttbl">
                        <colgroup><col style="width:20px"><col><col><col></colgroup>
                        <thead><tr><th>#</th><th>Ct</th><th>Rate</th><th>NER</th></tr></thead>
                        <tbody id="rActBody"><tr><td colspan="4" style="text-align:center;color:var(--text2);padding:10px;font-style:italic">Select a floorplan</td></tr></tbody>
                        <tfoot><tr><td>&#8709;</td><td id="rActTotCt">&mdash;</td><td id="rActTotRate">&mdash;</td><td id="rActTotNer" class="tner">&mdash;</td></tr></tfoot>
                      </table>
                    </div>
                  </div>
                  <!-- Reforecast -->
                  <div class="tc-forecast">
                    <div class="tc-hdr fct" style="color:var(--accent-orange)">
                      Renewal RFC <span class="edit-badge">Editable</span>
                      <div class="fct-btns"><button class="btn-xs add" onclick="addTier('RENEWAL')">&#65291; Add</button></div>
                    </div>
                    <div class="tier-scroll">
                      <table class="ttbl">
                        <colgroup><col style="width:20px"><col><col><col><col style="width:22px"></colgroup>
                        <thead><tr><th>#</th><th>Ct</th><th>Rate</th><th>NER</th><th></th></tr></thead>
                        <tbody id="rFcBody"><tr><td colspan="5" style="text-align:center;color:var(--text2);padding:10px;font-style:italic">Select a plan</td></tr></tbody>
                        <tfoot><tr><td>&#8709;</td><td id="rFcTotCt">&mdash;</td><td id="rFcTotRate">&mdash;</td><td id="rFcTotNer" class="tner">&mdash;</td><td></td></tr></tfoot>
                      </table>
                    </div>
                  </div>
                </div>
              </div><!-- /tier-inner renewals -->

              <div class="tier-divider"></div>

              <!-- NEW LEASES -->
              <div class="tier-inner">
                <div class="tier-sec-hdr">
                  <span style="color:var(--accent-green);font-weight:700;font-size:.75rem">&#9654; New Leases</span>
                </div>
                <div class="tcols">
                  <!-- Budget -->
                  <div class="tc-budget">
                    <div class="tc-hdr bgt">Budgeted Tiers</div>
                    <div class="tier-scroll">
                      <table class="ttbl">
                        <colgroup><col style="width:20px"><col><col><col></colgroup>
                        <thead><tr><th>#</th><th>Ct</th><th>Rate</th><th>NER</th></tr></thead>
                        <tbody id="nBudBody"><tr><td colspan="4" style="text-align:center;color:var(--text2);padding:10px;font-style:italic">Select a floorplan</td></tr></tbody>
                        <tfoot><tr><td>&#8709;</td><td id="nBudTotCt">&mdash;</td><td id="nBudTotRate">&mdash;</td><td id="nBudTotNer" class="tner">&mdash;</td></tr></tfoot>
                      </table>
                    </div>
                  </div>
                  <!-- Actuals -->
                  <div class="tc-actuals">
                    <div class="tc-hdr act">Actuals YTD</div>
                    <div class="tier-scroll">
                      <table class="ttbl">
                        <colgroup><col style="width:20px"><col><col><col></colgroup>
                        <thead><tr><th>#</th><th>Ct</th><th>Rate</th><th>NER</th></tr></thead>
                        <tbody id="nActBody"><tr><td colspan="4" style="text-align:center;color:var(--text2);padding:10px;font-style:italic">Select a floorplan</td></tr></tbody>
                        <tfoot><tr><td>&#8709;</td><td id="nActTotCt">&mdash;</td><td id="nActTotRate">&mdash;</td><td id="nActTotNer" class="tner">&mdash;</td></tr></tfoot>
                      </table>
                    </div>
                  </div>
                  <!-- Reforecast -->
                  <div class="tc-forecast">
                    <div class="tc-hdr fct" style="color:var(--accent-green)">
                      New Lease RFC <span class="edit-badge">Editable</span>
                      <div class="fct-btns"><button class="btn-xs add" onclick="addTier('NEW')">&#65291; Add</button></div>
                    </div>
                    <div class="tier-scroll">
                      <table class="ttbl">
                        <colgroup><col style="width:20px"><col><col><col><col style="width:22px"></colgroup>
                        <thead><tr><th>#</th><th>Ct</th><th>Rate</th><th>NER</th><th></th></tr></thead>
                        <tbody id="nFcBody"><tr><td colspan="5" style="text-align:center;color:var(--text2);padding:10px;font-style:italic">Select a plan</td></tr></tbody>
                        <tfoot><tr><td>&#8709;</td><td id="nFcTotCt">&mdash;</td><td id="nFcTotRate">&mdash;</td><td id="nFcTotNer" class="tner">&mdash;</td><td></td></tr></tfoot>
                      </table>
                    </div>
                  </div>
                </div>
              </div><!-- /tier-inner new leases -->

            </div><!-- /tier-row -->
          </div><!-- /coll-sec-body -->
        </div><!-- /tier coll-sec -->

        <!-- BOTTOM ROW: Comps + Stakeholder -->
        <div class="coll-sec">
          <div class="coll-sec-hdr" onclick="toggleCollSec(this)">
            <span class="coll-sec-title">&#128202; Market Comps &amp; Stakeholder Summary</span>
            <span style="font-size:.7rem;color:var(--text2);margin-right:8px" id="compsSummaryLbl"></span>
            <span class="coll-sec-chev">&#9660;</span>
          </div>
          <div class="coll-sec-body">
            <div class="bottom-row">

              <!-- MARKET COMPS -->
              <div class="comps-sec">
                <div class="comps-hdr">
                  <span class="comps-hdr-t">Comps &mdash; <strong style="color:var(--accent-cyan)" id="compsFpName">&mdash;</strong></span>
                  <span class="ctype-pill" id="compsTypePill">&mdash;</span>
                  <span style="font-size:.7rem;color:var(--text2)" id="compsCntLbl"></span>
                </div>
                <div class="comps-body">
                  <div class="comps-scroll">
                    <table class="ctbl">
                      <colgroup><col style="width:32%"><col style="width:26%"><col style="width:16%"><col style="width:12%"><col style="width:14%"></colgroup>
                      <thead>
                        <tr>
                          <th>Competitor</th>
                          <th>Floorplan</th>
                          <th class="r">NER</th>
                          <th class="c">Sold</th>
                          <th class="c">Incl</th>
                        </tr>
                      </thead>
                      <tbody id="compsTbody">
                        <tr><td colspan="5" style="text-align:center;color:var(--text2);padding:14px;font-style:italic">Select a floorplan</td></tr>
                      </tbody>
                    </table>
                  </div>
                  <table class="ctbl cfooter">
                    <colgroup><col style="width:32%"><col style="width:26%"><col style="width:16%"><col style="width:12%"><col style="width:14%"></colgroup>
                    <tbody>
                      <tr>
                        <td colspan="2" style="text-align:right;color:var(--text2);font-weight:400">All Competitors</td>
                        <td class="r" id="cAllNer">&mdash;</td>
                        <td class="c" style="color:var(--accent-red)" id="cSoldCnt">&mdash;</td>
                        <td class="c" id="cAllCnt">&mdash;</td>
                      </tr>
                      <tr>
                        <td colspan="2" style="text-align:right;color:var(--text2);font-weight:400">Leasing Comps</td>
                        <td class="r" id="cLcNer">&mdash;</td>
                        <td class="c">&mdash;</td>
                        <td class="c" style="color:var(--accent-cyan)" id="cLcCnt">&mdash;</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div><!-- /comps-sec -->

              <!-- STAKEHOLDER PANEL -->
              <div class="stkh-sec">
                <div class="stkh-hdr">
                  <span class="stkh-title">&#128221; Stakeholder Summary Builder</span>
                  <div style="display:flex;gap:4px;margin-left:auto;margin-right:8px">
                    <button class="btn-xs save stkh-tab" id="tabSummary" onclick="switchStkhTab('summary')">&#128221; Summary</button>
                    <button class="btn-xs save stkh-tab active-tab" id="tabTrend" onclick="switchStkhTab('trend')">&#128200; Leasing Trend</button>
                    <button class="btn-xs save stkh-tab" id="tabRate" onclick="switchStkhTab('rate')">&#128178; Rate Trends</button>
                  </div>
                </div>

                <!-- VIEW 1: Summary Builder -->
                <div class="stkh-body" id="viewSummary" style="display:none">
                  <div class="stkh-controls">
                    <label class="stkh-ctrl-lbl"><input type="checkbox" id="incProp" checked> Property KPIs</label>
                    <label class="stkh-ctrl-lbl"><input type="checkbox" id="incTiers" checked> Reforecast Tiers</label>
                    <label class="stkh-ctrl-lbl"><input type="checkbox" id="incComps" checked> Market Comps</label>
                    <label class="stkh-ctrl-lbl"><input type="checkbox" id="incLTB" checked> Left to Budget</label>
                  </div>
                  <div class="stkh-ta-wrap">
                    <textarea class="stkh-ta" id="stkTA" placeholder="Click Build to generate a copy-paste stakeholder summary for the selected floorplan..."></textarea>
                    <div class="stkh-actions">
                      <button class="btn btn-p" style="font-size:.8rem" onclick="buildAndCopyStkMsg()">&#128203; Copy to Clipboard</button>
                      <button class="btn btn-g" style="font-size:.8rem" onclick="document.getElementById('stkTA').value=''">Clear</button>
                      <span class="stkh-note" id="cpyNote"></span>
                    </div>
                  </div>
                </div>

                <!-- VIEW 2: Leasing Trend chart -->
                <div class="stkh-body" id="viewTrend" style="padding:12px 16px 8px">
                  <div style="font-size:.7rem;color:var(--text2);margin-bottom:8px">Cumulative leases by tier &mdash; <strong style="color:var(--accent-cyan)" id="trendFpLbl">&mdash;</strong></div>
                  <div class="trend-legend">
                    <span class="tleg-item"><span class="tleg-dot" style="background:var(--accent-green)"></span>Actuals</span>
                    <span class="tleg-item"><span class="tleg-dot" style="background:var(--accent-blue)"></span>Budget</span>
                    <span class="tleg-item"><span class="tleg-dot" style="background:var(--accent-gold)"></span>Reforecast</span>
                    <span style="font-size:.65rem;color:var(--text2);margin-left:auto;padding-right:4px">&#9655; shaded = future</span>
                  </div>
                  <svg id="trendSvg" viewBox="0 0 560 210" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block">
                    <text x="280" y="110" text-anchor="middle" font-size="11" fill="rgba(148,163,184,.4)">Select a floorplan and plan</text>
                  </svg>
                </div>

                <!-- VIEW 3: Rate Trends chart -->
                <div class="stkh-body" id="viewRate" style="padding:12px 16px 8px;display:none">
                  <div style="font-size:.7rem;color:var(--text2);margin-bottom:6px">NER by tier &mdash; <strong style="color:var(--accent-cyan)" id="rateFpLbl">&mdash;</strong>&nbsp;<span style="font-size:.62rem;opacity:.6">(dot size = bed count)</span></div>
                  <div class="trend-legend">
                    <span class="tleg-item"><span class="tleg-dot" style="background:var(--accent-green)"></span>Actuals YTD</span>
                    <span class="tleg-item"><span class="tleg-dot" style="background:var(--accent-gold)"></span>Reforecast</span>
                    <span class="tleg-item"><span style="width:10px;height:10px;border-radius:50%;border:2px solid var(--accent-blue);display:inline-block"></span>&nbsp;Budget (float)</span>
                  </div>
                  <svg id="rateSvg" viewBox="0 0 580 210" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block">
                    <text x="290" y="110" text-anchor="middle" font-size="11" fill="rgba(148,163,184,.4)">Select a floorplan and plan</text>
                  </svg>
                  <div style="display:flex;gap:16px;margin-top:4px;padding-left:50px" id="rateAvgRow"></div>
                </div>

              </div><!-- /stkh-sec -->

            </div><!-- /bottom-row -->
          </div><!-- /coll-sec-body -->
        </div><!-- /bottom coll-sec -->

      </div><!-- /scroll -->
    </div><!-- /mcontent -->
  </div><!-- /rfs2-body -->
</div><!-- /rfs2 -->

<script>
// =============================================================
//  RFS 2.0 — JavaScript
// =============================================================
const _$ = id => document.getElementById(id);

// ── App state ─────────────────────────────────────────────────
let _ay      = {{ current_ay }};
let _prop    = null, _propName = '';
let _fp      = null, _fpName = '', _fpCode = '', _compType = '';
let _fk      = null;
let _plans   = [];
let _summ    = {};

// ── Formatters ────────────────────────────────────────────────
const _fc  = v => (v == null || v === '') ? '\u2014' : '$' + Number(v).toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const _fp2 = v => (v == null || v === '') ? '\u2014' : Number(v).toFixed(1) + '%';
const _fn  = v => (v == null || v === '') ? '\u2014' : Math.round(Number(v)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
function _esc(s) { return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function _esc2(s) { return String(s || '').replace(/\\/g,'\\\\').replace(/'/g,"\\'"); }

// ── HTTP helpers ──────────────────────────────────────────────
async function _get(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) { console.error('RFS2 GET', url, r.status); return null; }
    return r.json();
  } catch(e) { console.error('RFS2 GET', url, e); return null; }
}
async function _post(url, body) {
  try {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) { console.error('RFS2 POST', url, r.status); return null; }
    return r.json();
  } catch(e) { console.error('RFS2 POST', url, e); return null; }
}

// ── Flash indicator ───────────────────────────────────────────
function flash() {
  const d = _$('saveFlash');
  d.classList.add('on');
  setTimeout(() => d.classList.remove('on'), 1500);
}

// ── Collapsibles ──────────────────────────────────────────────
function toggleSC(hdr) {
  const body = hdr.nextElementSibling;
  const chev = hdr.querySelector('.sc-chev');
  body.classList.toggle('collapsed');
  chev.classList.toggle('c');
}
function toggleCollSec(hdr) {
  const body = hdr.nextElementSibling;
  const chev = hdr.querySelector('.coll-sec-chev');
  body.classList.toggle('collapsed');
  chev.classList.toggle('c');
}

// ── Plan dropdown ─────────────────────────────────────────────
function togglePlanMenu() { _$('planMenu').classList.toggle('open'); }
document.addEventListener('click', e => {
  if (!e.target.closest('#planWrap')) _$('planMenu')?.classList.remove('open');
});

function renderPlanMenu() {
  const active   = _plans.filter(p => !p.archived);
  const archived = _plans.filter(p =>  p.archived);
  let html = '';
  active.forEach(p => {
    const cls = p.key === _fk ? 'plan-item active' : 'plan-item';
    html += `<div class="${cls}" onclick="selectPlan(${p.key})">
      <span class="plan-name">${_esc(p.name)}${p.approved ? ' \u2713' : ''}</span>
      <button class="plan-arch-btn" onclick="event.stopPropagation();archivePlan(${p.key})" title="Archive">\u2715</button>
    </div>`;
  });
  if (archived.length) {
    html += '<div class="plan-divider"></div><div class="plan-arch-hdr">Archived</div>';
    archived.forEach(p => {
      html += `<div class="plan-item archived" onclick="selectPlan(${p.key})">
        <span class="plan-name">${_esc(p.name)}</span>
        <button class="plan-revive-btn" onclick="event.stopPropagation();revivePlan(${p.key})" title="Revive">\u271a</button>
      </div>`;
    });
  }
  if (!html) html = '<div style="padding:8px 10px;font-size:.72rem;color:var(--text2)">No plans \u2014 click New Plan</div>';
  _$('planMenu').innerHTML = html;
}

function updatePlanLabel() {
  const p = _plans.find(x => x.key === _fk);
  _$('planTriggerLbl').textContent = p ? p.name : '\u2014 no plan \u2014';
  const btn = _$('apprBtn');
  if (p?.approved) { btn.innerHTML = '\u2713 Approved'; btn.classList.add('on'); }
  else             { btn.innerHTML = '\u25cb Pending';  btn.classList.remove('on'); }
  const inp = _$('plannedInp');
  if (inp && p) inp.value = p.plannedUse != null ? p.plannedUse : '';
}

async function selectPlan(key) {
  _fk = key;
  updatePlanLabel(); renderPlanMenu();
  _$('planMenu').classList.remove('open');
  if (_fp) await loadTierData();
}
async function archivePlan(key) {
  if (!confirm('Archive this plan?')) return;
  await _post('/rfs2/api/forecasts/archive', { forecast_key: key });
  await loadForecasts();
  if (_fp) loadTierData();
}
async function revivePlan(key) {
  await _post('/rfs2/api/forecasts/revive', { forecast_key: key });
  await loadForecasts();
}

// ── Properties ────────────────────────────────────────────────
async function loadProperties() {
  const data = await _get('/rfs2/api/properties');
  if (!data) return;
  const sel = _$('propSel');
  sel.innerHTML = '<option value="">\u2014 select property \u2014</option>';
  data.forEach(p => {
    const o = document.createElement('option');
    o.value = p.PROPERTY_KEY;
    o.textContent = p.PROPERTY_NAME;
    sel.appendChild(o);
  });
}
async function onPropChange() {
  const sel = _$('propSel');
  _prop = sel.value ? +sel.value : null;
  _propName = sel.options[sel.selectedIndex]?.text || '';
  _fp = null; _fk = null; _fpName = ''; _fpCode = ''; _compType = '';
  _$('fpList').innerHTML = '<div style="padding:12px 10px;font-size:.72rem;color:var(--text2)">Loading\u2026</div>';
  _$('planTriggerLbl').textContent = '\u2014 select plan \u2014';
  resetKpis();
  if (!_prop) { _$('fpList').innerHTML = '<div style="padding:12px 10px;font-size:.72rem;color:var(--text2)">Select a property</div>'; return; }
  await Promise.all([loadForecasts(), loadFloorplans()]);
}
async function onAyChange() {
  _ay = +_$('aySel').value;
  if (_prop) await Promise.all([loadForecasts(), loadFloorplans()]);
}

// ── Forecasts ─────────────────────────────────────────────────
async function loadForecasts() {
  const data = await _get(`/rfs2/api/forecasts?property_key=${_prop}&ay=${_ay}`);
  if (!data) return;
  _plans = data.map(f => ({
    key: f.FORECAST_KEY, name: f.FORECAST_NAME,
    archived: !!f.FLAG_ARCHIVED, approved: !!f.FLAG_APPROVED,
    plannedUse: f.INDUCEMENT_PLANNED_USE ?? 0
  }));
  if (!_fk || !_plans.find(p => p.key === _fk)) {
    _fk = _plans.find(p => !p.archived)?.key ?? (_plans[0]?.key ?? null);
  }
  renderPlanMenu(); updatePlanLabel();
}

// ── Floorplans ────────────────────────────────────────────────
async function loadFloorplans() {
  const data = await _get(`/rfs2/api/floorplans?property_key=${_prop}`);
  const list = _$('fpList');
  if (!data?.length) {
    list.innerHTML = '<div style="padding:12px 10px;font-size:.72rem;color:var(--text2)">No floorplans found</div>';
    return;
  }
  const total = data.reduce((s, f) => s + (f.BEDS || 0), 0);
  _$('lpFpBeds').textContent = total + ' beds';
  list.innerHTML = data.map(f =>
    `<div class="fpi" id="fpi${f.FLOORPLAN_KEY}"
          onclick="selectFloorplan(${f.FLOORPLAN_KEY},'${_esc2(f.FLOORPLAN)}','${_esc2(f.FLOORPLAN_CODE||f.FLOORPLAN)}','${_esc2(f.COMPARE_AS_FLOORPLAN_TYPE||'')}')">
       <span class="fpi-name">${_esc(f.FLOORPLAN)}</span>
       <span class="fpi-beds">${f.BEDS}bd</span>
     </div>`
  ).join('');
}
async function selectFloorplan(key, name, code, ct) {
  _fp = key; _fpName = name; _fpCode = code; _compType = ct;
  document.querySelectorAll('.fpi').forEach(e => e.classList.remove('active'));
  _$('fpi' + key)?.classList.add('active');
  _$('ssName').textContent    = name;
  _$('ssLtbFpName').textContent = name;
  _$('ssSub').textContent     = 'Floorplan \u00b7 ' + (ct || '\u2014') + ' type';
  _$('trendFpLbl').textContent = name;
  _$('rateFpLbl').textContent  = name;
  _$('compsFpName').textContent = name;
  await loadTierData();
}

// ── Master data loader ────────────────────────────────────────
async function loadTierData() {
  if (!_fp) return;
  const base = `property_key=${_prop}&floorplan_key=${_fp}&ay=${_ay}`;
  const fkStr = _fk ? '&forecast_key=' + _fk : '';
  const [budR, budN, actR, actN, fcR, fcN, summ, ltb, comps] = await Promise.all([
    _get(`/rfs2/api/budget-tiers?${base}&lease_type=RENEWAL`),
    _get(`/rfs2/api/budget-tiers?${base}&lease_type=NEW`),
    _get(`/rfs2/api/actuals?${base}&lease_type=RENEWAL`),
    _get(`/rfs2/api/actuals?${base}&lease_type=NEW`),
    _fk ? _get(`/rfs2/api/forecast-tiers?forecast_key=${_fk}&floorplan_key=${_fp}&lease_type=RENEWAL`) : Promise.resolve([]),
    _fk ? _get(`/rfs2/api/forecast-tiers?forecast_key=${_fk}&floorplan_key=${_fp}&lease_type=NEW`)     : Promise.resolve([]),
    _get(`/rfs2/api/property-summary?${base}${fkStr}`),
    _get(`/rfs2/api/left-to-budget?${base}${fkStr}`),
    _fk ? _get(`/rfs2/api/comps?forecast_key=${_fk}&property_key=${_prop}&compare_type=${encodeURIComponent(_compType)}`) : Promise.resolve([]),
  ]);
  if (budR)  renderBudget('r', budR);
  if (budN)  renderBudget('n', budN);
  if (actR)  renderActuals('r', actR);
  if (actN)  renderActuals('n', actN);
  if (fcR)   renderForecast('r', fcR);
  if (fcN)   renderForecast('n', fcN);
  if (summ)  { _summ = summ; renderSummary(summ); }
  if (ltb)   renderLtb(ltb);
  if (comps) renderComps(comps);
  if (_fk)   { loadRateTrends(); loadLeasingTrend(); }
}

// ── Budget tiers ──────────────────────────────────────────────
function renderBudget(side, rows) {
  const tbody = _$(side + 'BudBody');
  if (!rows || !rows.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text2);padding:8px;font-style:italic">No budget tiers</td></tr>';
    _$(side+'BudTotCt').textContent = _$(side+'BudTotRate').textContent = _$(side+'BudTotNer').textContent = '\u2014';
    return;
  }
  let ct = 0, rExt = 0, nExt = 0;
  tbody.innerHTML = rows.map((r, i) => {
    ct += r.BEDS || 0;
    rExt += (r.RATE || 0) * (r.BEDS || 0);
    nExt += (r.RATE || 0) * (r.BEDS || 0);
    return `<tr><td>${i+1}</td><td>${_fn(r.BEDS)}</td><td>${_fc(r.RATE)}</td><td class="tner">${_fc(r.RATE)}</td></tr>`;
  }).join('');
  _$(side+'BudTotCt').textContent   = _fn(ct);
  _$(side+'BudTotRate').textContent = _fc(ct ? rExt / ct : 0);
  _$(side+'BudTotNer').textContent  = _fc(ct ? nExt / ct : 0);
}

// ── Actuals ───────────────────────────────────────────────────
function renderActuals(side, data) {
  const tbody = _$(side + 'ActBody');
  const rent = data?.rent || [], ner = data?.ner || [];
  const maxLen = Math.max(rent.length, ner.length);
  if (!maxLen) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text2);padding:8px;font-style:italic">No actuals</td></tr>';
    _$(side+'ActTotCt').textContent = _$(side+'ActTotRate').textContent = _$(side+'ActTotNer').textContent = '\u2014';
    return;
  }
  let ct = 0, rExt = 0, nExt = 0;
  const rows = [];
  for (let i = 0; i < maxLen; i++) {
    const r = rent[i] || {}, n = ner[i] || {};
    const c    = r.LEASED_COUNT_RENT || n.LEASED_COUNT_NER || 0;
    const rate = r.RENT_PER_SPACE || 0;
    const nerv = n.NER_PER_SPACE  || 0;
    ct += c; rExt += rate * c; nExt += nerv * c;
    rows.push(`<tr><td>T${i+1}</td><td>${_fn(c)}</td><td>${_fc(rate)}</td><td class="tner">${_fc(nerv)}</td></tr>`);
  }
  tbody.innerHTML = rows.join('');
  _$(side+'ActTotCt').textContent   = _fn(ct);
  _$(side+'ActTotRate').textContent = _fc(ct ? rExt / ct : 0);
  _$(side+'ActTotNer').textContent  = _fc(ct ? nExt / ct : 0);
}

// ── Forecast tiers (editable) ────────────────────────────────
function renderForecast(side, rows) {
  const lt    = side === 'r' ? 'RENEWAL' : 'NEW';
  const tbody = _$(side + 'FcBody');
  if (!rows || !rows.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text2);padding:10px;font-style:italic">${_fk ? 'No tiers \u2014 click + Add' : 'Select a plan'}</td></tr>`;
    _$(side+'FcTotCt').textContent = _$(side+'FcTotRate').textContent = _$(side+'FcTotNer').textContent = '\u2014';
    return;
  }
  let ct = 0, rExt = 0, nExt = 0;
  tbody.innerHTML = rows.map((r, i) => {
    ct   += r.LEASE_COUNT   || 0;
    rExt += r.RATE_EXTENDED || 0;
    nExt += r.NER_EXTENDED  || 0;
    return `<tr data-tk="${r.FORECAST_TIERS_KEY}" data-lt="${lt}">
      <td>${i+1}</td>
      <td><input class="tinp" type="number" min="0" value="${r.LEASE_COUNT || 0}"
          onblur="saveTier(${r.FORECAST_TIERS_KEY},'${lt}')" data-f="ct"></td>
      <td><input class="tinp" type="number" min="0" step="0.01" value="${(r.RATE || 0).toFixed(2)}"
          onblur="saveTier(${r.FORECAST_TIERS_KEY},'${lt}')" data-f="rate"></td>
      <td class="tner" id="nerCell${r.FORECAST_TIERS_KEY}">${_fc(r.NER)}</td>
      <td><button class="btn-del" onclick="delTier(${r.FORECAST_TIERS_KEY},'${lt}')" title="Delete">\u00d7</button></td>
    </tr>`;
  }).join('');
  _$(side+'FcTotCt').textContent   = _fn(ct);
  _$(side+'FcTotRate').textContent = _fc(ct ? rExt / ct : 0);
  _$(side+'FcTotNer').textContent  = _fc(ct ? nExt / ct : 0);
}

async function saveTier(tk, lt) {
  const row = document.querySelector(`[data-tk="${tk}"]`);
  if (!row) return;
  const lc   = parseFloat(row.querySelector('[data-f="ct"]').value)   || 0;
  const rate = parseFloat(row.querySelector('[data-f="rate"]').value) || 0;
  const ord  = Array.from(row.parentNode.children).indexOf(row) + 1;
  const res  = await _post('/rfs2/api/forecast-tiers/save', { forecast_tiers_key: tk, lease_count: lc, rate: rate, tier_order: ord });
  if (res?.ok) {
    _$('nerCell' + tk).textContent = _fc(res.ner);
    flash();
    loadRateTrends();
  }
}
async function addTier(lt) {
  if (!_fk || !_fp) return;
  const side    = lt === 'RENEWAL' ? 'r' : 'n';
  const rows    = document.querySelectorAll(`[data-lt="${lt}"]`);
  const lastRate = rows.length ? (parseFloat(rows[rows.length-1].querySelector('[data-f="rate"]')?.value) || 0) : 0;
  const res = await _post('/rfs2/api/forecast-tiers/add', {
    forecast_key: _fk, floorplan_key: _fp, floorplan_code: _fpCode,
    property_key: _prop, property_name: _propName,
    lease_type: lt, rate: lastRate
  });
  if (res?.ok) {
    const fc = await _get(`/rfs2/api/forecast-tiers?forecast_key=${_fk}&floorplan_key=${_fp}&lease_type=${lt}`);
    if (fc) renderForecast(side, fc);
  }
}
async function delTier(tk, lt) {
  if (!confirm('Delete this tier?')) return;
  const res = await _post('/rfs2/api/forecast-tiers/delete', { forecast_tiers_key: tk });
  if (res?.ok) {
    const side = lt === 'RENEWAL' ? 'r' : 'n';
    const fc   = await _get(`/rfs2/api/forecast-tiers?forecast_key=${_fk}&floorplan_key=${_fp}&lease_type=${lt}`);
    if (fc) renderForecast(side, fc);
    loadRateTrends();
  }
}

// ── Summary / KPI strip ───────────────────────────────────────
function renderSummary(s) {
  const map = [
    ['lpPrelB','budget_occ','p'],    ['lpPrelA','actual_prelease','p'],   ['lpPrelF','forecast_prelease','p'],
    ['lpRateB','budget_avg_rate','c'],['lpRateA','actual_avg_rate','c'],  ['lpRateF','forecast_avg_rate','c'],
    ['lpNerB','budget_ner','c'],     ['lpNerA','actual_ner','c'],         ['lpNerF','forecast_ner','c'],
    ['ssPrelB','budget_occ','p'],    ['ssPrelA','actual_prelease','p'],   ['ssPrelF','forecast_prelease','p'],
    ['ssRateB','budget_avg_rate','c'],['ssRateA','actual_avg_rate','c'],  ['ssRateF','forecast_avg_rate','c'],
    ['ssNerB','budget_ner','c'],     ['ssNerA','actual_ner','c'],         ['ssNerF','forecast_ner','c'],
  ];
  map.forEach(([id, k, t]) => { const el = _$(id); if (el) el.textContent = t === 'p' ? _fp2(s[k]) : _fc(s[k]); });
  _$('lpIndUsed').textContent  = _fc(s.inducement_used || 0);
  _$('lpIndFc').textContent    = _fc(s.forecast_concession_ext || 0);
  const tot = (s.inducement_used || 0) + (s.forecast_concession_ext || 0);
  _$('lpIndTotal').textContent = _fc(tot);
  _$('lpIndTot2').textContent  = _fc(tot);
  const tc  = (s.act_r?.count || 0) + (s.act_n?.count || 0);
  const tfc = (s.fc_r?.count  || 0) + (s.fc_n?.count  || 0);
  _$('tierMeta').textContent = (s.total_beds || 0) + ' beds \u00b7 ' + tc + ' leased \u00b7 ' + Math.max(0,(s.total_beds||0)-tc-tfc) + ' remaining';
}
function renderLtb(ltb) {
  _$('ltbAct').textContent = _fn(ltb.actuals_total);
  _$('ltbFc').textContent  = _fn(ltb.forecast_total);
  const rem = ltb.left_to_budget;
  _$('ltbRem').textContent    = (rem >= 0 ? '+' : '') + _fn(rem);
  _$('ltbRem').style.color = rem < 0 ? 'var(--accent-red)' : rem === 0 ? 'var(--accent-gold)' : 'var(--accent-green)';
}
function resetKpis() {
  ['lpPrelB','lpPrelA','lpPrelF','lpRateB','lpRateA','lpRateF','lpNerB','lpNerA','lpNerF',
   'ssPrelB','ssPrelA','ssPrelF','ssRateB','ssRateA','ssRateF','ssNerB','ssNerA','ssNerF',
   'ltbAct','ltbFc','ltbRem','tierMeta'].forEach(id => { const el = _$(id); if (el) el.textContent = '\u2014'; });
}

// ── Planned inducement ────────────────────────────────────────
async function savePlannedUse(val) {
  if (!_fk) return;
  await _post('/rfs2/api/forecasts/planned-use', { forecast_key: _fk, planned_use: +val || 0 });
  flash();
  const p = _plans.find(x => x.key === _fk);
  if (p) p.plannedUse = +val || 0;
}

// ── Approved toggle ───────────────────────────────────────────
async function toggleApproved() {
  if (!_fk) return;
  const p = _plans.find(x => x.key === _fk);
  if (!p) return;
  p.approved = !p.approved;
  await _post('/rfs2/api/forecasts/approve', { forecast_key: _fk, approved: p.approved });
  updatePlanLabel(); renderPlanMenu(); flash();
}

// ── Clone / New plan ──────────────────────────────────────────
async function clonePlan() {
  if (!_fk) { alert('Select a plan first.'); return; }
  const p    = _plans.find(x => x.key === _fk);
  const name = prompt('New plan name:', (p?.name || '') + ' (Copy)');
  if (!name) return;
  const res = await _post('/rfs2/api/forecasts/clone', { forecast_key: _fk, new_name: name });
  if (res?.ok) { await loadForecasts(); _fk = res.forecast_key; updatePlanLabel(); renderPlanMenu(); if (_fp) loadTierData(); }
}
async function newPlan() {
  if (!_prop) { alert('Select a property first.'); return; }
  const name = prompt('Plan name:', 'RFC \u00b7 ' + new Date().toLocaleDateString('en-US', { month: 'short', year: 'numeric' }));
  if (!name) return;
  const res = await _post('/rfs2/api/forecasts/create', { property_key: _prop, property_name: _propName, forecast_name: name, ay: _ay });
  if (res?.ok) { await loadForecasts(); _fk = res.forecast_key; updatePlanLabel(); renderPlanMenu(); if (_fp) loadTierData(); }
}

// ── Market comps ──────────────────────────────────────────────
function renderComps(rows) {
  _$('compsTypePill').textContent = _compType || '\u2014';
  if (!rows || !rows.length) {
    _$('compsTbody').innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text2);padding:12px;font-style:italic">No comps found</td></tr>';
    _$('compsSummaryLbl').textContent = '';
    return;
  }
  const incl    = rows.filter(r => r.FLAG_INCLUDE);
  const leasing = incl.filter(r => !r.FLAG_SOLD_OUT);
  _$('compsCntLbl').textContent    = incl.length + ' incl \u00b7 ' + leasing.length + ' leasing';
  _$('compsSummaryLbl').textContent = incl.length + ' incl \u00b7 ' + leasing.length + ' leasing';
  _$('compsTbody').innerHTML = rows.map(r => {
    const on   = r.FLAG_INCLUDE;
    const sold = r.FLAG_SOLD_OUT ? '<span class="bdg bdg-r">Yes</span>' : '<span class="bdg bdg-b">No</span>';
    return `<tr${on ? '' : ' class="excl"'}>
      <td>${_esc(r.COMP_PROPERTY_NAME)}</td>
      <td>${_esc(r.FLOORPLAN_NAME || r.FLOORPLAN)}</td>
      <td class="r">${_fc(r.NER)}</td>
      <td class="c">${sold}</td>
      <td class="c"><button class="toggle-btn ${on ? 'ton' : 'toff'}" onclick="toggleComp(${r.FLOORPLAN_ASSIGNMENT_KEY})">${on ? '\u2713' : '\u2717'}</button></td>
    </tr>`;
  }).join('');
  const allN = rows.filter(r => r.NER);
  const lcN  = leasing.filter(r => r.NER);
  _$('cAllNer').textContent  = allN.length ? _fc(allN.reduce((s,r) => s+r.NER, 0) / allN.length) : '\u2014';
  _$('cLcNer').textContent   = lcN.length  ? _fc(lcN.reduce((s,r)  => s+r.NER, 0) / lcN.length)  : '\u2014';
  _$('cAllCnt').textContent  = rows.length;
  _$('cSoldCnt').textContent = rows.filter(r => r.FLAG_SOLD_OUT).length;
  _$('cLcCnt').textContent   = leasing.length;
}
async function toggleComp(fak) {
  await _post('/rfs2/api/comps/toggle', { floorplan_assignment_key: fak, forecast_key: _fk });
  const comps = await _get(`/rfs2/api/comps?forecast_key=${_fk}&property_key=${_prop}&compare_type=${encodeURIComponent(_compType)}`);
  if (comps) renderComps(comps);
}

// ── Stakeholder tabs ──────────────────────────────────────────
function switchStkhTab(tab) {
  ['summary', 'trend', 'rate'].forEach(t => {
    _$('tab' + t.charAt(0).toUpperCase() + t.slice(1))?.classList.toggle('active-tab', t === tab);
    const v = _$('view' + t.charAt(0).toUpperCase() + t.slice(1));
    if (v) v.style.display = t === tab ? '' : 'none';
  });
}
async function buildAndCopyStkMsg() {
  const s = _summ;
  let msg = `=== RENT FORECAST SUMMARY: ${_fpName} ===\n`;
  if (_$('incProp').checked)  msg += `\nPROPERTY KPIs\nPrelease:  Bgt ${_fp2(s.budget_occ)} | Act ${_fp2(s.actual_prelease)} | Fc ${_fp2(s.forecast_prelease)}\nAvg Rate:  Bgt ${_fc(s.budget_avg_rate)} | Act ${_fc(s.actual_avg_rate)} | Fc ${_fc(s.forecast_avg_rate)}\nNER:       Bgt ${_fc(s.budget_ner)} | Act ${_fc(s.actual_ner)} | Fc ${_fc(s.forecast_ner)}\n`;
  if (_$('incLTB').checked)   msg += `\nLEFT TO BUDGET\nActuals: ${_fn(_summ.actuals_total)} | Forecast: ${_fn(_summ.forecast_total)}\n`;
  _$('stkTA').value = msg;
  navigator.clipboard.writeText(msg).then(() => {
    _$('cpyNote').textContent = '\u2713 Copied!';
    setTimeout(() => _$('cpyNote').textContent = '', 2000);
  });
}

// ── Rate Trends SVG ───────────────────────────────────────────
async function loadRateTrends() {
  if (!_fp || !_fk) return;
  const data = await _get(`/rfs2/api/rate-trends?property_key=${_prop}&floorplan_key=${_fp}&ay=${_ay}&forecast_key=${_fk}`);
  if (data) drawRateChart(data);
}
function drawRateChart(data) {
  const svg = _$('rateSvg');
  const W = 580, yB = 194, yT = 22, xL = 50;
  const actuals  = data.actuals   || [];
  const budget   = data.budget    || [];
  const refc     = data.reforecast|| [];
  const allNer   = [...actuals, ...budget, ...refc].map(r => r.NER || 0).filter(v => v > 0);
  if (!allNer.length) {
    svg.innerHTML = '<text x="290" y="110" text-anchor="middle" font-size="11" fill="rgba(148,163,184,.4)">No rate data</text>';
    return;
  }
  const nerMin = Math.floor(Math.min(...allNer) / 25) * 25 - 25;
  const nerMax = Math.ceil( Math.max(...allNer) / 25) * 25 + 25;
  const yS = v => yB - (v - nerMin) / (nerMax - nerMin) * (yB - yT);
  const maxBeds = Math.max(...[...actuals, ...budget, ...refc].map(r => r.BEDS || r.LEASE_COUNT || 1));
  const rS  = b => Math.max(3, Math.min(10, 3 + (b / maxBeds) * 7));
  const nA  = actuals.length, nR = refc.length, nB = budget.length;
  const total = nA + nR;
  const xStep = total > 0 ? (W - xL - 30) / Math.max(total + 1, 2) : 60;
  const xA  = i => xL + (i + 1) * xStep;
  const xR  = i => xL + (nA + i + 1.5) * xStep;
  const xBu = i => xL + (i + 1) * xStep;
  let html = '';
  // Grid + Y axis labels
  for (let n = nerMin; n <= nerMax; n += 25) {
    const y = yS(n);
    html += `<line x1="${xL}" y1="${y.toFixed(1)}" x2="${W-10}" y2="${y.toFixed(1)}" stroke="${n===nerMin?'rgba(255,255,255,.18)':'rgba(255,255,255,.07)'}" stroke-width="1"/>`;
    html += `<text x="${xL-2}" y="${(y+3).toFixed(1)}" font-size="8" fill="rgba(255,255,255,.4)" text-anchor="end">$${_fn(n)}</text>`;
  }
  // Actuals / Reforecast divider
  if (nA > 0 && nR > 0) {
    const dx = (xA(nA - 1) + xR(0)) / 2;
    html += `<line x1="${dx.toFixed(1)}" y1="${yT}" x2="${dx.toFixed(1)}" y2="${yB}" stroke="rgba(255,255,255,.2)" stroke-width="1" stroke-dasharray="4,3"/>`;
    html += `<text x="${(xA(nA/2-.5)).toFixed(1)}" y="${yT-2}" font-size="7" fill="rgba(74,222,128,.5)" text-anchor="middle">\u25c4 Actuals YTD</text>`;
    html += `<text x="${(xR(nR/2-.5)).toFixed(1)}" y="${yT-2}" font-size="7" fill="rgba(251,191,36,.5)" text-anchor="middle">Reforecast \u25ba</text>`;
  }
  // Actuals series (green)
  if (nA > 1) html += `<g class="rt-act"><polyline points="${actuals.map((r,i)=>`${xA(i).toFixed(1)},${yS(r.NER||0).toFixed(1)}`).join(' ')}" fill="none" stroke="rgba(74,222,128,.7)" stroke-width="2"/>`;
  else if (nA === 1) html += '<g class="rt-act">';
  actuals.forEach((r, i) => {
    const x = xA(i), y = yS(r.NER || 0), rd = rS(r.BEDS || r.LEASE_COUNT || 1);
    html += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${rd.toFixed(1)}" fill="#4ade80"/>`;
    html += `<text x="${x.toFixed(1)}" y="${(y-rd-2).toFixed(1)}" font-size="7" fill="rgba(74,222,128,.95)" text-anchor="middle" font-weight="700">${_fc(r.NER)}</text>`;
    html += `<text x="${x.toFixed(1)}" y="${(yB+12).toFixed(1)}" font-size="8" fill="rgba(74,222,128,.6)" text-anchor="middle">${i+1}</text>`;
  });
  if (nA > 0) html += '</g>';
  // Bridge line
  if (nA > 0 && nR > 0) {
    html += `<line x1="${xA(nA-1).toFixed(1)}" y1="${yS(actuals[nA-1].NER||0).toFixed(1)}" x2="${xR(0).toFixed(1)}" y2="${yS(refc[0].NER||0).toFixed(1)}" stroke="rgba(251,191,36,.25)" stroke-width="1" stroke-dasharray="3,3"/>`;
  }
  // Reforecast series (gold)
  if (nR > 1) html += `<g class="rt-fc"><polyline points="${refc.map((r,i)=>`${xR(i).toFixed(1)},${yS(r.NER||0).toFixed(1)}`).join(' ')}" fill="none" stroke="rgba(251,191,36,.8)" stroke-width="2"/>`;
  else if (nR === 1) html += '<g class="rt-fc">';
  refc.forEach((r, i) => {
    const x = xR(i), y = yS(r.NER || 0), rd = rS(r.LEASE_COUNT || 1);
    html += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${rd.toFixed(1)}" fill="#fbbf24"/>`;
    html += `<text x="${x.toFixed(1)}" y="${(y-rd-2).toFixed(1)}" font-size="7.5" fill="rgba(251,191,36,.98)" text-anchor="middle" font-weight="700">${_fc(r.NER)}</text>`;
    html += `<text x="${x.toFixed(1)}" y="${(yB+12).toFixed(1)}" font-size="8" fill="rgba(251,191,36,.6)" text-anchor="middle">${nA+i+1}</text>`;
  });
  if (nR > 0) html += '</g>';
  // Budget hollow rings (blue, floating)
  if (nB > 0) {
    html += '<g class="rt-bud">';
    budget.forEach((r, i) => {
      const x = xBu(i), y = yS(r.NER || 0), rd = rS(r.BEDS || 1);
      html += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(rd+1).toFixed(1)}" fill="rgba(100,181,246,.1)" stroke="#64b5f6" stroke-width="2"/>`;
      html += `<text x="${x.toFixed(1)}" y="${(y-rd-3).toFixed(1)}" font-size="7" fill="rgba(100,181,246,.8)" text-anchor="middle" font-weight="700">${_fc(r.NER)}</text>`;
    });
    html += '</g>';
  }
  svg.innerHTML = html;
  // Avg NER row
  const avgA = nA ? actuals.reduce((s,r) => s+(r.NER||0), 0) / nA : 0;
  const avgR = nR ? refc.reduce((s,r)    => s+(r.NER||0), 0) / nR : 0;
  const avgB = nB ? budget.reduce((s,r)  => s+(r.NER||0), 0) / nB : 0;
  _$('rateAvgRow').innerHTML =
    `<div style="font-size:.62rem;color:var(--text2)">Avg NER \u2192</div>` +
    `<div style="font-size:.65rem;font-weight:800;color:var(--accent-blue)">${nB ? 'Bgt: '+_fc(avgB) : 'Bgt: \u2014'}</div>` +
    `<div style="font-size:.65rem;font-weight:800;color:var(--accent-green)">${nA ? 'Act: '+_fc(avgA) : 'Act: \u2014'}</div>` +
    `<div style="font-size:.65rem;font-weight:800;color:var(--accent-gold)">${nR ? 'RFC: '+_fc(avgR) : 'RFC: \u2014'}</div>`;
}

// ── Leasing Trend SVG ─────────────────────────────────────────
async function loadLeasingTrend() {
  if (!_fp || !_fk) return;
  const data = await _get(`/rfs2/api/leasing-trend?property_key=${_prop}&floorplan_key=${_fp}&ay=${_ay}&forecast_key=${_fk}`);
  if (data) drawTrendChart(data);
}
function drawTrendChart(data) {
  const svg  = _$('trendSvg');
  const W    = 560, yB = 188, yT = 33, xL = 44;
  const act  = data.actuals  || [];
  const fc   = data.forecast || [];
  const budPct = data.budget_pct || 0;
  const all  = [...act, ...fc];
  if (!all.length) {
    svg.innerHTML = '<text x="280" y="110" text-anchor="middle" font-size="11" fill="rgba(148,163,184,.4)">No trend data</text>';
    return;
  }
  const maxX = all[all.length-1]?.x || 1;
  const xS   = x => xL + (x / maxX) * (W - xL - 10);
  const yS   = p => yB - (p / 125) * (yB - yT);
  let html = '';
  // Horizontal grid
  [0, 25, 50, 75, 100, 125].forEach(p => {
    const y = yS(p);
    html += `<line x1="${xL}" y1="${y.toFixed(1)}" x2="${W-5}" y2="${y.toFixed(1)}" stroke="${p===0?'rgba(255,255,255,.15)':'rgba(255,255,255,.07)'}" stroke-width="1"/>`;
    html += `<text x="${xL-4}" y="${(y+3).toFixed(1)}" font-size="8" fill="rgba(255,255,255,.4)" text-anchor="end">${p}</text>`;
  });
  // Budget flat line (blue dashed)
  if (budPct > 0) {
    const y = yS(budPct);
    html += `<g class="ser-bud">`;
    html += `<line x1="${xL}" y1="${y.toFixed(1)}" x2="${W-5}" y2="${y.toFixed(1)}" stroke="rgba(100,181,246,.9)" stroke-width="2" stroke-dasharray="5,3"/>`;
    html += `<text x="${W-6}" y="${(y-2).toFixed(1)}" font-size="8" fill="rgba(100,181,246,.8)" text-anchor="end">Bgt ${budPct.toFixed(1)}%</text>`;
    html += `</g>`;
  }
  // Future shading (if fc tiers exist)
  if (fc.length > 0 && act.length > 0) {
    const fx = xS(act[act.length-1].x);
    html += `<rect x="${fx.toFixed(1)}" y="${yT}" width="${W-5-fx}" height="${yB-yT}" fill="rgba(255,255,255,.025)"/>`;
    html += `<line x1="${fx.toFixed(1)}" y1="${yT}" x2="${fx.toFixed(1)}" y2="${yB}" stroke="rgba(255,255,255,.2)" stroke-width="1.5" stroke-dasharray="4,3"/>`;
    html += `<text x="${(fx+4).toFixed(1)}" y="${yT+10}" font-size="7.5" fill="rgba(255,255,255,.3)">\u25b7 Forecast</text>`;
  }
  // Actuals (green, solid)
  if (act.length > 1) {
    html += `<g class="ser-act"><polyline points="${act.map(p=>`${xS(p.x).toFixed(1)},${yS(p.y).toFixed(1)}`).join(' ')}" fill="none" stroke="rgba(74,222,128,.95)" stroke-width="3"/>`;
    act.forEach(p => html += `<circle cx="${xS(p.x).toFixed(1)}" cy="${yS(p.y).toFixed(1)}" r="4.5" fill="#4ade80"/>`);
    html += '</g>';
  }
  // Reforecast continuation (gold dashed)
  if (fc.length > 0) {
    const bridge = act.length ? `${xS(act[act.length-1].x).toFixed(1)},${yS(act[act.length-1].y).toFixed(1)} ` : '';
    html += `<g class="ser-fc"><polyline points="${bridge}${fc.map(p=>`${xS(p.x).toFixed(1)},${yS(p.y).toFixed(1)}`).join(' ')}" fill="none" stroke="rgba(251,191,36,.8)" stroke-width="2" stroke-dasharray="5,3"/>`;
    fc.forEach(p => html += `<circle cx="${xS(p.x).toFixed(1)}" cy="${yS(p.y).toFixed(1)}" r="3.5" fill="rgba(251,191,36,.7)"/>`);
    html += '</g>';
  }
  svg.innerHTML = html;
}

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', loadProperties);
</script>
{% endblock %}
'''

out_path = os.path.join(os.path.dirname(__file__), 'templates', 'rent_forecast2.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(TEMPLATE)

print(f"Written {len(TEMPLATE):,} chars to {out_path}")
print(f"File size: {os.path.getsize(out_path):,} bytes")
