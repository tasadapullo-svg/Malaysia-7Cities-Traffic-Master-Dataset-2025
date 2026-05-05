# Malaysia 7-City Traffic Master Dataset 2025

This repository provides the supporting dataset and reproducible Python workflow for a seven-city Malaysian urban traffic-performance analysis in 2025.

The dataset integrates four groups of variables:

1. TomTom-derived city-level traffic-performance indicators.
2. OpenStreetMap road-network structure indicators.
3. OpenDOSM 2025 state-level population estimates.
4. data.gov.my JPJ 2025 vehicle-registration transaction indicators.

The archived version of this dataset is available through Zenodo:

**DOI:** `10.5281/zenodo.20032206`

---

## 1. Study cities

The final master dataset covers seven Malaysian cities:

| No. | City |
|---:|---|
| 1 | George Town |
| 2 | Kota Bharu |
| 3 | Kuala Lumpur |
| 4 | Seberang Perai |
| 5 | Johor Bahru |
| 6 | Ipoh |
| 7 | Kajang |

---

## 2. Repository structure

```text
S1_Data_Malaysia_7Cities_Traffic_Master_Dataset_2025
│
├─ 01_master_dataset
│  └─ Malaysia_7Cities_master_dataset.xlsx
│
├─ 02_tomtom_input
│  └─ TomTom_7cities_indicators.xlsx
│
├─ 03_osm_network
│  ├─ OSM_road_network_indicators_7_cities.xlsx
│  ├─ OSM_validation_report.xlsx
│  ├─ city_boundaries
│  └─ road_edges
│
├─ 04_population_vehicle
│  ├─ population_vehicle_indicators_7_cities.xlsx
│  ├─ raw_population_state_2025_selected.parquet
│  └─ raw_vehicles_2025_selected.parquet
│
├─ 05_python_scripts
│  ├─ OSM.py
│  ├─ validate_osm_output.py
│  ├─ download_population_vehicle.py
│  └─ merge_master_dataset.py
│
└─ 06_documentation
   ├─ README.md
   ├─ DATA_DICTIONARY.md
   ├─ DATA_AVAILABILITY_STATEMENT.txt
   └─ METHODS_DATA_DESCRIPTION.docx