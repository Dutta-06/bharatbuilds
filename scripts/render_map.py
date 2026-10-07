"""Render a city's grid, hotspots and relief points as a standalone Leaflet map.

    python scripts/render_map.py delhi     # writes docs/maps/delhi.html

Open the file in a browser and check it looks like the city.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "maps"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chhaanv grid: __NAME__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 html,body,#map{height:100%;margin:0;font:14px system-ui,sans-serif}
 .legend{background:#fff;padding:8px 10px;border-radius:6px;line-height:1.6}
 .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
 .cell-label{background:none;border:none;box-shadow:none;font-size:11px;color:#333;font-weight:600}
</style></head><body><div id="map"></div><script>
const city = __CITY__, hotspots = __HOTSPOTS__, relief = __RELIEF__;
const b = city.bounds;
const map = L.map('map').fitBounds([[b.south, b.west], [b.north, b.east]]);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom: 18, attribution: '&copy; OpenStreetMap contributors'}).addTo(map);
L.rectangle([[b.south, b.west], [b.north, b.east]], {color: '#888', weight: 1, fill: false}).addTo(map);
for (const c of city.cells) {
  L.circleMarker([c.lat, c.lon], {radius: 5, color: '#1f6f50', fillOpacity: .9})
    .bindPopup(`<b>${c.name}</b> · ${c.name_hi}<br>${c.id}<br>elevation: ${c.elevation_m ?? 'not set'} m`)
    .bindTooltip(c.name, {permanent: true, direction: 'right', className: 'cell-label'}).addTo(map);
}
for (const h of hotspots) {
  L.circleMarker([h.lat, h.lon], {radius: 7, color: '#c0392b', fillOpacity: .6})
    .bindPopup(`<b>${h.name}</b><br>${h.kind} · cell ${h.cell_id}<br>verified: ${h.verified}`).addTo(map);
}
for (const p of relief) {
  L.circleMarker([p.lat, p.lon], {radius: 6, color: '#2471a3', fillOpacity: .6})
    .bindPopup(`<b>${p.name}</b><br>${p.type}: ${p.amenities.join(', ')}<br>cell ${p.cell_id}`).addTo(map);
}
const legend = L.control({position: 'bottomleft'});
legend.onAdd = () => { const d = L.DomUtil.create('div', 'legend'); d.innerHTML =
  `<b>${city.name}</b> · ${city.cells.length} cells<br>` +
  '<span class="dot" style="background:#1f6f50"></span>cell centroid<br>' +
  '<span class="dot" style="background:#c0392b"></span>waterlogging hotspot<br>' +
  '<span class="dot" style="background:#2471a3"></span>relief point'; return d; };
legend.addTo(map);
</script></body></html>
"""


def read(folder: str, city_id: str, key: str) -> list:
    path = DATA / folder / f"{city_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))[key] if path.exists() else []


def main(city_id: str) -> None:
    city = json.loads((DATA / "cities" / f"{city_id}.json").read_text(encoding="utf-8"))
    html = (PAGE.replace("__NAME__", city["name"])
                .replace("__CITY__", json.dumps(city, ensure_ascii=False))
                .replace("__HOTSPOTS__", json.dumps(read("hotspots", city_id, "hotspots"), ensure_ascii=False))
                .replace("__RELIEF__", json.dumps(read("relief", city_id, "points"), ensure_ascii=False)))
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{city_id}.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "delhi")
