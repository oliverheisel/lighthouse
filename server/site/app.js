const map = L.map("map", { scrollWheelZoom: false }).setView([20, 0], 2);

L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  { maxZoom: 20, attribution: "© OpenStreetMap © CARTO" }
).addTo(map);

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
  // makes sure we always have the directory of index.html
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

loadJson("data.min.json")
  .then(points => {
    for (const p of points) {
      const col = colorHex(p.color);
      const popup = `<b>${p.name}</b><br>${p.sequence || ""}`;

      L.circleMarker([p.lat, p.lon], {
        radius: 5,
        color: col,
        fillColor: col,
        fillOpacity: 0.95,
        weight: 1
      })
        .bindTooltip(p.name, { sticky: true })
        .bindPopup(popup)
        .addTo(map);
    }
  })
  .catch(err => {
    console.error(err);
    alert(err.message);
  });
