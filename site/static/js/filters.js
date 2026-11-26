// Shared by the Explore, Timeline and Map pages.
//
// 1. Reads the atlas data embedded in the page (<script id="atlas-data">).
// 2. Keeps the filter form in sync with the page address, e.g.
//    map.html?population=saka&level=archaeology, so a filtered view can be shared
//    and filters carry over when you switch between Explore, Timeline and Map.
// 3. Decides which claims match, and tells the page whenever that changes.
//
// Safety: data text is only ever inserted with textContent (via Atlas.el), never as
// HTML, so a contributor's text can't inject code into the page.
(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("atlas-data").textContent);
  const form = document.getElementById("filters");
  const FIELDS = ["q", "population", "period", "level", "strength", "category"];

  // Search ignores case and accents ("Kanişka" finds "Kanishka").
  const fold = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  const popText = Object.fromEntries(
    data.populations.map((p) => [p.id, [p.name, ...(p.aliases || [])].join(" ")]));
  const regionText = Object.fromEntries(data.regions.map((r) => [r.id, r.name]));
  const haystack = new Map(data.claims.map((c) => [c.id, fold([
    c.title, c.statement, c.discussion, (c.tags || []).join(" "),
    c.populations.map((p) => popText[p]).join(" "),
    c.regions.map((r) => regionText[r]).join(" "),
  ].join(" "))]));

  function readForm() {
    const s = {};
    for (const f of FIELDS) s[f] = form.elements[f].value.trim();
    return s;
  }

  function matches(c, s) {
    if (s.q && !fold(s.q).split(/\s+/).every((w) => haystack.get(c.id).includes(w))) return false;
    if (s.population && !c.populations.includes(s.population)) return false;
    if (s.period && !(c.period && (c.period.periods || []).includes(s.period))) return false;
    if (s.level && !c.evidence_levels.includes(s.level)) return false;
    if (s.strength && c.strength !== s.strength) return false;
    if (s.category && c.category !== s.category) return false;
    return true;
  }

  function filterQuery(s) {
    const p = new URLSearchParams();
    for (const f of FIELDS) if (s[f]) p.set(f, s[f]);
    return p.toString();
  }

  function syncURL(s) {
    const params = new URLSearchParams(location.search);
    for (const f of FIELDS) s[f] ? params.set(f, s[f]) : params.delete(f);
    const qs = params.toString();
    history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
    // Carry the filters to the other explore views.
    const fq = filterQuery(s);
    document.querySelectorAll("a.keep-filters").forEach((a) => {
      const base = a.getAttribute("href").split("?")[0];
      a.setAttribute("href", base + (fq ? "?" + fq : ""));
    });
  }

  const listeners = [];
  let current = [];

  function update() {
    const s = readForm();
    syncURL(s);
    current = data.claims.filter((c) => matches(c, s));
    const count = document.getElementById("filter-count");
    if (count) {
      count.textContent = current.length === data.claims.length
        ? `${current.length} claims`
        : `${current.length} of ${data.claims.length} claims match`;
    }
    listeners.forEach((fn) => fn(current, s));
  }

  // Fill the form from the address bar on first load.
  const initial = new URLSearchParams(location.search);
  for (const f of FIELDS) if (initial.has(f)) form.elements[f].value = initial.get(f);
  // If a link already sets one of the filters hidden under "More filters", show them.
  const more = document.getElementById("more-filters");
  if (more && FIELDS.some((f) => f !== "q" && initial.get(f))) more.open = true;

  let timer;
  form.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(update, 120); });
  form.addEventListener("change", update);
  form.addEventListener("reset", () => setTimeout(update, 0));

  // Build DOM elements safely: el("a", {href: "x"}, "text", childNode, ...)
  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      // setProperty also handles CSS variables like "--cat" (plain assignment silently ignores them).
      if (k === "style" && typeof v === "object") for (const [p, val] of Object.entries(v)) node.style.setProperty(p, val);
      else if (k === "dataset") Object.assign(node.dataset, v);
      else node.setAttribute(k, v === true ? "" : v);
    }
    for (const ch of children.flat()) {
      if (ch === null || ch === undefined || ch === false) continue;
      node.append(ch instanceof Node ? ch : document.createTextNode(String(ch)));
    }
    return node;
  }

  const formatYear = (y) => (y < 0 ? `${-y} BCE` : `${y} CE`);

  window.Atlas = {
    data,
    el,
    formatYear,
    onChange(fn) { listeners.push(fn); },
    start: update,
    get matched() { return current; },
    levelsById: Object.fromEntries(data.levels.map((l) => [l.id, l])),
    regionsById: Object.fromEntries(data.regions.map((r) => [r.id, r])),
  };
})();
