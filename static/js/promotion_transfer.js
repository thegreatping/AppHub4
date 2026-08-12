/* Promotion/Transfer Alert JS v1 */
"use strict";

// ── State ──────────────────────────────────────────────────────────────────────
let allEmployees = [];
let allProperties = [];
let allPayrollEntities = [];
let currentPage = 1;
let allHistory = [];
let _sortCol = "employee_name", _sortDir = "asc";

// ── Boot ───────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    loadReferenceData();
    setupTabs();
    populatePropertyPositions();
    populateCorporatePositions();
});

async function loadReferenceData() {
    const [empRes, propRes, payRes] = await Promise.all([
        fetch("/paf/api/employees"),
        fetch("/paf/api/properties"),
        fetch("/paf/api/payroll-entities"),
    ]);
    allEmployees   = await empRes.json();
    allProperties  = await propRes.json();
    allPayrollEntities = await payRes.json();

    // Populate payroll entity dropdown
    const peSelect = document.getElementById("newPayrollEntity");
    allPayrollEntities.forEach(name => {
        const opt = document.createElement("option");
        opt.value = opt.textContent = name;
        peSelect.appendChild(opt);
    });

    // Populate property dropdown
    const propSelect = document.getElementById("newPropertyLocation");
    allProperties.forEach(p => {
        const opt = document.createElement("option");
        opt.value = `${p.name} - ${p.key}`;
        opt.textContent = p.name;
        opt.dataset.entity = p.entity;
        opt.dataset.payroll = p.payroll;
        opt.dataset.key = p.key;
        propSelect.appendChild(opt);
    });

    // Populate RM properties checkgrid
    const rmGrid = document.getElementById("rmPropsGrid");
    allProperties.forEach(p => {
        const div = document.createElement("div");
        div.className = "paf-check-item";
        div.innerHTML = `<input type="checkbox" value="${p.name}"> ${p.name}`;
        div.addEventListener("click", () => {
            const cb = div.querySelector("input");
            cb.checked = !cb.checked;
            div.classList.toggle("checked", cb.checked);
        });
        rmGrid.appendChild(div);
    });

    // Employee autocomplete
    setupEmployeeCombo();
}

// ── Tabs ───────────────────────────────────────────────────────────────────────
function setupTabs() {
    document.querySelectorAll(".paf-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".paf-tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".paf-panel").forEach(p => p.classList.remove("active"));
            tab.classList.add("active");
            document.getElementById("tab-" + tab.dataset.tab).classList.add("active");
            if (tab.dataset.tab === "history") loadHistory();
            if (tab.dataset.tab === "admin")   loadAdmins();
        });
    });
}

// ── Employee combo search ──────────────────────────────────────────────────────
function setupEmployeeCombo() {
    const input    = document.getElementById("empSearch");
    const dropdown = document.getElementById("empDropdown");

    input.addEventListener("input", () => {
        const q = input.value.trim().toLowerCase();
        dropdown.innerHTML = "";
        if (q.length < 2) { dropdown.classList.remove("open"); return; }
        const matches = allEmployees.filter(e => e.name.toLowerCase().includes(q)).slice(0, 30);
        if (!matches.length) { dropdown.classList.remove("open"); return; }
        matches.forEach(emp => {
            const item = document.createElement("div");
            item.className = "paf-combo-item";
            item.innerHTML = `${emp.name}<div class="emp-title">${emp.title || ""}</div>`;
            item.addEventListener("click", () => selectEmployee(emp));
            dropdown.appendChild(item);
        });
        dropdown.classList.add("open");
    });

    document.addEventListener("click", e => {
        if (!e.target.closest(".paf-combo-wrap")) dropdown.classList.remove("open");
    });
}

function selectEmployee(emp) {
    document.getElementById("empSearch").value           = emp.name;
    document.getElementById("empName").value             = emp.name;
    document.getElementById("empCode").value             = emp.code;
    document.getElementById("empFirst").value            = emp.first;
    document.getElementById("empLast").value             = emp.last;
    document.getElementById("empEmail").value            = emp.email;
    document.getElementById("empSupervisorName").value   = emp.supervisor_name;
    document.getElementById("empSupervisorEmail").value  = emp.supervisor_email;
    document.getElementById("empCodeDisplay").value      = emp.code;
    document.getElementById("hiringMgrDisplay").value    = emp.supervisor_name;
    document.getElementById("hiringMgrName").value       = emp.supervisor_name;
    document.getElementById("hiringMgrEmail").value      = emp.supervisor_email;
    document.getElementById("empDropdown").classList.remove("open");
}

// ── Location change ────────────────────────────────────────────────────────────
function onLocationChange() {
    const loc = document.getElementById("locationType").value;
    document.getElementById("propertyFields").style.display   = loc === "Property"  ? "block" : "none";
    document.getElementById("corporateFields").style.display  = loc === "Corporate" ? "block" : "none";

    // Refresh position list based on location type
    populatePositionsByLocation(loc);

    // Reset entity fields
    document.getElementById("newCompanyEntity").value  = "";
    document.getElementById("newPayrollEntity").value  = "";
    document.getElementById("newPropertyLocation").value = "";
}

function onPropertySelect() {
    const sel = document.getElementById("newPropertyLocation");
    const opt = sel.options[sel.selectedIndex];
    if (!opt || !opt.dataset.entity) return;

    // Auto-fill entity dropdowns from property data
    setOrAddOption("newCompanyEntity", opt.dataset.entity);
    setOrAddOption("newPayrollEntity", opt.dataset.payroll);
}

function setOrAddOption(selectId, value) {
    const sel = document.getElementById(selectId);
    for (let o of sel.options) {
        if (o.value === value) { sel.value = value; return; }
    }
    const opt = document.createElement("option");
    opt.value = opt.textContent = value;
    sel.appendChild(opt);
    sel.value = value;
}

// ── Position dropdowns ─────────────────────────────────────────────────────────
const PROPERTY_POSITIONS = [
    "Assistant Manager",
    "Assistant Manager of Leasing & Operations",
    "Executive Director",
    "General Manager",
    "Groundskeeper",
    "Housekeeper",
    "Leasing Consultant",
    "Leasing Manager",
    "Maintenance Supervisor",
    "Maintenance Technician",
    "Marketing Manager",
    "New Development Property Manager",
    "Porter",
    "Property Manager",
    "Regional Manager",
    "Resident Advisor",
    "Resident Assistant",
    "Resident Director",
    "Senior Assistant Manager",
    "Senior Leasing Manager",
    "Senior Maintenance Supervisor",
    "Senior Property Manager",
    "Shuttle Bus Driver",
    "Temporary Turn Associate",
    "Other",
];

const CORPORATE_POSITIONS = [
    "Centralized Marketing Specialist",
    "Marketing Support Specialist",
    "National Operations Specialist",
    "Property Accountant",
    "Regional Manager",
    "Regional Sales Manager",
    "Regional Vice President",
    "Resident Accounts Manager",
    "Sales Support Specialist",
    "Other",
];

function populatePropertyPositions() {
    fillPositionSelect(PROPERTY_POSITIONS);
}

function populateCorporatePositions() {
    // pre-built — just used when location changes
}

function fillPositionSelect(list) {
    const sel = document.getElementById("newPositionSelect");
    sel.innerHTML = '<option value="">-- Select --</option>';
    list.forEach(p => {
        const opt = document.createElement("option");
        opt.value = opt.textContent = p;
        sel.appendChild(opt);
    });
}

function populatePositionsByLocation(loc) {
    if (loc === "Corporate") {
        fillPositionSelect(CORPORATE_POSITIONS);
    } else {
        fillPositionSelect(PROPERTY_POSITIONS);
    }
    document.getElementById("otherTitleWrap").style.display = "none";
    document.getElementById("rmPropsWrap").style.display    = "none";
}

function onPositionChange() {
    const val = document.getElementById("newPositionSelect").value;
    document.getElementById("otherTitleWrap").style.display = val === "Other" ? "block" : "none";
    document.getElementById("rmPropsWrap").style.display    = val === "Regional Manager" ? "block" : "none";
}

// ── Toggle buttons ─────────────────────────────────────────────────────────────
function toggleBtn(btnId) {
    const btn = document.getElementById(btnId);
    const label = document.getElementById(btnId.replace("Btn", "Label"));
    const isOn = btn.dataset.value === "0";
    btn.dataset.value = isOn ? "1" : "0";
    btn.classList.toggle("on", isOn);
    if (label) label.textContent = isOn ? "Yes" : "No";

    // Job req warning
    if (btnId === "jobReqBtn") {
        const warn = document.getElementById("jobReqWarn");
        warn.classList.toggle("show", !isOn);
    }
}

function onPayTypeChange() {
    const t = document.getElementById("newPayType").value;
    const hr  = document.getElementById("newHourlyRate");
    const sal = document.getElementById("newAnnualSalary");
    hr.disabled  = t !== "Hourly";
    sal.disabled = t !== "Salary";
    if (t !== "Hourly")  hr.value  = "";
    if (t !== "Salary") sal.value = "";
}

function onRentDiscountChange() {
    const on = document.getElementById("rentDiscountBtn").dataset.value === "1";
    document.getElementById("rentDiscountFields").style.display = on ? "block" : "none";
}

function onRelocChange() {
    const on = document.getElementById("relocBtn").dataset.value === "1";
    document.getElementById("relocFields").style.display = on ? "block" : "none";
}

function onCellChange() {
    const on = document.getElementById("cellBtn").dataset.value === "1";
    document.getElementById("cellFields").style.display = on ? "block" : "none";
}

// ── System access toggles ──────────────────────────────────────────────────────
function toggleAccess(item) {
    item.classList.toggle("selected");
}

// ── Step navigation ────────────────────────────────────────────────────────────
function goToPage(n) {
    if (n > currentPage && !validatePage(currentPage)) return;

    document.getElementById(`page-${currentPage}`).style.display = "none";
    document.getElementById(`step-dot-${currentPage}`).classList.remove("active");
    document.getElementById(`step-dot-${currentPage}`).classList.add("done");

    currentPage = n;
    document.getElementById(`page-${currentPage}`).style.display = "block";
    document.getElementById(`step-dot-${currentPage}`).classList.remove("done");
    document.getElementById(`step-dot-${currentPage}`).classList.add("active");

    window.scrollTo(0, 0);
}

function validatePage(n) {
    if (n === 1) {
        if (document.getElementById("jobReqBtn").dataset.value !== "1") {
            showError("A job requisition must be submitted before proceeding."); return false;
        }
        if (!document.getElementById("empName").value) {
            showError("Please select an employee."); return false;
        }
        if (!document.getElementById("effectiveDate").value) {
            showError("Effective date is required."); return false;
        }
        if (!document.getElementById("pafType").value) {
            showError("PAF Type is required."); return false;
        }
        if (!document.getElementById("locationType").value) {
            showError("New Location is required."); return false;
        }
        if (!getPositionTitle()) {
            showError("New Position/Title is required."); return false;
        }
        if (!document.getElementById("newCompanyEntity").value) {
            showError("New Company/Entity is required."); return false;
        }
        if (!document.getElementById("newPayrollEntity").value) {
            showError("New Payroll Entity is required."); return false;
        }
        if (!document.getElementById("hiringMgrName").value) {
            showError("Hiring Manager is required."); return false;
        }
    }
    if (n === 2) {
        const pt = document.getElementById("newPayType").value;
        if (!pt) { showError("New Pay Type is required."); return false; }
        if (pt === "Hourly" && !document.getElementById("newHourlyRate").value) {
            showError("New Base Hourly Rate is required."); return false;
        }
        if (pt === "Salary" && !document.getElementById("newAnnualSalary").value) {
            showError("New Annual Salary is required."); return false;
        }
        const rdOn = document.getElementById("rentDiscountBtn").dataset.value === "1";
        if (rdOn && !document.getElementById("rentDiscountPct").value) {
            showError("Rent Discount % is required."); return false;
        }
        if (rdOn && !document.getElementById("baseRent").value) {
            showError("Base Rent is required."); return false;
        }
        const relOn = document.getElementById("relocBtn").dataset.value === "1";
        if (relOn && !document.getElementById("relocAmount").value) {
            showError("Relocation Amount is required."); return false;
        }
        const cellOn = document.getElementById("cellBtn").dataset.value === "1";
        if (cellOn && !document.getElementById("cellAmount").value) {
            showError("Cell Phone Amount is required."); return false;
        }
    }
    return true;
}

function showError(msg) {
    const el = document.getElementById("pafError");
    el.textContent = msg;
    el.style.display = "block";
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => { el.style.display = "none"; }, 5000);
}

function getPositionTitle() {
    const sel = document.getElementById("newPositionSelect").value;
    if (sel === "Other") return document.getElementById("otherTitleInput").value.trim();
    return sel;
}

function getRMProperties() {
    const checked = [...document.querySelectorAll("#rmPropsGrid .paf-check-item.checked input")];
    return checked.map(cb => cb.value).join("; ");
}

function getSelectedAccess() {
    const result = {};
    document.querySelectorAll(".paf-access-item.selected").forEach(item => {
        result[item.dataset.field] = true;
    });
    return result;
}

// ── Submit ─────────────────────────────────────────────────────────────────────
async function submitForm() {
    if (!validatePage(3)) return;

    const btn = document.getElementById("btnSubmit");
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Submitting...';

    const loc = document.getElementById("locationType").value;
    const access = getSelectedAccess();

    const payload = {
        employee_name:           document.getElementById("empName").value,
        employee_code:           document.getElementById("empCode").value,
        employee_first:          document.getElementById("empFirst").value,
        employee_last:           document.getElementById("empLast").value,
        effective_date:          document.getElementById("effectiveDate").value,
        paf_type:                document.getElementById("pafType").value,
        location_type:           loc,
        new_property_location:   loc === "Property"  ? document.getElementById("newPropertyLocation").value : "",
        new_home_office_location: loc === "Corporate" ? document.getElementById("homeOfficeLocation").value : "",
        new_office_location:     loc === "Corporate" ? document.getElementById("homeOfficeLocation").value : "",
        new_company_entity:      document.getElementById("newCompanyEntity").value,
        new_payroll_entity:      document.getElementById("newPayrollEntity").value,
        new_department:          loc === "Corporate" ? document.getElementById("newDepartment").value : "",
        new_position_title:      getPositionTitle(),
        rm_properties:           getRMProperties(),
        hiring_manager_name:     document.getElementById("hiringMgrName").value,
        hiring_manager_email:    document.getElementById("hiringMgrEmail").value,
        job_req:                 document.getElementById("jobReqBtn").dataset.value === "1",
        new_pay_type:            document.getElementById("newPayType").value,
        new_hourly_rate:         document.getElementById("newHourlyRate").value || null,
        new_annual_salary:       document.getElementById("newAnnualSalary").value || null,
        rent_discount:           document.getElementById("rentDiscountBtn").dataset.value === "1",
        rent_discount_pct:       document.getElementById("rentDiscountPct").value || null,
        base_rent:               document.getElementById("baseRent").value || null,
        cell_phone_reimbursement: document.getElementById("cellBtn").dataset.value === "1",
        cell_phone_amount:       document.getElementById("cellAmount").value || null,
        relocation_assistance:   document.getElementById("relocBtn").dataset.value === "1",
        relocation_amount:       document.getElementById("relocAmount").value || null,
        special_payment_requests: document.getElementById("specialPayments").value,
        paycom_client:           !!access.paycom_client,
        adaptive_insights:       !!access.adaptive_insights,
        amex:                    !!access.amex,
        avidxchange:             !!access.avidxchange,
        certify:                 !!access.certify,
        concur:                  !!access.concur,
        grace_hill:              !!access.grace_hill,
        other_information:       document.getElementById("otherInformation").value,
    };

    try {
        const res = await fetch("/paf/api/alerts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const result = await res.json();
        if (res.ok && result.success) {
            // Hide all pages, show success
            for (let i = 1; i <= 3; i++) document.getElementById(`page-${i}`).style.display = "none";
            document.getElementById("pafSuccess").style.display = "block";
        } else {
            showError(result.error || "Submission failed.");
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Submit';
        }
    } catch (err) {
        showError("Network error. Please try again.");
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Submit';
    }
}

function resetForm() {
    // Reset to page 1
    document.getElementById("pafSuccess").style.display = "none";
    for (let i = 1; i <= 3; i++) {
        document.getElementById(`page-${i}`).style.display = i === 1 ? "block" : "none";
        const dot = document.getElementById(`step-dot-${i}`);
        dot.classList.remove("active", "done");
        if (i === 1) dot.classList.add("active");
    }
    currentPage = 1;

    // Clear all inputs
    document.querySelectorAll("#tab-submit input:not([type=hidden]):not([type=checkbox]), #tab-submit textarea, #tab-submit select").forEach(el => {
        if (el.tagName === "SELECT") el.selectedIndex = 0;
        else el.value = "";
    });
    document.querySelectorAll(".paf-toggle-btn").forEach(btn => {
        btn.dataset.value = "0";
        btn.classList.remove("on");
        const lbl = document.getElementById(btn.id.replace("Btn", "Label"));
        if (lbl) lbl.textContent = "No";
    });
    document.querySelectorAll(".paf-access-item.selected").forEach(el => el.classList.remove("selected"));
    document.querySelectorAll(".paf-check-item.checked").forEach(el => {
        el.classList.remove("checked");
        el.querySelector("input").checked = false;
    });
    document.getElementById("propertyFields").style.display   = "none";
    document.getElementById("corporateFields").style.display  = "none";
    document.getElementById("otherTitleWrap").style.display   = "none";
    document.getElementById("rmPropsWrap").style.display      = "none";
    document.getElementById("rentDiscountFields").style.display = "none";
    document.getElementById("relocFields").style.display        = "none";
    document.getElementById("cellFields").style.display         = "none";
    document.getElementById("empCodeDisplay").value = "";
    document.getElementById("hiringMgrDisplay").value = "";
    document.getElementById("btnSubmit").disabled = false;
    document.getElementById("btnSubmit").innerHTML = '<i class="fa-solid fa-paper-plane"></i> Submit';
    fillPositionSelect(PROPERTY_POSITIONS);
}

// ── History (admin) ────────────────────────────────────────────────────────────
async function loadHistory() {
    const tbody = document.getElementById("historyBody");
    const empty = document.getElementById("historyEmpty");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text-secondary);">Loading...</td></tr>';
    const res = await fetch("/paf/api/alerts");
    if (!res.ok) { tbody.innerHTML = ""; empty.style.display = "block"; return; }
    allHistory = await res.json();
    renderHistory(_applySort(allHistory));
}

function renderHistory(data) {
    const tbody = document.getElementById("historyBody");
    const empty = document.getElementById("historyEmpty");
    tbody.innerHTML = "";
    if (!data.length) {
        empty.style.display = "block";
        document.getElementById("historyTable").style.display = "none";
        return;
    }
    document.getElementById("historyTable").style.display = "";
    empty.style.display = "none";
    data.forEach(r => {
        const badgeClass = r.paf_type === "Promotion" ? "paf-badge-promotion" : "paf-badge-transfer";
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${r.id}</td>
            <td>${r.date_submitted}</td>
            <td><strong>${r.employee_name}</strong></td>
            <td><span class="paf-badge ${badgeClass}">${r.paf_type}</span></td>
            <td>${r.position}</td>
            <td>${r.effective_date}</td>
            <td>${r.location_type === "Property" ? r.property : r.department || r.location_type}</td>
            <td style="font-size:0.75rem;color:var(--text-secondary);">${r.submitted_by}</td>
        `;
        tbody.appendChild(tr);
    });
}

function sortHistory(th) {
    const col = th.dataset.col;
    if (_sortCol === col) {
        _sortDir = _sortDir === "asc" ? "desc" : "asc";
    } else {
        _sortCol = col;
        _sortDir = "asc";
    }
    document.querySelectorAll("#historyTable th[data-col]").forEach(h => h.classList.remove("sort-asc", "sort-desc"));
    th.classList.add(_sortDir === "asc" ? "sort-asc" : "sort-desc");
    filterHistory();
}

function _applySort(arr) {
    return [...arr].sort((a, b) => {
        let va = a[_sortCol] ?? "";
        let vb = b[_sortCol] ?? "";
        if (typeof va === "number" || typeof vb === "number") {
            va = Number(va) || 0; vb = Number(vb) || 0;
            return _sortDir === "asc" ? va - vb : vb - va;
        }
        va = String(va).toLowerCase(); vb = String(vb).toLowerCase();
        return _sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    });
}

function filterHistory() {
    const q = document.getElementById("historySearch").value.toLowerCase();
    let filtered = allHistory.filter(r =>
        r.employee_name.toLowerCase().includes(q) ||
        r.paf_type.toLowerCase().includes(q) ||
        r.position.toLowerCase().includes(q) ||
        r.submitted_by.toLowerCase().includes(q)
    );
    renderHistory(_applySort(filtered));
}

// ── Admin ──────────────────────────────────────────────────────────────────────
let _allAdmins = [], _adminSortCol = 'email', _adminSortDir = 'asc';

function sortAdminTbl(th) {
    const col = th.dataset.col;
    if (_adminSortCol === col) {
        _adminSortDir = _adminSortDir === 'asc' ? 'desc' : 'asc';
    } else {
        _adminSortCol = col; _adminSortDir = 'asc';
    }
    document.querySelectorAll('#adminTable th[data-col]').forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
    th.classList.add(_adminSortDir === 'asc' ? 'sort-asc' : 'sort-desc');
    renderAdmins(_applyAdminSort(_allAdmins));
}

function _applyAdminSort(arr) {
    return [...arr].sort((a, b) => {
        const va = String(a[_adminSortCol] ?? '').toLowerCase();
        const vb = String(b[_adminSortCol] ?? '').toLowerCase();
        return _adminSortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    });
}

function renderAdmins(data) {
    const tbody = document.getElementById('adminBody');
    if (!tbody) return;
    tbody.innerHTML = data.map(a =>
        `<tr><td>${a.email}</td>` +
        `<td style="color:var(--text-secondary);font-size:0.75rem;">${a.date_created || ''}</td>` +
        `<td><button class="paf-btn paf-btn-danger" onclick="removeAdmin(${a.id}, this)">Remove</button></td></tr>`
    ).join('');
}

async function loadAdmins() {
    if (!document.getElementById('adminBody')) return;
    const res = await fetch('/paf/api/admins');
    if (!res.ok) return;
    _allAdmins = await res.json();
    renderAdmins(_applyAdminSort(_allAdmins));
}

async function addAdmin() {
    const input = document.getElementById("adminEmailInput");
    const email = input.value.trim().toLowerCase();
    if (!email) return;
    const res = await fetch("/paf/api/admins", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
    });
    const result = await res.json();
    if (res.ok && result.success) { input.value = ""; loadAdmins(); }
    else alert(result.error || "Failed to add admin.");
}

async function removeAdmin(id, btn) {
    if (!confirm("Remove this admin?")) return;
    btn.disabled = true;
    await fetch(`/paf/api/admins/${id}`, { method: "DELETE" });
    loadAdmins();
}
