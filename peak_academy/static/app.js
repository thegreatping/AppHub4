// Click-to-sort tables and type-to-filter boxes. No dependencies.
(function () {
  function cellValue(td, kind) {
    const raw = td.dataset.value !== undefined ? td.dataset.value : td.textContent.trim();
    if (kind === "text") return raw.toLowerCase();
    if (kind === "date") return raw && raw !== "None" ? Date.parse(raw) || 0 : -Infinity;
    const n = parseFloat(String(raw).replace(/[,%]/g, ""));
    return isNaN(n) ? -Infinity : n;
  }

  document.querySelectorAll("table.sortable").forEach(function (table) {
    table.querySelectorAll("th").forEach(function (th, idx) {
      const kind = th.dataset.sort || (th.classList.contains("num") ? "num" : "text");
      th.addEventListener("click", function () {
        const asc = !th.classList.contains("sorted-asc");
        table.querySelectorAll("th").forEach(function (h) { h.classList.remove("sorted-asc", "sorted-desc"); });
        th.classList.add(asc ? "sorted-asc" : "sorted-desc");
        const body = table.tBodies[0];
        Array.from(body.rows)
          .sort(function (a, b) {
            const x = cellValue(a.cells[idx], kind), y = cellValue(b.cells[idx], kind);
            return (x > y ? 1 : x < y ? -1 : 0) * (asc ? 1 : -1);
          })
          .forEach(function (r) { body.appendChild(r); });
      });
    });
  });

  document.querySelectorAll("input[data-filter-table]").forEach(function (input) {
    const table = document.getElementById(input.dataset.filterTable);
    if (!table) return;
    input.addEventListener("input", function () {
      const q = input.value.trim().toLowerCase();
      Array.from(table.tBodies[0].rows).forEach(function (r) {
        r.style.display = !q || r.textContent.toLowerCase().includes(q) ? "" : "none";
      });
    });
  });
})();
