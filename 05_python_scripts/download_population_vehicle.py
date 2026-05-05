import os
import sys
import pandas as pd

# ==========================================================
# Step 4: Download and process population + vehicle data
# Project structure:
#
# D:\2026Graduation Thesis
# └─ OSM
#    ├─ External_Data
#    │  └─ download_population_vehicle.py
#    ├─ OSM_output
#    └─ External_Data_Output
#
# Output:
#   OSM/External_Data_Output/population_vehicle_indicators_7_cities.xlsx
# ==========================================================


# ==========================================================
# 1. Path settings
# ==========================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OSM_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_DIR = os.path.dirname(OSM_DIR)

OUTPUT_DIR = os.path.join(OSM_DIR, "External_Data_Output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_EXCEL = os.path.join(
    OUTPUT_DIR,
    "population_vehicle_indicators_7_cities.xlsx"
)

RAW_POP_FILE = os.path.join(
    OUTPUT_DIR,
    "raw_population_state_2025_selected.parquet"
)

RAW_VEHICLE_FILE = os.path.join(
    OUTPUT_DIR,
    "raw_vehicles_2025_selected.parquet"
)

print("=" * 80)
print("STEP 4: POPULATION AND VEHICLE DATA EXTRACTION")
print("=" * 80)
print(f"Script directory : {SCRIPT_DIR}")
print(f"OSM directory    : {OSM_DIR}")
print(f"Project directory: {PROJECT_DIR}")
print(f"Output directory : {OUTPUT_DIR}")
print("=" * 80)


# ==========================================================
# 2. Data URLs
# ==========================================================

POPULATION_STATE_URL = "https://storage.dosm.gov.my/population/population_state.parquet"
VEHICLE_2025_URL = "https://storage.data.gov.my/transportation/vehicles_2025.parquet"


# ==========================================================
# 3. City-state matching table
# ==========================================================

city_state_map = pd.DataFrame([
    {"city": "George Town", "matched_state": "Pulau Pinang"},
    {"city": "Kota Bharu", "matched_state": "Kelantan"},
    {"city": "Kuala Lumpur", "matched_state": "W.P. Kuala Lumpur"},
    {"city": "Seberang Perai", "matched_state": "Pulau Pinang"},
    {"city": "Johor Bahru", "matched_state": "Johor"},
    {"city": "Ipoh", "matched_state": "Perak"},
    {"city": "Kajang", "matched_state": "Selangor"},
])


# ==========================================================
# 4. Helper functions
# ==========================================================

def normalize_text(x):
    """
    Standardize state names for matching.
    """
    if pd.isna(x):
        return ""

    text = str(x).strip().lower()

    text = text.replace("wilayah persekutuan", "w.p.")
    text = text.replace("wp ", "w.p. ")
    text = text.replace("w.p ", "w.p. ")
    text = text.replace("pulau pinang", "pulau pinang")
    text = text.replace("penang", "pulau pinang")

    return text


def check_required_columns(df, required_cols, dataset_name):
    """
    Check whether required columns exist.
    """
    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        print(f"\nERROR: Missing columns in {dataset_name}: {missing}")
        print(f"Available columns in {dataset_name}:")
        print(list(df.columns))
        raise ValueError(f"Required columns missing in {dataset_name}.")


def safe_divide(a, b):
    """
    Safe division. Return None if denominator is zero or missing.
    """
    if pd.isna(a) or pd.isna(b) or b == 0:
        return None
    return a / b


def read_parquet_with_message(url, columns=None, dataset_name="dataset"):
    """
    Read remote parquet file with clear error message.
    """
    try:
        print(f"Reading {dataset_name} from:")
        print(url)

        if columns is None:
            df = pd.read_parquet(url)
        else:
            try:
                df = pd.read_parquet(url, columns=columns)
            except Exception as col_error:
                print(f"Column-limited reading failed for {dataset_name}.")
                print(f"Reason: {col_error}")
                print("Trying to read the full parquet file instead...")
                df = pd.read_parquet(url)

        print(f"{dataset_name} loaded successfully.")
        print(f"{dataset_name} shape: {df.shape}")
        return df

    except ImportError as e:
        print("\nERROR: Missing parquet engine.")
        print("Please install pyarrow:")
        print("pip install pyarrow openpyxl")
        raise e

    except Exception as e:
        print(f"\nERROR: Failed to download or read {dataset_name}.")
        print("Possible reasons:")
        print("1. Internet connection problem")
        print("2. data.gov.my / OpenDOSM temporary server issue")
        print("3. URL changed")
        print("4. pyarrow is not installed")
        print(f"Original error: {e}")
        raise e


# ==========================================================
# 5. Download and process population data
# ==========================================================

print("\n" + "=" * 80)
print("1. DOWNLOADING OPENDOSM POPULATION_STATE DATA")
print("=" * 80)

population_required_cols = [
    "date",
    "state",
    "sex",
    "age",
    "ethnicity",
    "population"
]

pop = read_parquet_with_message(
    POPULATION_STATE_URL,
    columns=population_required_cols,
    dataset_name="OpenDOSM population_state"
)

check_required_columns(pop, population_required_cols, "population_state")

pop["date"] = pd.to_datetime(pop["date"], errors="coerce")
pop["sex_key"] = pop["sex"].astype(str).str.strip().str.lower()
pop["age_key"] = pop["age"].astype(str).str.strip().str.lower()
pop["ethnicity_key"] = pop["ethnicity"].astype(str).str.strip().str.lower()

# Keep 2025 total population by state.
# OpenDOSM population unit is usually '000 persons', so multiply by 1000.
pop_2025 = pop[
    (pop["date"].dt.year == 2025)
    & (pop["sex_key"] == "both")
    & (pop["age_key"] == "overall")
    & (pop["ethnicity_key"] == "overall")
].copy()

if pop_2025.empty:
    print("\nERROR: No 2025 total population records found.")
    print("Please inspect the source fields below:")
    print("Unique years:", sorted(pop["date"].dt.year.dropna().unique().tolist())[-10:])
    print("Unique sex:", pop["sex"].dropna().unique()[:20])
    print("Unique age:", pop["age"].dropna().unique()[:20])
    print("Unique ethnicity:", pop["ethnicity"].dropna().unique()[:20])
    raise ValueError("Population filtering returned empty data.")

pop_2025["population_state_2025_persons"] = (
    pd.to_numeric(pop_2025["population"], errors="coerce") * 1000
)

pop_2025["state_key"] = pop_2025["state"].apply(normalize_text)

pop_2025_clean = pop_2025[[
    "state",
    "state_key",
    "population_state_2025_persons"
]].copy()

pop_2025_clean = pop_2025_clean.drop_duplicates(subset=["state_key"])

pop_2025_clean.to_parquet(RAW_POP_FILE, index=False)

print("Population 2025 rows after filtering:", len(pop_2025_clean))
print(pop_2025_clean)


# ==========================================================
# 6. Download and process vehicle registration data
# ==========================================================

print("\n" + "=" * 80)
print("2. DOWNLOADING JPJ VEHICLE REGISTRATION DATA 2025")
print("=" * 80)

vehicle_required_cols = [
    "date_reg",
    "state",
    "category"
]

vehicles = read_parquet_with_message(
    VEHICLE_2025_URL,
    columns=vehicle_required_cols,
    dataset_name="data.gov.my vehicles_2025"
)

check_required_columns(vehicles, vehicle_required_cols, "vehicles_2025")

vehicles["date_reg"] = pd.to_datetime(vehicles["date_reg"], errors="coerce")
vehicles["state_key"] = vehicles["state"].apply(normalize_text)
vehicles["category"] = vehicles["category"].astype(str).str.strip().str.lower()

vehicles_2025 = vehicles[
    vehicles["date_reg"].dt.year == 2025
].copy()

if vehicles_2025.empty:
    print("\nERROR: No 2025 vehicle registration records found.")
    print("Unique years:", sorted(vehicles["date_reg"].dt.year.dropna().unique().tolist())[-10:])
    raise ValueError("Vehicle filtering returned empty data.")

vehicles_2025.to_parquet(RAW_VEHICLE_FILE, index=False)

print("Vehicle registration records in 2025:", len(vehicles_2025))
print("Vehicle categories found:")
print(sorted(vehicles_2025["category"].dropna().unique().tolist()))


# ==========================================================
# 7. Aggregate vehicle registrations by state
# ==========================================================

print("\n" + "=" * 80)
print("3. AGGREGATING VEHICLE REGISTRATION DATA BY STATE")
print("=" * 80)

vehicle_all = (
    vehicles_2025
    .groupby(["state", "state_key"], as_index=False)
    .size()
    .rename(columns={"size": "vehicle_reg_2025_state"})
)

vehicle_by_category = (
    vehicles_2025
    .groupby(["state_key", "category"], as_index=False)
    .size()
    .rename(columns={"size": "count"})
)

vehicle_pivot = (
    vehicle_by_category
    .pivot_table(
        index="state_key",
        columns="category",
        values="count",
        aggfunc="sum",
        fill_value=0
    )
    .reset_index()
)

# Rename common categories.
# The exact category names follow data.gov.my values.
rename_dict = {
    "car": "car_reg_2025_state",
    "motorcycle": "motorcycle_reg_2025_state",
    "lorry": "lorry_reg_2025_state",
    "vans": "van_reg_2025_state",
    "van": "van_reg_2025_state",
    "bus": "bus_reg_2025_state",
    "trailers": "trailer_reg_2025_state",
    "trailer": "trailer_reg_2025_state",
    "other": "other_vehicle_reg_2025_state"
}

vehicle_pivot = vehicle_pivot.rename(columns=rename_dict)

vehicle_state = vehicle_all.merge(
    vehicle_pivot,
    on="state_key",
    how="left"
)

# Ensure required vehicle columns exist.
required_vehicle_output_cols = [
    "car_reg_2025_state",
    "motorcycle_reg_2025_state",
    "lorry_reg_2025_state",
    "van_reg_2025_state",
    "bus_reg_2025_state",
    "trailer_reg_2025_state",
    "other_vehicle_reg_2025_state"
]

for col in required_vehicle_output_cols:
    if col not in vehicle_state.columns:
        vehicle_state[col] = 0

# Fill numeric missing values.
for col in ["vehicle_reg_2025_state"] + required_vehicle_output_cols:
    vehicle_state[col] = pd.to_numeric(vehicle_state[col], errors="coerce").fillna(0).astype(int)

print("Vehicle state-level summary:")
print(vehicle_state[[
    "state",
    "vehicle_reg_2025_state",
    "car_reg_2025_state",
    "motorcycle_reg_2025_state"
]].head(20))


# ==========================================================
# 8. Merge city-state, population, and vehicle data
# ==========================================================

print("\n" + "=" * 80)
print("4. MERGING CITY-STATE MATCHING, POPULATION, AND VEHICLE DATA")
print("=" * 80)

city_state_map["state_key"] = city_state_map["matched_state"].apply(normalize_text)

merged = city_state_map.merge(
    pop_2025_clean,
    on="state_key",
    how="left"
)

merged = merged.merge(
    vehicle_state,
    on="state_key",
    how="left",
    suffixes=("_pop", "_veh")
)

# Check unmatched population or vehicle records.
unmatched_population = merged[merged["population_state_2025_persons"].isna()]
unmatched_vehicle = merged[merged["vehicle_reg_2025_state"].isna()]

if not unmatched_population.empty:
    print("\nWARNING: Some cities did not match population data.")
    print(unmatched_population[["city", "matched_state", "state_key"]])

if not unmatched_vehicle.empty:
    print("\nWARNING: Some cities did not match vehicle registration data.")
    print(unmatched_vehicle[["city", "matched_state", "state_key"]])


# ==========================================================
# 9. Calculate normalized indicators
# ==========================================================

print("\n" + "=" * 80)
print("5. CALCULATING NORMALIZED INDICATORS")
print("=" * 80)

numeric_fill_cols = [
    "vehicle_reg_2025_state",
    "car_reg_2025_state",
    "motorcycle_reg_2025_state",
    "lorry_reg_2025_state",
    "van_reg_2025_state",
    "bus_reg_2025_state",
    "trailer_reg_2025_state",
    "other_vehicle_reg_2025_state"
]

for col in numeric_fill_cols:
    if col in merged.columns:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)

merged["population_state_2025_persons"] = pd.to_numeric(
    merged["population_state_2025_persons"],
    errors="coerce"
)

merged["vehicle_reg_per_1000_pop_2025"] = merged.apply(
    lambda r: safe_divide(r["vehicle_reg_2025_state"], r["population_state_2025_persons"]) * 1000
    if safe_divide(r["vehicle_reg_2025_state"], r["population_state_2025_persons"]) is not None
    else None,
    axis=1
)

merged["car_reg_per_1000_pop_2025"] = merged.apply(
    lambda r: safe_divide(r["car_reg_2025_state"], r["population_state_2025_persons"]) * 1000
    if safe_divide(r["car_reg_2025_state"], r["population_state_2025_persons"]) is not None
    else None,
    axis=1
)

merged["motorcycle_reg_per_1000_pop_2025"] = merged.apply(
    lambda r: safe_divide(r["motorcycle_reg_2025_state"], r["population_state_2025_persons"]) * 1000
    if safe_divide(r["motorcycle_reg_2025_state"], r["population_state_2025_persons"]) is not None
    else None,
    axis=1
)

merged["car_share_of_vehicle_reg_2025"] = merged.apply(
    lambda r: safe_divide(r["car_reg_2025_state"], r["vehicle_reg_2025_state"]),
    axis=1
)

merged["motorcycle_share_of_vehicle_reg_2025"] = merged.apply(
    lambda r: safe_divide(r["motorcycle_reg_2025_state"], r["vehicle_reg_2025_state"]),
    axis=1
)


# ==========================================================
# 10. Add metadata and limitation notes
# ==========================================================

merged["population_source"] = "OpenDOSM population_state 2025"
merged["vehicle_source"] = "data.gov.my JPJ vehicles_2025 registration transactions"
merged["spatial_matching_level"] = "state-level proxy"
merged["limitation"] = (
    "Vehicle registration state refers to JPJ registration office state; "
    "it is not city-level vehicle stock and not active licensed vehicles."
)


# ==========================================================
# 11. Select final columns
# ==========================================================

final_cols = [
    "city",
    "matched_state",
    "population_state_2025_persons",
    "vehicle_reg_2025_state",
    "car_reg_2025_state",
    "motorcycle_reg_2025_state",
    "lorry_reg_2025_state",
    "van_reg_2025_state",
    "bus_reg_2025_state",
    "trailer_reg_2025_state",
    "other_vehicle_reg_2025_state",
    "vehicle_reg_per_1000_pop_2025",
    "car_reg_per_1000_pop_2025",
    "motorcycle_reg_per_1000_pop_2025",
    "car_share_of_vehicle_reg_2025",
    "motorcycle_share_of_vehicle_reg_2025",
    "population_source",
    "vehicle_source",
    "spatial_matching_level",
    "limitation"
]

for col in final_cols:
    if col not in merged.columns:
        merged[col] = None

final_df = merged[final_cols].copy()

# Round numeric columns.
numeric_cols = final_df.select_dtypes(include="number").columns
final_df[numeric_cols] = final_df[numeric_cols].round(4)


# ==========================================================
# 12. Validation checks
# ==========================================================

validation_checks = []

def add_validation(city, check_name, status, value, expected, note=""):
    validation_checks.append({
        "city": city,
        "check_name": check_name,
        "status": status,
        "value": value,
        "expected": expected,
        "note": note
    })


for _, row in final_df.iterrows():
    city = row["city"]

    if pd.notna(row["population_state_2025_persons"]) and row["population_state_2025_persons"] > 0:
        add_validation(city, "population_positive", "PASS", row["population_state_2025_persons"], "> 0")
    else:
        add_validation(city, "population_positive", "FAIL", row["population_state_2025_persons"], "> 0")

    if pd.notna(row["vehicle_reg_2025_state"]) and row["vehicle_reg_2025_state"] >= 0:
        add_validation(city, "vehicle_registration_non_negative", "PASS", row["vehicle_reg_2025_state"], ">= 0")
    else:
        add_validation(city, "vehicle_registration_non_negative", "FAIL", row["vehicle_reg_2025_state"], ">= 0")

    car_share = row["car_share_of_vehicle_reg_2025"]
    moto_share = row["motorcycle_share_of_vehicle_reg_2025"]

    if pd.notna(car_share) and 0 <= car_share <= 1:
        add_validation(city, "car_share_range", "PASS", car_share, "0–1")
    else:
        add_validation(city, "car_share_range", "FAIL", car_share, "0–1")

    if pd.notna(moto_share) and 0 <= moto_share <= 1:
        add_validation(city, "motorcycle_share_range", "PASS", moto_share, "0–1")
    else:
        add_validation(city, "motorcycle_share_range", "FAIL", moto_share, "0–1")


validation_df = pd.DataFrame(validation_checks)

summary_df = (
    validation_df
    .groupby(["status"])
    .size()
    .reset_index(name="count")
)


# ==========================================================
# 13. Export Excel
# ==========================================================

print("\n" + "=" * 80)
print("6. EXPORTING EXCEL")
print("=" * 80)

with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
    final_df.to_excel(writer, sheet_name="city_state_indicators", index=False)
    city_state_map.to_excel(writer, sheet_name="city_state_matching", index=False)
    pop_2025_clean.to_excel(writer, sheet_name="population_state_2025", index=False)
    vehicle_state.to_excel(writer, sheet_name="vehicle_state_2025", index=False)
    validation_df.to_excel(writer, sheet_name="validation_checks", index=False)
    summary_df.to_excel(writer, sheet_name="validation_summary", index=False)

print("\n" + "=" * 80)
print("ALL DONE")
print("=" * 80)
print(f"Output Excel: {OUTPUT_EXCEL}")
print(f"Raw population selected file: {RAW_POP_FILE}")
print(f"Raw vehicle selected file   : {RAW_VEHICLE_FILE}")
print("=" * 80)

print("\nFinal city-state indicators:")
print(final_df)

print("\nValidation summary:")
print(summary_df)

failed = validation_df[validation_df["status"] == "FAIL"]
if failed.empty:
    print("\nNo FAIL checks found.")
else:
    print("\nFAIL checks found:")
    print(failed)

print("\nScript finished successfully.")