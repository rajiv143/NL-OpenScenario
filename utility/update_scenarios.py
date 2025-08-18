#!/usr/bin/env python3
"""Update a few key scenarios with the criteria fix"""

import sys
import json

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter

def update_key_scenarios():
    """Update the most important scenarios with the criteria fix"""
    key_scenarios = [
        'basic_following_001_stop_and_go_traffic_01.json',
        'basic_following_001_sudden_brake_ahead_01.json',
        'basic_following_002_following_slow_leader_02.json',
        'lane_change_051_cut_in_ahead_01.json'
    ]
    
    converter = JsonToXoscConverter()
    
    for scenario_file in key_scenarios:
        try:
            print(f"Updating {scenario_file}...")
            
            with open(f'generated_scenarios/{scenario_file}', 'r') as f:
                json_data = json.load(f)
            
            # Convert with new criteria fix
            xosc_content = converter.convert(json_data)
            
            # Write to converted_scenarios directory 
            output_file = scenario_file.replace('.json', '.xosc')
            with open(f'converted_scenarios/{output_file}', 'w') as f:
                f.write(xosc_content)
            
            print(f"  ✅ Updated converted_scenarios/{output_file}")
            
        except Exception as e:
            print(f"  ❌ Failed to update {scenario_file}: {e}")

if __name__ == '__main__':
    update_key_scenarios()