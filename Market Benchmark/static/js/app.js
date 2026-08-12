/* Market Benchmark — Frontend Logic */
(function() {
    'use strict';

    // ── State ───────────────────────────────────────────────────────────────
    let parentKey = null;
    let dateKey = null;
    let selectedCompKey = null;
    let isReadonly = false;
    // Track modified fields per comp: Map<compKey, Set<fieldId>>
    // fieldId = 'cf:FIELD' for comp-fact, 'fp:KEY:FIELD' for floorplan
    let modifiedFields = new Map();
    let schoolsLoaded = false;

    // ── DOM refs ────────────────────────────────────────────────────────────
    const ddParent = document.getElementById('ddParentProperty');
    const ddWeeks = document.getElementById('ddWeeks');
    const compList = document.getElementById('compList');
    const compFactGrid = document.getElementById('compFactGrid');
    const floorplanGrid = document.getElementById('floorplanGrid');
    const rightPanel = document.querySelector('.right-panel');

    // ── Init ────────────────────────────────────────────────────────────────
    async function init() {
        setupTabs();
        setupTheme();
        setupCollapse();
        await Promise.all([loadParentProperties(), loadWeeks()]);
        ddParent.addEventListener('change', onParentChange);
        ddWeeks.addEventListener('change', onWeekChange);
        document.getElementById('ddAY').addEventListener('change', onAYChange);
    }

    // ── Tabs ────────────────────────────────────────────────────────────────
    function setupTabs() {
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
                if (tab.dataset.tab === 'schools' && !schoolsLoaded) { loadSchools(); schoolsLoaded = true; }
                if (tab.dataset.tab === 'markets' && !marketsLoaded) { loadMarkets(); marketsLoaded = true; }
                if (tab.dataset.tab === 'comps' && !compsLoaded) { loadCompProperties(); compsLoaded = true; }
                if (tab.dataset.tab === 'assign-comps') { loadAssignComps(); }
                if (tab.dataset.tab === 'floorplans') { loadFloorplans(); }
            });
        });
    }

    // ── Theme ───────────────────────────────────────────────────────────────
    function setupTheme() {
        const saved = localStorage.getItem('mrb_theme') || 'dark';
        document.documentElement.setAttribute('data-theme', saved);
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const t = btn.dataset.theme;
                document.documentElement.setAttribute('data-theme', t);
                localStorage.setItem('mrb_theme', t);
            });
        });
    }

    // ── Collapse toggle ─────────────────────────────────────────────────────
    function setupCollapse() {
        const toggle = document.querySelector('.comp-section-toggle');
        if (toggle) {
            toggle.addEventListener('click', () => {
                const section = toggle.closest('.comp-section');
                section.classList.toggle('collapsed');
            });
        }
    }

    // ── Read-only check ─────────────────────────────────────────────────────
    function checkReadonly() {
        if (!dateKey) { isReadonly = false; }
        else {
            const dk = String(dateKey);
            const surveyDate = new Date(dk.slice(0,4) + '-' + dk.slice(4,6) + '-' + dk.slice(6,8));
            const sixDaysAgo = new Date();
            sixDaysAgo.setDate(sixDaysAgo.getDate() - 7);
            sixDaysAgo.setHours(0,0,0,0);
            isReadonly = surveyDate < sixDaysAgo;
        }
        if (isReadonly) {
            rightPanel.classList.add('readonly-mode');
        } else {
            rightPanel.classList.remove('readonly-mode');
        }
    }

    // ── Load Parent Properties ──────────────────────────────────────────────
    let parentPropsData = [];

    async function loadParentProperties() {
        const resp = await fetch('/api/parent-properties');
        parentPropsData = await resp.json();
        ddParent.innerHTML = '<option value="">— Select Property —</option>' +
            parentPropsData.map(p => `<option value="${p.key}">${p.name}</option>`).join('');
    }

    function getParentMarketKey() {
        if (!parentKey) return null;
        const p = parentPropsData.find(x => x.key === parentKey);
        return p ? p.market_key : null;
    }

    // ── Load Weeks ──────────────────────────────────────────────────────────
    async function loadWeeks() {
        const ay = document.getElementById('ddAY').value || '2026';
        const resp = await fetch(`/api/weeks?ay=${ay}`);
        const data = await resp.json();
        ddWeeks.innerHTML = '<option value="">— Select Week —</option>' +
            data.map(w => `<option value="${w.date_key}">${w.date_key} (wk ${w.relative_week})</option>`).join('');
    }

    // ── Event Handlers ──────────────────────────────────────────────────────
    function onParentChange() {
        parentKey = parseInt(ddParent.value) || null;
        modifiedFields = new Map();
        loadComps();
        const activeTab = document.querySelector('.tab.active');
        if (activeTab && activeTab.dataset.tab === 'assign-comps') loadAssignComps();
        if (activeTab && activeTab.dataset.tab === 'floorplans') loadFloorplans();
    }

    function onWeekChange() {
        dateKey = parseInt(ddWeeks.value) || null;
        modifiedFields = new Map();
        checkReadonly();
        loadComps();
        const activeTab = document.querySelector('.tab.active');
        if (activeTab && activeTab.dataset.tab === 'assign-comps') loadAssignComps();
    }

    function onAYChange() {
        loadWeeks();
    }

    async function loadComps() {
        compList.innerHTML = '';
        compFactGrid.innerHTML = '';
        floorplanGrid.innerHTML = '';
        selectedCompKey = null;
        if (!parentKey || !dateKey) return;

        const resp = await fetch(`/api/comp-assignments?parent_key=${parentKey}&date_key=${dateKey}`);
        const data = await resp.json();
        if (!data.length) {
            compList.innerHTML = '<div class="placeholder" style="padding:12px;font-size:0.85rem;">No comp assignments for this week yet.</div>';
            return;
        }
        compList.innerHTML = data.map(c =>
            `<div class="comp-item" data-key="${c.comp_property_key}" data-name="${(c.comp_property_name||'').replace(/"/g,'&quot;')}">
                <span class="comp-rank">#${c.rank_order}</span>${c.comp_property_name}
            </div>`
        ).join('');

        compList.querySelectorAll('.comp-item').forEach(el => {
            el.addEventListener('click', () => selectComp(el));
        });
    }

    async function selectComp(el) {
        compList.querySelectorAll('.comp-item').forEach(e => e.classList.remove('active'));
        el.classList.add('active');
        selectedCompKey = parseInt(el.dataset.key);
        await Promise.all([loadCompFact(), loadFloorplanFact()]);
        reapplyModified(selectedCompKey);
        // If Floor Plans tab is active, reload it for this comp (keepSearch=true)
        const activeTab = document.querySelector('.tab.active');
        if (activeTab && activeTab.dataset.tab === 'floorplans') {
            fpSelectedKey = null;
            closeFpDetail();
            await loadFloorplans(selectedCompKey, el.dataset.name || '', true);
        }
    }

    // ── Helpers ─────────────────────────────────────────────────────────────
    function v(val) { return val != null && val !== '' ? val : '—'; }
    function chk(val) { return val ? 'checked' : ''; }

    // ── Load Comp Fact ──────────────────────────────────────────────────────
    async function loadCompFact() {
        if (!selectedCompKey || !dateKey) return;
        const resp = await fetch(`/api/comp-fact?property_key=${selectedCompKey}&date_key=${dateKey}`);
        const data = await resp.json();
        if (!data.length) {
            compFactGrid.innerHTML = '<p class="placeholder">No comp data for this selection.</p>';
            return;
        }
        const r = data[0];
        compFactGrid.innerHTML = `
        <div class="comp-card">
            <div class="comp-card-header">
                <div>
                    <div class="comp-card-title">${v(r.PROPERTY_NAME)}</div>
                    <div class="comp-card-stats">
                        <span>Units:<span class="stat-val">${v(r.APARTMENT_COUNT)}</span></span>
                        <span>Beds:<span class="stat-val">${v(r.BED_COUNT_COMPILED)}</span></span>
                        <span>Market:<span class="stat-val">${v(r.MARKET_CITY_STATE)}</span></span>
                    </div>
                </div>
                <div class="comp-card-meta">
                    Survey Date: <span class="meta-val">${v(r.DATE_KEY)}</span><br>
                    AY: <span class="meta-val">${document.getElementById('ddAY').value}</span>
                </div>
            </div>

            <div class="waived-section">
                <h4>Waived Premiums</h4>
                <div class="waived-grid">
                    <div class="waived-item"><input type="checkbox" ${chk(r.PREMIUM_01_WAIVED)} data-field="PREMIUM_01_WAIVED"><span class="waived-label">5-Mo</span><input type="number" value="${r.PREMIUM_01 || ''}" data-field="PREMIUM_01"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.PREMIUM_02_WAIVED)} data-field="PREMIUM_02_WAIVED"><span class="waived-label">10-Mo</span><input type="number" value="${r.PREMIUM_02 || ''}" data-field="PREMIUM_02"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.PREMIUM_03_WAIVED)} data-field="PREMIUM_03_WAIVED"><span class="waived-label">View</span><input type="number" value="${r.PREMIUM_03 || ''}" data-field="PREMIUM_03"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.PREMIUM_04_WAIVED)} data-field="PREMIUM_04_WAIVED"><span class="waived-label">Floor</span><input type="number" value="${r.PREMIUM_04 || ''}" data-field="PREMIUM_04"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.PREMIUM_05_WAIVED)} data-field="PREMIUM_05_WAIVED"><span class="waived-label">Bldg</span><input type="number" value="${r.PREMIUM_05 || ''}" data-field="PREMIUM_05"></div>
                </div>
            </div>

            <div class="waived-section">
                <h4>Waived Fees</h4>
                <div class="waived-grid">
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_01_WAIVED)} data-field="FEE_01_WAIVED"><span class="waived-label">App Fee</span><input type="number" value="${r.FEE_01 || ''}" data-field="FEE_01"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_02_WAIVED)} data-field="FEE_02_WAIVED"><span class="waived-label">Admin</span><input type="number" value="${r.FEE_02 || ''}" data-field="FEE_02"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_03_WAIVED)} data-field="FEE_03_WAIVED"><span class="waived-label">Amenity</span><input type="number" value="${r.FEE_03 || ''}" data-field="FEE_03"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_04_WAIVED)} data-field="FEE_04_WAIVED"><span class="waived-label">Move-In</span><input type="number" value="${r.FEE_04 || ''}" data-field="FEE_04"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_05_WAIVED)} data-field="FEE_05_WAIVED"><span class="waived-label">Pet</span><input type="number" value="${r.FEE_05 || ''}" data-field="FEE_05"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_06_WAIVED)} data-field="FEE_06_WAIVED"><span class="waived-label">Pet Rent</span><input type="number" value="${r.FEE_06 || ''}" data-field="FEE_06"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_07_WAIVED)} data-field="FEE_07_WAIVED"><span class="waived-label">Furniture</span><input type="number" value="${r.FEE_07 || ''}" data-field="FEE_07"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_08_WAIVED)} data-field="FEE_08_WAIVED"><span class="waived-label">Parking</span><input type="number" value="${r.FEE_08 || ''}" data-field="FEE_08"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_09_WAIVED)} data-field="FEE_09_WAIVED"><span class="waived-label">Water</span><input type="number" value="${r.FEE_09 || ''}" data-field="FEE_09"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_10_WAIVED)} data-field="FEE_10_WAIVED"><span class="waived-label">Gas</span><input type="number" value="${r.FEE_10 || ''}" data-field="FEE_10"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_11_WAIVED)} data-field="FEE_11_WAIVED"><span class="waived-label">Electric</span><input type="number" value="${r.FEE_11 || ''}" data-field="FEE_11"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.FEE_12_WAIVED)} data-field="FEE_12_WAIVED"><span class="waived-label">Trash</span><input type="number" value="${r.FEE_12 || ''}" data-field="FEE_12"></div>
                    <div class="waived-item"><input type="checkbox" ${chk(r.DEPOSIT_WAIVED)} data-field="DEPOSIT_WAIVED"><span class="waived-label">Deposit</span></div>
                </div>
            </div>

            <div class="swot-row">
                <div class="swot-cell"><div class="swot-label">Opportunity</div><div class="swot-val">${v(r.SUMMARY_COMP_OPPORTUNITY)}</div></div>
                <div class="swot-cell"><div class="swot-label">Strength</div><div class="swot-val">${v(r.SUMMARY_COMP_STRENGTH)}</div></div>
                <div class="swot-cell"><div class="swot-label">Weakness</div><div class="swot-val">${v(r.SUMMARY_COMP_WEAKNESS)}</div></div>
                <div class="swot-cell"><div class="swot-label">Threat</div><div class="swot-val">${v(r.SUMMARY_COMP_THREAT)}</div></div>
            </div>
        </div>`;
    }

    // ── Load Floorplan Fact ─────────────────────────────────────────────────
    async function loadFloorplanFact() {
        if (!selectedCompKey || !dateKey) return;
        const resp = await fetch(`/api/floorplan-fact?property_key=${selectedCompKey}&date_key=${dateKey}`);
        const data = await resp.json();
        if (!data.length) {
            floorplanGrid.innerHTML = '<p class="placeholder">No floorplan data for this selection.</p>';
            return;
        }
        floorplanGrid.classList.add('floorplan-grid');
        floorplanGrid.innerHTML = `<table>
            <tr>
                <th>Floorplan</th><th>Type</th><th>Compare As</th><th>Units</th><th>Beds</th>
                <th>Fall Rent</th><th>Concession</th><th>Gift</th><th>Current Rent</th>
                <th>Sold Out</th><th>No Online</th>
            </tr>
            ${data.map(fp => `<tr>
                <td><strong>${fp.FLOORPLAN_NAME || ''}</strong></td>
                <td>${fp.FLOORPLAN_TYPE || ''}</td>
                <td>${fp.COMPARE_AS_FLOORPLAN_TYPE || ''}</td>
                <td>${fp.APARTMENT_COUNT || ''}</td>
                <td>${fp.BED_COUNT || ''}</td>
                <td><input type="number" value="${fp.RENT_PRELEASE_FURNISHED || ''}" data-key="${fp.FLOORPLAN_ASSIGNMENT_KEY}" data-field="RENT_PRELEASE_FURNISHED"></td>
                <td><input type="number" value="${fp.CONCESSION_ANNUAL_AMOUNT || ''}" data-key="${fp.FLOORPLAN_ASSIGNMENT_KEY}" data-field="CONCESSION_ANNUAL_AMOUNT"></td>
                <td><input type="number" value="${fp.GIFT_INCENTIVE_ANNUAL_AMOUNT || ''}" data-key="${fp.FLOORPLAN_ASSIGNMENT_KEY}" data-field="GIFT_INCENTIVE_ANNUAL_AMOUNT"></td>
                <td><input type="number" value="${fp.RENT_CURRENT_TERM_FURNISHED || ''}" data-key="${fp.FLOORPLAN_ASSIGNMENT_KEY}" data-field="RENT_CURRENT_TERM_FURNISHED"></td>
                <td class="chk-cell"><input type="checkbox" ${fp.FLAG_SOLD_OUT ? 'checked' : ''} data-key="${fp.FLOORPLAN_ASSIGNMENT_KEY}" data-field="FLAG_SOLD_OUT"></td>
                <td class="chk-cell"><input type="checkbox" ${fp.FLAG_NO_PRICING_ONLINE ? 'checked' : ''} data-key="${fp.FLOORPLAN_ASSIGNMENT_KEY}" data-field="FLAG_NO_PRICING_ONLINE"></td>
            </tr>`).join('')}
        </table>`;
    }

    // ── Boot ────────────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', init);

    // ── Auto-save: Floorplan fields ─────────────────────────────────────────
    document.addEventListener('change', async (e) => {
        if (isReadonly) return;
        const el = e.target;
        const key = el.dataset.key;
        const field = el.dataset.field;
        if (!key || !field) return;
        // It's a floorplan field
        const value = el.type === 'checkbox' ? (el.checked ? 1 : 0) : (el.value || null);
        const resp = await fetch('/api/floorplan-fact/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                floorplan_assignment_key: parseInt(key),
                date_key: dateKey,
                field: field,
                value: value
            })
        });
        if (resp.ok) {
            el.classList.add('field-modified');
            trackModified(selectedCompKey, `fp:${key}:${field}`);
        } else {
            el.style.borderColor = '#ef4444';
            setTimeout(() => { el.style.borderColor = ''; }, 2000);
        }
    });

    // ── Auto-save: Comp Fact fields (no data-key, just data-field) ──────────
    document.addEventListener('change', async (e) => {
        if (isReadonly) return;
        const el = e.target;
        if (el.dataset.key) return; // skip floorplan fields (handled above)
        const field = el.dataset.field;
        if (!field || !selectedCompKey || !dateKey) return;
        const value = el.type === 'checkbox' ? (el.checked ? 1 : 0) : (el.value || null);
        const resp = await fetch('/api/comp-fact/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                property_key: selectedCompKey,
                date_key: dateKey,
                field: field,
                value: value
            })
        });
        if (resp.ok) {
            el.classList.add('field-modified');
            trackModified(selectedCompKey, `cf:${field}`);
        } else {
            el.style.borderColor = '#ef4444';
            setTimeout(() => { el.style.borderColor = ''; }, 2000);
        }
    });

    // ── Modified-field tracking ─────────────────────────────────────────────
    function trackModified(compKey, fieldId) {
        if (!modifiedFields.has(compKey)) modifiedFields.set(compKey, new Set());
        modifiedFields.get(compKey).add(fieldId);
    }

    function reapplyModified(compKey) {
        const set = modifiedFields.get(compKey);
        if (!set) return;
        set.forEach(id => {
            if (id.startsWith('cf:')) {
                const f = id.slice(3);
                const el = compFactGrid.querySelector(`[data-field="${f}"]`);
                if (el) el.classList.add('field-modified');
            } else if (id.startsWith('fp:')) {
                const [, k, f] = id.split(':');
                const el = floorplanGrid.querySelector(`[data-key="${k}"][data-field="${f}"]`);
                if (el) el.classList.add('field-modified');
            }
        });
    }

    // ── Schools Tab ─────────────────────────────────────────────────────────
    const schoolsGrid = document.getElementById('schoolsGrid');
    const schoolSearch = document.getElementById('schoolSearch');
    const schoolShowInactive = document.getElementById('schoolShowInactive');
    const btnAddSchool = document.getElementById('btnAddSchool');
    let schoolsData = [];
    let marketsData = [];

    schoolSearch.addEventListener('input', debounce(loadSchools, 300));
    schoolShowInactive.addEventListener('change', loadSchools);
    btnAddSchool.addEventListener('click', addSchool);

    async function loadSchools() {
        const q = schoolSearch.value.trim();
        const showInactive = schoolShowInactive.checked;
        const url = q ? `/api/schools?q=${encodeURIComponent(q)}` : `/api/schools`;
        const [schoolResp, marketResp] = await Promise.all([fetch(url), marketsData.length ? null : fetch('/api/markets')].filter(Boolean));
        schoolsData = await schoolResp.json();
        if (marketResp) marketsData = await marketResp.json();
        renderSchools(showInactive ? schoolsData : schoolsData.filter(s => s.FLAG_ACTIVE));
    }

    function renderSchools(data) {
        if (!data.length) {
            schoolsGrid.innerHTML = '<p class="placeholder" style="padding:12px;">No schools found.</p>';
            return;
        }
        const cols = [
            { key: 'SCHOOL_NAME', label: 'School Name', type: 'text', cls: 'school-name-input' },
            { key: 'SCHOOL_TYPE', label: 'Type', type: 'text' },
            { key: 'MARKET_KEY', label: 'Market', type: 'select' },
            { key: 'SCHOOL_ADDRESS1', label: 'Address', type: 'text' },
            { key: 'SCHOOL_CITY', label: 'City', type: 'text' },
            { key: 'SCHOOL_STATE', label: 'St', type: 'text' },
            { key: 'SCHOOL_ZIP', label: 'Zip', type: 'text' },
            { key: 'SCHOOL_PHONE1', label: 'Phone', type: 'text' },
            { key: 'STUDENTS_ENROLLED', label: 'Enrolled', type: 'number' },
            { key: 'STUDENTS_UNDERGRADUATE', label: 'Undergrad', type: 'number' },
            { key: 'STUDENTS_GRADUATE', label: 'Grad', type: 'number' },
            { key: 'STUDENTS_ONLINE', label: 'Online', type: 'number' },
            { key: 'STUDENTS_ONSITE', label: 'On-Site', type: 'number' },
            { key: 'STUDENTS_INTERNATIONAL', label: 'Intl', type: 'number' },
            { key: 'BEDS_ON_CAMPUS', label: 'Beds', type: 'number' },
            { key: 'BEDS_ON_CAMPUS_OCCUPIED', label: 'Beds Occ', type: 'number' },
        ];
        const ths = cols.map(c => `<th>${c.label}</th>`).join('') + '<th></th>';
        const marketOpts = marketsData.map(m =>
            `<option value="${m.key}">${m.name}</option>`
        ).join('');
        const rows = data.map(s => {
            const inactive = !s.FLAG_ACTIVE;
            const tds = cols.map(c => {
                if (c.type === 'select') {
                    const sel = s[c.key];
                    return `<td><select data-school-key="${s.SCHOOL_KEY}" data-field="${c.key}">
                        <option value="">—</option>${marketOpts.replace(`value="${sel}"`, `value="${sel}" selected`)}
                    </select></td>`;
                }
                const val = s[c.key] != null ? s[c.key] : '';
                const cls = c.cls ? ` class="${c.cls}"` : '';
                return `<td><input type="${c.type}" value="${String(val).replace(/"/g, '&quot;')}" data-school-key="${s.SCHOOL_KEY}" data-field="${c.key}"${cls}></td>`;
            }).join('');
            const actionBtn = inactive
                ? `<button class="btn-activate" data-school-key="${s.SCHOOL_KEY}" data-action="activate">Activate</button>`
                : `<button class="btn-deactivate" data-school-key="${s.SCHOOL_KEY}" data-action="deactivate">Deactivate</button>`;
            return `<tr class="${inactive ? 'school-inactive' : ''}">${tds}<td>${actionBtn}</td></tr>`;
        }).join('');
        schoolsGrid.innerHTML = `<table><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table>`;

        // Auto-save on field change (inputs and selects)
        schoolsGrid.querySelectorAll('input, select').forEach(el => {
            el.addEventListener('change', async () => {
                const sk = parseInt(el.dataset.schoolKey);
                const field = el.dataset.field;
                let value;
                if (el.tagName === 'SELECT') {
                    value = el.value ? parseInt(el.value) : null;
                    // Also update MARKET_CITY_STATE denormalized field
                    const mkt = marketsData.find(m => m.key === value);
                    if (mkt) {
                        await fetch('/api/schools/update', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ school_key: sk, field: 'MARKET_CITY_STATE', value: mkt.name })
                        });
                    }
                } else if (el.type === 'number') {
                    value = el.value ? parseInt(el.value) : null;
                } else {
                    value = el.value || null;
                }
                const resp = await fetch('/api/schools/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ school_key: sk, field, value })
                });
                if (resp.ok) {
                    el.classList.add('field-modified');
                } else {
                    el.style.borderColor = '#ef4444';
                    setTimeout(() => { el.style.borderColor = ''; }, 2000);
                }
            });
        });

        // Activate/Deactivate buttons
        schoolsGrid.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const sk = parseInt(btn.dataset.schoolKey);
                const val = btn.dataset.action === 'activate' ? 1 : 0;
                const resp = await fetch('/api/schools/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ school_key: sk, field: 'FLAG_ACTIVE', value: val })
                });
                if (resp.ok) loadSchools();
            });
        });
    }

    async function addSchool() {
        const name = prompt('Enter new school name:');
        if (!name) return;
        const resp = await fetch('/api/schools/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ school_name: name })
        });
        if (resp.ok) {
            schoolSearch.value = name;
            loadSchools();
        }
    }

    // ── Markets Tab ─────────────────────────────────────────────────────────
    const marketsGridEl = document.getElementById('marketsGrid');
    const marketSearchEl = document.getElementById('marketSearch');
    const btnAddMarket = document.getElementById('btnAddMarket');
    let marketsLoaded = false;

    marketSearchEl.addEventListener('input', debounce(loadMarkets, 300));
    btnAddMarket.addEventListener('click', addMarket);

    async function loadMarkets() {
        const q = marketSearchEl.value.trim();
        const url = q ? `/api/markets/all?q=${encodeURIComponent(q)}` : `/api/markets/all`;
        const resp = await fetch(url);
        const data = await resp.json();
        renderMarkets(data);
    }

    function renderMarkets(data) {
        if (!data.length) {
            marketsGridEl.innerHTML = '<p class="placeholder" style="padding:12px;">No markets found.</p>';
            return;
        }
        const rows = data.map(m => {
            const key = m.MARKET_KEY;
            const city = (m.MARKET_CITY || '').replace(/"/g, '&quot;');
            const st = (m.MARKET_STATE || '').replace(/"/g, '&quot;');
            const cs = city && st ? `${city.toUpperCase()}, ${st.toUpperCase()}` : '';
            const missingCity = !m.MARKET_CITY;
            const missingSt = !m.MARKET_STATE;
            const missingAny = missingCity || missingSt;
            const orangeStyle = 'border-color:#f97316;box-shadow:0 0 0 1px #f97316;';
            return `<tr>
                <td><input type="number" value="${key}" disabled style="width:50px;opacity:0.6;"></td>
                <td><input type="text" value="${city}" data-market-key="${key}" data-field="MARKET_CITY" style="min-width:160px;${missingCity ? orangeStyle : ''}"></td>
                <td><input type="text" value="${st}" data-market-key="${key}" data-field="MARKET_STATE" style="width:40px;text-transform:uppercase;${missingSt ? orangeStyle : ''}"></td>
                <td><input type="text" value="${cs}" disabled style="min-width:180px;opacity:0.7;${missingAny ? orangeStyle : ''}"></td>
                <td><button class="btn-delete-market" data-market-key="${key}" title="Delete">🗑️</button></td>
            </tr>`;
        }).join('');
        marketsGridEl.innerHTML = `<table>
            <thead><tr><th>Key</th><th>City</th><th>St</th><th>City, State</th><th></th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;

        marketsGridEl.querySelectorAll('input:not([disabled])').forEach(el => {
            el.addEventListener('change', async () => {
                const mk = parseInt(el.dataset.marketKey);
                const field = el.dataset.field;
                const value = el.value || null;
                const resp = await fetch('/api/markets/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ market_key: mk, field, value })
                });
                if (resp.ok) {
                    el.classList.add('field-modified');
                    // Auto-update MARKET_CITY_STATE
                    const row = el.closest('tr');
                    const cityEl = row.querySelector('[data-field="MARKET_CITY"]');
                    const stEl = row.querySelector('[data-field="MARKET_STATE"]');
                    const csEl = row.querySelectorAll('input')[3]; // disabled city_state
                    const c = (cityEl.value || '').toUpperCase();
                    const s = (stEl.value || '').toUpperCase();
                    const newCS = c && s ? `${c}, ${s}` : '';
                    csEl.value = newCS;
                    // Save city_state
                    await fetch('/api/markets/update', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ market_key: mk, field: 'MARKET_CITY_STATE', value: newCS || null })
                    });
                    // Update orange highlights
                    cityEl.style.borderColor = c ? '' : '#f97316';
                    cityEl.style.boxShadow = c ? '' : '0 0 0 1px #f97316';
                    stEl.style.borderColor = s ? '' : '#f97316';
                    stEl.style.boxShadow = s ? '' : '0 0 0 1px #f97316';
                    csEl.style.borderColor = (c && s) ? '' : '#f97316';
                    csEl.style.boxShadow = (c && s) ? '' : '0 0 0 1px #f97316';
                } else {
                    el.style.borderColor = '#ef4444';
                    setTimeout(() => { el.style.borderColor = ''; }, 2000);
                }
            });
        });

        // Delete buttons
        marketsGridEl.querySelectorAll('.btn-delete-market').forEach(btn => {
            btn.addEventListener('click', async () => {
                if (!confirm('Delete this market?')) return;
                const mk = parseInt(btn.dataset.marketKey);
                const resp = await fetch('/api/markets/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ market_key: mk })
                });
                if (resp.ok) loadMarkets();
            });
        });
    }

    async function addMarket() {
        const city = prompt('Enter city name:');
        if (!city) return;
        const state = prompt('Enter 2-letter state code:');
        if (!state) return;
        const resp = await fetch('/api/markets/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ city, state })
        });
        if (resp.ok) {
            marketSearchEl.value = city;
            loadMarkets();
        }
    }

    // ── Comps Tab ───────────────────────────────────────────────────────────
    const compsGridEl = document.getElementById('compsGrid');
    const compSearchEl = document.getElementById('compSearch');
    const compShowInactive = document.getElementById('compShowInactive');
    const btnAddComp = document.getElementById('btnAddComp');
    let compsLoaded = false;

    compSearchEl.addEventListener('input', debounce(loadCompProperties, 300));
    compShowInactive.addEventListener('change', loadCompProperties);
    btnAddComp.addEventListener('click', addCompProperty);

    async function loadCompProperties() {
        const q = compSearchEl.value.trim();
        const inactive = compShowInactive.checked ? '1' : '0';
        if (!marketsData.length) {
            const mr = await fetch('/api/markets');
            marketsData = await mr.json();
        }
        const url = `/api/comp-properties?q=${encodeURIComponent(q)}&inactive=${inactive}`;
        const resp = await fetch(url);
        const data = await resp.json();
        renderCompProperties(data);
    }

    function renderCompProperties(data) {
        if (!data.length) {
            compsGridEl.innerHTML = '<p class="placeholder" style="padding:12px;">No comp properties found.</p>';
            return;
        }
        const cols = [
            { key: 'PROPERTY_NAME', label: 'Property Name', type: 'text', style: 'min-width:240px;font-weight:600;' },
            { key: 'ADDRESS_CITY', label: 'City', type: 'text', style: 'min-width:100px;' },
            { key: 'ADDRESS_STATE', label: 'St', type: 'text', style: 'width:40px;text-transform:uppercase;' },
            { key: 'MARKET_KEY', label: 'Market', type: 'select' },
            { key: 'BED_COUNT_STATIC', label: 'Beds', type: 'number', style: 'width:65px;' },
            { key: 'APARTMENT_COUNT', label: 'Units', type: 'number', style: 'width:65px;' },
        ];
        const marketOpts = marketsData.map(m => `<option value="${m.key}">${m.name}</option>`).join('');
        const ths = cols.map(c => `<th>${c.label}</th>`).join('') + '<th></th>';
        const rows = data.map(cp => {
            const inactive = !cp.FLAG_ACTIVE;
            const tds = cols.map(c => {
                if (c.type === 'select') {
                    const sel = cp[c.key];
                    const missing = sel == null;
                    const mStyle = missing ? 'border-color:#eab308;box-shadow:0 0 0 1px #eab308;' : '';
                    return `<td><select data-comp-key="${cp.PROPERTY_KEY}" data-field="${c.key}" style="${mStyle}">
                        <option value="">—</option>${marketOpts.replace(`value="${sel}"`, `value="${sel}" selected`)}
                    </select></td>`;
                }
                const val = cp[c.key] != null ? cp[c.key] : '';
                const empty = val === '' || val === 0;
                const critical = (c.key === 'BED_COUNT_STATIC' || c.key === 'APARTMENT_COUNT');
                let highlight = '';
                if (empty) highlight = critical ? 'border-color:#f97316;box-shadow:0 0 0 1px #f97316;' : 'border-color:#eab308;box-shadow:0 0 0 1px #eab308;';
                const st = (c.style || '') + highlight;
                return `<td><input type="${c.type}" value="${String(val).replace(/"/g, '&quot;')}" data-comp-key="${cp.PROPERTY_KEY}" data-field="${c.key}" style="${st}"></td>`;
            }).join('');
            const actionBtn = inactive
                ? `<button class="btn-activate" data-comp-key="${cp.PROPERTY_KEY}" data-action="activate">Activate</button>`
                : `<button class="btn-deactivate" data-comp-key="${cp.PROPERTY_KEY}" data-action="deactivate">Deactivate</button>`;
            return `<tr class="${inactive ? 'school-inactive' : ''}" data-pk="${cp.PROPERTY_KEY}">${tds}<td>${actionBtn}</td></tr>`;
        }).join('');
        compsGridEl.innerHTML = `<table><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table>`;

        // Auto-save on field change
        compsGridEl.querySelectorAll('input, select').forEach(el => {
            el.addEventListener('change', async (e) => {
                e.stopPropagation();
                const pk = parseInt(el.dataset.compKey);
                const field = el.dataset.field;
                let value;
                if (el.type === 'checkbox') {
                    value = el.checked ? 1 : 0;
                } else if (el.tagName === 'SELECT') {
                    value = el.value ? parseInt(el.value) : null;
                    if (field === 'MARKET_KEY' && value) {
                        const mkt = marketsData.find(m => m.key === value);
                        if (mkt) await fetch('/api/comp-properties/update', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({property_key:pk, field:'MARKET_CITY_STATE', value:mkt.name}) });
                    }
                } else if (el.type === 'number') {
                    value = el.value !== '' ? parseFloat(el.value) : null;
                } else {
                    value = el.value || null;
                }
                const resp = await fetch('/api/comp-properties/update', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({property_key:pk, field, value}) });
                if (resp.ok) el.classList.add('field-modified');
                else { el.style.borderColor = '#ef4444'; setTimeout(() => { el.style.borderColor = ''; }, 2000); }
            });
        });

        // Row click opens detail (any cell, including inputs)
        compsGridEl.querySelectorAll('tr[data-pk]').forEach(row => {
            row.addEventListener('click', (e) => {
                if (e.target.tagName === 'BUTTON') return;
                openCompDetail(parseInt(row.dataset.pk));
            });
        });

        // Activate/Deactivate buttons
        compsGridEl.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const pk = parseInt(btn.dataset.compKey);
                const val = btn.dataset.action === 'activate' ? 1 : 0;
                await fetch('/api/comp-properties/update', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({property_key:pk, field:'FLAG_ACTIVE', value:val}) });
                loadCompProperties();
            });
        });
    }

    async function addCompProperty() {
        const name = prompt('Enter new comp property name:');
        if (!name) return;
        const resp = await fetch('/api/comp-properties/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ property_name: name })
        });
        if (resp.ok) {
            compSearchEl.value = name;
            loadCompProperties();
        }
    }

    // ── Comp Detail Slide-out Panel ─────────────────────────────────────────
    const compDetailOverlay = document.getElementById('compDetailOverlay');
    const compDetailBody = document.getElementById('compDetailBody');
    const compDetailName = document.getElementById('compDetailName');
    const compJumpSearch = document.getElementById('compJumpSearch');
    const compGearBtn = document.getElementById('compGearBtn');
    const compSettingsOverlay = document.getElementById('compSettingsOverlay');
    const compSettingsModal = document.getElementById('compSettingsModal');
    const compSettingsList = document.getElementById('compSettingsList');
    let compDetailData = {};
    let compDetailPK = null;
    let compDetailSort = 'category'; // 'category' or 'az'
    let schoolsListCache = []; // for school dropdowns

    // Field categories
    const COMP_CATEGORIES = [
        { name: 'Identity', fields: ['PROPERTY_NAME','ADDRESS_1','ADDRESS_CITY','ADDRESS_STATE','ADDRESS_ZIP','PHONE_1','URL_WEBSITE','URL_FACEBOOK','URL_INSTAGRAM','URL_TWITTER'] },
        { name: 'Market & Location', fields: ['MARKET_KEY','MARKET_CITY','MARKET_STATE','MARKET_CITY_STATE','DISTANCE_TO_CAMPUS','LATITUDE','LONGITUDE','TIME_ZONE'] },
        { name: 'Physical', fields: ['BED_COUNT_STATIC','BED_COUNT_COMPILED','APARTMENT_COUNT','BUILD_YEAR','ASSET_CLASS'] },
        { name: 'Ownership', fields: ['COMPANY','OWNER','OWNER_GROUP','PM_NAME'] },
        { name: 'Status & Flags', fields: ['FLAG_ACTIVE','FLAG_COMP','FLAG_PARENT','FLAG_REPORTABLE','FLAG_DISPOSITIONED','FLAG_MIXED_USE','FLAG_STUDENT_ONLY','FLAG_CONVENTIONAL_ONLY','FLAG_INCLUDE_COMP','FLAG_EXCLUDE_FROM_CALCS','FLAG_COMPLETE_LOGIC','STATUS','DATE_DISPOSITIONED','DATE_LAST_UPDATED'] },
        { name: 'SWOT', fields: ['STRENGTH','WEAKNESS','OPPORTUNITY','THREAT'] },
        { name: 'Amenities', fields: ['AMENITY_FREE_TEXT','FLAG_AMENITY_BASKETBALL','FLAG_AMENITY_BUSINESS_CTR','FLAG_AMENITY_COFFEE_BAR','FLAG_AMENITY_COURTYARDS','FLAG_AMENITY_FIRE_PITS','FLAG_AMENITY_FITNESS_CTR','FLAG_AMENITY_GAME_ROOM','FLAG_AMENITY_GOLF_SIMULATOR','FLAG_AMENITY_HAMMOCKS','FLAG_AMENITY_HOT_TUB','FLAG_AMENITY_ON_BUS_ROUTE','FLAG_AMENITY_ON_SITE_RETAIL','FLAG_AMENITY_OUTDOOR_GRILLING','FLAG_AMENITY_PACKAGE_LOCKERS','FLAG_AMENITY_POOL','FLAG_AMENITY_SHUTTLE','FLAG_AMENITY_STUDY_ROOMS','FLAG_AMENITY_TANNING','FLAG_AMENITY_TENNIS','FLAG_AMENITY_THEATER','FLAG_AMENITY_VOLLEYBALL'] },
        { name: 'Schools', fields: ['SCHOOL_KEY_1','SCHOOL_NAME_1','SCHOOL_NOTES_1','SCHOOL_KEY_2','SCHOOL_NAME_2','SCHOOL_NOTES_2','SCHOOL_KEY_3','SCHOOL_NAME_3','SCHOOL_NOTES_3','SCHOOL_KEY_4','SCHOOL_NAME_4','SCHOOL_NOTES_4','SCHOOL_KEY_5','SCHOOL_NAME_5','SCHOOL_NOTES_5'] },
        { name: 'Fees (Static)', fields: ['FEE_ADMIN','FEE_AMENITY','FEE_APPLICATION','FEE_CABLE','FEE_ELECTRIC','FEE_FURNITURE','FEE_GAS','FEE_INTERNET','FEE_MOVEIN','FEE_MOVEOUT','FEE_OTHER1','FEE_PARKING','FEE_PET','FEE_PET_RENT','FEE_TRASH','FEE_WATER','FEE_OTHER2','FEE_OTHER3','FEE_OTHER4','FEE_OTHER5'] },
        { name: 'Deposit', fields: ['DEPOSIT_AMOUNT','DEPOSIT_AMOUNT_U','DEPOSIT_WAIVED'] },
    ];

    // Load settings from localStorage
    let compFieldSettings = JSON.parse(localStorage.getItem('mrb_comp_fields') || 'null');
    if (!compFieldSettings) {
        compFieldSettings = COMP_CATEGORIES.map(cat => ({ name: cat.name, visible: true, fields: cat.fields.map(f => ({ key: f, visible: true })) }));
    }

    function saveFieldSettings() { localStorage.setItem('mrb_comp_fields', JSON.stringify(compFieldSettings)); }

    document.getElementById('compDetailClose').addEventListener('click', closeCompDetail);
    compGearBtn.addEventListener('click', openCompSettings);
    document.getElementById('compSettingsClose').addEventListener('click', closeCompSettings);
    compSettingsOverlay.addEventListener('click', closeCompSettings);

    // Sort toggle
    document.querySelectorAll('.comp-sort-toggle button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.comp-sort-toggle button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            compDetailSort = btn.dataset.sort;
            renderCompDetail();
        });
    });

    // Jump search
    compJumpSearch.addEventListener('input', () => {
        const q = compJumpSearch.value.toLowerCase();
        compDetailBody.querySelectorAll('.comp-detail-row').forEach(row => {
            row.classList.remove('highlighted');
            if (q && row.dataset.field.toLowerCase().includes(q)) row.classList.add('highlighted');
        });
        // Scroll to first match
        const first = compDetailBody.querySelector('.comp-detail-row.highlighted');
        if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });

    // Resize handle
    const resizeHandle = document.getElementById('compResizeHandle');
    resizeHandle.addEventListener('mousedown', (e) => {
        e.preventDefault();
        const startX = e.clientX;
        const startW = compDetailOverlay.offsetWidth;
        function onMove(ev) { compDetailOverlay.style.width = Math.max(380, startW - (ev.clientX - startX)) + 'px'; }
        function onUp() { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); }
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    });

    async function openCompDetail(pk) {
        compDetailPK = pk;
        compDetailOverlay.classList.add('open');
        if (!schoolsListCache.length) {
            const sr = await fetch('/api/schools');
            schoolsListCache = await sr.json();
        }
        const resp = await fetch(`/api/comp-properties/detail?property_key=${pk}`);
        compDetailData = await resp.json();
        compDetailName.textContent = compDetailData.PROPERTY_NAME || `Key: ${pk}`;
        renderCompDetail();
    }

    function closeCompDetail() { compDetailOverlay.classList.remove('open'); }

    function renderCompDetail() {
        const d = compDetailData;
        if (!d || !d.PROPERTY_KEY) return;

        if (compDetailSort === 'az') {
            // Flat alphabetical list of all visible fields
            const allFields = [];
            compFieldSettings.forEach(cat => {
                if (!cat.visible) return;
                cat.fields.forEach(f => { if (f.visible) allFields.push(f.key); });
            });
            allFields.sort();
            compDetailBody.innerHTML = allFields.map(f => renderDetailRow(f, d[f])).join('');
        } else {
            // Category view
            compDetailBody.innerHTML = compFieldSettings.filter(cat => cat.visible).map(cat => {
                const visFields = cat.fields.filter(f => f.visible);
                if (!visFields.length) return '';
                const isAmenities = cat.name === 'Amenities';
                const rows = visFields.map(f => renderDetailRow(f.key, d[f.key], isAmenities)).join('');
                const bodyInner = isAmenities ? `<div class="comp-amenities-grid">${rows}</div>` : rows;
                return `<div class="comp-detail-section">
                    <div class="comp-detail-section-header" onclick="this.classList.toggle('collapsed');this.nextElementSibling.classList.toggle('collapsed')">
                        <span class="chevron">▼</span><h3>${cat.name}</h3>
                    </div>
                    <div class="comp-detail-section-body">${bodyInner}</div>
                </div>`;
            }).join('');
        }

        // Wire up auto-save on detail fields
        compDetailBody.querySelectorAll('input, select').forEach(el => {
            el.addEventListener('change', async () => {
                const field = el.dataset.field;
                let value;
                if (el.type === 'checkbox') value = el.checked ? 1 : 0;
                else if (el.tagName === 'SELECT') value = el.value ? parseInt(el.value) : null;
                else if (el.type === 'number') value = el.value !== '' ? parseFloat(el.value) : null;
                else value = el.value || null;

                // If this is a school name dropdown, resolve name string + save key separately
                if (el.dataset.schoolSlot) {
                    const slot = el.dataset.schoolSlot;
                    const school = schoolsListCache.find(s => s.SCHOOL_KEY === value);
                    const nameValue = school ? school.SCHOOL_NAME : null;
                    // Save the key
                    await fetch('/api/comp-properties/update', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ property_key: compDetailPK, field: `SCHOOL_KEY_${slot}`, value }) });
                    // Save the name
                    const resp2 = await fetch('/api/comp-properties/update', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ property_key: compDetailPK, field: `SCHOOL_NAME_${slot}`, value: nameValue }) });
                    if (resp2.ok) {
                        el.classList.add('field-modified');
                        // Update the key display
                        const keyDisplay = compDetailBody.querySelector(`#schoolKeyDisplay_${slot}`);
                        if (keyDisplay) keyDisplay.textContent = value != null ? value : '—';
                        compDetailData[`SCHOOL_KEY_${slot}`] = value;
                        compDetailData[`SCHOOL_NAME_${slot}`] = nameValue;
                    }
                    return;
                }
                const resp = await fetch('/api/comp-properties/update', {
                    method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({ property_key: compDetailPK, field, value })
                });
                if (resp.ok) el.classList.add('field-modified');
                else { el.style.borderColor = '#ef4444'; setTimeout(() => { el.style.borderColor = ''; }, 2000); }
            });
        });
    }

    function renderDetailRow(field, value, compact = false) {
        let label = field.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()).replace(/Flag /g, '');
        if (label.startsWith('Amenity ')) label = 'Amenity - ' + label.slice(8);
        const missing = value == null || value === '';
        const isFlag = field.startsWith('FLAG_');
        const isSchoolKey = /^SCHOOL_KEY_\d$/.test(field);
        const isSchoolName = /^SCHOOL_NAME_\d$/.test(field);
        const isNum = !isSchoolKey && (field.includes('COUNT') || field.includes('YEAR') || field.includes('AMOUNT') || field.includes('FEE_') || field.includes('DISTANCE') || field.includes('LATITUDE') || field.includes('LONGITUDE') || field.includes('KEY'));
        let input;
        if (isFlag) {
            input = `<input type="checkbox" ${value ? 'checked' : ''} data-field="${field}" style="width:18px;height:18px;accent-color:var(--accent);">`;
        } else if (isSchoolName) {
            const slot = field.slice(-1); // '1'..'5'
            const curKey = compDetailData[`SCHOOL_KEY_${slot}`];
            const opts = schoolsListCache.map(s =>
                `<option value="${s.SCHOOL_KEY}" ${s.SCHOOL_KEY === curKey ? 'selected' : ''}>${s.SCHOOL_NAME}</option>`
            ).join('');
            input = `<select data-field="${field}" data-school-slot="${slot}"><option value="">— None —</option>${opts}</select>`;
        } else if (isSchoolKey) {
            // Read-only display — driven by Name dropdown
            const slot = field.slice(-1);
            input = `<span style="opacity:0.6;font-size:0.82rem;padding:4px 8px;background:var(--bg-raised);border-radius:3px;" id="schoolKeyDisplay_${slot}">${value != null ? value : '—'}</span>`;
        } else if (isNum) {
            input = `<input type="number" value="${value != null ? value : ''}" data-field="${field}">`;
        } else {
            input = `<input type="text" value="${value != null ? String(value).replace(/"/g, '&quot;') : ''}" data-field="${field}">`;
        }
        if (compact) {
            // Compact 2-col checkbox row — strip 'Amenity - ' prefix for brevity
            const shortLabel = label.startsWith('Amenity - ') ? label.slice(10) : label;
            return `<div class="comp-detail-row comp-amenity-row" data-field="${field}">
                <span class="detail-label" style="width:auto;flex:1;font-size:0.78rem;">${shortLabel}</span>
                <span class="detail-value" style="flex:0;padding-right:4px;">${input}</span>
            </div>`;
        }
        return `<div class="comp-detail-row ${missing && !isFlag ? 'missing' : ''}" data-field="${field}">
            <span class="detail-label">${label}</span>
            <span class="detail-value">${input}</span>
        </div>`;
    }

    // ── Comp Settings (Gear) ────────────────────────────────────────────────
    function openCompSettings() {
        compSettingsOverlay.classList.add('open');
        compSettingsModal.classList.add('open');
        renderCompSettings();
    }
    function closeCompSettings() {
        compSettingsOverlay.classList.remove('open');
        compSettingsModal.classList.remove('open');
    }

    function renderCompSettings() {
        compSettingsList.innerHTML = compFieldSettings.map((cat, ci) => {
            const visIcon = cat.visible ? '👁' : '👁‍🗨';
            const visCls = cat.visible ? '' : ' hidden';
            const fieldsHtml = cat.fields.map((f, fi) => {
                const fVis = f.visible ? '👁' : '👁‍🗨';
                const fCls = f.visible ? '' : ' is-hidden';
                return `<div class="comp-settings-field${fCls}" draggable="true" data-ci="${ci}" data-fi="${fi}">
                    <span class="field-drag-grip">⋮⋮</span>
                    <span style="flex:1">${f.key}</span>
                    <button class="comp-vis-btn${f.visible ? '' : ' hidden'}" data-ci="${ci}" data-fi="${fi}">${fVis}</button>
                </div>`;
            }).join('');
            return `<div class="comp-settings-cat${cat.visible ? '' : ' is-hidden'}" draggable="true" data-ci="${ci}">
                <div class="comp-settings-cat-header">
                    <span class="drag-grip">☰</span>
                    <span class="comp-settings-cat-name">${cat.name}</span>
                    <button class="comp-vis-btn${visCls}" data-ci="${ci}" data-toggle="cat">${visIcon}</button>
                </div>
                <div class="comp-settings-fields">${fieldsHtml}</div>
            </div>`;
        }).join('');

        // Category drag/drop
        compSettingsList.querySelectorAll('.comp-settings-cat').forEach(el => {
            el.addEventListener('dragstart', (e) => { e.dataTransfer.setData('cat-ci', el.dataset.ci); el.classList.add('dragging'); });
            el.addEventListener('dragend', () => el.classList.remove('dragging'));
            el.addEventListener('dragover', (e) => { e.preventDefault(); el.classList.add('drag-over'); });
            el.addEventListener('dragleave', () => el.classList.remove('drag-over'));
            el.addEventListener('drop', (e) => {
                e.preventDefault(); el.classList.remove('drag-over');
                const from = parseInt(e.dataTransfer.getData('cat-ci'));
                const to = parseInt(el.dataset.ci);
                if (from === to) return;
                const [moved] = compFieldSettings.splice(from, 1);
                compFieldSettings.splice(to, 0, moved);
                saveFieldSettings(); renderCompSettings(); renderCompDetail();
            });
        });

        // Visibility toggles
        compSettingsList.querySelectorAll('.comp-vis-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const ci = parseInt(btn.dataset.ci);
                if (btn.dataset.toggle === 'cat') {
                    compFieldSettings[ci].visible = !compFieldSettings[ci].visible;
                } else {
                    const fi = parseInt(btn.dataset.fi);
                    compFieldSettings[ci].fields[fi].visible = !compFieldSettings[ci].fields[fi].visible;
                }
                saveFieldSettings(); renderCompSettings(); renderCompDetail();
            });
        });

        // Field drag/drop within categories
        compSettingsList.querySelectorAll('.comp-settings-field').forEach(el => {
            el.addEventListener('dragstart', (e) => { e.stopPropagation(); e.dataTransfer.setData('field-loc', `${el.dataset.ci}:${el.dataset.fi}`); el.classList.add('dragging'); });
            el.addEventListener('dragend', () => el.classList.remove('dragging'));
            el.addEventListener('dragover', (e) => { e.preventDefault(); e.stopPropagation(); el.classList.add('drag-over-field'); });
            el.addEventListener('dragleave', () => el.classList.remove('drag-over-field'));
            el.addEventListener('drop', (e) => {
                e.preventDefault(); e.stopPropagation(); el.classList.remove('drag-over-field');
                const [fromCI, fromFI] = e.dataTransfer.getData('field-loc').split(':').map(Number);
                const toCI = parseInt(el.dataset.ci);
                const toFI = parseInt(el.dataset.fi);
                if (fromCI === toCI) {
                    const [moved] = compFieldSettings[fromCI].fields.splice(fromFI, 1);
                    compFieldSettings[toCI].fields.splice(toFI, 0, moved);
                    saveFieldSettings(); renderCompSettings(); renderCompDetail();
                }
            });
        });
    }

    // ── Assign Comps Tab ───────────────────────────────────────────────────
    const assignCompsList   = document.getElementById('assignCompsList');
    const assignAvailList   = document.getElementById('assignAvailList');
    const assignAvailSearch = document.getElementById('assignAvailSearch');
    const assignCompsTitle  = document.getElementById('assignCompsTitle');
    const assignCountBadge  = document.getElementById('assignCountBadge');
    let assignCompsData = [];   // currently assigned rows
    let allCompProps    = [];   // full comp property list (loaded once)

    async function loadAssignComps() {
        const noParent = !parentKey;
        const noWeek   = !dateKey;

        if (noParent) {
            assignCompsTitle.textContent = 'Select a parent property and week to manage comp assignments.';
            assignCompsList.innerHTML = '<p class="placeholder">Select a parent property and week.</p>';
            assignAvailList.innerHTML  = '<p class="placeholder">Select a parent property and week.</p>';
            assignCountBadge.textContent = '';
            return;
        }
        if (noWeek) {
            const pName = ddParent.options[ddParent.selectedIndex].text;
            assignCompsTitle.innerHTML = `<strong>${pName}</strong> &mdash; <span style="color:#f59e0b;">⚠ Select a Week from the left panel.</span>`;
            assignCompsList.innerHTML = '<p class="placeholder">Select a Week to continue.</p>';
            assignAvailList.innerHTML  = '<p class="placeholder">Select a Week to continue.</p>';
            assignCountBadge.textContent = '';
            return;
        }

        const pName     = ddParent.options[ddParent.selectedIndex].text;
        const weekLabel = ddWeeks.options[ddWeeks.selectedIndex].text;
        assignCompsTitle.innerHTML = `<strong>${pName}</strong> &mdash; week of ${weekLabel}`;

        // Load assigned comps
        const resp = await fetch(`/api/assign-comps?parent_key=${parentKey}`);
        assignCompsData = await resp.json();
        assignCountBadge.textContent = assignCompsData.length || '';

        // Load full comp list once
        if (!allCompProps.length) {
            const cr = await fetch('/api/comp-properties?inactive=0');
            allCompProps = await cr.json();
        }

        renderAssignComps();
        renderAssignAvailable();
    }

    function renderAssignAvailable() {
        const q = (assignAvailSearch ? assignAvailSearch.value : '').toLowerCase();
        const assignedIds = new Set(assignCompsData.map(d => d.comp_id));
        const parentMktKey = getParentMarketKey();
        let list = allCompProps.filter(cp => {
            if (parentMktKey != null && cp.MARKET_KEY !== parentMktKey) return false;
            return true;
        });
        if (q) list = list.filter(cp => (cp.PROPERTY_NAME || '').toLowerCase().includes(q) || (cp.MARKET_CITY_STATE || '').toLowerCase().includes(q));

        if (!list.length) {
            assignAvailList.innerHTML = q
                ? '<p class="placeholder" style="padding:12px;">No comps match your search.</p>'
                : '<p class="placeholder" style="padding:12px;">No comps found in this market.</p>';
            return;
        }
        assignAvailList.innerHTML = list.map(cp => {
            const isAssigned = assignedIds.has(cp.PROPERTY_KEY);
            const arrowHtml = isAssigned ? '' : `<button class="assign-avail-add" data-comp-key="${cp.PROPERTY_KEY}" title="Add to assigned" draggable="false">&rarr;</button>`;
            return `<div class="assign-avail-item${isAssigned ? ' is-assigned' : ''}" data-comp-key="${cp.PROPERTY_KEY}">
                <span class="avail-name">${cp.PROPERTY_NAME}</span>
                <span class="avail-market">${cp.MARKET_CITY_STATE || ''}</span>
                ${arrowHtml}
            </div>`;
        }).join('');

        assignAvailList.querySelectorAll('.assign-avail-add').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const compKey = parseInt(btn.dataset.compKey);
                btn.disabled = true;
                btn.style.opacity = '0.3';
                const resp = await fetch('/api/assign-comps/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ parent_key: parentKey, comp_key: compKey, date_key: dateKey })
                });
                if (resp.ok) {
                    await loadAssignComps();
                } else {
                    btn.disabled = false;
                    btn.style.opacity = '';
                    const err = await resp.json().catch(() => ({}));
                    alert('Failed to add comp: ' + (err.error || resp.status));
                }
            });
        });
    }

    assignAvailSearch.addEventListener('input', () => renderAssignAvailable());

    function renderAssignComps() {
        assignCountBadge.textContent = assignCompsData.length || '';
        if (!assignCompsData.length) {
            assignCompsList.innerHTML = '<p class="placeholder">No comps assigned yet. Click a comp on the left to add it.</p>';
            return;
        }
        assignCompsList.innerHTML = assignCompsData.map((item, idx) => {
            const isPeak    = idx === 0;
            const badgeCls  = isPeak ? 'assign-rank-badge rank-peak' : 'assign-rank-badge';
            const badgeTip  = isPeak ? 'Peak Property comp (rank 0)' : `Rank ${idx}`;
            const startFmt  = item.start_date ? item.start_date.slice(0, 10) : '—';
            // Rank 0 (parent itself) cannot be unassigned
            const leftArrow = isPeak
                ? `<span style="width:2rem;flex-shrink:0;"></span>`
                : `<button class="assign-unassign-btn" data-map-id="${item.map_id}" title="Remove from assigned" draggable="false">&larr;</button>`;
            return `<div class="assign-comp-row" draggable="true" data-map-id="${item.map_id || ''}">
                ${leftArrow}
                <span class="assign-drag-handle" title="Drag to reorder">≡</span>
                <span class="${badgeCls}" title="${badgeTip}">${idx}</span>
                <span class="assign-comp-name">${item.comp_name}</span>
                <span class="assign-comp-market">${item.market || '\u2014'}</span>
                <span class="assign-comp-dates">from ${startFmt}</span>
            </div>`;
        }).join('');

        // Drag-to-reorder
        assignCompsList.querySelectorAll('.assign-comp-row').forEach(row => {
            row.addEventListener('dragstart', (e) => {
                if (!row.dataset.mapId) { e.preventDefault(); return; } // rank-0 row, not draggable
                e.dataTransfer.setData('assign-map-id', row.dataset.mapId);
                row.classList.add('dragging');
            });
            row.addEventListener('dragend', () => row.classList.remove('dragging'));
            row.addEventListener('dragover', (e) => { e.preventDefault(); row.classList.add('drag-over'); });
            row.addEventListener('dragleave', () => row.classList.remove('drag-over'));
            row.addEventListener('drop', async (e) => {
                e.preventDefault();
                row.classList.remove('drag-over');
                const fromId = parseInt(e.dataTransfer.getData('assign-map-id'));
                const toId   = parseInt(row.dataset.mapId);
                if (fromId === toId) return;
                const fromIdx = assignCompsData.findIndex(d => d.map_id === fromId);
                const toIdx   = assignCompsData.findIndex(d => d.map_id === toId);
                if (fromIdx < 0 || toIdx < 0) return;
                const [moved] = assignCompsData.splice(fromIdx, 1);
                assignCompsData.splice(toIdx, 0, moved);
                const orders = assignCompsData.map((d, i) => ({ map_id: d.map_id, order_id: i }));
                renderAssignComps(); // optimistic
                await fetch('/api/assign-comps/reorder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ orders })
                });
            });
        });

        // Remove (← button)
        assignCompsList.querySelectorAll('.assign-unassign-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const mapId = parseInt(btn.dataset.mapId);
                await fetch('/api/assign-comps/remove', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ map_id: mapId })
                });
                await loadAssignComps();
            });
        });
    }

    function debounce(fn, ms) {
        let t;
        return function(...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), ms); };
    }

    // ── Floor Plans ─────────────────────────────────────────────────────────
    const fpGrid           = document.getElementById('fpGrid');
    const fpTitle          = document.getElementById('fpTitle');
    const fpShowInactive   = document.getElementById('fpShowInactive');
    const btnAddFloorplan  = document.getElementById('btnAddFloorplan');
    const fpDetailOverlay  = document.getElementById('fpDetailOverlay');
    const fpDetailBody     = document.getElementById('fpDetailBody');
    const fpDetailName     = document.getElementById('fpDetailName');
    const fpModifiedBy     = document.getElementById('fpModifiedBy');
    const fpActivateBtn    = document.getElementById('fpActivateBtn');
    const fpCompSearch     = document.getElementById('fpCompSearch');
    const fpCompDropdown   = document.getElementById('fpCompDropdown');
    let fpData = [];
    let fpSelectedKey = null;
    let fpCompKey = null;       // PROPERTY_KEY of the comp being viewed
    let fpCompName = '';        // display name of the comp being viewed
    let fpAllComps = [];        // full list for search dropdown

    const FP_TYPES = ['Studio','1x1','1x1 DBL','2x1','2x1 DBL','2x2','2x2 DBL',
                      '3x1','3x2','3x3','3x3 DBL','4x2','4x2 DBL','4x4','4x4 DBL','5x5'];

    // Called when left-nav comp changes or when tab is activated
    async function loadFloorplans(overrideCompKey, overrideCompName, keepSearch) {
        // Determine which comp to show:
        // 1. explicit override (from search dropdown)
        // 2. left-nav selected comp
        // 3. nothing selected yet
        const targetKey  = overrideCompKey  ?? selectedCompKey ?? null;
        const targetName = overrideCompName ?? (selectedCompKey
            ? (compList.querySelector('.comp-item.active')?.textContent.replace(/^#\d+\s*/, '').trim() || '')
            : '');

        if (!targetKey) {
            fpTitle.textContent = '';
            if (!keepSearch) { fpCompSearch.placeholder = 'Search all comp properties...'; fpCompSearch.value = ''; }
            btnAddFloorplan.disabled = true;
            fpGrid.innerHTML = '<p class="placeholder" style="padding:16px;">Select a comp from the left panel or search above.</p>';
            closeFpDetail();
            return;
        }

        fpCompKey  = targetKey;
        fpCompName = targetName || `Property ${targetKey}`;
        if (!keepSearch) fpCompSearch.value = '';
        fpTitle.textContent = fpCompName;
        btnAddFloorplan.disabled = false;

        const showInactive = fpShowInactive.checked ? '1' : '0';
        const resp = await fetch(`/api/floorplans?property_key=${fpCompKey}&show_inactive=${showInactive}`);
        fpData = await resp.json();
        renderFpGrid();
        fixFpNameColumnWidth();
        positionFpOverlay();
        if (fpSelectedKey) {
            const still = fpData.find(r => r.FLOORPLAN_ASSIGNMENT_KEY === fpSelectedKey);
            if (still) openFpDetail(fpSelectedKey); else closeFpDetail();
        }
    }

    // ── Comp search dropdown ─────────────────────────────────────────────────
    async function ensureFpAllComps() {
        if (fpAllComps.length) return;
        const r = await fetch('/api/comp-properties?q=&show_inactive=0');
        if (r.ok) fpAllComps = await r.json();
    }

    fpCompSearch.addEventListener('focus', async () => {
        await ensureFpAllComps();
        fpCompSearch.value = '';
        renderFpCompDropdown('');
    });
    fpCompSearch.addEventListener('click', async () => {
        await ensureFpAllComps();
        fpCompSearch.value = '';
        renderFpCompDropdown('');
    });
    fpCompSearch.addEventListener('input', () => renderFpCompDropdown(fpCompSearch.value));
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.fp-comp-search-wrap')) fpCompDropdown.style.display = 'none';
    });

    function renderFpCompDropdown(q) {
        const term = (q || '').toLowerCase().trim();
        const list = fpAllComps.filter(c =>
            !term || c.PROPERTY_NAME.toLowerCase().includes(term)
        ).slice(0, 40);
        if (!list.length) { fpCompDropdown.style.display = 'none'; return; }
        fpCompDropdown.innerHTML = list.map(c =>
            `<div class="fp-comp-opt" data-key="${c.PROPERTY_KEY}" data-name="${c.PROPERTY_NAME.replace(/"/g,'&quot;')}">${c.PROPERTY_NAME}<span class="fp-comp-opt-market">${c.MARKET_CITY_STATE||''}</span></div>`
        ).join('');
        fpCompDropdown.style.display = 'block';
        fpCompDropdown.querySelectorAll('.fp-comp-opt').forEach(el => {
            el.addEventListener('mousedown', async (e) => {
                e.preventDefault();
                const key  = parseInt(el.dataset.key);
                const name = el.dataset.name;
                fpCompDropdown.style.display = 'none';
                fpSelectedKey = null;
                closeFpDetail();
                await loadFloorplans(key, name);
            });
        });
    }

    function fixFpNameColumnWidth() {
        const cells = fpGrid.querySelectorAll('.fp-cell-name');
        if (!cells.length) return;
        let maxW = 0;
        cells.forEach(c => { maxW = Math.max(maxW, c.getBoundingClientRect().width); });
        const w = Math.max(180, Math.ceil(maxW)) + 'px';
        const tpl = `${w} 90px 120px 65px 65px 85px 80px`;
        fpGrid.querySelectorAll('.fp-grid-header, .fp-row').forEach(r => {
            r.style.gridTemplateColumns = tpl;
        });
    }

    function renderFpGrid() {
        if (!fpData.length) {
            fpGrid.innerHTML = '<p class="placeholder" style="padding:16px;">No floor plans found. Click + New Floor Plan to add one.</p>';
            return;
        }
        fpGrid.innerHTML = `
            <div class="fp-grid-header">
                <span>Name</span><span>Type</span><span>Compare As</span>
                <span>Apts</span><span>Beds</span><span>Prelease</span><span>Status</span>
            </div>
            ${fpData.map(fp => {
                const statusBadge = fp.FLAG_SOLD_OUT
                    ? '<span class="fp-badge sold-out">SOLD OUT</span>'
                    : fp.FLAG_ACTIVE
                        ? '<span class="fp-badge active">Active</span>'
                        : '<span class="fp-badge inactive">Inactive</span>';
                const sel = fp.FLOORPLAN_ASSIGNMENT_KEY === fpSelectedKey ? ' selected' : '';
                const inact = !fp.FLAG_ACTIVE ? ' inactive' : '';
                return `<div class="fp-row${sel}${inact}" data-key="${fp.FLOORPLAN_ASSIGNMENT_KEY}">
                    <span class="fp-cell-name">${fp.FLOORPLAN_NAME || '—'}</span>
                    <span class="fp-cell">${fp.FLOORPLAN_TYPE || '—'}</span>
                    <span class="fp-cell">${fp.COMPARE_AS_FLOORPLAN_TYPE || '—'}</span>
                    <span class="fp-cell">${fp.APARTMENT_COUNT ?? '—'}</span>
                    <span class="fp-cell">${fp.BED_COUNT ?? '—'}</span>
                    <span class="fp-cell">${fp.PRELEASE_PCT != null ? fp.PRELEASE_PCT.toFixed(1) + '%' : '—'}</span>
                    <span class="fp-cell">${statusBadge}</span>
                </div>`;
            }).join('')}`;
        fpGrid.querySelectorAll('.fp-row').forEach(row => {
            row.addEventListener('click', () => openFpDetail(parseInt(row.dataset.key)));
        });
    }

    async function openFpDetail(key) {
        fpSelectedKey = key;
        fpGrid.querySelectorAll('.fp-row').forEach(r => r.classList.toggle('selected', parseInt(r.dataset.key) === key));
        fpDetailOverlay.classList.add('open');
        positionFpOverlay();
        renderFpDetail(fpData.find(r => r.FLOORPLAN_ASSIGNMENT_KEY === key));
    }

    function positionFpOverlay() {
        const rect = fpGrid.getBoundingClientRect();
        const tableRight = rect.right;
        const available = window.innerWidth - tableRight - 100;
        fpDetailOverlay.style.width = Math.max(300, available) + 'px';
    }

    function closeFpDetail() {
        fpSelectedKey = null;
        fpDetailOverlay.classList.remove('open');
        fpGrid.querySelectorAll('.fp-row').forEach(r => r.classList.remove('selected'));
    }

    function renderFpDetail(fp) {
        if (!fp) return;
        fpDetailName.textContent = fp.FLOORPLAN_NAME || `Key: ${fp.FLOORPLAN_ASSIGNMENT_KEY}`;
        document.getElementById('fpDetailCompName').textContent = fpCompName || '';
        fpModifiedBy.textContent = fp.MODIFIED_BY ? `Last edited by ${fp.MODIFIED_BY} (${fp.DATE_MODIFIED || ''})` : '';
        fpActivateBtn.textContent = fp.FLAG_ACTIVE ? 'Deactivate' : 'Activate';
        fpActivateBtn.className = 'fp-activate-btn ' + (fp.FLAG_ACTIVE ? 'is-active' : 'is-inactive');

        const typeOpts = FP_TYPES.map(t => `<option${t === fp.FLOORPLAN_TYPE ? ' selected' : ''}>${t}</option>`).join('');
        const cmpOpts  = FP_TYPES.map(t => `<option${t === fp.COMPARE_AS_FLOORPLAN_TYPE ? ' selected' : ''}>${t}</option>`).join('');

        const flagRow = (label, field) => `
            <div class="fp-field-row">
                <span class="fp-label">${label}</span>
                <span class="fp-val"><input type="checkbox" data-field="${field}"${fp[field] ? ' checked' : ''}></span>
            </div>`;
        const numRow = (label, field, step) => `
            <div class="fp-field-row">
                <span class="fp-label">${label}</span>
                <span class="fp-val"><input type="number" step="${step || 1}" data-field="${field}" value="${fp[field] ?? ''}"></span>
            </div>`;
        const textRow = (label, field) => `
            <div class="fp-field-row">
                <span class="fp-label">${label}</span>
                <span class="fp-val"><input type="text" data-field="${field}" value="${fp[field] ?? ''}"></span>
            </div>`;
        const textareaRow = (label, field) => `
            <div class="fp-field-row" style="align-items:flex-start;">
                <span class="fp-label" style="padding-top:5px;">${label}</span>
                <span class="fp-val"><textarea data-field="${field}">${fp[field] ?? ''}</textarea></span>
            </div>`;
        const premRow = (n) => `
            <div class="fp-premium-row">
                <input type="text" data-field="UNIT_PREMIUM_${n}_NAME" value="${fp[`UNIT_PREMIUM_${n}_NAME`] ?? ''}" placeholder="Premium ${n} name">
                <input type="number" step="0.01" data-field="UNIT_PREMIUM_${n}_AMOUNT" value="${fp[`UNIT_PREMIUM_${n}_AMOUNT`] ?? ''}">
                <div class="fp-premium-waived"><input type="checkbox" data-field="UNIT_PREMIUM_${n}_WAIVED"${fp[`UNIT_PREMIUM_${n}_WAIVED`] ? ' checked' : ''}> Waived</div>
            </div>`;

        fpDetailBody.innerHTML = `
            ${fpSection('Identity', `
                ${textRow('Name', 'FLOORPLAN_NAME')}
                <div class="fp-field-row"><span class="fp-label">Type</span><span class="fp-val"><select data-field="FLOORPLAN_TYPE">${typeOpts}</select></span></div>
                <div class="fp-field-row"><span class="fp-label">Compare As</span><span class="fp-val"><select data-field="COMPARE_AS_FLOORPLAN_TYPE">${cmpOpts}</select></span></div>
                ${numRow('Beds', 'FLOORPLAN_BEDS')}
                ${numRow('Baths', 'FLOORPLAN_BATHS')}
                ${numRow('Order', 'FLOORPLAN_ORDER')}
            `)}
            ${fpSection('Counts', `
                ${numRow('Apartments', 'APARTMENT_COUNT')}
                ${numRow('Beds', 'BED_COUNT')}
                ${numRow('Beds Furnished', 'BEDS_FURNISHED')}
                ${numRow('Sq Ft', 'APARTMENT_SQFT')}
            `)}
            ${fpSection('Flags', `
                ${flagRow('Sold Out', 'FLAG_SOLD_OUT')}
                ${flagRow('Double Occ', 'FLAG_DOUBLE_OCC')}
                ${flagRow('Exclude', 'FLAG_EXCLUDE')}
                ${flagRow('Furniture Fee RR', 'FLAG_FURNITURE_FEE_RR')}
                ${flagRow('Utility Cap', 'FLAG_UTILITY_CAP')}
                ${flagRow('Utility Cap RR', 'FLAG_UTILITY_CAP_RR')}
                ${flagRow('Water Fee RR', 'FLAG_WATER_FEE_RR')}
            `)}
            ${fpSection('Financials', `
                ${numRow('Furniture Fee', 'FURNITURE_FEE', '0.01')}
                ${numRow('Utility Cap', 'UTILITY_CAP', '0.01')}
                ${numRow('Water Fee', 'WATER_FEE', '0.01')}
            `)}
            ${fpSection('Unit Premiums', `
                <div style="display:grid;grid-template-columns:1fr 90px 70px;gap:6px;padding:0 0 4px;font-size:0.72rem;font-weight:700;text-transform:uppercase;color:var(--text-secondary);">
                    <span>Name</span><span>Amount</span><span style="text-align:center;">Waived</span>
                </div>
                ${[1,2,3,4,5].map(premRow).join('')}
            `)}
            ${fpSection('Notes', `
                ${textareaRow('Floorplan', 'SUMMARY_FLOORPLAN')}
                ${textareaRow('Concessions', 'SUMMARY_CONCESSIONS')}
                ${textareaRow('Gift Incentives', 'SUMMARY_GIFT_INCENTIVES')}
                ${textareaRow('Prelease Specials', 'SUMMARY_PRELEASE_SPECIALS')}
                ${textareaRow('Current Term', 'SUMMARY_CURRENT_TERM_SPECIALS')}
                ${textareaRow('Referrals', 'SUMMARY_REFERRALS')}
            `)}`;

        // Collapse toggles
        fpDetailBody.querySelectorAll('.fp-section-header').forEach(hdr => {
            hdr.addEventListener('click', () => {
                hdr.classList.toggle('collapsed');
                hdr.nextElementSibling.classList.toggle('collapsed');
            });
        });

        // Auto-save on blur / change
        fpDetailBody.querySelectorAll('[data-field]').forEach(el => {
            const save = async () => {
                const field = el.dataset.field;
                const value = el.type === 'checkbox' ? (el.checked ? 1 : 0) : el.value;
                const resp = await fetch('/api/floorplans/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ floorplan_assignment_key: fpSelectedKey, field, value })
                });
                if (resp.ok) {
                    // Update local cache
                    const rec = fpData.find(r => r.FLOORPLAN_ASSIGNMENT_KEY === fpSelectedKey);
                    if (rec) rec[field] = (el.type === 'checkbox') ? (el.checked ? 1 : 0) : value;
                    // Flash save indicator on inputs (not checkboxes)
                    if (el.type !== 'checkbox') {
                        el.classList.add('fp-saved');
                        setTimeout(() => el.classList.remove('fp-saved'), 1200);
                    }
                    // Refresh the grid row if name/type/status changed
                    if (['FLOORPLAN_NAME','FLOORPLAN_TYPE','COMPARE_AS_FLOORPLAN_TYPE',
                         'APARTMENT_COUNT','BED_COUNT','FLAG_SOLD_OUT'].includes(field)) {
                        renderFpGrid();
                    }
                }
            };
            if (el.type === 'checkbox') el.addEventListener('change', save);
            else el.addEventListener('blur', save);
        });
    }

    function fpSection(title, bodyHtml) {
        return `<div class="fp-section">
            <div class="fp-section-header"><span class="chevron">▼</span><h3>${title}</h3></div>
            <div class="fp-section-body">${bodyHtml}</div>
        </div>`;
    }

    document.getElementById('fpDetailClose').addEventListener('click', closeFpDetail);

    fpActivateBtn.addEventListener('click', async () => {
        if (!fpSelectedKey) return;
        const rec = fpData.find(r => r.FLOORPLAN_ASSIGNMENT_KEY === fpSelectedKey);
        if (!rec) return;
        const newActive = rec.FLAG_ACTIVE ? 0 : 1;
        const resp = await fetch('/api/floorplans/activate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ floorplan_assignment_key: fpSelectedKey, active: newActive })
        });
        if (resp.ok) {
            rec.FLAG_ACTIVE = newActive;
            renderFpGrid();
            positionFpOverlay();
            renderFpDetail(rec);
        }
    });

    fpShowInactive.addEventListener('change', () => loadFloorplans(fpCompKey, fpCompName, true));

    window.addEventListener('resize', () => { if (fpDetailOverlay.classList.contains('open')) positionFpOverlay(); });

    // Resize handle
    (function setupFpResize() {
        const handle = document.getElementById('fpResizeHandle');
        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            const startX = e.clientX;
            const startW = fpDetailOverlay.offsetWidth;
            function onMove(ev) { fpDetailOverlay.style.width = Math.max(360, startW - (ev.clientX - startX)) + 'px'; }
            function onUp() { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); }
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    })();

    // + New Floor Plan modal
    const fpModalOverlay = document.createElement('div');
    fpModalOverlay.className = 'fp-modal-overlay';
    fpModalOverlay.innerHTML = `
        <div class="fp-modal">
            <h3>New Floor Plan</h3>
            <label>Floor Plan Name</label>
            <input type="text" id="fpNewName" placeholder="e.g. 2x2A" autocomplete="off">
            <label>Type</label>
            <select id="fpNewType">${FP_TYPES.map(t => `<option>${t}</option>`).join('')}</select>
            <div class="fp-modal-btns">
                <button class="fp-modal-cancel" id="fpModalCancel">Cancel</button>
                <button class="fp-modal-save" id="fpModalSave">Create</button>
            </div>
        </div>`;
    document.body.appendChild(fpModalOverlay);

    btnAddFloorplan.addEventListener('click', () => {
        document.getElementById('fpNewName').value = '';
        fpModalOverlay.classList.add('open');
        setTimeout(() => document.getElementById('fpNewName').focus(), 50);
    });
    document.getElementById('fpModalCancel').addEventListener('click', () => fpModalOverlay.classList.remove('open'));
    document.getElementById('fpModalSave').addEventListener('click', async () => {
        const name = document.getElementById('fpNewName').value.trim();
        const type = document.getElementById('fpNewType').value;
        if (!name) { document.getElementById('fpNewName').focus(); return; }
        const resp = await fetch('/api/floorplans/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ property_key: fpCompKey, floorplan_name: name, floorplan_type: type })
        });
        if (resp.ok) {
            const d = await resp.json();
            fpModalOverlay.classList.remove('open');
            await loadFloorplans(fpCompKey, fpCompName, true);
            openFpDetail(d.floorplan_assignment_key);
        }
    });
})();
