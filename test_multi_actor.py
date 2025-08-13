#!/usr/bin/env python3
"""Test multi-actor scenario conversion"""

import sys

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter
import json

def test_multi_actor():
    # Load and test the problematic multi-actor scenario
    with open('generated_scenarios/multi_actor_167_intersection_chaos_02.json', 'r') as f:
        json_data = json.load(f)
    
    print("Multi-actor scenario analysis:")
    print(f"  Actors: {len(json_data.get('actors', []))}")
    for i, actor in enumerate(json_data.get('actors', [])):
        print(f"    {i+1}. {actor['id']} ({actor['type']}) - {actor.get('model', 'no model')}")
        if 'spawn' in actor:
            criteria = actor['spawn'].get('criteria', {})
            print(f"       Spawn: {criteria.get('road_relationship', 'any_road')}, {criteria.get('is_intersection', False)}")
    
    # Convert and capture debug output
    converter = JsonToXoscConverter()
    
    try:
        xosc_content = converter.convert(json_data)
        print("✅ Conversion successful")
        
        # Write output for inspection
        with open('test_multi_actor_output.xosc', 'w') as f:
            f.write(xosc_content)
            
    except Exception as e:
        print(f"❌ Conversion failed: {e}")

if __name__ == '__main__':
    test_multi_actor()