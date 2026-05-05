import os
import time
import pandas as pd
import geopandas as gpd
import osmnx as ox

# ==========================================================
# OSM Road Network Extraction for 7 Malaysian Cities
# Output:
# 1. OSM_road_network_indicators_7_cities.xlsx
# 2. boundary geojson for each city
# 3. road edge geojson for each city
# ==========================================================

# --------------------------
# 1. Output folders
# --------------------------
OUTPUT_DIR = "OSM_output"
EDGE_DIR = os.path.join(OUTPUT_DIR, "road_edges")
BOUNDARY_DIR = os.path.join(OUTPUT_DIR, "city_boundaries")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(EDGE_DIR, exist_ok=True)
os.makedirs(BOUNDARY_DIR, exist_ok=True)

OUTPUT_EXCEL = os.path.join(OUTPUT_DIR, "OSM_road_network_indicators_7_cities.xlsx")

# --------------------------
# 2. OSMnx settings
# --------------------------
ox.settings.use_cache = True
ox.settings.log_console = True
ox.settings.timeout = 300

# --------------------------
# 3. Study cities
# --------------------------
cities = [
    {
        "city": "George Town",
        "query": "George Town, Penang, Malaysia"
    },
    {
        "city": "Kota Bharu",
        "query": "Kota Bharu, Kelantan, Malaysia"
    },
    {
        "city": "Kuala Lumpur",
        "query": "Kuala Lumpur, Malaysia"
    },
    {
        "city": "Seberang Perai",
        "query": "Seberang Perai, Penang, Malaysia"
    },
    {
        "city": "Johor Bahru",
        "query": "Johor Bahru, Johor, Malaysia"
    },
    {
        "city": "Ipoh",
        "query": "Ipoh, Perak, Malaysia"
    },
    {
        "city": "Kajang",
        "query": "Kajang, Selangor, Malaysia"
    }
]

# --------------------------
# 4. Road classes
# --------------------------
DRIVABLE_CLASSES = [
    "motorway", "motorway_link",
    "trunk", "trunk_link",
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
    "service"
]

ROAD_CLASS_PRIORITY = [
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
    "service"
]


def safe_name(name: str) -> str:
    """Convert city name to safe file name."""
    return name.replace(" ", "_").replace("/", "_").replace("-", "_")


def highway_to_list(value):
    """Convert OSM highway value to list."""
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def has_any_highway(value, classes):
    """Check whether an OSM edge belongs to any target highway class."""
    values = highway_to_list(value)
    return any(v in classes for v in values)


def main_highway_class(value):
    """Assign one main highway class based on priority."""
    values = highway_to_list(value)
    for cls in ROAD_CLASS_PRIORITY:
        if cls in values:
            return cls
    return values[0]


def sum_length_by_classes(edges_gdf, classes):
    """Sum road length for selected highway classes."""
    selected = edges_gdf[
        edges_gdf["highway"].apply(lambda x: has_any_highway(x, classes))
    ]
    return selected["length_km"].sum()


# --------------------------
# 5. Main loop
# --------------------------
results = []

for item in cities:
    city = item["city"]
    query = item["query"]
    file_city = safe_name(city)

    print("\n" + "=" * 70)
    print(f"Processing: {city}")
    print(f"OSM query: {query}")
    print("=" * 70)

    try:
        # --------------------------------------------------
        # 5.1 Download city boundary from OSM / Nominatim
        # --------------------------------------------------
        boundary = ox.geocoder.geocode_to_gdf(query)
        boundary = boundary.to_crs(epsg=4326)

        boundary_file = os.path.join(BOUNDARY_DIR, f"{file_city}_boundary.geojson")
        boundary.to_file(boundary_file, driver="GeoJSON")

        # --------------------------------------------------
        # 5.2 Download drive road network by place boundary
        # --------------------------------------------------
        G = ox.graph.graph_from_place(
            query,
            network_type="drive",
            simplify=True,
            retain_all=True,
            truncate_by_edge=True
        )

        # --------------------------------------------------
        # 5.3 Project graph to metre-based CRS
        # --------------------------------------------------
        G_proj = ox.projection.project_graph(G)

        # --------------------------------------------------
        # 5.4 Convert directed graph to undirected graph
        #     This avoids double-counting two-way roads.
        # --------------------------------------------------
        G_undir = ox.convert.to_undirected(G_proj)

        # Convert graph to GeoDataFrames
        nodes, edges = ox.convert.graph_to_gdfs(
            G_undir,
            nodes=True,
            edges=True,
            fill_edge_geometry=True
        )

        # --------------------------------------------------
        # 5.5 Keep drivable classes only
        # --------------------------------------------------
        edges = edges[edges["highway"].notna()].copy()

        edges["highway_main"] = edges["highway"].apply(main_highway_class)

        edges_drive = edges[
            edges["highway"].apply(lambda x: has_any_highway(x, DRIVABLE_CLASSES))
        ].copy()

        # OSMnx length field is in metres after graph construction.
        edges_drive["length_km"] = edges_drive["length"] / 1000.0

        # Save road edges for later checking
        edge_file = os.path.join(EDGE_DIR, f"{file_city}_osm_drive_edges.geojson")
        edges_drive.to_crs(epsg=4326).to_file(edge_file, driver="GeoJSON")

        # --------------------------------------------------
        # 5.6 City area
        # --------------------------------------------------
        # Use same projected CRS as road edges.
        boundary_proj = boundary.to_crs(edges_drive.crs)
        area_km2 = boundary_proj.geometry.area.iloc[0] / 1_000_000.0

        # --------------------------------------------------
        # 5.7 Road length indicators
        # --------------------------------------------------
        total_road_length_km = edges_drive["length_km"].sum()

        motorway_km = sum_length_by_classes(edges_drive, ["motorway", "motorway_link"])
        trunk_km = sum_length_by_classes(edges_drive, ["trunk", "trunk_link"])
        primary_km = sum_length_by_classes(edges_drive, ["primary", "primary_link"])
        secondary_km = sum_length_by_classes(edges_drive, ["secondary", "secondary_link"])

        major_road_km = motorway_km + trunk_km + primary_km + secondary_km

        # --------------------------------------------------
        # 5.8 Intersection count
        # --------------------------------------------------
        # tolerance=5 means roughly consolidating nodes within about 10 m.
        intersections = ox.simplification.consolidate_intersections(
            G_proj,
            tolerance=5,
            rebuild_graph=False,
            dead_ends=False
        )

        intersection_count = len(intersections)

        # --------------------------------------------------
        # 5.9 Density and proxy indicators
        # --------------------------------------------------
        road_density_km_per_km2 = total_road_length_km / area_km2
        intersection_density_per_km2 = intersection_count / area_km2

        highway_dependency_proxy = (
            (motorway_km + trunk_km) / total_road_length_km
            if total_road_length_km > 0 else None
        )

        major_road_share = (
            major_road_km / total_road_length_km
            if total_road_length_km > 0 else None
        )

        # --------------------------------------------------
        # 5.10 Save result
        # --------------------------------------------------
        results.append({
            "city": city,
            "osm_query": query,
            "area_km2": round(area_km2, 3),
            "total_road_length_km": round(total_road_length_km, 3),
            "motorway_km": round(motorway_km, 3),
            "trunk_km": round(trunk_km, 3),
            "primary_km": round(primary_km, 3),
            "secondary_km": round(secondary_km, 3),
            "major_road_km": round(major_road_km, 3),
            "intersection_count": int(intersection_count),
            "road_density_km_per_km2": round(road_density_km_per_km2, 3),
            "intersection_density_per_km2": round(intersection_density_per_km2, 3),
            "highway_dependency_proxy": round(highway_dependency_proxy, 4),
            "major_road_share": round(major_road_share, 4),
            "boundary_file": boundary_file,
            "edge_file": edge_file,
            "status": "success",
            "error": ""
        })

        print(f"Finished: {city}")
        print(f"Area: {area_km2:.2f} km2")
        print(f"Total road length: {total_road_length_km:.2f} km")
        print(f"Intersection count: {intersection_count}")

        # Avoid too frequent Overpass/Nominatim requests.
        time.sleep(8)

    except Exception as e:
        print(f"ERROR: {city}")
        print(str(e))

        results.append({
            "city": city,
            "osm_query": query,
            "area_km2": None,
            "total_road_length_km": None,
            "motorway_km": None,
            "trunk_km": None,
            "primary_km": None,
            "secondary_km": None,
            "major_road_km": None,
            "intersection_count": None,
            "road_density_km_per_km2": None,
            "intersection_density_per_km2": None,
            "highway_dependency_proxy": None,
            "major_road_share": None,
            "boundary_file": "",
            "edge_file": "",
            "status": "failed",
            "error": str(e)
        })

# --------------------------
# 6. Export Excel
# --------------------------
df = pd.DataFrame(results)
df.to_excel(OUTPUT_EXCEL, index=False)

print("\n" + "=" * 70)
print("ALL DONE")
print(f"Output Excel: {OUTPUT_EXCEL}")
print("=" * 70)
print(df)