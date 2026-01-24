const map = L.map("map", { scrollWheelZoom: true }).setView([20, 0], 2);

L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  { maxZoom: 20, attribution: "© OpenStreetMap © CARTO" }
).addTo(map);

/* ------------------------------
   URL param helper
-------------------------------- */
function getUrlParam(name) {
  try {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
  } catch (e) {
    return null;
  }
}

function normalizeTargetUrl(raw) {
  if (!raw) return "";
  let s = String(raw).trim();
  return s.replace(/\/+$/, "");
}

/* ------------------------------
   Encode cmd payload (Base64URL)
-------------------------------- */
function base64UrlEncodeString(str) {
  const b64 = btoa(unescape(encodeURIComponent(str)));
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function makeKey(p) {
  return (
    p.key ||
    (p.osm_type && (p.osm_id ?? p.id) ? p.osm_type[0] + (p.osm_id ?? p.id) : "") ||
    (p.type && p.id ? p.type[0] + p.id : "")
  );
}

function buildCmdPayload(p) {
  return {
    id: makeKey(p),
    name: p.name || "",
    color: p.color || "",
    sequence: p.sequence || "",
    main_period: p.main_period ?? null,
    main_character: p.main_character || "",
    sectors: Array.isArray(p.sectors) ? p.sectors.slice(0, 5) : []
  };
}

function buildCmdParam(p) {
  return base64UrlEncodeString(JSON.stringify(buildCmdPayload(p)));
}

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

/* ------------------------------
   Color + multicolor helpers (for filtering)
-------------------------------- */
function normalizeColorName(c) {
  const v = (c || "").toString().trim().toLowerCase();
  if (!v) return "";
  // keep expected OSM/seamark palette
  if (["red", "green", "white", "yellow", "blue"].includes(v)) return v;
  // common abbreviations in some datasets
  if (v === "w") return "white";
  if (v === "r") return "red";
  if (v === "g") return "green";
  if (v === "y") return "yellow";
  if (v === "b") return "blue";
  return v;
}

function sectorColors(p) {
  const out = [];
  const secs = Array.isArray(p.sectors) ? p.sectors : [];
  for (const s of secs) {
    const c = normalizeColorName(s && (s.c ?? s.colour));
    if (c) out.push(c);
  }
  return out;
}

function isMultiColor(p) {
  const set = new Set(sectorColors(p).filter(Boolean));
  // fallback: if no sectors, not multicolor
  return set.size >= 2;
}

function pointHasAnyColor(p, wantedSet) {
  if (!wantedSet || wantedSet.size === 0) return true;
  const main = normalizeColorName(p.color);
  if (main && wantedSet.has(main)) return true;

  for (const c of sectorColors(p)) {
    if (wantedSet.has(c)) return true;
  }
  return false;
}

/* ------------------------------
   Popup (simple)
-------------------------------- */
function popupHtml(p) {
  const name = p.name || "Unnamed";
  const key = makeKey(p);
  const seq = p.sequence || "";

  const base = getBaseUrl();
  const cmd = buildCmdParam(p);
  const url = base ? `${base}/?cmd=${cmd}` : `?cmd=${cmd}`;

  return `
    <div class="popup" style="min-width:220px">
      <div><b>${name}</b> | <span>${key}</span></div>
      ${seq ? `<div>Seq: ${seq}</div>` : ""}
      <div style="margin-top:8px">
        Link:
        <a href="${url}" target="_self" rel="noopener noreferrer">
          Link to your lighthouse
        </a>
      </div>
    </div>
  `;
}

/* ------------------------------
   Controls: Filter (top) + Base URL (bottom)
-------------------------------- */
const BottomPanelControl = L.Control.extend({
  options: { position: "bottomleft" },

  onAdd: function () {
    const defaultFromParam = normalizeTargetUrl(getUrlParam("url"));
    const fallbackDefault = "http://lighthouse.local:8501/lighthouse";
    const defaultBase = defaultFromParam || fallbackDefault;

    const div = L.DomUtil.create("div", "bottom-panel");
    div.innerHTML = `
      <div style="
        background: rgba(0,0,0,0.78);
        color: white;
        padding: 8px 10px;
        font-size: 12px;
        border-radius: 6px;
        width: 260px;
      ">

        <div style="font-weight:600; margin-bottom:6px;">Filters</div>

        <div style="margin-bottom:6px;">
          <label style="display:block; margin-bottom:3px;">Multicolor</label>
          <select id="fltMulticolor" style="width:100%; font-size:12px; padding:4px;">
            <option value="all">All</option>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </div>

        <div style="margin-bottom:10px;">
          <label style="display:block; margin-bottom:3px;">Colors</label>
          <div style="display:flex; flex-wrap:wrap; gap:6px;">
            ${["red","green","white","yellow","blue"].map(c => `
              <label style="display:flex; align-items:center; gap:4px;">
                <input type="checkbox" class="fltColor" value="${c}" />
                <span>${c}</span>
              </label>
            `).join("")}
          </div>
          <div style="margin-top:6px; display:flex; gap:6px;">
            <button id="btnAllColors" style="flex:1; padding:4px; font-size:12px;">All</button>
            <button id="btnNoColors" style="flex:1; padding:4px; font-size:12px;">None</button>
          </div>
        </div>

        <div style="border-top: 1px solid rgba(255,255,255,0.15); padding-top:8px;">
          <div style="margin-bottom:4px;">Detail base URL</div>
          <input
            id="linkBaseInput"
            type="text"
            value="${defaultBase}"
            style="width: 100%; font-size: 12px; padding: 4px;"
          />
        </div>

        <div id="fltStats" style="margin-top:6px; opacity:0.85;"></div>
      </div>
    `;

    L.DomEvent.disableClickPropagation(div);
    L.DomEvent.disableScrollPropagation(div);

    return div;
  }
});

map.addControl(new BottomPanelControl());

/* ------------------------------
   Marker store + filtering
-------------------------------- */
let ALL_POINTS = [];
let ALL_MARKERS = []; // { marker, point, key }
let MARKERS_BY_KEY = new Map();

function getSelectedColorSet() {
  const boxes = document.querySelectorAll(".fltColor");
  const set = new Set();
  boxes.forEach(b => {
    if (b.checked) set.add(b.value);
  });
  return set;
}

function getMulticolorMode() {
  const el = document.getElementById("fltMulticolor");
  return el ? el.value : "all";
}

function pointPassesFilters(p) {
  const mode = getMulticolorMode();
  if (mode === "yes" && !isMultiColor(p)) return false;
  if (mode === "no" && isMultiColor(p)) return false;

  const wanted = getSelectedColorSet();
  if (!pointHasAnyColor(p, wanted)) return false;

  return true;
}

function applyFilters() {
  let shown = 0;
  for (const it of ALL_MARKERS) {
    const ok = pointPassesFilters(it.point);
    if (ok) {
      if (!map.hasLayer(it.marker)) it.marker.addTo(map);
      shown += 1;
    } else {
      if (map.hasLayer(it.marker)) map.removeLayer(it.marker);
    }
  }

  const stats = document.getElementById("fltStats");
  if (stats) stats.textContent = `Showing ${shown} / ${ALL_MARKERS.length}`;
}

function wireFilterUI() {
  const sel = document.getElementById("fltMulticolor");
  if (sel) sel.addEventListener("change", applyFilters);

  const boxes = document.querySelectorAll(".fltColor");
  boxes.forEach(b => b.addEventListener("change", applyFilters));

  const allBtn = document.getElementById("btnAllColors");
  const noneBtn = document.getElementById("btnNoColors");

  if (allBtn) {
    allBtn.addEventListener("click", (e) => {
      e.preventDefault();
      document.querySelectorAll(".fltColor").forEach(b => (b.checked = true));
      applyFilters();
    });
  }

  if (noneBtn) {
    noneBtn.addEventListener("click", (e) => {
      e.preventDefault();
      document.querySelectorAll(".fltColor").forEach(b => (b.checked = false));
      applyFilters();
    });
  }
}

/* ------------------------------
   Focus selected lighthouse by ?id=
-------------------------------- */
function focusMarker(selectedKey) {
  if (!selectedKey) return false;

  const marker = MARKERS_BY_KEY.get(String(selectedKey));
  if (!marker) return false;

  const latlng = marker.getLatLng();
  map.setView(latlng, 10, { animate: true });

  L.circleMarker(latlng, {
    radius: 11,
    weight: 2,
    fillOpacity: 0,
    opacity: 1
  }).addTo(map);

  setTimeout(() => marker.openPopup(), 250);
  return true;
}

/* ------------------------------
   Load & render points (RICH)
-------------------------------- */
const selectedId = getUrlParam("id"); // e.g. n1208638993

loadJson("data.rich.json")
  .then(points => {
    ALL_POINTS = points || [];

    for (const p of ALL_POINTS) {
      if (typeof p.lat !== "number" || typeof p.lon !== "number") continue;

      const col = colorHex(p.color);
      const name = p.name || "Unnamed";
      const key = makeKey(p);

      const marker = L.circleMarker([p.lat, p.lon], {
        radius: 5,
        color: col,
        fillColor: col,
        fillOpacity: 0.95,
        weight: 1
      })
        .bindTooltip(name, { sticky: true });

      marker.bindPopup("");
      marker.on("popupopen", () => {
        marker.setPopupContent(popupHtml(p));
      });

      ALL_MARKERS.push({ marker, point: p, key });
      if (key) MARKERS_BY_KEY.set(String(key), marker);

      // add initially (filters applied after wiring)
      marker.addTo(map);
    }

    wireFilterUI();
    applyFilters();

    const ok = focusMarker(selectedId);
    if (selectedId && !ok) console.warn("Selected id not found:", selectedId);
  })
  .catch(err => {
    console.error(err);
    alert(err.message);
  });
