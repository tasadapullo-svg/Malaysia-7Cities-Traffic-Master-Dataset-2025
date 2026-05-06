# Malaysia 7 Cities Traffic-Performance Diagnosis: Supplementary Materials

This ZIP contains the files needed to support reproducibility of the manuscript.

## Main components

- **S1_master_dataset_and_dictionary**: master city-level dataset and variable dictionary.
- **S2_TomTom_FCD_indicators**: TomTom traffic-performance indicators used in the manuscript.
- **S3_OSM_network_indicators_and_validation**: recalibrated OSM road-network indicators and validation report.
- **S4_population_vehicle_background_proxy**: population and vehicle-registration background proxies, selected raw parquet files, and readable CSV exports from the population/vehicle workbook.
- **S5_figure_source_data_and_analysis_script**: source data for Figure 3, Figure 4, Figure 5, Figure 6, Table 3, Table 4, Table 5, sensitivity analysis, and the Python reproduction script.
- **S6_validation_and_reproducibility_notes**: formula checks, validation status counts, formula/method notes, and data-availability statement.

## How to rerun key analysis

1. Unzip this package.
2. Install Python packages if needed: `pandas`, `numpy`, `scipy`, `pyarrow`, and `openpyxl`.
3. From the unzipped folder, run:

```bash
python S5_figure_source_data_and_analysis_script/rerun_multidimensional_diagnosis.py
```

The script writes reproduced outputs to `reproduced_outputs`.

## Interpretation boundary

- TomTom indicators are platform-based FCD benchmarks, not ground-truth traffic counts.
- OSM indicators are contextual road-network variables.
- Population and vehicle indicators are state-level background proxies.
- Ward clustering is exploratory and diagnostic, not predictive or causal.
