#!/usr/bin/env python3
"""
Batch convert all rebuilt scenarios to XOSC format
"""

import sys
import glob
import json
import os
from pathlib import Path

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter

def batch_convert_rebuilt_scenarios():
    """Convert all rebuilt scenarios to XOSC format"""
    
    # Find all JSON files in rebuilt_scenarios directory
    json_files = glob.glob("rebuilt_scenarios/*.json")
    json_files.sort()  # Sort for consistent ordering
    
    if not json_files:
        print("No JSON files found in rebuilt_scenarios/ directory")
        return
    
    # Create output directory
    output_dir = "converted_rebuilt_scenarios"
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize converter
    converter = JsonToXoscConverter()
    
    print(f"Converting {len(json_files)} rebuilt scenarios...")
    print("=" * 60)
    
    success_count = 0
    failed_count = 0
    failed_files = []
    
    for i, json_file in enumerate(json_files, 1):
        try:
            scenario_name = Path(json_file).stem
            print(f"[{i:3d}/{len(json_files):3d}] Converting {scenario_name}... ", end="", flush=True)
            
            # Load JSON data
            with open(json_file, 'r') as f:
                json_data = json.load(f)
            
            # Convert to XOSC
            xosc_content = converter.convert(json_data)
            
            # Write XOSC file
            output_file = os.path.join(output_dir, f"{scenario_name}.xosc")
            with open(output_file, 'w') as f:
                f.write(xosc_content)
            
            print("✅ SUCCESS")
            success_count += 1
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            failed_count += 1
            failed_files.append((json_file, str(e)))
    
    # Print summary
    print("\n" + "=" * 60)
    print("CONVERSION SUMMARY")
    print("=" * 60)
    print(f"✅ Successful conversions: {success_count}")
    print(f"❌ Failed conversions: {failed_count}")
    print(f"📊 Success rate: {success_count/(success_count+failed_count)*100:.1f}%")
    print(f"📁 Output directory: {output_dir}/")
    
    if failed_files:
        print(f"\n⚠️  Failed files:")
        for file, error in failed_files:
            print(f"   {file}: {error}")
    
    if success_count > 0:
        print(f"\n🎉 Successfully converted {success_count} scenarios!")
        print("Ready for CARLA ScenarioRunner testing.")
    
    return success_count, failed_count

if __name__ == '__main__':
    batch_convert_rebuilt_scenarios()