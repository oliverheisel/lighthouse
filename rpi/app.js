// rpi/app.js
// Streamlit-safe Leaflet map:
// - no normal navigation
// - updates parent URL query param ?id=... via history.replaceState (no reload)
// - clicking a marker updates ?id=... so Streamlit can read it
// - if the app is opened with ?id=..., the map auto-zooms to that lighthouse and opens its tooltip

function parentWin() {
  try {
    return window.parent;
  } catch (e) {
    return window;
  }
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

function makeKey(p) {
  return (
    p.key ||
    (p.osm_type && (p.osm_id ?? p.id)
      ? p.osm_type[0] + (p.osm_id ?? p.id)
      : "") ||
    (p.type && p.id ? p.type[0] + p.id : "")
  );
}

function setParentQueryParam(key) {
  const w = parentWin();
  if (!w || !w.location) return;

  try {
    const url = new URL(w.location.href);
    url.searchParams.set("id", key);

    // Replace the URL in the browser bar WITHOUT navigation/reload
    w.history.replaceState({}, "", url.toString());

    // Also emit a message (optional, useful for debugging)
    w.postMessage({ type: "lighthouse:selected", id: key }, "*");
  } catch (e) {
    console.warn("Failed to set parent URL param", e);
  }
}

function getSelectedIdFromParent() {
  // Prefer parent URL because we are inside a Streamlit iframe
  try {
    const url = new URL(parentWin().location.href);
    return url.searchParams.get("id");
  } catch (e) {
    try {
      const url = new URL(window.location.href);
      return url.searchParams.get("id");
    } catch (e2) {
      return null;
    }
  }
}

function zoomToKey(map, markersByKey, key) {
  const marker = markersByKey[key];
  if (!marker) return false;

  const ll = marker.getLatLng();

  // Sensible default zoom for "zoom into lighthouse"
  const targetZoom = Math.max(map.getZoom(), 14);
  map.setView(ll, targetZoom, { animate: true });

  // Tooltip is already configured, so open it to give immediate feedback
  try {
    marker.openTooltip();
  } catch (e) {}

  return true;
}

(function main() {
  const points = window.POINTS || [];

  const map = L.map("map", { scrollWheelZoom: true }).setView([20, 0], 2);

  L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    { maxZoom: 20, attribution: "© OpenStreetMap © CARTO" }
  ).addTo(map);

  const markersByKey = {};

  for (const p of points) {
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
      .bindTooltip(name, { sticky: true })
      .addTo(map);

    markersByKey[key] = marker;

    marker.on("click", () => {
      setParentQueryParam(key);
      zoomToKey(map, markersByKey, key);
    });
  }

  // Auto-zoom on initial load if opened with ?id=...
  const initialId = getSelectedIdFromParent();
  if (initialId) {
    // Wait a moment so the map has a size and Leaflet can compute positions
    setTimeout(() => {
      zoomToKey(map, markersByKey, initialId);
    }, 50);
  }
})();
