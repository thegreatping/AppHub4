/* milestones.js v2 */
(function () {
    "use strict";

    const propList   = document.getElementById("msPropList");
    const propSearch = document.getElementById("msPropSearch");
    const propCount  = document.getElementById("msPropCount");
    const msEmpty    = document.getElementById("msEmpty");
    const msContent  = document.getElementById("msContent");
    const msLoading  = document.getElementById("msLoading");
    const tableHead  = document.getElementById("msTableHead");
    const tableBody  = document.getElementById("msTableBody");
    const msPropName = document.getElementById("msPropName");
    const msPropType = document.getElementById("msPropType");
    const saveStatus = document.getElementById("msSaveStatus");
    const monthBtns  = document.getElementById("msMonthBtns");
    const lockBanner = document.getElementById("msLockBanner");

    let allProps      = [];
    let activeKey     = null;
    let allMonths     = [];   // full list returned by API (up to 12)
    let allEmployees  = [];   // cached for re-render on month count change
    let displayMonths = 8;    // currently visible month count
    let editLocked    = false; // true when Day(today) >= 20
    let saveTimer     = null;
    let pendingSaves  = 0;

    // ── Helpers ────────────────────────────────────────────────────────────────

    function fmtMonth(yyyymm) {
        const y = Math.floor(yyyymm / 100);
        const m = yyyymm % 100;
        const names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
        return names[m - 1] + " " + y;
    }

    function setSaveStatus(state, msg) {
        saveStatus.className = "ms-save-status " + state;
        saveStatus.textContent = msg;
    }

    // ── Month selector ─────────────────────────────────────────────────────────

    monthBtns.addEventListener("click", e => {
        const btn = e.target.closest(".ms-mbtn");
        if (!btn) return;
        displayMonths = parseInt(btn.dataset.n, 10);
        monthBtns.querySelectorAll(".ms-mbtn").forEach(b => b.classList.toggle("active", b === btn));
        if (allEmployees.length > 0 || allMonths.length > 0) {
            renderTable(allEmployees, allMonths.slice(0, displayMonths));
        }
    });

    // ── Load property list ─────────────────────────────────────────────────────

    async function loadProperties() {
        propCount.textContent = "";
        const res = await fetch("/milestones/api/properties");
        allProps = await res.json();
        propCount.textContent = "(" + allProps.length + ")";
        renderPropList(allProps);
    }

    function renderPropList(items) {
        propList.innerHTML = "";
        items.forEach(p => {
            const el = document.createElement("div");
            el.className = "ms-prop-item" + (p.key === activeKey ? " active" : "");
            el.dataset.key = p.key;
            el.innerHTML = `<div class="ms-prop-item-name">${p.name}</div>`;
            el.addEventListener("click", () => selectProperty(p));
            propList.appendChild(el);
        });
    }

    propSearch.addEventListener("input", () => {
        const q = propSearch.value.trim().toLowerCase();
        const filtered = q ? allProps.filter(p => p.name.toLowerCase().includes(q)) : allProps;
        renderPropList(filtered);
    });

    // ── Select property ────────────────────────────────────────────────────────

    async function selectProperty(prop) {
        activeKey = prop.key;
        msPropName.textContent = prop.name;
        msPropType.textContent = prop.ptype || "";
        setSaveStatus("", "");

        // Highlight in list
        propList.querySelectorAll(".ms-prop-item").forEach(el => {
            el.classList.toggle("active", parseInt(el.dataset.key) === activeKey);
        });

        msEmpty.style.display = "none";
        msContent.style.display = "flex";
        tableHead.innerHTML = "";
        tableBody.innerHTML = "";
        msLoading.style.display = "flex";

        const res  = await fetch("/milestones/api/employees?property_key=" + activeKey);
        const data = await res.json();
        msLoading.style.display = "none";

        allMonths    = data.months    || [];
        allEmployees = data.employees || [];
        editLocked   = !!data.edit_locked;
        lockBanner.style.display = editLocked ? "flex" : "none";
        renderTable(allEmployees, allMonths.slice(0, displayMonths));
    }

    // ── Render employee table ──────────────────────────────────────────────────

    function renderTable(employees, months) {
        tableHead.innerHTML = "";
        tableBody.innerHTML = "";

        // Head
        const tr = document.createElement("tr");
        tr.innerHTML = `<th style="min-width:200px">Employee</th><th style="min-width:120px">Type</th>`;
        months.forEach((m, i) => {
            const isCurrent = i === 0;
            tr.innerHTML += `<th class="month-col${isCurrent ? " month-current" : ""}">
                ${fmtMonth(m)}${isCurrent ? `<span class="ms-editable-badge">editable</span>` : ""}
            </th>`;
        });
        tableHead.appendChild(tr);

        // Body — group by MILESTONE_TYPE
        const groups = {};
        employees.forEach(e => {
            const t = e.type || "Other";
            if (!groups[t]) groups[t] = [];
            groups[t].push(e);
        });

        Object.keys(groups).sort().forEach(gtype => {
            const gtr = document.createElement("tr");
            gtr.className = "ms-group-row";
            gtr.innerHTML = `<td colspan="${2 + months.length}">${gtype}</td>`;
            tableBody.appendChild(gtr);

            groups[gtype].forEach(emp => {
                const row = document.createElement("tr");
                let cells = `<td>${escHtml(emp.name)}</td>
                             <td class="ms-type-cell">${escHtml(emp.type)}</td>`;
                months.forEach((m, i) => {
                    const val = emp.points[String(m)];
                    const displayVal = val != null ? val : "";
                    const isCurrent = i === 0;
                    if (isCurrent && !editLocked) {
                        cells += `<td class="month-col month-current">
                            <input class="ms-pts-input"
                                   type="number" min="0" max="9999"
                                   data-code="${escAttr(emp.code)}"
                                   data-month="${m}"
                                   value="${displayVal}"
                                   placeholder="-">
                        </td>`;
                    } else if (isCurrent) {
                        cells += `<td class="month-col month-current ms-readonly-cell">${displayVal !== "" ? displayVal : "<span class=\"ms-no-val\">-</span>"}</td>`;
                    } else {
                        cells += `<td class="month-col ms-readonly-cell">${displayVal !== "" ? displayVal : "<span class=\"ms-no-val\">-</span>"}</td>`;
                    }
                });
                row.innerHTML = cells;
                tableBody.appendChild(row);
            });
        });

        tableBody.querySelectorAll(".ms-pts-input").forEach(input => {
            input.addEventListener("change", onPointsChange);
        });
    }

    // ── Save points ────────────────────────────────────────────────────────────

    async function onPointsChange(e) {
        const input  = e.target;
        const code   = input.dataset.code;
        const month  = input.dataset.month;
        const raw    = input.value.trim();
        const points = raw === "" ? null : parseInt(raw, 10);

        input.classList.remove("saved", "error");
        input.classList.add("saving");
        pendingSaves++;
        setSaveStatus("saving", "Saving...");

        try {
            const res = await fetch("/milestones/api/points/save", {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify({
                    employee_code: code,
                    yyyymm:        parseInt(month, 10),
                    points:        points,
                    property_key:  activeKey,
                }),
            });
            const data = await res.json();
            input.classList.remove("saving");
            if (data.ok) {
                input.classList.add("saved");
                setTimeout(() => input.classList.remove("saved"), 1500);
            } else {
                input.classList.add("error");
            }
        } catch (err) {
            input.classList.remove("saving");
            input.classList.add("error");
        }

        pendingSaves--;
        if (pendingSaves <= 0) {
            pendingSaves = 0;
            setSaveStatus("saved", "All changes saved");
            clearTimeout(saveTimer);
            saveTimer = setTimeout(() => setSaveStatus("", ""), 3000);
        }
    }

    // ── Utility ────────────────────────────────────────────────────────────────

    function escHtml(s) {
        return String(s || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function escAttr(s) { return escHtml(s); }

    // ── Init ────────────────────────────────────────────────────────────────────
    loadProperties();
})();
