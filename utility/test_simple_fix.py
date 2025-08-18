#!/usr/bin/env python3
"""Test simple approach: modify JSON to force specific road"""

import sys
import json

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter

def test_simple():
    # Load and modify the JSON to be more specific
    with open('generated_scenarios/basic_following_001_stop_and_go_traffic_01.json', 'r') as f:
        json_data = json.load(f)
    
    # Force ego to a specific position that should work
    json_data['ego_start_position'] = "230.8,-246.0,0.0,6.28"  # Further back on road 27, lane 1
    
    # Remove ego_spawn to use explicit position
    if 'ego_spawn' in json_data:
        del json_data['ego_spawn']
    
    # Make actor constraints less strict
    json_data['actors'][0]['spawn']['criteria'] = {
        'lane_type': 'Driving',
        'road_relationship': 'same_road',
        'lane_relationship': 'same_lane',
        'distance_to_ego': {'min': 10, 'max': 40},  # Wider range
        'relative_position': 'ahead'
    }
    
    print("Modified JSON for testing:")
    print(f"  Ego position: {json_data['ego_start_position']}")
    print(f"  Actor criteria: {json_data['actors'][0]['spawn']['criteria']}")
    
    # Convert
    converter = JsonToXoscConverter()
    
    try:
        xosc_content = converter.convert(json_data)
        
        with open('test_simple_output.xosc', 'w') as f:
            f.write(xosc_content)
        
        print("✅ Simple test successful! Check test_simple_output.xosc")
        
    except Exception as e:
        print(f"❌ Simple test failed: {e}")

if __name__ == '__main__':
    test_simple()