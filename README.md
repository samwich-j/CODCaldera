# COD Caldera Player Path Analysis

This project analyzes player movement data from the Call of Duty: Warzone **Caldera** map. It is built around Activision's public map data repository and custom-defined Points of Interest (POIs).

The goal is to:
- Identify the **most popular landing zones**
- Measure **average survival time** based on landing location
- Visualize **player death hotspots**

---

## 📁 Project Structure

```none
CalderaMapAnalysis/
│
├── data/                  # Map boundaries and extracted player data
│   ├── CalderaCoordinates.xlsx
│   └── caldera_breadcrumbs.csv  ← Generated from USD file (not included here)
│
├── src/                   # Main analysis and data extraction scripts
│   ├── CalderaEndpointDownload.py
│   └── CalderaEndpointAnalysis.py
│
├── outputs/               # Heatmaps and summary visualizations
├── requirements.txt       # Python dependencies
├── .gitignore
└── README.md

1. Install dependencies (in a virtual environment recommended):

pip install -r requirements.txt

2. Extract the data (run once):

python src/CalderaEndpointDownload.py

This will generate caldera_breadcrumbs.csv in the data/ folder.
Make sure to update the usd_file_path in the script to point to your local .usda file.

3. Run the analysis and generate heatmaps:

python src/CalderaEndpointAnalysis.py
