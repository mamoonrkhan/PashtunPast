// Languages page: search the cognate table, show/hide language columns, and
// optionally hide forms nobody has checked yet. The table itself is plain HTML
// built by the Python script; this only hides and shows parts of it.
(function () {
  "use strict";
  const form = document.getElementById("ling-filters");
  const table = document.getElementById("cognate-table");
  const rows = [...table.tBodies[0].rows];
  const count = document.getElementById("ling-count");
  const fold = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  function update() {
    const q = fold(form.elements.q.value.trim());
    const field = form.elements.field.value;
    const shown = new Set([...form.querySelectorAll("input[name=lang]:checked")].map((i) => i.value));
    const verifiedOnly = form.elements.verified_only.checked;

    table.querySelectorAll("[data-lang]").forEach((cell) => { cell.hidden = !shown.has(cell.dataset.lang); });
    table.querySelectorAll(".form").forEach((f) => { f.hidden = verifiedOnly && f.dataset.status !== "verified"; });

    let visible = 0;
    for (const row of rows) {
      const ok = (!q || fold(row.dataset.search).includes(q)) && (!field || row.dataset.field === field);
      row.hidden = !ok;
      if (ok) visible++;
    }
    count.textContent = `${visible} of ${rows.length} meanings shown`;
  }

  form.addEventListener("input", update);
  form.addEventListener("change", update);
  update();
})();
