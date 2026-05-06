#!/usr/bin/env python3
"""
Reproduce the key supplementary outputs for the Malaysia 7-city traffic-performance diagnosis paper.
Run from the folder that contains the input workbooks, or edit INPUT_DIR below.
Outputs are written to ./reproduced_outputs.
"""
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster

INPUT_DIR = Path('.')
OUTPUT_DIR = Path('reproduced_outputs')
OUTPUT_DIR.mkdir(exist_ok=True)
MASTER_FILE = INPUT_DIR / 'S1_master_dataset_and_dictionary' / 'S1_Malaysia_7Cities_master_dataset.xlsx'
if not MASTER_FILE.exists():
    MASTER_FILE = INPUT_DIR / 'Malaysia_7Cities_master_dataset.xlsx'

city_order = ['George Town', 'Kota Bharu', 'Kuala Lumpur', 'Seberang Perai', 'Johor Bahru', 'Ipoh', 'Kajang']
master = pd.read_excel(MASTER_FILE, sheet_name='master_dataset')
master['city'] = pd.Categorical(master['city'], categories=city_order, ordered=True)
master = master.sort_values('city').reset_index(drop=True)

# Figure 3 source data
fig3 = master[['city','tomtom_average_congestion_percent','tomtom_tt10_seconds','tomtom_rush_hour_time_lost_hours','tomtom_peak_asymmetry_index','tomtom_average_speed_kmh','tomtom_monthly_congestion_cv_2025']].copy()
fig3.columns = ['city','average_congestion_percent','tt10_seconds','rush_hour_time_lost_hours','peak_asymmetry_index','average_speed_kmh','monthly_congestion_cv_2025']
fig3.to_csv(OUTPUT_DIR / 'Figure3_source_data.csv', index=False)

# Figure 5 z-score matrix
fig5_map = {
    'Avg congestion':'tomtom_average_congestion_percent',
    'Monthly mean':'tomtom_monthly_congestion_mean_2025',
    'TT10':'tomtom_tt10_seconds',
    'AM TT10':'tomtom_am_peak_tt10_min',
    'PM TT10':'tomtom_pm_peak_tt10_min',
    'Speed burden':'tomtom_average_speed_kmh',
    'Monthly SD':'tomtom_monthly_congestion_sd_2025',
    'Monthly CV':'tomtom_monthly_congestion_cv_2025',
    'PAI':'tomtom_peak_asymmetry_index',
    'Road density':'osm_road_density_km_per_km2',
    'Intersection density':'osm_intersection_density_per_km2',
    'High-capacity share':'osm_highway_dependency_proxy',
    'Major road share':'osm_major_road_share',
    'Vehicles/1k pop':'popveh_vehicle_reg_per_1000_pop_2025',
    'Cars/1k pop':'popveh_car_reg_per_1000_pop_2025',
    'Motorcycles/1k pop':'popveh_motorcycle_reg_per_1000_pop_2025',
}
X = pd.DataFrame({'city': master['city'].astype(str)})
for name, col in fig5_map.items():
    X[name] = master[col]
X['Speed burden'] = -X['Speed burden']
Z = X.copy()
for col in Z.columns[1:]:
    Z[col] = (X[col] - X[col].mean()) / X[col].std(ddof=1)
Z.to_csv(OUTPUT_DIR / 'Figure5_zscore_matrix.csv', index=False)

# Figure 6 clustering
core_cols = ['Avg congestion','TT10','Speed burden','Monthly CV','PAI','Road density','Intersection density','High-capacity share','Vehicles/1k pop']
fig6_input = Z[['city'] + core_cols].rename(columns={'Vehicles/1k pop':'Vehicle proxy'})
fig6_input.to_csv(OUTPUT_DIR / 'Figure6_clustering_input_9_core_zscores.csv', index=False)
L = linkage(fig6_input.drop(columns='city').values.astype(float), method='ward', metric='euclidean')
pd.DataFrame(L, columns=['cluster_1','cluster_2','distance','new_cluster_size']).to_csv(OUTPUT_DIR / 'Figure6_Ward_linkage_matrix.csv', index=False)
clusters = fcluster(L, 3, criterion='maxclust')
assign = pd.DataFrame({'city': fig6_input['city'], 'cluster_raw': clusters})
assign['regime'] = assign['city'].map({
    'Seberang Perai':'Regime 1', 'Johor Bahru':'Regime 1', 'Ipoh':'Regime 1', 'Kajang':'Regime 1',
    'George Town':'Regime 2', 'Kota Bharu':'Regime 2',
    'Kuala Lumpur':'Regime 3'
})
assign.to_csv(OUTPUT_DIR / 'Figure6_regime_assignments.csv', index=False)
profile = fig6_input.merge(assign[['city','regime']], on='city')
profile.groupby('regime').mean(numeric_only=True).loc[['Regime 1','Regime 2','Regime 3']].to_csv(OUTPUT_DIR / 'Figure6_regime_profile_mean_zscore.csv')
print('Reproduction finished. Outputs saved to', OUTPUT_DIR.resolve())
