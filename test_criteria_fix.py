#!/usr/bin/env python3
"""Test the criteria fix"""

import sys

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter
import json

def test_criteria():
    # Test the basic following scenario that was failing
    with open('generated_scenarios/basic_following_001_sudden_brake_ahead_01.json', 'r') as f:
        json_data = json.load(f)
    
    print("Testing criteria fix...")
    print(f"Scenario: {json_data.get('scenario_name', 'unknown')}")
    print(f"Success distance: {json_data.get('success_distance', 100)}")
    print(f"Collision allowed: {json_data.get('collision_allowed', True)}")
    
    # Convert
    converter = JsonToXoscConverter()
    
    try:
        xosc_content = converter.convert(json_data)
        
        # Write output
        with open('test_criteria_fixed.xosc', 'w') as f:
            f.write(xosc_content)
        
        print("✅ Conversion successful!")
        
        # Check the generated criteria
        if 'criteria_DrivenDistanceTest' in xosc_content:
            print("✅ DrivenDistanceTest criterion included")
        
        if 'criteria_RunningStopTest' in xosc_content:
            print("❌ RunningStopTest criterion still present (should be removed)")
        else:
            print("✅ RunningStopTest criterion removed")
        
        if 'criteria_CollisionTest' in xosc_content:
            collision_allowed = json_data.get('collision_allowed', True)
            if not collision_allowed:
                print("✅ CollisionTest criterion included (collisions not allowed)")
            else:
                print("⚠️  CollisionTest criterion included even though collisions are allowed")
        else:
            print("✅ CollisionTest criterion not included")
            
    except Exception as e:
        print(f"❌ Conversion failed: {e}")

if __name__ == '__main__':
    test_criteria()