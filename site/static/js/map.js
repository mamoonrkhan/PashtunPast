// Map page (Leaflet).
//
// Every region from data/geo/ is drawn as a rough shape. Shading shows how many
// of the currently filtered claims mention that region. Clicking a region lists
// those claims in the side panel.
(function () {
  "use strict";
  const { el, regionsById } = Atlas;
  const geo = JSON.parse(document.getElementById("geo-data").textContent);
  const panel = document.getElementById("map-panel");

  const map = L.map("map", { scrollWheelZoom: false });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 9,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  let counts = {};
  let selected = new URLSearchParams(location.search).get("region");
  const layers = {};

  function style(feature) {
    const id = feature.properties.id;
    const n = counts[id] || 0;
    const max = Math.max(1, ...Object.values(counts));
    return {
      color: id === selected ? "#111111" : "#1f4e79",
      weight: id === selected ? 3 : 1.5,
      dashArray: "4 3",                         // dashed outline = "approximate"
      fillColor: n ? "#1f4e79" : "#9aa0a6",
      fillOpacity: n ? 0.15 + 0.5 * (n / max) : 0.05,
    };
  }

  const regionLayer = L.geoJSON(geo, {
    style,
    onEachFeature(feature, layer) {
      const id = feature.properties.id;
      layers[id] = layer;
      // Pass a DOM node, not an HTML string, so data text can't inject HTML.
      layer.bindTooltip(() => el("span", {}, `${feature.properties.name} · ${counts[id] || 0} claim(s)`), { sticky: true });
      layer.on("click", () => select(id));
    },
  }).addTo(map);
  map.fitBounds(regionLayer.getBounds(), { padding: [10, 10] });

  function select(id) {
    selected = id;
    const params = new URLSearchParams(location.search);
    id ? params.set("region", id) : params.delete("region");
    history.replaceState(null, "", location.pathname + "?" + params.toString());
    regionLayer.setStyle(style);
    renderPanel();
    // The button that was used has just been replaced, so move keyboard focus
    // (and, on phones, the scroll position) to the panel's new heading.
    panel.querySelector("h2").focus();
  }

  function renderPanel() {
    if (!selected || !regionsById[selected]) {
      // A list of every region as buttons: the keyboard- and screen-reader-friendly
      // way to choose a region, and a text summary of what the map shows.
      const regions = Atlas.data.regions
        .map((r) => ({ r, n: counts[r.id] || 0 }))
        .sort((a, b) => b.n - a.n || a.r.name.localeCompare(b.r.name));
      panel.replaceChildren(
        el("h2", { tabindex: "-1" }, "Regions"),
        el("p", { class: "small muted" }, "Click a shape on the map, or choose a region here."),
        el("ul", { class: "region-list" }, regions.map(({ r, n }) => {
          const btn = el("button", { type: "button", class: "link-button region-button" },
            r.name, " ", el("span", { class: "muted" }, `(${n})`));
          btn.addEventListener("click", () => select(r.id));
          return el("li", {}, btn);
        })));
      return;
    }
    const r = regionsById[selected];
    const feature = geo.features.find((f) => f.properties.id === selected);
    const claims = Atlas.matched.filter((c) => c.regions.includes(selected));
    panel.replaceChildren(
      el("h2", { tabindex: "-1" }, r.name),
      r.modern ? el("p", { class: "small" }, "Today: " + r.modern.join("; ")) : null,
      feature ? el("p", { class: "small muted" }, feature.properties.note) : null,
      el("h3", {}, `${claims.length} matching claim(s)`),
      el("ul", { class: "panel-claims" }, claims.map((c) =>
        el("li", {},
          el("a", { href: c.url }, c.title), " ",
          el("span", { class: `badge strength strength-${c.strength}` }, c.strength),
          c.status !== "verified" ? el("span", { class: "badge status-unverified small-badge" }, "UNVERIFIED") : null))),
      el("button", { type: "button", class: "link-button" }, "← All regions"));
    panel.querySelector("button").addEventListener("click", () => select(null));
  }

  Atlas.onChange((matched) => {
    counts = {};
    for (const c of matched) for (const r of c.regions) counts[r] = (counts[r] || 0) + 1;
    regionLayer.setStyle(style);
    renderPanel();
  });
  Atlas.start();
})();
