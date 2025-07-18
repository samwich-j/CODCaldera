# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""
CalderaEndpointAnalysis.py

Analyzes player movement data from Call of Duty: Warzone Caldera map.
Performs the following:
- Loads landing and death location data
- Classifies each location by polygon-defined POIs
- Calculates survival and death stats by POI
- Generates heatmaps of player behavior
- Exports summary tables as CSV

Author: Sam Johnston
"""

import os
import pandas as pd
import re
import sys
from shapely.geometry import Point, Polygon
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PolygonPatch
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import matplotlib.patheffects as path_effects

# Set working directory to project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
os.chdir(PROJECT_ROOT)
print(f"📁 Working directory set to: {os.getcwd()}")


# ========== Data Loading Functions ==========

def load_data(breadcrumbs_path='data/caldera_breadcrumbs.csv', boundaries_path='data/CalderaCoordinates.xlsx'):
    """
    Load breadcrumb and POI data from local files.

    Parameters:
        breadcrumbs_path (str): Path to CSV with breadcrumb data.
        boundaries_path (str): Path to Excel file with POI polygons.

    Returns:
        tuple: (breadcrumbs_df, boundaries_df)
    """
    try:
        breadcrumbs_df = pd.read_csv(breadcrumbs_path)
        boundaries_df = pd.read_excel(boundaries_path)
        print("✅ Loaded breadcrumbs and POI boundaries.")
        return breadcrumbs_df, boundaries_df
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        sys.exit()
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        sys.exit()


# ========== Polygon Creation ==========

def parse_poi_polygons(boundaries_df):
    """
    Convert POI coordinate rows from Excel into shapely polygons.

    Parameters:
        boundaries_df (DataFrame): Excel table with named POIs and coordinates.

    Returns:
        list: A list of dictionaries, each with 'name', 'letter', and 'polygon' keys.
    """
    def parse_coords_from_row(row):
        coords = []
        for i in range(1, 10):
            coord_val = row.get(f'Coordinate {i}')
            if pd.notna(coord_val):
                numbers = re.findall(r'-?\d+\.?\d*', str(coord_val))
                if len(numbers) == 2:
                    coords.append((float(numbers[0]), float(numbers[1])))
        return coords

    poi_polygons = []
    for _, row in boundaries_df.iterrows():
        coords = parse_coords_from_row(row)
        if coords:
            poi_polygons.append({
                "name": row['Name'],
                "letter": row['Shape'],
                "polygon": Polygon(coords)
            })
    return poi_polygons


# ========== Point Classification ==========

def classify_point(x, y, poi_polygons):
    """
    Determine which POI (if any) a point falls within.

    Parameters:
        x (float): X coordinate.
        y (float): Y coordinate.
        poi_polygons (list): List of polygon definitions.

    Returns:
        str: Name of the POI or 'Other'.
    """
    point = Point(x, y)
    for poi in poi_polygons:
        if poi['polygon'].contains(point):
            return poi['name']
    return 'Other'


# ========== Summary Statistics ==========

def create_landing_and_survival_stats(breadcrumbs_df, poi_polygons):
    """
    Calculate landing positions, death positions, and survival time.

    Parameters:
        breadcrumbs_df (DataFrame): Full breadcrumb trail with life and position.
        poi_polygons (list): List of POI polygons.

    Returns:
        tuple: (analysis_df with landing + survival, death_df with death points)
    """
    unique_id = ['match_id', 'player_id']
    active_df = breadcrumbs_df[breadcrumbs_df['life'] >= 0].copy()

    active_df['start_time'] = active_df.groupby(unique_id)['time_step'].transform('min')
    landing_window_df = active_df[active_df['time_step'] <= (active_df['start_time'] + 45)]
    landing_df = landing_window_df.loc[landing_window_df.groupby(unique_id)['pos_z'].idxmin()]

    death_df = breadcrumbs_df.loc[breadcrumbs_df.groupby(unique_id)['life'].idxmax()]
    survival_df = active_df.groupby(unique_id)['time_step'].max().reset_index(name='survival_time')

    analysis_df = pd.merge(landing_df[unique_id + ['pos_x', 'pos_y']], survival_df, on=unique_id)
    analysis_df['landing_poi'] = analysis_df.apply(lambda row: classify_point(row['pos_x'], row['pos_y'], poi_polygons), axis=1)
    death_df['death_poi'] = death_df.apply(lambda row: classify_point(row['pos_x'], row['pos_y'], poi_polygons), axis=1)

    return analysis_df, death_df


def summarize_landing_data(analysis_df, poi_polygons):
    """
    Create a summary table of player counts and survival by POI.

    Returns:
        DataFrame: Summary with player_count, avg_survival_time, and survival_score.
    """
    name_to_letter = {p['name']: p['letter'] for p in poi_polygons}
    grouped = analysis_df.groupby('landing_poi')

    df = grouped.size().to_frame('player_count')
    df['avg_survival_time'] = grouped['survival_time'].mean()
    df = df[df.index != 'Other']

    min_time = df['avg_survival_time'].min()
    max_time = df['avg_survival_time'].max()
    df['survival_score'] = (
        ((df['avg_survival_time'] - min_time) / (max_time - min_time) * 100)
        if (max_time - min_time) > 0 else 100
    ).astype(int)

    df['POI'] = df.index.map(name_to_letter)
    df['Name'] = df.index
    return df

def summarize_death_data(death_df, poi_polygons):
    """
    Create a summary of total deaths by POI.

    Returns:
        DataFrame: Summary with death_count per POI.
    """
    name_to_letter = {p['name']: p['letter'] for p in poi_polygons}
    df = death_df.groupby('death_poi').size().to_frame('death_count')
    df = df[df.index != 'Other']
    df['POI'] = df.index.map(name_to_letter)
    df['Name'] = df.index
    return df


def create_heatmap(map_df, column, title, cmap_name, scatter_df, poi_polygons):
    """
    Generate and save a heatmap visualization for the given POI metric.

    Parameters:
        map_df (DataFrame): Summary table indexed by POI name.
        column (str): Column name to color by (e.g., 'player_count').
        title (str): Plot title and output filename label.
        cmap_name (str): Matplotlib colormap to use.
        scatter_df (DataFrame): Raw player position data.
        poi_polygons (list): List of POI polygons.
    """
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.set_facecolor('black')
    ax.scatter(scatter_df['pos_x'], scatter_df['pos_y'], s=1, alpha=0.05, color='gray')

    values = map_df[column]
    norm = Normalize(vmin=values.min(), vmax=values.max())
    cmap = plt.get_cmap(cmap_name)

    for poi in poi_polygons:
        name = poi['name']
        if name in values.index:
            color = cmap(norm(values[name]))
            patch = PolygonPatch(poi['polygon'].exterior.coords, facecolor=color, edgecolor='white', linewidth=0.5, alpha=0.8)
            ax.add_patch(patch)

            centroid = poi['polygon'].centroid
            ax.text(centroid.x, centroid.y, poi['letter'], color='white', fontsize=14, ha='center', va='center',
                    path_effects=[path_effects.Stroke(linewidth=2, foreground='black'), path_effects.Normal()])

    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    fig.colorbar(sm, ax=ax, label=title)

    ax.set_title(title)
    ax.set_xlabel('X Coordinate')
    ax.set_ylabel('Y Coordinate')
    ax.set_xlim(-70000, 70000)
    ax.set_ylim(-70000, 70000)
    fig.tight_layout()

    output_path = f'outputs/heatmap_{title.replace(" ", "_")}.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='black')
    plt.show()


def main():
    print("\n=== COD Caldera Analysis ===")

    # Step 1: Load data
    breadcrumbs_df, boundaries_df = load_data()
    
    # Step 2: Parse POIs
    poi_polygons = parse_poi_polygons(boundaries_df)

    # Step 3: Analyze and classify locations
    analysis_df, death_df = create_landing_and_survival_stats(breadcrumbs_df, poi_polygons)

    # Step 4: Summarize data
    landing_summary = summarize_landing_data(analysis_df, poi_polygons)
    death_summary = summarize_death_data(death_df, poi_polygons)

    print("\n--- Landing Hotspots ---")
    print(landing_summary[['POI', 'Name', 'player_count']].sort_values(by='player_count', ascending=False))

    print("\n--- Safest Landing Spots ---")
    print(landing_summary[['POI', 'Name', 'survival_score']].sort_values(by='survival_score', ascending=False))

    print("\n--- Deadliest POIs ---")
    print(death_summary[['POI', 'Name', 'death_count']].sort_values(by='death_count', ascending=False))

    # Step 5: Visualizations
    print("\n--- Generating Heatmaps ---")
    create_heatmap(landing_summary.set_index('Name'), 'player_count', 'Player Count by Landing POI', 'viridis', analysis_df, poi_polygons)
    create_heatmap(landing_summary.set_index('Name'), 'survival_score', 'Landing Survival Score (0–100)', 'magma', analysis_df, poi_polygons)
    create_heatmap(death_summary.set_index('Name'), 'death_count', 'Player Death Count by POI', 'hot', death_df, poi_polygons)

    # === Save summary tables ===
    landing_summary.to_csv("outputs/landing_summary.csv", index=False)
    death_summary.to_csv("outputs/death_summary.csv", index=False)
    print("📁 Saved summary tables to 'outputs/'")


if __name__ == "__main__":
    main()


