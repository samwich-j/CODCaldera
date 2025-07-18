# -*- coding: utf-8 -*-
"""
Created on Fri Jun 20 15:44:01 2025

@author: Sam Johnston
"""

import pandas as pd
from shapely.geometry import Point, Polygon
import re
import sys
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PolygonPatch
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import matplotlib.patheffects as path_effects

# --- Step 1: Load All Data ---
print("--- Loading All Data ---")
try:
    breadcrumbs_df = pd.read_csv('caldera_breadcrumbs.csv')
    boundaries_df = pd.read_excel('CalderaCoordinates.xlsx')
    print("Successfully loaded breadcrumbs data and your custom boundaries.")
except FileNotFoundError as e:
    print(f"ERROR: Could not find a required file. Please check file names. Details: {e}")
    sys.exit()
except Exception as e:
    print(f"An error occurred while reading the files: {e}")
    sys.exit()

# --- Step 2: Landing Spot & Death Location Analysis ---
print("--- Analyzing player paths for landing and death locations... ---")
unique_player_id = ['match_id', 'player_id']
active_play_df = breadcrumbs_df[breadcrumbs_df['life'] >= 0].copy()
active_play_df['start_time'] = active_play_df.groupby(unique_player_id)['time_step'].transform('min')
landing_window_df = active_play_df[active_play_df['time_step'] <= (active_play_df['start_time'] + 45)]
landing_spots_df = landing_window_df.loc[landing_window_df.groupby(unique_player_id)['pos_z'].idxmin()]
death_locations_df = breadcrumbs_df.loc[breadcrumbs_df.groupby(unique_player_id)['life'].idxmax()]
survival_df = active_play_df.groupby(unique_player_id)['time_step'].max().to_frame('survival_time').reset_index()
analysis_df = pd.merge(landing_spots_df[unique_player_id + ['pos_x', 'pos_y']], survival_df, on=unique_player_id)
print(f"Found landing data for {len(analysis_df)} unique players.")
print(f"Found death locations for {len(death_locations_df)} players.")

# --- Step 3: Prepare Polygon Definitions ---
print("--- Parsing your custom Excel format for POI boundaries ---")
poi_polygons = []
def parse_coords_from_row(row):
    coords = []
    for i in range(1, 10):
        coord_val = row.get(f'Coordinate {i}')
        if pd.notna(coord_val):
            numbers = re.findall(r'-?\d+\.?\d*', str(coord_val))
            if len(numbers) == 2:
                coords.append((float(numbers[0]), float(numbers[1])))
    return coords
for index, row in boundaries_df.iterrows():
    coordinates = parse_coords_from_row(row)
    if coordinates:
        poi_polygons.append({"name": row['Name'], "letter": row['Shape'], "polygon": Polygon(coordinates)})

# --- Step 4: Classify Locations & Calculate Stats ---
print("--- Classifying locations and calculating statistics... ---")
def classify_point(x, y):
    point = Point(x, y)
    for poi in poi_polygons:
        if poi['polygon'].contains(point):
            return poi['name']
    return 'Other'
analysis_df['landing_poi'] = analysis_df.apply(lambda row: classify_point(row['pos_x'], row['pos_y']), axis=1)
death_locations_df['death_poi'] = death_locations_df.apply(lambda row: classify_point(row['pos_x'], row['pos_y']), axis=1)
print("Classification complete.")

# --- Step 5: Create and Display Final Summary Tables ---
# Landing Spot Summary
poi_groups = analysis_df.groupby('landing_poi')
landing_summary_df = poi_groups.size().to_frame('player_count')
landing_summary_df['avg_survival_time'] = poi_groups['survival_time'].mean()
landing_summary_df_filtered = landing_summary_df[landing_summary_df.index != 'Other'].copy()
min_time = landing_summary_df_filtered['avg_survival_time'].min()
max_time = landing_summary_df_filtered['avg_survival_time'].max()
if (max_time - min_time) > 0:
    landing_summary_df_filtered['survival_score'] = ((landing_summary_df_filtered['avg_survival_time'] - min_time) / (max_time - min_time) * 100).astype(int)
else:
    landing_summary_df_filtered['survival_score'] = 100
name_to_letter = {poi['name']: poi['letter'] for poi in poi_polygons}
landing_summary_df_filtered['POI'] = landing_summary_df_filtered.index.map(name_to_letter)
landing_summary_df_filtered['Name'] = landing_summary_df_filtered.index

# Death Location Summary
death_summary_df = death_locations_df.groupby('death_poi').size().to_frame('death_count')
death_summary_df_filtered = death_summary_df[death_summary_df.index != 'Other'].copy()
death_summary_df_filtered['POI'] = death_summary_df_filtered.index.map(name_to_letter)
death_summary_df_filtered['Name'] = death_summary_df_filtered.index

print("\n" + "="*50)
print("--- FINAL ANALYSIS RESULTS ---")
print("="*50)
player_count_table = landing_summary_df_filtered[['POI', 'Name', 'player_count']].sort_values(by='player_count', ascending=False)
print("\n--- Landing Hotspots (Most Popular) ---")
print(player_count_table.to_string())
survival_score_table = landing_summary_df_filtered[['POI', 'Name', 'survival_score']].sort_values(by='survival_score', ascending=False)
print("\n--- Safest Landing Spots (Best Survival) ---")
print(survival_score_table.to_string())
death_count_table = death_summary_df_filtered[['POI', 'Name', 'death_count']].sort_values(by='death_count', ascending=False)
print("\n--- Deadliest POIs (Most Deaths) ---")
print(death_count_table.to_string())


# --- Step 6: Generate All Heatmap Visualizations ---
print("\n--- Generating Heatmap Visualizations (3 total) ---")
def create_summary_heatmap(map_df, data_column_name, title, cmap_name, scatter_df):
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.set_facecolor('black')
    ax.scatter(scatter_df['pos_x'], scatter_df['pos_y'], s=1, alpha=0.05, color='gray')
    data_column = map_df[data_column_name]
    norm = Normalize(vmin=data_column.min(), vmax=data_column.max())
    cmap = plt.get_cmap(cmap_name)
    for poi in poi_polygons:
        poi_name = poi['name']
        if poi_name in data_column.index:
            value = data_column[poi_name]
            color = cmap(norm(value))
            patch = PolygonPatch(poi['polygon'].exterior.coords, facecolor=color, edgecolor='white', linewidth=0.5, alpha=0.8)
            ax.add_patch(patch)
            centroid = poi['polygon'].centroid
            ax.text(centroid.x, centroid.y, poi['letter'], color='white', fontsize=14, ha='center', va='center', fontweight='bold', path_effects=[path_effects.Stroke(linewidth=2, foreground='black'), path_effects.Normal()])
    sm = ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    fig.colorbar(sm, ax=ax, label=title)
    ax.set_title(f'Heatmap of {title}')
    ax.set_xlabel('X Coordinate'); ax.set_ylabel('Y Coordinate')
    ax.set_xlim(-70000, 70000); ax.set_ylim(-70000, 70000)
    fig.tight_layout()
    # NEW: Uncomment the line below to save the figure as a PNG
    plt.savefig(f'heatmap_{title.replace(" ", "_")}.png', dpi=300, bbox_inches='tight', facecolor='black')
    plt.show()

# Plot 1: Player Count by Landing POI
print("Generating Heatmap 1: Player Count by Landing POI...")
create_summary_heatmap(landing_summary_df_filtered.set_index('Name'), 'player_count', 'Player Count by Landing POI', 'viridis', analysis_df)

# Plot 2: Survival Score by Landing POI
print("Generating Heatmap 2: Landing Survival Score by POI...")
create_summary_heatmap(landing_summary_df_filtered.set_index('Name'), 'survival_score', 'Landing Survival Score (0-100)', 'magma', analysis_df)

# Plot 3: Death Count by POI
print("Generating Heatmap 3: Player Death Count by POI...")
create_summary_heatmap(death_summary_df_filtered.set_index('Name'), 'death_count', 'Player Death Count by POI', 'hot', death_locations_df)

# Plot 4 (Bonus): Raw Death Location Density
print("Generating Heatmap 4: Raw Player Death Location Density...")
fig, ax = plt.subplots(figsize=(12, 12))
ax.set_facecolor('black')
h = ax.hist2d(x=death_locations_df['pos_x'], y=death_locations_df['pos_y'], bins=250, range=[[-70000, 70000], [-70000, 70000]], cmap='hot', cmin=1)
fig.colorbar(h[3], ax=ax, label='Number of Player Deaths per Cell')
for poi in poi_polygons:
    patch = PolygonPatch(poi['polygon'].exterior.coords, facecolor='none', edgecolor='cyan', linewidth=1.5, alpha=0.9)
    ax.add_patch(patch)
    centroid = poi['polygon'].centroid
    ax.text(centroid.x, centroid.y, poi['letter'], color='white', fontsize=14, ha='center', va='center', fontweight='bold', path_effects=[path_effects.Stroke(linewidth=2, foreground='black')])
ax.set_title('Heatmap of Player Death Locations')
ax.set_xlabel('X Coordinate'); ax.set_ylabel('Y Coordinate')
ax.set_xlim(-70000, 70000); ax.set_ylim(-70000, 70000)
fig.tight_layout()
# NEW: Uncomment the line below to save the figure as a PNG
plt.savefig('heatmap_raw_death_density.png', dpi=300, bbox_inches='tight', facecolor='black')
plt.show()

print("\n--- All tasks complete. ---")