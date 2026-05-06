# Formula and method reference notes

This file lists the methodological support used for the formulas and analytical steps in the manuscript.

1. TomTom 10 km travel time, congestion, and rush-hour time lost: TomTom Traffic Index methodology and traffic-index documentation.
2. Peak asymmetry index (PAI): A normalized difference index constructed from AM and PM TT10. It follows the standard logic of relative difference / normalized imbalance metrics. It is defined explicitly in the manuscript and reproduced in the analysis script.
3. Coefficient of variation (CV): Standard descriptive-statistics measure, computed as standard deviation divided by mean.
4. Road density and intersection density: Standard network-density measures used in transport geography and OSM/OSMnx-based urban network analysis.
5. High-capacity road share and major road share: Ratio indicators based on OSM highway classes. Raw OSM motorway tags are retained, while motorway + trunk is used as a calibrated high-capacity proxy.
6. z-score standardisation: Standard sample standardisation using sample standard deviation (ddof = 1).
7. Ward linkage: Hierarchical clustering method using Euclidean distance and within-cluster variance minimisation.

Key references in the manuscript include TomTom (2025, 2026a, 2026b), Boeing (2025), Acharya et al. (2025), Seong et al. (2023), Zang et al. (2023), and Zhang et al. (2025).
