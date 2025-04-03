import folium
import requests
import xml.etree.ElementTree as ET
from shapely.geometry import Point, Polygon
from folium import Element, CustomIcon

# --- Config ---
kml_path = "zone_ops_stav-v2.kml"
output_html = "index.html"
map_center = [58.97104, 5.74131]

# --- Create map ---
fmap = folium.Map(location=map_center, zoom_start=13, zoom_control=False, control_scale=False)

# --- Load KML zones ---
ns = {'kml': 'http://www.opengis.net/kml/2.2'}
tree = ET.parse(kml_path)
root = tree.getroot()

zones = []
for placemark in root.findall(".//kml:Placemark", ns):
    name = placemark.find("kml:name", ns).text
    polygon_elem = placemark.find(".//kml:Polygon", ns)
    if polygon_elem is None:
        continue

    coords = []
    for coord_string in polygon_elem.findall(".//kml:coordinates", ns):
        coord_list = coord_string.text.strip().split()
        ring = [(float(c.split(',')[1]), float(c.split(',')[0])) for c in coord_list]
        coords.append(ring)

    outer_ring = coords[0]
    poly = Polygon(outer_ring)
    zones.append({"name": name, "polygon": poly, "count": 0})

    folium.Polygon(
        locations=outer_ring,
        popup=name,
        color="blue",
        weight=2,
        fill=True,
        fill_color="blue",
        fill_opacity=0.3
    ).add_to(fmap)

# --- Counters ---
total_scooters = 0
available_scooters = 0
out_of_zones = 0

# --- Battery category counters ---
black_count = 0
brown_count = 0
orange_count = 0
yellow_count = 0
green_count = 0
red_count = 0

# --- Fetch VOI scooters ---
url = "https://api.entur.io/mobility/v2/gbfs/v2/voistavanger/free_bike_status"
headers = {"ET-Client-Name": "voi-zone-map-script"}
response = requests.get(url, headers=headers)

if response.status_code == 200:
    bikes = response.json().get("data", {}).get("bikes", [])
    total_scooters = len(bikes)

    for bike in bikes:
        lat = bike["lat"]
        lon = bike["lon"]
        battery = bike.get("current_fuel_percent", 0)
        is_disabled = bike.get("is_disabled", False)

        if not is_disabled:
            available_scooters += 1

        point = Point(lat, lon)
        in_zone = False
        for zone in zones:
            if zone["polygon"].contains(point):
                zone["count"] += 1
                in_zone = True
                break
        if not in_zone:
            out_of_zones += 1

        # --- Choose icon and count category ---
        if is_disabled and battery > 0.10:
            icon_path = "scooter_icon_red.png"
            red_count += 1
        elif battery < 0.04:
            icon_path = "scooter_icon_black.png"
            black_count += 1
        elif battery < 0.10:
            icon_path = "scooter_icon_brown.png"
            brown_count += 1
        elif battery < 0.25:
            icon_path = "scooter_icon_orange.png"
            orange_count += 1
        elif battery < 0.55:
            icon_path = "scooter_icon_yellow.png"
            yellow_count += 1
        else:
            icon_path = "scooter_icon_green.png"
            green_count += 1

        icon = CustomIcon(
            icon_image=icon_path,
            icon_size=(30, 30),
            icon_anchor=(15, 15)
        )

        popup_text = f"🔋 Battery: {battery * 100:.1f}%<br>Status: {'Disabled' if is_disabled else 'Available'}"

        folium.Marker(
            location=[lat, lon],
            popup=popup_text,
            icon=icon
        ).add_to(fmap)
else:
    print("⚠️ Failed to fetch VOI scooter data:", response.status_code)

# --- Calculate availability percentage ---
availability_percent = (available_scooters / total_scooters * 100) if total_scooters else 0

# --- Sort zones by count descending ---
zones_sorted = sorted(zones, key=lambda z: z["count"], reverse=True)

## --- Left box: Zone counts ---
table_html = f"""
<div style="
    position: fixed;
    top: 20px;
    left: 20px;
    z-index: 1000;
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    padding: 16px 20px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
    max-height: 800px;
    overflow-y: auto;
    width: 280px;
    border: 1px solid #eee;
">
    <h3 style="margin-top: 0; font-size: 16px; color: #333;">🛴 Scooter Zones</h3>
    <p style="margin: 4px 0;"><strong>Total scooters:</strong> {total_scooters}</p>
    <p style="margin: 4px 0;"><strong>Out-of-zone:</strong> {out_of_zones}</p>
    <table style="width: 100%; margin-top: 10px; border-collapse: collapse;">
        <thead>
            <tr style="border-bottom: 2px solid #ddd;">
                <th style="text-align: left; padding: 6px 0; color: #555;">Zone</th>
                <th style="text-align: right; padding: 6px 0; color: #555;">Count</th>
            </tr>
        </thead>
        <tbody>
"""

for i, zone in enumerate(zones_sorted):
    bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"
    table_html += f"""
        <tr style="background: {bg};">
            <td style="padding: 6px 0;">{zone['name']}</td>
            <td style="padding: 6px 0; text-align: right; font-family: monospace;">{zone['count']}</td>
        </tr>
    """

table_html += """
        </tbody>
    </table>
</div>
"""

fmap.get_root().html.add_child(Element(table_html))

# --- Right box: Battery stats ---
category_html = f"""
<div style="
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 1000;
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    padding: 16px 20px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
    width: 260px;
    border: 1px solid #eee;
">
    <h3 style="margin-top: 0; font-size: 16px; color: #333;">⚡ Battery Stats</h3>
    <p style="margin: 4px 0; color: green;"><strong>Availability:</strong> {availability_percent:.1f}%</p>
    <table style="width: 100%; margin-top: 10px; border-collapse: collapse;">
        <tbody>
            <tr><td style="padding: 6px 0;"> <span style='color:#333;'>Critical low &lt; 4%</span></td><td style="text-align: right; font-family: monospace;">{black_count}</td></tr>
            <tr><td style="padding: 6px 0;"> <span style='color:#6e4b3a;'>Superlow 4–10%</span></td><td style="text-align: right; font-family: monospace;">{brown_count}</td></tr>
            <tr><td style="padding: 6px 0;"> <span style='color:#e67e22;'>10–25%</span></td><td style="text-align: right; font-family: monospace;">{orange_count}</td></tr>
            <tr><td style="padding: 6px 0;"> <span style='color:#f1c40f;'>25–55%</span></td><td style="text-align: right; font-family: monospace;">{yellow_count}</td></tr>
            <tr><td style="padding: 6px 0;"> <span style='color:#27ae60;'>Good &gt; 55%</span></td><td style="text-align: right; font-family: monospace;">{green_count}</td></tr>
            <tr><td style="padding: 6px 0;"> <span style='color:#e74c3c;'>Broken (&gt;10% + disabled)</span></td><td style="text-align: right; font-family: monospace;">{red_count}</td></tr>
        </tbody>
    </table>
</div>
"""

fmap.get_root().html.add_child(Element(category_html))

# --- Title box ---
title_html = """
<div style="
    position: fixed;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 1000;
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    padding: 12px 24px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 20px;
    font-weight: 600;
    color: #333;
    border: 1px solid #eee;
">
    VOI Fleet Stavanger
</div>
"""

fmap.get_root().html.add_child(Element(title_html))

# --- Save map ---
fmap.save(output_html)
print(f"✅ Map saved as '{output_html}' with updated battery categories")
