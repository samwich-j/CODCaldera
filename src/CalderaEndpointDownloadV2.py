



###......Caldera Endpoint Download........###


from pxr import Usd
import pandas as pd
import numpy as np
import sys
import re

# --- Step 1: Define File Path and Open USD Stage ---
usd_file_path = r"C:/Users/10877401/OneDrive - Utah Valley University/Analysis Projects/CalderaCODMap/caldera-main/caldera-main/caldera.usda"

print("--- Opening USD Stage ---")
try:
    stage = Usd.Stage.Open(usd_file_path)
    if not stage:
        raise Exception("Failed to open the USD stage.")
    print("SUCCESS: Stage opened successfully.\n")

    # --- Step 2: Find all individual player data paths ---
    print("--- Step 2: Finding all individual player paths ---")
    player_paths = []
    for prim in stage.Traverse():
        path_str = str(prim.GetPath())
        if '/players/breadcrumbs/match_' in path_str and '/player_' in path_str:
            player_paths.append(path_str)

    if not player_paths:
        raise Exception("Could not find any individual player paths.")
    
    print(f"Found {len(player_paths)} individual player paths to process.")

    # --- Step 3: Loop through each player and extract data in chunks ---
    print("--- Step 3: Extracting data in chunks. This will take a very long time... ---")
    
    all_player_data_chunk = []
    output_filename = 'caldera_breadcrumbs.csv'
    chunk_size = 200
    header_written = False

    # Main loop through every player path found
    for i, path in enumerate(player_paths):
        # NEW: Print the start of processing for each player
        print(f"-> Processing player {i+1}/{len(player_paths)}: {path}")
        
        try:
            # This is the inner loop logic for a single player
            prim = stage.GetPrimAtPath(path)
            if not prim: continue

            match = re.search(r'match_(\d+)', path)
            player = re.search(r'player_(\d+)', path)
            match_id = int(match.group(1)) if match else -1
            player_id = int(player.group(1)) if player else -1

            pos_attr = prim.GetAttribute('xformOp:translate')
            life_attr = prim.GetAttribute('primvars:life')
            
            if not pos_attr or not life_attr: continue
                
            time_samples = pos_attr.GetTimeSamples()
            for time_code in time_samples:
                pos = pos_attr.Get(time_code)
                life = life_attr.Get(time_code)
                
                if pos is not None and life is not None:
                    all_player_data_chunk.append({
                        'match_id': match_id, 'player_id': player_id, 'time_step': time_code,
                        'pos_x': pos[0], 'pos_y': pos[1], 'pos_z': pos[2], 'life': life
                    })
        except Exception as player_error:
            # NEW: If an error occurs with one player, print it and continue
            print(f"  - FAILED to process player {path}. Error: {player_error}")
            continue

        # Chunking logic to save progress and manage memory
        if (i + 1) % chunk_size == 0 or (i + 1) == len(player_paths):
            if not all_player_data_chunk:
                print(f"  - No data in current chunk to save. Continuing...")
                continue
            
            print(f"  --> Processed players up to {i+1}. Saving chunk of {len(all_player_data_chunk)} rows to CSV...")
            
            df_chunk = pd.DataFrame(all_player_data_chunk)
            
            if not header_written:
                df_chunk.to_csv(output_filename, index=False, mode='w')
                header_written = True
            else:
                df_chunk.to_csv(output_filename, index=False, mode='a', header=False)
            
            all_player_data_chunk = [] # Clear the chunk

    print(f"\nSUCCESS! Full breadcrumb data extraction complete. File saved to '{output_filename}'")

except Exception as e:
    print(f"A top-level ERROR occurred: {e}")