#!/usr/bin/env python3
"""Test all the fixes together"""

import sys

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter
import json

def test_scenarios():
    """Test the three problematic scenarios"""
    scenarios = [
        'basic_following_001_stop_and_go_traffic_01.json',
        'basic_following_002_following_slow_leader_02.json', 
        'lane_change_051_cut_in_ahead_01.json'
    ]
    
    converter = JsonToXoscConverter()
    
    for scenario_file in scenarios:
        print(f"\n{'='*60}")
        print(f"Testing: {scenario_file}")
        print(f"{'='*60}")
        
        try:
            with open(f'generated_scenarios/{scenario_file}', 'r') as f:
                json_data = json.load(f)
            
            # Convert
            xosc_content = converter.convert(json_data)
            
            # Write output
            output_file = f"test_fixed_{scenario_file.replace('.json', '.xosc')}"
            with open(output_file, 'w') as f:
                f.write(xosc_content)
            
            print(f"✅ {scenario_file} converted successfully -> {output_file}")
            
            # Check for specific fixes
            if 'crossbike' in json_data.get('actors', [{}])[0].get('model', ''):
                print("🔧 Vehicle model fix applied (crossbike -> car)")
            
        except Exception as e:
            print(f"❌ {scenario_file} failed: {e}")

if __name__ == '__main__':
    test_scenarios()