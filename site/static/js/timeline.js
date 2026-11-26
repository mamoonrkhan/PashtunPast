// Timeline page.
//
// Each dated claim becomes a row with a bar from its start to its end year.
// Positions are percentages of the visible range, so the chart resizes with the
// window. A top lane shows the named periods for orientation.
(function () {
  "use strict";
  const { data, el, formatYear } = Atlas;
  const root = document.getElementById("timeline");
  const empty = document.getElementById("empty");
  let range = [-3000, 2050];

  const pct = (year) => ((year - range[0]) / (range[1] - range[0])) * 100;

  // Pick the smallest year step that keeps labels at least ~70px apart,
  // so the axis stays readable on a phone as well as a wide screen.
  function tickStep(span, trackPx) {
    for (const step of [50, 100, 250, 500, 1000, 2000]) {
      if ((trackPx * step) / span >= 70) return step;
    }
    return 2000;
  }

  function axis() {
    const row = el("div", { class: "tl-row tl-axis", "aria-hidden": "true" }, el("div", { class: "tl-label" }));
    row.append(el("div", { class: "tl-track" }));
    return row;
  }

  // Ticks are added after the axis is on the page, because their spacing
  // depends on how wide the track actually is.
  function fillTicks(row) {
    const track = row.querySelector(".tl-track");
    const step = tickStep(range[1] - range[0], track.clientWidth || 600);
    for (let y = Math.ceil(range[0] / step) * step; y <= range[1]; y += step) {
      const label = y === 0 ? "BCE | CE" : formatYear(y);
      track.append(el("span", { class: "tl-tick", style: { left: pct(y) + "%" } }, label));
    }
  }

  // Periods can overlap, so put them in as few lanes as possible without collisions.
  function periodLanes() {
    const lanes = [];
    const sorted = [...data.periods].sort((a, b) => a.start - b.start);
    for (const p of sorted) {
      let lane = lanes.find((l) => l[l.length - 1].end <= p.start);
      if (!lane) lanes.push((lane = []));
      lane.push(p);
    }
    return lanes.map((lane, i) => {
      const track = el("div", { class: "tl-track" });
      for (const p of lane) {
        if (p.end < range[0] || p.start > range[1]) continue;
        const a = Math.max(p.start, range[0]), b = Math.min(p.end, range[1]);
        track.append(el("span", {
          class: "tl-period",
          style: { left: pct(a) + "%", width: (pct(b) - pct(a)) + "%" },
          title: `${p.label}: ${formatYear(p.start)} – ${formatYear(p.end)} (approximate)`,
        }, p.label));
      }
      return el("div", { class: "tl-row tl-periods" }, el("div", { class: "tl-label" }, i === 0 ? "Periods" : ""), track);
    });
  }

  function claimRow(c) {
    const { start, end } = c.period;
    const a = Math.max(start, range[0]), b = Math.min(end, range[1]);
    const left = pct(a), width = Math.max(pct(b) - left, 0.8);
    const tip = `${c.title} — ${c.period.label} · strength: ${c.strength}`;
    const bar = el("a", {
      class: `tl-bar strength-${c.strength}` + (start < range[0] ? " cut-left" : "") + (end > range[1] ? " cut-right" : ""),
      href: c.url,
      title: tip,
      "aria-label": tip,
      style: { left: left + "%", width: width + "%", "--cat": data.category_colors[c.category] },
    });
    return el("div", { class: "tl-row" },
      el("div", { class: "tl-label" }, el("a", { href: c.url }, c.title)),
      el("div", { class: "tl-track" }, bar));
  }

  function legend() {
    const box = document.getElementById("timeline-legend");
    box.replaceChildren(
      ...Object.entries(data.categories).map(([id, label]) =>
        el("span", { class: "legend-item" }, el("span", { class: "swatch", style: { background: data.category_colors[id] } }), label)),
      el("span", { class: "legend-item" }, el("span", { class: "swatch striped" }), "Contested"));
  }

  function render(matched) {
    const dated = matched
      .filter((c) => c.period && c.period.end >= range[0] && c.period.start <= range[1])
      .sort((x, y) => x.period.start - y.period.start || x.period.end - y.period.end);
    const axisRow = axis();
    root.replaceChildren(axisRow, ...periodLanes(), ...dated.map(claimRow));
    fillTicks(axisRow);
    empty.hidden = dated.length > 0;
  }

  // Re-draw when the window size changes (e.g. a phone is rotated).
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => render(Atlas.matched), 150);
  });

  document.querySelectorAll(".timeline-controls button").forEach((btn) => {
    btn.addEventListener("click", () => {
      range = btn.dataset.range.split(",").map(Number);
      document.querySelectorAll(".timeline-controls button").forEach((b) => b.classList.toggle("active", b === btn));
      render(Atlas.matched);
    });
  });

  legend();
  Atlas.onChange(render);
  Atlas.start();
})();
