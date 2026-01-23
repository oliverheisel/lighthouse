const map = L.map("map", { scrollWheelZoom: true }).setView([20, 0], 2);

L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  { maxZoom: 20, attribution: "© OpenStreetMap © CARTO" }
).addTo(map);

/* ------------------------------
   Link base selector (bottom-left)
-------------------------------- */
const LinkControl = L.Control.extend({
  options: { position: "bottomleft" },

  onAdd: function () {
    const div = L.DomUtil.create("div", "link-control");
    div.innerHTML = `
      <div style="
        background: rgba(0,0,0,0.75);
        color: white;
        padding: 6px 8px;
        font-size: 12px;
        border-radius: 4px;
      ">
        <div style="margin-bottom:4px;">Detail base URL</div>
        <input
          id="linkBaseInput"
          type="text"
          value="http://lighthouse.local:8501"
          style="
            width: 220px;
            font-size: 12px;
            padding: 3px;
          "
        />
      </div>
    `;

    L.DomEvent.disableClickPropagation(div);
    L.DomEvent.disableScrollPropagation(div);

    return div;
  }
});

map.addControl(new LinkControl());

/* ------------------------------
   Helpers
-------------------------------- */
function getBaseUrl() {
  const el = document.getElementById("linkBaseInput");
  if (!el || !el.value) return "";
  return el.value.trim().replace(/\/+$/, "");
}

function colorHex(c) {
  const v = (c || "").toLowerCase();
  if (v === "red") return "#ff4b4b";
  if (v === "green") return "#2ecc71";
  if (v === "white") return "#ffffff";
  if (v === "yellow") return "#f1c40f";
  if (v === "blue") return "#4aa3ff";
  return "#cfcfcf";
}

function basePath() {
  let p = window.location.pathname;
  if (!p.endsWith("/")) p = p.substring(0, p.lastIndexOf("/") + 1);
  return p;
}

async function loadJson(filename) {
  const url = basePath() + filename;

  const resp = await fetch(url, { cache: "no-store" });
  const text = await resp.text();

  if (!resp.ok) {
    throw new Error(`GET ${url} -> HTTP ${resp.status}. First bytes: ${text.slice(0, 200)}`);
  }

  try {
    return JSON.parse(text);
  } catch (e) {
    throw new Error(`Invalid JSON from ${url}. First bytes: ${text.slice(0, 200)}`);
  }
}

function makeKey(p) {
  return (
    p.key ||
    (p.osm_type && (p.osm_id ?? p.id) ? p.osm_type[0] + (p.osm_id ?? p.id) : "") ||
    (p.type && p.id ? p.type[0] + p.id : "")
  );
}

function popupHtml(name, key, seq) {
  const base = getBaseUrl();
  const url = base ? `${base}/?id=${key}` : `?id=${key}`;

  return `
    <div class="popup">
      <div><b>${name}</b> | <span>${key}</span></div>
      <div>Seq: ${seq}</div>
      <div>
        Link:
        <a href="${url}" target="_blank" rel="noopener noreferrer">
          ${url}
        </a>
      </div>
    </div>
  `;
}

/* ------------------------------
   Load & render points
-------------------------------- */
loadJson("data.min.json")
  .then(points => {
    for (const p of points) {
      if (typeof p.lat !== "number" || typeof p.lon !== "number") continue;

      const col = colorHex(p.color);
      const name = p.name || "Unnamed";
      const seq = p.sequence || "";
      const key = makeKey(p);

      const marker = L.circleMarker([p.lat, p.lon], {
        radius: 5,
        color: col,
        fillColor: col,
        fillOpacity: 0.95,
        weight: 1
      })
        .bindTooltip(name, { sticky: true })
        .addTo(map);

      // Create an empty popup first
      marker.bindPopup("");

      // Rebuild popup HTML each time it opens (so URL always matches input)
      marker.on("popupopen", () => {
        marker.setPopupContent(popupHtml(name, key, seq));
      });
    }
  })
  .catch(err => {
    console.error(err);
    alert(err.message);
  });
