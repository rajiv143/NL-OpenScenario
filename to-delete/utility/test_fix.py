#!/usr/bin/env python3
"""Test the lane direction fix"""

import sys

# Mock carla module to avoid import errors
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

# Now import and test
from xosc_json import JsonToXoscConverter
import json

def test_fix():
    # Load the problematic JSON
    with open('generated_scenarios/basic_following_001_stop_and_go_traffic_01.json', 'r') as f:
        json_data = json.load(f)
    
    # Create converter and test
    converter = JsonToXoscConverter()
    
    try:
        xosc_content = converter.convert(json_data)
        
        # Write output for inspection
        with open('test_fix_output.xosc', 'w') as f:
            f.write(xosc_content)
        
        print("✅ Conversion successful! Check test_fix_output.xosc")
        
    except Exception as e:
        print(f"❌ Conversion failed: {e}")

if __name__ == '__main__':
    test_fix()