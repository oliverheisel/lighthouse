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
  const payload = buildCmdPayload(p);
  return base64UrlEncodeString(JSON.stringify(payload));
}

/* ------------------------------
   Link base selector (bottom-left)
-------------------------------- */
const LinkControl = L.Control.extend({
  options: { position: "bottomleft" },

  onAdd: function () {
    const defaultFromParam = normalizeTargetUrl(getUrlParam("url"));
    const fallbackDefault = "http://lighthouse.local:8501/lighthouse";
    const defaultBase = defaultFromParam || fallbackDefault;

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
          value="${defaultBase}"
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

/* ------------------------------
   Popup (simple: name, id, seq, link)
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
        <a href="${url}" target="_self">
          Link to your lighthouse
        </a>
      </div>
    </div>
  `;
}

/* ------------------------------
   Load & render points (RICH)
-------------------------------- */
loadJson("data.rich.json")
  .then(points => {
    for (const p of points) {
      if (typeof p.lat !== "number" || typeof p.lon !== "number") continue;

      const col = colorHex(p.color);
      const name = p.name || "Unnamed";

      const marker = L.circleMarker([p.lat, p.lon], {
        radius: 5,
        color: col,
        fillColor: col,
        fillOpacity: 0.95,
        weight: 1
      })
        .bindTooltip(name, { sticky: true })
        .addTo(map);

      marker.bindPopup("");

      marker.on("popupopen", () => {
        marker.setPopupContent(popupHtml(p));
      });
    }
  })
  .catch(err => {
    console.error(err);
    alert(err.message);
  });
