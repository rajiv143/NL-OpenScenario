#!/usr/bin/env python3
"""Test the original conversion works"""

import sys

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import main
import os

def test_original():
    # Simulate command line arguments
    sys.argv = [
        'xosc_json.py',
        'generated_scenarios/basic_following_001_stop_and_go_traffic_01.json',
        '-o', 'test_original_output.xosc'
    ]
    
    try:
        main()
        print("✅ Original command line test successful!")
        
        # Check if file was created
        if os.path.exists('test_original_output.xosc'):
            print("✅ Output file created successfully")
        else:
            print("❌ Output file not found")
            
    except Exception as e:
        print(f"❌ Original test failed: {e}")

if __name__ == '__main__':
    test_original()