const map = L.map("map", {
  scrollWheelZoom: false
}).setView([20, 0], 2);

L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  {
    maxZoom: 20,
    attribution: "© OpenStreetMap © CARTO"
  }
).addTo(map);

function colorHex(c) {
  const v = (c || "").toLowerCase();
  if (v === "red") return "#ff4b4b";
  if (v === "green") return "#2ecc71";
  if (v === "white") return "#ffffff";
  if (v === "yellow") return "#f1c40f";
  return "#cfcfcf";
}

fetch("data.min.json", { cache: "no-store" })
  .then(r => {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  })
  .then(points => {
    for (const p of points) {
      const col = colorHex(p.color);

      L.circleMarker([p.lat, p.lon], {
        radius: 5,
        color: col,
        fillColor: col,
        fillOpacity: 0.95,
        weight: 1
      })
        .bindTooltip(p.name, { sticky: true })
        .bindPopup(`<b>${p.name}</b><br>${p.sequence || ""}`)
        .addTo(map);
    }
  })
  .catch(err => {
    console.error(err);
    alert("Failed to load lighthouse data");
  });
