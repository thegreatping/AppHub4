/* ──────────────────────────────────────────────────────────────────────────
   TableMenu — shared unified column header menu for AppHub module tables.
   Clicking any column header opens one popover with: Sort A→Z / Z→A and an
   Excel-style multi-select value filter. No "Show Data" drilldown (module
   tables have no underlying data table to drill into).

   Behaviour:
   - Auto-enhances tables matching ENHANCE_SELECTOR (opt-in by class).
   - Operates purely on rendered DOM rows, so it is independent of each
     module's data pipeline and survives tbody re-renders (MutationObserver).
   - Intercepts header clicks in the capture phase to override any native
     onclick="sortX(this)" sort handlers.
   - Leadership Scorecard tables (.sc-table/.sc-dd-table) and the table
     manager (.stm-table) are intentionally NOT in the selector.
   ────────────────────────────────────────────────────────────────────────── */
(function () {
    'use strict';

    var ENHANCE_SELECTOR = [
        'table.data-table',
        'table.scm-table',
        'table.paf-table',
        'table.vs-table',
        'table.ms-table',
        'table.qad-table',
        'table.qas-table',
        'table.spr-steps'
    ].join(', ');

    // Header text that should never get a sort/filter menu.
    var SKIP_HEADER_TEXT = { '': 1, 'actions': 1, 'action': 1, 'fav': 1, 'theme': 1 };

    var menuEl = null;       // single shared popover
    var activeTable = null;  // table the popover currently targets
    var activeIdx = -1;      // column index the popover currently targets

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function getMenu() {
        if (menuEl) return menuEl;
        menuEl = document.createElement('div');
        menuEl.className = 'tm-menu';
        document.body.appendChild(menuEl);
        return menuEl;
    }

    function stateFor(table) {
        if (!table._tm) table._tm = { sort: null, filters: {} };
        return table._tm;
    }

    function headerCells(table) {
        var thead = table.tHead;
        if (!thead || !thead.rows.length) return [];
        // Last header row maps 1:1 to columns even when upper rows use colspans.
        var row = thead.rows[thead.rows.length - 1];
        return Array.prototype.slice.call(row.cells);
    }

    function firstBody(table) {
        return table.tBodies && table.tBodies[0] ? table.tBodies[0] : null;
    }

    function cellText(row, idx) {
        var c = row.cells[idx];
        return c ? c.textContent.trim().replace(/\s+/g, ' ') : '';
    }

    // Group each primary data row with any trailing satellite rows (expandable
    // detail / colspan rows have fewer cells than the header has columns) so
    // they travel together through sort and hide together through filter.
    function rowGroups(table) {
        var tb = firstBody(table);
        if (!tb) return [];
        var headerCount = headerCells(table).length;
        var groups = [];
        var cur = null;
        Array.prototype.slice.call(tb.rows).forEach(function (row) {
            var isPrimary = !cur || row.cells.length >= headerCount;
            if (isPrimary) { cur = { primary: row, sats: [] }; groups.push(cur); }
            else { cur.sats.push(row); }
        });
        return groups;
    }

    function thEligible(th) {
        if (th._tmSkip) return false;
        if (th.querySelector('input, button, select')) { th._tmSkip = true; return false; }
        var txt = th.textContent.trim().toLowerCase();
        if (SKIP_HEADER_TEXT[txt]) { th._tmSkip = true; return false; }
        return true;
    }

    // ── Decoration ──────────────────────────────────────────────────────────
    function decorateHeaders(table) {
        var st = stateFor(table);
        headerCells(table).forEach(function (th) {
            if (!thEligible(th)) return;
            if (!th._tmDecorated) {
                th._tmDecorated = true;
                th.classList.add('tm-th');
                var caret = document.createElement('span');
                caret.className = 'tm-caret';
                caret.innerHTML = '\u25BE';
                th.appendChild(caret);
            }
            var idx = th.cellIndex;
            var filtered = !!st.filters[idx];
            var dot = th.querySelector('.tm-dot');
            if (filtered && !dot) {
                dot = document.createElement('span');
                dot.className = 'tm-dot';
                th.insertBefore(dot, th.querySelector('.tm-caret'));
            } else if (!filtered && dot) {
                dot.remove();
            }
        });
    }

    // ── Sort / filter application ───────────────────────────────────────────
    function isNumericColumn(rows, idx) {
        var sawNumber = false;
        for (var i = 0; i < rows.length; i++) {
            var t = cellText(rows[i], idx).replace(/[$,%\s]/g, '');
            if (t === '' || t === '-') continue;
            if (isNaN(Number(t))) return false;
            sawNumber = true;
        }
        return sawNumber;
    }

    function applySort(table) {
        var st = stateFor(table);
        if (!st.sort) return;
        var tb = firstBody(table);
        if (!tb) return;
        var idx = st.sort.idx, dir = st.sort.dir;
        var groups = rowGroups(table);
        if (!groups.length) return;
        var primaries = groups.map(function (g) { return g.primary; });
        var numeric = isNumericColumn(primaries, idx);
        groups.sort(function (a, b) {
            var av = cellText(a.primary, idx), bv = cellText(b.primary, idx);
            var r;
            if (numeric) {
                var an = parseFloat(av.replace(/[$,%\s]/g, ''));
                var bn = parseFloat(bv.replace(/[$,%\s]/g, ''));
                if (isNaN(an)) an = -Infinity;
                if (isNaN(bn)) bn = -Infinity;
                r = an - bn;
            } else {
                r = av.localeCompare(bv, undefined, { numeric: true, sensitivity: 'base' });
            }
            return dir < 0 ? -r : r;
        });
        groups.forEach(function (g) {
            tb.appendChild(g.primary);
            g.sats.forEach(function (s) { tb.appendChild(s); });
        });
    }

    function applyFilters(table) {
        var st = stateFor(table);
        if (!firstBody(table)) return;
        var idxs = Object.keys(st.filters);
        rowGroups(table).forEach(function (g) {
            var show = true;
            for (var i = 0; i < idxs.length; i++) {
                var sel = st.filters[idxs[i]];
                if (!sel) continue;
                if (!sel.has(cellText(g.primary, Number(idxs[i])))) { show = false; break; }
            }
            g.primary.classList.toggle('tm-row-hidden', !show);
            // Satellites hide with a hidden parent; otherwise the module controls them.
            g.sats.forEach(function (s) { if (!show) s.classList.add('tm-row-hidden'); else s.classList.remove('tm-row-hidden'); });
        });
    }

    function reapply(table) {
        var obs = table._tmObs;
        if (obs) obs.disconnect();
        decorateHeaders(table);
        applySort(table);
        applyFilters(table);
        if (obs) obs.observe(table, { childList: true, subtree: true });
    }

    function scheduleReapply(table) {
        if (table._tmPending) return;
        table._tmPending = true;
        // setTimeout (not requestAnimationFrame) so it still fires in background tabs.
        setTimeout(function () { table._tmPending = false; reapply(table); }, 0);
    }

    // ── Popover ─────────────────────────────────────────────────────────────
    function distinctValues(table, idx) {
        var seen = Object.create(null);
        var out = [];
        rowGroups(table).forEach(function (g) {
            if (g.primary.cells.length <= idx) return;
            var v = cellText(g.primary, idx);
            if (!(v in seen)) { seen[v] = 1; out.push(v); }
        });
        out.sort(function (a, b) { return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }); });
        return out;
    }

    function positionMenu(anchor) {
        var menu = getMenu();
        var rect = anchor.getBoundingClientRect();
        var width = Math.max(rect.width, 210);
        var left = Math.min(rect.left, window.innerWidth - width - 8);
        var top = rect.bottom + 2;
        if (top + 360 > window.innerHeight) top = Math.max(8, window.innerHeight - 360 - 8);
        menu.style.left = Math.max(8, left) + 'px';
        menu.style.top = top + 'px';
        menu.style.width = width + 'px';
    }

    function renderMenu() {
        var menu = getMenu();
        var table = activeTable, idx = activeIdx;
        var st = stateFor(table);
        var all = distinctValues(table, idx);
        var sel = st.filters[idx];
        var allSelected = !sel;
        menu.innerHTML =
            '<div class="tm-action" data-act="sort-asc"><span class="ico">\u25B2</span> Sort A to Z</div>' +
            '<div class="tm-action" data-act="sort-desc"><span class="ico">\u25BC</span> Sort Z to A</div>' +
            '<div class="tm-divider"></div>' +
            '<div class="tm-search"><input type="text" placeholder="Filter list..."></div>' +
            '<div class="tm-all-row" data-act="all"><input type="checkbox" ' + (allSelected ? 'checked' : '') +
                ' tabindex="-1" style="pointer-events:none"> <strong>(Select all)</strong></div>' +
            '<div class="tm-list">' +
            all.map(function (v) {
                var checked = allSelected || sel.has(v);
                return '<div class="tm-item ' + (checked ? 'selected' : '') + '" data-val="' + esc(v) + '">' +
                    '<input type="checkbox" ' + (checked ? 'checked' : '') + ' tabindex="-1" style="pointer-events:none">' +
                    '<span>' + (esc(v) || '<em style="opacity:.6">(blank)</em>') + '</span></div>';
            }).join('') +
            '</div>' +
            '<div class="tm-hint">Click a value to show only it &bull; Ctrl+click to multi-select</div>' +
            '<div class="tm-footer"><button type="button" data-act="clear">Clear</button>' +
            '<button type="button" data-act="done">Done</button></div>';
    }

    function openMenu(table, th) {
        var menu = getMenu();
        var idx = th.cellIndex;
        var wasOpenForThis = menu.classList.contains('open') && activeTable === table && activeIdx === idx;
        closeMenu();
        if (wasOpenForThis) return;
        activeTable = table;
        activeIdx = idx;
        renderMenu();
        positionMenu(th);
        menu.classList.add('open');
    }

    function closeMenu() {
        if (menuEl) menuEl.classList.remove('open');
    }

    function refreshMenuKeepingSearch() {
        var menu = getMenu();
        var input = menu.querySelector('.tm-search input');
        var sv = input ? input.value : '';
        renderMenu();
        if (sv) {
            var ni = menu.querySelector('.tm-search input');
            if (ni) { ni.value = sv; filterList(ni); }
        }
    }

    function filterList(input) {
        var q = input.value.trim().toLowerCase();
        var list = getMenu().querySelector('.tm-list');
        if (!list) return;
        Array.prototype.slice.call(list.querySelectorAll('.tm-item')).forEach(function (el) {
            el.style.display = (!q || el.textContent.toLowerCase().indexOf(q) !== -1) ? '' : 'none';
        });
    }

    function doSort(dir) {
        stateFor(activeTable).sort = { idx: activeIdx, dir: dir };
        closeMenu();
        reapply(activeTable);
    }

    function onItemClick(value, ev) {
        var st = stateFor(activeTable);
        var all = distinctValues(activeTable, activeIdx);
        if (ev && (ev.ctrlKey || ev.metaKey)) {
            var set = st.filters[activeIdx] ? new Set(st.filters[activeIdx]) : new Set(all);
            if (set.has(value)) set.delete(value); else set.add(value);
            st.filters[activeIdx] = (set.size >= all.length) ? null : set;
            if (!st.filters[activeIdx]) delete st.filters[activeIdx];
        } else {
            var cur = st.filters[activeIdx];
            if (cur && cur.size === 1 && cur.has(value)) delete st.filters[activeIdx];
            else st.filters[activeIdx] = new Set([value]);
        }
        refreshMenuKeepingSearch();
        reapply(activeTable);
    }

    function selectAll() {
        var st = stateFor(activeTable);
        if (st.filters[activeIdx]) delete st.filters[activeIdx];
        else st.filters[activeIdx] = new Set();
        refreshMenuKeepingSearch();
        reapply(activeTable);
    }

    function clearFilter() {
        delete stateFor(activeTable).filters[activeIdx];
        refreshMenuKeepingSearch();
        reapply(activeTable);
    }

    // ── Menu interaction (delegated) ────────────────────────────────────────
    getMenu().addEventListener('click', function (e) {
        var item = e.target.closest('.tm-item');
        if (item) { onItemClick(item.getAttribute('data-val'), e); return; }
        var act = e.target.closest('[data-act]');
        if (!act) return;
        switch (act.getAttribute('data-act')) {
            case 'sort-asc': doSort(1); break;
            case 'sort-desc': doSort(-1); break;
            case 'all': selectAll(); break;
            case 'clear': clearFilter(); break;
            case 'done': closeMenu(); break;
        }
    });
    getMenu().addEventListener('input', function (e) {
        if (e.target.matches('.tm-search input')) filterList(e.target);
    });

    // ── Header click interception (capture phase overrides native sort) ─────
    document.addEventListener('click', function (e) {
        var th = e.target.closest('th');
        if (!th) return;
        var table = th.closest('table');
        if (!table || !table._tmEnhanced || th._tmSkip) return;
        if (e.target.closest('input, button, select, a')) return; // leave controls alone
        if (!th._tmDecorated) return; // not an eligible header
        e.stopPropagation();
        e.preventDefault();
        openMenu(table, th);
    }, true);

    // ── Global dismiss handlers ─────────────────────────────────────────────
    document.addEventListener('pointerdown', function (e) {
        if (e.target.closest('.tm-menu') || e.target.closest('th.tm-th')) return;
        closeMenu();
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });
    document.addEventListener('scroll', function (e) {
        if (e.target instanceof Element && e.target.closest('.tm-menu')) return;
        closeMenu();
    }, true);
    window.addEventListener('resize', closeMenu);

    // ── Enhancement + auto-discovery ────────────────────────────────────────
    function enhance(table) {
        if (table._tmEnhanced) return;
        table._tmEnhanced = true;
        decorateHeaders(table);
        // Watch the whole table so late-rendered headers, tbody re-renders, and
        // full-table rebuilds all re-decorate and re-apply the active sort/filter.
        var obs = new MutationObserver(function () { scheduleReapply(table); });
        obs.observe(table, { childList: true, subtree: true });
        table._tmObs = obs;
    }

    function scan(root) {
        (root || document).querySelectorAll(ENHANCE_SELECTOR).forEach(enhance);
    }

    function init() {
        scan();
        // Catch SPA content swaps and dynamically rendered tables.
        var bodyObs = new MutationObserver(function (muts) {
            for (var i = 0; i < muts.length; i++) {
                var added = muts[i].addedNodes;
                for (var j = 0; j < added.length; j++) {
                    var n = added[j];
                    if (n.nodeType !== 1) continue;
                    if (n.matches && n.matches(ENHANCE_SELECTOR)) enhance(n);
                    if (n.querySelectorAll) scan(n);
                }
            }
        });
        bodyObs.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.TableMenu = { enhance: enhance, enhanceAll: scan };
})();
