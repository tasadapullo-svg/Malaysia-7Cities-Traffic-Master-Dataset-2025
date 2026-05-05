import os
import ast
import json
import math
import warnings

import pandas as pd
import geopandas as gpd
import numpy as np

# ==========================================================
# Validation script for OSM road-network indicators
# Input:
#   OSM_output/OSM_road_network_indicators_7_cities.xlsx
#
# Output:
#   OSM_output/OSM_validation_report.xlsx
# ==========================================================

# ----------------------------------------------------------
# 0. Ignore non-critical GeoJSON parsing warning
# ----------------------------------------------------------
warnings.filterwarnings(
    "ignore",
    message="Could not parse column 'reversed' as JSON*",
    category=UserWarning
)

# ----------------------------------------------------------
# 1. Path settings
# ----------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

OUTPUT_DIR = os.path.join(PROJECT_DIR, "OSM_output")
INPUT_EXCEL = os.path.join(OUTPUT_DIR, "OSM_road_network_indicators_7_cities.xlsx")
VALIDATION_EXCEL = os.path.join(OUTPUT_DIR, "OSM_validation_report.xlsx")

EXPECTED_CITIES = [
    "George Town",
    "Kota Bharu",
    "Kuala Lumpur",
    "Seberang Perai",
    "Johor Bahru",
    "Ipoh",
    "Kajang"
]

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


# ==========================================================
# Helper functions
# ==========================================================

def resolve_existing_path(path_value):
    """
    Resolve relative file paths saved in the Excel file.

    The main OSM.py may save edge_file as:
        OSM_output/road_edges/City_osm_drive_edges.geojson

    Depending on PyCharm working directory, this validation script
    needs to check several possible base directories.
    """
    if path_value is None:
        return None

    try:
        if pd.isna(path_value):
            return None
    except Exception:
        pass

    path_str = str(path_value).strip()

    if path_str == "" or path_str.lower() in ["nan", "none", "null"]:
        return None

    candidates = [
        path_str,
        os.path.join(PROJECT_DIR, path_str),
        os.path.join(SCRIPT_DIR, path_str),
        os.path.join(os.getcwd(), path_str),
    ]

    # Remove duplicate candidates
    cleaned_candidates = []
    for p in candidates:
        p_norm = os.path.normpath(p)
        if p_norm not in cleaned_candidates:
            cleaned_candidates.append(p_norm)

    for candidate in cleaned_candidates:
        if os.path.exists(candidate):
            return candidate

    # Return the most likely full path even if it does not exist
    return os.path.normpath(os.path.join(PROJECT_DIR, path_str))


def parse_highway(value):
    """
    Robustly convert OSM highway field to a clean list.

    Possible input types:
    1. string: 'primary'
    2. list: ['primary', 'secondary']
    3. tuple / set / numpy array
    4. stringified list: "['primary', 'secondary']"
    5. JSON-like string: '["primary", "secondary"]'
    6. missing value
    """
    # Missing value
    if value is None:
        return []

    # Native list-like values
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip().strip("'\"") for v in value if v is not None]

    # Numpy array
    if isinstance(value, np.ndarray):
        return [str(v).strip().strip("'\"") for v in value.tolist() if v is not None]

    # Pandas missing value
    try:
        is_missing = pd.isna(value)
        if isinstance(is_missing, (bool, np.bool_)) and is_missing:
            return []
    except Exception:
        pass

    value_str = str(value).strip()

    if value_str == "" or value_str.lower() in ["nan", "none", "null"]:
        return []

    # Try Python literal list, e.g. "['primary', 'secondary']"
    if value_str.startswith("[") and value_str.endswith("]"):
        try:
            parsed = ast.literal_eval(value_str)
            if isinstance(parsed, (list, tuple, set)):
                return [
                    str(v).strip().strip("'\"")
                    for v in parsed
                    if v is not None
                ]
        except Exception:
            pass

        # Try JSON list, e.g. '["primary", "secondary"]'
        try:
            parsed = json.loads(value_str)
            if isinstance(parsed, list):
                return [
                    str(v).strip().strip("'\"")
                    for v in parsed
                    if v is not None
                ]
        except Exception:
            pass

    # Normal single highway class
    return [value_str.strip().strip("'\"")]


def has_any_highway(value, target_classes):
    """
    Check whether an OSM edge belongs to any target highway class.
    """
    values = parse_highway(value)
    return any(v in target_classes for v in values)


def sum_length_by_classes(edges, target_classes):
    """
    Sum edge length for selected highway classes.
    """
    selected = edges[
        edges["highway"].apply(lambda x: has_any_highway(x, target_classes))
    ].copy()

    if selected.empty:
        return 0.0

    return pd.to_numeric(selected["length_km"], errors="coerce").fillna(0).sum()


def add_check(checks, city, check_name, status, value, expected, note=""):
    """
    Add one validation check record.
    """
    checks.append({
        "city": city,
        "check_name": check_name,
        "status": status,
        "value": value,
        "expected": expected,
        "note": note
    })


def to_number(value):
    """
    Convert a value to float.
    """
    try:
        if pd.isna(value):
            return math.nan
    except Exception:
        pass

    try:
        return float(value)
    except Exception:
        return math.nan


def close_enough(a, b, tolerance):
    """
    Compare two numeric values with tolerance.
    """
    a_num = to_number(a)
    b_num = to_number(b)

    if math.isnan(a_num) or math.isnan(b_num):
        return False

    return abs(a_num - b_num) <= tolerance


def safe_positive(value):
    """
    Check whether a numeric value is positive.
    """
    value_num = to_number(value)
    return (not math.isnan(value_num)) and value_num > 0


def safe_non_negative(value):
    """
    Check whether a numeric value is non-negative.
    """
    value_num = to_number(value)
    return (not math.isnan(value_num)) and value_num >= 0


# ==========================================================
# Main validation workflow
# ==========================================================

def main():
    checks = []
    recomputed_rows = []

    print("\n" + "=" * 70)
    print("OSM VALIDATION STARTED")
    print(f"Project directory: {PROJECT_DIR}")
    print(f"Input Excel: {INPUT_EXCEL}")
    print("=" * 70)

    # ------------------------------------------------------
    # 1. Check whether input Excel exists
    # ------------------------------------------------------
    if not os.path.exists(INPUT_EXCEL):
        raise FileNotFoundError(
            f"Cannot find input Excel: {INPUT_EXCEL}. "
            f"Please run OSM.py first."
        )

    df = pd.read_excel(INPUT_EXCEL)

    # ------------------------------------------------------
    # 2. Required columns
    # ------------------------------------------------------
    required_columns = [
        "city",
        "area_km2",
        "total_road_length_km",
        "motorway_km",
        "trunk_km",
        "primary_km",
        "secondary_km",
        "major_road_km",
        "intersection_count",
        "road_density_km_per_km2",
        "intersection_density_per_km2",
        "highway_dependency_proxy",
        "major_road_share",
        "edge_file",
        "status"
    ]

    for col in required_columns:
        if col not in df.columns:
            add_check(
                checks,
                "ALL",
                f"required_column_{col}",
                "FAIL",
                "missing",
                "exists",
                "The output Excel does not contain this required column."
            )

    missing_cols = [col for col in required_columns if col not in df.columns]

    if missing_cols:
        check_df = pd.DataFrame(checks)
        check_df.to_excel(VALIDATION_EXCEL, index=False)

        print("Validation stopped because required columns are missing.")
        print(f"Missing columns: {missing_cols}")
        print(f"Report saved to: {VALIDATION_EXCEL}")
        return

    # ------------------------------------------------------
    # 3. Check city completeness
    # ------------------------------------------------------
    existing_cities = set(df["city"].astype(str).tolist())

    for city in EXPECTED_CITIES:
        if city in existing_cities:
            add_check(checks, city, "city_exists", "PASS", city, "exists")
        else:
            add_check(checks, city, "city_exists", "FAIL", "missing", "exists")

    extra_cities = existing_cities - set(EXPECTED_CITIES)

    for city in extra_cities:
        add_check(
            checks,
            city,
            "unexpected_city",
            "WARNING",
            city,
            "only 7 expected cities",
            "This city is not in the expected 7-city list."
        )

    # ------------------------------------------------------
    # 4. Row-level validation
    # ------------------------------------------------------
    for _, row in df.iterrows():
        city = str(row["city"]).strip()

        # 4.1 Status check
        if str(row["status"]).lower() == "success":
            add_check(checks, city, "download_status", "PASS", row["status"], "success")
        else:
            add_check(
                checks,
                city,
                "download_status",
                "FAIL",
                row["status"],
                "success",
                "OSM download or processing failed."
            )
            continue

        area = to_number(row["area_km2"])
        total = to_number(row["total_road_length_km"])
        motorway = to_number(row["motorway_km"])
        trunk = to_number(row["trunk_km"])
        primary = to_number(row["primary_km"])
        secondary = to_number(row["secondary_km"])
        major = to_number(row["major_road_km"])
        intersections = to_number(row["intersection_count"])
        road_density = to_number(row["road_density_km_per_km2"])
        intersection_density = to_number(row["intersection_density_per_km2"])
        highway_proxy = to_number(row["highway_dependency_proxy"])
        major_share = to_number(row["major_road_share"])
        edge_file_raw = row["edge_file"]
        edge_file = resolve_existing_path(edge_file_raw)

        # 4.2 Positive area
        if safe_positive(area):
            add_check(checks, city, "area_positive", "PASS", area, "> 0")
        else:
            add_check(checks, city, "area_positive", "FAIL", area, "> 0")

        # 4.3 Area sanity warning
        # This is a loose sanity range, not an official boundary test.
        if safe_positive(area) and 5 <= area <= 3000:
            add_check(checks, city, "area_sanity", "PASS", area, "5–3000 km2")
        else:
            add_check(
                checks,
                city,
                "area_sanity",
                "WARNING",
                area,
                "5–3000 km2",
                "Area is outside the loose sanity range. Check whether OSM boundary matches the intended city boundary."
            )

        # 4.4 Road length positive
        if safe_positive(total):
            add_check(checks, city, "total_road_length_positive", "PASS", total, "> 0")
        else:
            add_check(checks, city, "total_road_length_positive", "FAIL", total, "> 0")

        # 4.5 Class length non-negative
        for name, value in [
            ("motorway_km", motorway),
            ("trunk_km", trunk),
            ("primary_km", primary),
            ("secondary_km", secondary),
            ("major_road_km", major)
        ]:
            if safe_non_negative(value):
                add_check(checks, city, f"{name}_non_negative", "PASS", value, ">= 0")
            else:
                add_check(checks, city, f"{name}_non_negative", "FAIL", value, ">= 0")

        # 4.6 Major road length should not exceed total road length
        if not math.isnan(major) and not math.isnan(total) and major <= total + 0.01:
            add_check(checks, city, "major_not_exceed_total", "PASS", major, f"<= {total}")
        else:
            add_check(checks, city, "major_not_exceed_total", "FAIL", major, f"<= {total}")

        # 4.7 Formula check: major road
        expected_major = motorway + trunk + primary + secondary

        if close_enough(major, expected_major, tolerance=0.02):
            add_check(checks, city, "major_road_formula", "PASS", major, expected_major)
        else:
            add_check(checks, city, "major_road_formula", "FAIL", major, expected_major)

        # 4.8 Formula check: road density
        expected_road_density = total / area if safe_positive(area) else math.nan

        if close_enough(road_density, expected_road_density, tolerance=0.02):
            add_check(checks, city, "road_density_formula", "PASS", road_density, expected_road_density)
        else:
            add_check(checks, city, "road_density_formula", "FAIL", road_density, expected_road_density)

        # 4.9 Intersection count
        if safe_positive(intersections):
            add_check(checks, city, "intersection_count_positive", "PASS", intersections, "> 0")
        else:
            add_check(checks, city, "intersection_count_positive", "FAIL", intersections, "> 0")

        # 4.10 Formula check: intersection density
        expected_intersection_density = intersections / area if safe_positive(area) else math.nan

        if close_enough(intersection_density, expected_intersection_density, tolerance=0.02):
            add_check(checks, city, "intersection_density_formula", "PASS", intersection_density, expected_intersection_density)
        else:
            add_check(checks, city, "intersection_density_formula", "FAIL", intersection_density, expected_intersection_density)

        # 4.11 Formula check: highway dependency proxy
        expected_highway_proxy = (motorway + trunk) / total if safe_positive(total) else math.nan

        if close_enough(highway_proxy, expected_highway_proxy, tolerance=0.002):
            add_check(checks, city, "highway_dependency_formula", "PASS", highway_proxy, expected_highway_proxy)
        else:
            add_check(checks, city, "highway_dependency_formula", "FAIL", highway_proxy, expected_highway_proxy)

        # 4.12 Formula check: major road share
        expected_major_share = major / total if safe_positive(total) else math.nan

        if close_enough(major_share, expected_major_share, tolerance=0.002):
            add_check(checks, city, "major_road_share_formula", "PASS", major_share, expected_major_share)
        else:
            add_check(checks, city, "major_road_share_formula", "FAIL", major_share, expected_major_share)

        # 4.13 Proxy range
        if not math.isnan(highway_proxy) and 0 <= highway_proxy <= 1:
            add_check(checks, city, "highway_dependency_range", "PASS", highway_proxy, "0–1")
        else:
            add_check(checks, city, "highway_dependency_range", "FAIL", highway_proxy, "0–1")

        if not math.isnan(major_share) and 0 <= major_share <= 1:
            add_check(checks, city, "major_road_share_range", "PASS", major_share, "0–1")
        else:
            add_check(checks, city, "major_road_share_range", "FAIL", major_share, "0–1")

        # 4.14 Edge GeoJSON existence
        if edge_file is not None and os.path.exists(edge_file):
            add_check(checks, city, "edge_file_exists", "PASS", edge_file, "exists")
        else:
            add_check(
                checks,
                city,
                "edge_file_exists",
                "FAIL",
                edge_file_raw,
                "exists",
                "The saved edge GeoJSON file cannot be found."
            )
            continue

        # --------------------------------------------------
        # 5. Recompute from saved edge GeoJSON
        # --------------------------------------------------
        try:
            edges = gpd.read_file(edge_file)

            if "length_km" not in edges.columns:
                add_check(
                    checks,
                    city,
                    "edge_length_km_column",
                    "FAIL",
                    "missing",
                    "exists",
                    "Saved edge GeoJSON does not contain length_km."
                )
                continue

            if "highway" not in edges.columns:
                add_check(
                    checks,
                    city,
                    "edge_highway_column",
                    "FAIL",
                    "missing",
                    "exists",
                    "Saved edge GeoJSON does not contain highway."
                )
                continue

            edges = edges.copy()
            edges["length_km"] = pd.to_numeric(edges["length_km"], errors="coerce").fillna(0)

            recomputed_total = edges["length_km"].sum()
            recomputed_motorway = sum_length_by_classes(edges, ["motorway", "motorway_link"])
            recomputed_trunk = sum_length_by_classes(edges, ["trunk", "trunk_link"])
            recomputed_primary = sum_length_by_classes(edges, ["primary", "primary_link"])
            recomputed_secondary = sum_length_by_classes(edges, ["secondary", "secondary_link"])
            recomputed_major = (
                recomputed_motorway
                + recomputed_trunk
                + recomputed_primary
                + recomputed_secondary
            )

            recomputed_rows.append({
                "city": city,
                "edge_file": edge_file,
                "excel_total_road_length_km": total,
                "recomputed_total_road_length_km": round(recomputed_total, 3),
                "difference_total_km": round(recomputed_total - total, 6),
                "excel_motorway_km": motorway,
                "recomputed_motorway_km": round(recomputed_motorway, 3),
                "excel_trunk_km": trunk,
                "recomputed_trunk_km": round(recomputed_trunk, 3),
                "excel_primary_km": primary,
                "recomputed_primary_km": round(recomputed_primary, 3),
                "excel_secondary_km": secondary,
                "recomputed_secondary_km": round(recomputed_secondary, 3),
                "excel_major_road_km": major,
                "recomputed_major_road_km": round(recomputed_major, 3)
            })

            # Since Excel values are rounded to 3 decimals, allow small tolerance.
            if close_enough(total, recomputed_total, tolerance=0.05):
                add_check(checks, city, "recompute_total_from_edges", "PASS", total, recomputed_total)
            else:
                add_check(checks, city, "recompute_total_from_edges", "FAIL", total, recomputed_total)

            if close_enough(motorway, recomputed_motorway, tolerance=0.05):
                add_check(checks, city, "recompute_motorway_from_edges", "PASS", motorway, recomputed_motorway)
            else:
                add_check(checks, city, "recompute_motorway_from_edges", "FAIL", motorway, recomputed_motorway)

            if close_enough(trunk, recomputed_trunk, tolerance=0.05):
                add_check(checks, city, "recompute_trunk_from_edges", "PASS", trunk, recomputed_trunk)
            else:
                add_check(checks, city, "recompute_trunk_from_edges", "FAIL", trunk, recomputed_trunk)

            if close_enough(primary, recomputed_primary, tolerance=0.05):
                add_check(checks, city, "recompute_primary_from_edges", "PASS", primary, recomputed_primary)
            else:
                add_check(checks, city, "recompute_primary_from_edges", "FAIL", primary, recomputed_primary)

            if close_enough(secondary, recomputed_secondary, tolerance=0.05):
                add_check(checks, city, "recompute_secondary_from_edges", "PASS", secondary, recomputed_secondary)
            else:
                add_check(checks, city, "recompute_secondary_from_edges", "FAIL", secondary, recomputed_secondary)

        except Exception as e:
            add_check(
                checks,
                city,
                "recompute_from_edge_file",
                "FAIL",
                str(e),
                "readable edge GeoJSON",
                "Could not recompute indicators from saved edge file."
            )

    # ------------------------------------------------------
    # 6. Export validation report
    # ------------------------------------------------------
    check_df = pd.DataFrame(checks)
    recompute_df = pd.DataFrame(recomputed_rows)

    summary = (
        check_df
        .groupby(["city", "status"])
        .size()
        .reset_index(name="count")
    )

    failed = check_df[check_df["status"] == "FAIL"]
    warning_df = check_df[check_df["status"] == "WARNING"]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with pd.ExcelWriter(VALIDATION_EXCEL, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="original_results", index=False)
        check_df.to_excel(writer, sheet_name="validation_checks", index=False)
        recompute_df.to_excel(writer, sheet_name="recomputed_from_edges", index=False)
        summary.to_excel(writer, sheet_name="summary", index=False)

        if not failed.empty:
            failed.to_excel(writer, sheet_name="failed_checks", index=False)

        if not warning_df.empty:
            warning_df.to_excel(writer, sheet_name="warnings", index=False)

    print("\n" + "=" * 70)
    print("VALIDATION FINISHED")
    print(f"Validation report saved to: {VALIDATION_EXCEL}")
    print("=" * 70)

    print("\nSummary by status:")
    print(summary)

    if failed.empty:
        print("\nNo FAIL checks found.")
    else:
        print("\nFAIL checks found. Please open failed_checks sheet.")
        print(failed[["city", "check_name", "value", "expected", "note"]])

    if not warning_df.empty:
        print("\nWarnings found. Please check whether city boundaries are reasonable.")
        print(warning_df[["city", "check_name", "value", "expected", "note"]])


if __name__ == "__main__":
    main()