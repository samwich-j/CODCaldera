"""
CalderaEndpointDownload.py

Extracts breadcrumb data for all players from the Caldera .usda file.
Outputs a CSV of player position and life values over time.

Author: Sam Johnston
"""


import os
import sys

# Ensure we're always running from the project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
os.chdir(PROJECT_ROOT)

# Confirm you're in the right place
print(f"📁 Current working directory set to: {os.getcwd()}")


import pandas as pd
import re
import sys
from pxr import Usd

# === File Paths ===
USD_FILE_PATH = r"changethistoyourusdafile"
OUTPUT_CSV = "data/caldera_breadcrumbs.csv"
CHUNK_SIZE = 200

# === Core Functions ===

def open_usd_stage(path):
    print("--- Opening USD Stage ---")
    try:
        stage = Usd.Stage.Open(path)
        if not stage:
            raise Exception("Failed to open the USD stage.")
        print("✅ Stage opened successfully.\n")
        return stage
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit()

def find_player_paths(stage):
    print("--- Step 2: Finding all individual player paths ---")
    player_paths = [
        str(prim.GetPath())
        for prim in stage.Traverse()
        if '/players/breadcrumbs/match_' in str(prim.GetPath()) and '/player_' in str(prim.GetPath())
    ]
    if not player_paths:
        raise Exception("Could not find any individual player paths.")
    print(f"✅ Found {len(player_paths)} individual player paths to process.")
    return player_paths

def extract_player_data(stage, path):
    try:
        prim = stage.GetPrimAtPath(path)
        if not prim: return []

        match = re.search(r'match_(\d+)', path)
        player = re.search(r'player_(\d+)', path)
        match_id = int(match.group(1)) if match else -1
        player_id = int(player.group(1)) if player else -1

        pos_attr = prim.GetAttribute('xformOp:translate')
        life_attr = prim.GetAttribute('primvars:life')

        if not pos_attr or not life_attr:
            return []

        return [
            {
                'match_id': match_id,
                'player_id': player_id,
                'time_step': t,
                'pos_x': pos[0],
                'pos_y': pos[1],
                'pos_z': pos[2],
                'life': life
            }
            for t in pos_attr.GetTimeSamples()
            if (pos := pos_attr.Get(t)) is not None and (life := life_attr.Get(t)) is not None
        ]
    except Exception as e:
        print(f"⚠️ Failed to process {path}. Error: {e}")
        return []

def save_chunk(chunk, header_written):
    df = pd.DataFrame(chunk)
    df.to_csv(OUTPUT_CSV, mode='a', index=False, header=not header_written)
    return len(df)

# === Main Execution ===

def main():
    stage = open_usd_stage(USD_FILE_PATH)
    player_paths = find_player_paths(stage)

    all_data_chunk = []
    header_written = False

    print(f"--- Step 3: Extracting data in chunks of {CHUNK_SIZE} ---")
    for i, path in enumerate(player_paths):
        print(f"-> Processing player {i+1}/{len(player_paths)}: {path}")
        data = extract_player_data(stage, path)
        all_data_chunk.extend(data)

        if (i + 1) % CHUNK_SIZE == 0 or (i + 1) == len(player_paths):
            if not all_data_chunk:
                print("  - No data to save in this chunk.")
                continue
            print(f"  --> Saving chunk at player {i+1} with {len(all_data_chunk)} rows...")
            rows_written = save_chunk(all_data_chunk, header_written)
            print(f"✅ {rows_written} rows written.")
            header_written = True
            all_data_chunk = []

    print(f"\n🎉 SUCCESS! Data saved to: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
