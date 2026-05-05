import os
import re
import math
import pandas as pd

# ==========================================================
# Merge TomTom + OSM + Population + Vehicle Data
#
# Project structure:
# D:\2026Graduation Thesis
# └─ OSM
#    ├─ OSM_output
#    │  └─ OSM_road_network_indicators_7_cities.xlsx
#    ├─ External_Data_Output
#    │  └─ population_vehicle_indicators_7_cities.xlsx
#    └─ merge_master_dataset.py
#
# Output:
#   OSM\Master_Dataset_Output\Malaysia_7Cities_master_dataset.xlsx
# ==========================================================


# ==========================================================
# 1. Path settings
# ==========================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OSM_DIR = SCRIPT_DIR
PROJECT_DIR = os.path.dirname(OSM_DIR)

OSM_FILE = os.path.join(
    OSM_DIR,
    "OSM_output",
    "OSM_road_network_indicators_7_cities.xlsx"
)

POP_VEH_FILE = os.path.join(
    OSM_DIR,
    "External_Data_Output",
    "population_vehicle_indicators_7_cities.xlsx"
)

# ==========================================================
# IMPORTANT:
# Change this path to your TomTom 7-city final indicator Excel.
#
# The TomTom file should be one row per city.
# It must contain a city column, such as:
# city / City / city_name / City Name
# ==========================================================

TOMTOM_FILE = os.path.join(
    OSM_DIR,
    "TomTom_Input",
    "TomTom_7cities_indicators.xlsx"
)

# If your TomTom file is elsewhere, directly replace the line above, for example:
# TOMTOM_FILE = r"D:\2026Graduation Thesis\TomTom_Output\TomTom_7cities_indicators.xlsx"

TOMTOM_SHEET = None
OSM_SHEET = None
POP_VEH_SHEET = "city_state_indicators"

OUTPUT_DIR = os.path.join(OSM_DIR, "Master_Dataset_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_EXCEL = os.path.join(
    OUTPUT_DIR,
    "Malaysia_7Cities_master_dataset.xlsx"
)

# Set this to True only if your TomTom file has multiple rows per city.
# If True, numeric columns will be averaged by city.
# For final paper, it is better to use an annual TomTom summary table with one row per city.
ALLOW_TOMTOM_AGGREGATION = False


EXPECTED_CITIES = [
    "George Town",
    "Kota Bharu",
    "Kuala Lumpur",
    "Seberang Perai",
    "Johor Bahru",
    "Ipoh",
    "Kajang"
]


CITY_NAME_MAP = {
    "georgetown": "George Town",
    "george town": "George Town",
    "george-town": "George Town",

    "kota bharu": "Kota Bharu",
    "kota bahru": "Kota Bharu",

    "kuala lumpur": "Kuala Lumpur",
    "kl": "Kuala Lumpur",

    "seberang perai": "Seberang Perai",
    "seberang prai": "Seberang Perai",

    "johor bahru": "Johor Bahru",
    "jb": "Johor Bahru",

    "ipoh": "Ipoh",

    "kajang": "Kajang",
}


# ==========================================================
# 2. Helper functions
# ==========================================================

def clean_column_name(col):
    """
    Convert column names into safe snake_case.
    """
    col = str(col).strip()
    col = col.replace("%", "percent")
    col = col.replace("/", "_")
    col = col.replace("-", "_")
    col = col.replace("(", "")
    col = col.replace(")", "")
    col = col.replace(".", "")
    col = re.sub(r"\s+", "_", col)
    col = re.sub(r"[^0-9a-zA-Z_]+", "", col)
    col = col.lower()
    col = re.sub(r"_+", "_", col)
    return col.strip("_")


def normalize_city_name(value):
    """
    Standardize city names for merging.
    """
    if pd.isna(value):
        return None

    text = str(value).strip()
    key = text.lower()
    key = key.replace("_", " ")
    key = key.replace("-", " ")
    key = re.sub(r"\s+", " ", key).strip()

    return CITY_NAME_MAP.get(key, text)


def find_city_column(df):
    """
    Find city column automatically.
    """
    possible_cols = [
        "city",
        "city_name",
        "cityname",
        "tomtom_city",
        "name",
        "urban_area",
        "location"
    ]

    lower_cols = {str(c).strip().lower().replace(" ", "_"): c for c in df.columns}

    for col in possible_cols:
        if col in lower_cols:
            return lower_cols[col]

    raise ValueError(
        "Cannot find city column. Please make sure the file has one column named "
        "city / City / city_name / City Name / name."
    )


def read_excel_auto(path, sheet_name=None, dataset_name="dataset"):
    """
    Read Excel file. If sheet_name is None, read the first sheet.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Cannot find {dataset_name} file:\n{path}"
        )

    xls = pd.ExcelFile(path)

    if sheet_name is None:
        sheet_name = xls.sheet_names[0]

    if sheet_name not in xls.sheet_names:
        raise ValueError(
            f"Sheet '{sheet_name}' not found in {dataset_name}.\n"
            f"Available sheets: {xls.sheet_names}"
        )

    df = pd.read_excel(path, sheet_name=sheet_name)
    df.columns = [clean_column_name(c) for c in df.columns]

    print(f"{dataset_name} loaded: {path}")
    print(f"Sheet: {sheet_name}")
    print(f"Shape: {df.shape}")

    return df, sheet_name


def prefix_columns(df, prefix, keep_cols):
    """
    Add prefix to non-key columns.
    """
    rename_dict = {}

    for col in df.columns:
        if col not in keep_cols:
            rename_dict[col] = f"{prefix}_{col}"

    return df.rename(columns=rename_dict)


def check_duplicate_city(df, dataset_name):
    """
    Check duplicate cities.
    """
    duplicated = df[df["city_std"].duplicated(keep=False)].copy()

    if not duplicated.empty:
        print(f"\nWARNING: Duplicate city rows found in {dataset_name}:")
        print(duplicated[["city_std"]])

    return duplicated


def aggregate_tomtom_by_city(df):
    """
    Aggregate TomTom table if multiple rows per city exist.

    Numeric columns: mean
    Non-numeric columns: first non-null value
    """
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    numeric_cols = [c for c in numeric_cols if c != "city_std"]

    non_numeric_cols = [
        c for c in df.columns
        if c not in numeric_cols and c != "city_std"
    ]

    agg_dict = {}

    for col in numeric_cols:
        agg_dict[col] = "mean"

    for col in non_numeric_cols:
        agg_dict[col] = lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else None

    out = df.groupby("city_std", as_index=False).agg(agg_dict)

    return out


def add_validation(checks, check_name, status, value, expected, note=""):
    checks.append({
        "check_name": check_name,
        "status": status,
        "value": value,
        "expected": expected,
        "note": note
    })


def numeric_missing_summary(df):
    """
    Count missing values by column.
    """
    rows = []

    for col in df.columns:
        rows.append({
            "column": col,
            "missing_count": int(df[col].isna().sum()),
            "missing_percent": round(df[col].isna().mean() * 100, 2)
        })

    return pd.DataFrame(rows)


# ==========================================================
# 3. Main workflow
# ==========================================================

def main():
    print("\n" + "=" * 80)
    print("MERGE MASTER DATASET: TOMTOM + OSM + POPULATION + VEHICLE")
    print("=" * 80)
    print(f"Project directory: {PROJECT_DIR}")
    print(f"OSM directory    : {OSM_DIR}")
    print(f"TomTom file      : {TOMTOM_FILE}")
    print(f"OSM file         : {OSM_FILE}")
    print(f"Population file  : {POP_VEH_FILE}")
    print(f"Output Excel     : {OUTPUT_EXCEL}")
    print("=" * 80)

    validation_checks = []

    # ------------------------------------------------------
    # 3.1 Read files
    # ------------------------------------------------------
    tomtom_raw, tomtom_sheet_used = read_excel_auto(
        TOMTOM_FILE,
        sheet_name=TOMTOM_SHEET,
        dataset_name="TomTom indicators"
    )

    osm_raw, osm_sheet_used = read_excel_auto(
        OSM_FILE,
        sheet_name=OSM_SHEET,
        dataset_name="OSM road-network indicators"
    )

    popveh_raw, popveh_sheet_used = read_excel_auto(
        POP_VEH_FILE,
        sheet_name=POP_VEH_SHEET,
        dataset_name="Population and vehicle indicators"
    )

    # ------------------------------------------------------
    # 3.2 Standardize city columns
    # ------------------------------------------------------
    tomtom_city_col = find_city_column(tomtom_raw)
    osm_city_col = find_city_column(osm_raw)
    popveh_city_col = find_city_column(popveh_raw)

    tomtom = tomtom_raw.copy()
    osm = osm_raw.copy()
    popveh = popveh_raw.copy()

    tomtom["city_std"] = tomtom[tomtom_city_col].apply(normalize_city_name)
    osm["city_std"] = osm[osm_city_col].apply(normalize_city_name)
    popveh["city_std"] = popveh[popveh_city_col].apply(normalize_city_name)

    # ------------------------------------------------------
    # 3.3 Keep expected 7 cities only
    # ------------------------------------------------------
    tomtom = tomtom[tomtom["city_std"].isin(EXPECTED_CITIES)].copy()
    osm = osm[osm["city_std"].isin(EXPECTED_CITIES)].copy()
    popveh = popveh[popveh["city_std"].isin(EXPECTED_CITIES)].copy()

    # ------------------------------------------------------
    # 3.4 Duplicate checks
    # ------------------------------------------------------
    tomtom_dupes = check_duplicate_city(tomtom, "TomTom")
    osm_dupes = check_duplicate_city(osm, "OSM")
    popveh_dupes = check_duplicate_city(popveh, "Population/vehicle")

    if not tomtom_dupes.empty:
        if ALLOW_TOMTOM_AGGREGATION:
            print("\nTomTom duplicate city rows will be aggregated by city.")
            tomtom = aggregate_tomtom_by_city(tomtom)
            add_validation(
                validation_checks,
                "tomtom_duplicate_city_rows",
                "WARNING",
                len(tomtom_dupes),
                "0",
                "TomTom rows were aggregated by city because ALLOW_TOMTOM_AGGREGATION=True."
            )
        else:
            add_validation(
                validation_checks,
                "tomtom_duplicate_city_rows",
                "FAIL",
                len(tomtom_dupes),
                "0",
                "TomTom file has multiple rows per city. Use an annual summary table or set ALLOW_TOMTOM_AGGREGATION=True."
            )

    if not osm_dupes.empty:
        add_validation(
            validation_checks,
            "osm_duplicate_city_rows",
            "FAIL",
            len(osm_dupes),
            "0",
            "OSM table should contain one row per city."
        )

    if not popveh_dupes.empty:
        add_validation(
            validation_checks,
            "population_vehicle_duplicate_city_rows",
            "FAIL",
            len(popveh_dupes),
            "0",
            "Population/vehicle table should contain one row per city."
        )

    # ------------------------------------------------------
    # 3.5 Expected city coverage
    # ------------------------------------------------------
    for dataset_name, df_check in [
        ("tomtom", tomtom),
        ("osm", osm),
        ("population_vehicle", popveh)
    ]:
        available = set(df_check["city_std"].dropna().tolist())
        missing = [c for c in EXPECTED_CITIES if c not in available]

        if missing:
            add_validation(
                validation_checks,
                f"{dataset_name}_city_coverage",
                "FAIL",
                ", ".join(missing),
                "all 7 expected cities",
                f"Missing cities in {dataset_name} table."
            )
        else:
            add_validation(
                validation_checks,
                f"{dataset_name}_city_coverage",
                "PASS",
                len(available),
                "7",
                ""
            )

    # ------------------------------------------------------
    # 3.6 Prefix columns before merge
    # ------------------------------------------------------
    tomtom_keep = ["city_std"]
    osm_keep = ["city_std"]
    popveh_keep = ["city_std"]

    tomtom_prefixed = prefix_columns(tomtom, "tomtom", keep_cols=tomtom_keep)
    osm_prefixed = prefix_columns(osm, "osm", keep_cols=osm_keep)
    popveh_prefixed = prefix_columns(popveh, "popveh", keep_cols=popveh_keep)

    # ------------------------------------------------------
    # 3.7 Master city frame
    # ------------------------------------------------------
    master = pd.DataFrame({
        "city": EXPECTED_CITIES
    })
    master["city_std"] = master["city"]

    master = master.merge(
        tomtom_prefixed,
        on="city_std",
        how="left"
    )

    master = master.merge(
        osm_prefixed,
        on="city_std",
        how="left"
    )

    master = master.merge(
        popveh_prefixed,
        on="city_std",
        how="left"
    )

    # Put city columns first
    cols = master.columns.tolist()
    first_cols = ["city", "city_std"]
    other_cols = [c for c in cols if c not in first_cols]
    master = master[first_cols + other_cols]

    # ------------------------------------------------------
    # 3.8 Sort by expected city order
    # ------------------------------------------------------
    city_order = {city: i for i, city in enumerate(EXPECTED_CITIES)}
    master["city_order"] = master["city"].map(city_order)
    master = master.sort_values("city_order").drop(columns=["city_order"])

    # ------------------------------------------------------
    # 3.9 Merge validation
    # ------------------------------------------------------
    if len(master) == 7:
        add_validation(
            validation_checks,
            "master_row_count",
            "PASS",
            len(master),
            "7",
            ""
        )
    else:
        add_validation(
            validation_checks,
            "master_row_count",
            "FAIL",
            len(master),
            "7",
            "Master dataset should contain exactly 7 rows."
        )

    # Check whether any source has all missing columns after merge.
    source_prefixes = ["tomtom_", "osm_", "popveh_"]

    for prefix in source_prefixes:
        source_cols = [c for c in master.columns if c.startswith(prefix)]

        if not source_cols:
            add_validation(
                validation_checks,
                f"{prefix}columns_exist",
                "FAIL",
                0,
                "> 0",
                f"No columns found for source prefix {prefix}."
            )
            continue

        missing_by_row = master[source_cols].isna().all(axis=1)
        failed_cities = master.loc[missing_by_row, "city"].tolist()

        if failed_cities:
            add_validation(
                validation_checks,
                f"{prefix}merge_complete",
                "FAIL",
                ", ".join(failed_cities),
                "no city fully missing",
                f"Some cities have no merged values for source prefix {prefix}."
            )
        else:
            add_validation(
                validation_checks,
                f"{prefix}merge_complete",
                "PASS",
                "all cities matched",
                "all cities matched",
                ""
            )

    validation_df = pd.DataFrame(validation_checks)

    validation_summary = (
        validation_df
        .groupby("status")
        .size()
        .reset_index(name="count")
    )

    missing_summary = numeric_missing_summary(master)

    # ------------------------------------------------------
    # 3.10 Data dictionary
    # ------------------------------------------------------
    dictionary_rows = []

    for col in master.columns:
        if col in ["city", "city_std"]:
            source = "merge_key"
        elif col.startswith("tomtom_"):
            source = "TomTom"
        elif col.startswith("osm_"):
            source = "OSM"
        elif col.startswith("popveh_"):
            source = "OpenDOSM / data.gov.my"
        else:
            source = "unknown"

        dictionary_rows.append({
            "column": col,
            "source": source,
            "description": "",
            "unit_or_scale": "",
            "note": ""
        })

    data_dictionary = pd.DataFrame(dictionary_rows)

    # Add important descriptions where names are known.
    known_descriptions = {
        "osm_area_km2": "OSM-derived city boundary area",
        "osm_total_road_length_km": "Total drivable road length extracted from OSM",
        "osm_motorway_km": "Motorway and motorway_link length",
        "osm_trunk_km": "Trunk and trunk_link length",
        "osm_primary_km": "Primary and primary_link length",
        "osm_secondary_km": "Secondary and secondary_link length",
        "osm_major_road_km": "Motorway + trunk + primary + secondary road length",
        "osm_intersection_count": "Consolidated OSM intersection count",
        "osm_road_density_km_per_km2": "Total road length divided by city area",
        "osm_intersection_density_per_km2": "Intersection count divided by city area",
        "osm_highway_dependency_proxy": "(motorway_km + trunk_km) / total_road_length_km",
        "osm_major_road_share": "major_road_km / total_road_length_km",
        "popveh_population_state_2025_persons": "2025 state-level population",
        "popveh_vehicle_reg_2025_state": "2025 state-level vehicle registration transactions",
        "popveh_car_reg_2025_state": "2025 state-level car registration transactions",
        "popveh_motorcycle_reg_2025_state": "2025 state-level motorcycle registration transactions",
        "popveh_vehicle_reg_per_1000_pop_2025": "Vehicle registration transactions per 1000 population",
        "popveh_car_reg_per_1000_pop_2025": "Car registration transactions per 1000 population",
        "popveh_motorcycle_reg_per_1000_pop_2025": "Motorcycle registration transactions per 1000 population",
        "popveh_car_share_of_vehicle_reg_2025": "Car share of vehicle registration transactions",
        "popveh_motorcycle_share_of_vehicle_reg_2025": "Motorcycle share of vehicle registration transactions",
    }

    for col, desc in known_descriptions.items():
        data_dictionary.loc[data_dictionary["column"] == col, "description"] = desc

    # ------------------------------------------------------
    # 3.11 Export Excel
    # ------------------------------------------------------
    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        master.to_excel(writer, sheet_name="master_dataset", index=False)
        validation_df.to_excel(writer, sheet_name="merge_validation", index=False)
        validation_summary.to_excel(writer, sheet_name="validation_summary", index=False)
        missing_summary.to_excel(writer, sheet_name="missing_summary", index=False)
        data_dictionary.to_excel(writer, sheet_name="data_dictionary", index=False)

        tomtom_raw.to_excel(writer, sheet_name="tomtom_raw", index=False)
        osm_raw.to_excel(writer, sheet_name="osm_raw", index=False)
        popveh_raw.to_excel(writer, sheet_name="population_vehicle_raw", index=False)

        city_matching = pd.DataFrame({
            "expected_city": EXPECTED_CITIES,
            "merge_city_std": EXPECTED_CITIES
        })
        city_matching.to_excel(writer, sheet_name="city_matching", index=False)

    print("\n" + "=" * 80)
    print("ALL DONE")
    print("=" * 80)
    print(f"Master dataset saved to:\n{OUTPUT_EXCEL}")
    print("\nValidation summary:")
    print(validation_summary)

    failed = validation_df[validation_df["status"] == "FAIL"]

    if failed.empty:
        print("\nNo FAIL checks found.")
        print("The merged master dataset is ready for review.")
    else:
        print("\nFAIL checks found. Please inspect the merge_validation sheet.")
        print(failed)

    print("\nMaster dataset preview:")
    print(master.head(10))


if __name__ == "__main__":
    main()