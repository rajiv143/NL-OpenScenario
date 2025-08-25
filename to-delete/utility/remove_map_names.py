#!/usr/bin/env python3
"""Remove explicit map names from all JSON scenario files"""

import os
import json
import glob

def remove_map_names():
    """Remove map_name from all JSON files in generated_scenarios"""
    json_files = glob.glob("generated_scenarios/*.json")
    
    # Filter out backup files
    json_files = [f for f in json_files if not f.endswith('.bak')]
    
    modified_count = 0
    
    for json_file in json_files:
        try:
            # Read the JSON file
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Check if map_name exists and remove it
            if 'map_name' in data:
                original_map = data['map_name']
                del data['map_name']
                
                # Write back the modified JSON
                with open(json_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                print(f"Removed map_name '{original_map}' from {os.path.basename(json_file)}")
                modified_count += 1
            else:
                print(f"No map_name found in {os.path.basename(json_file)}")
                
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
    
    print(f"\nModified {modified_count} files out of {len(json_files)} total files")

if __name__ == '__main__':
    remove_map_names()