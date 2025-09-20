#!/usr/bin/env python3
"""
Test script to verify road intelligence integration with xosc_json.py
"""

import json
import logging
from xosc_json import JsonToXoscConverter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

def test_road_intelligence_integration():
    """Test the enhanced spawn selection with road intelligence"""
    
    # Create converter
    converter = JsonToXoscConverter()
    
    # Check if road intelligence data was loaded
    print(f"Available maps with road intelligence: {list(converter.road_intelligence.keys())}")
    
    # Sample scenario JSON with new road intelligence criteria
    test_scenario = {
        "map_name": "Town01",
        "ego_vehicle_model": "vehicle.tesla.model3",
        "weather": "clear",
        "ego_spawn": {
            "criteria": {
                "road_context": "urban",
                "lane_type": "Driving",
                "speed_limit": {"min": 20, "max": 50}
            }
        },
        "actors": [
            {
                "id": "vehicle1",
                "type": "vehicle",
                "model": "vehicle.audi.a2",
                "spawn": {
                    "criteria": {
                        "road_context": "urban",
                        "road_relationship": "different_road",
                        "junction_proximity": {"min": 10, "max": 100},
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": 30, "max": 80}
                    }
                }
            }
        ],
        "actions": [
            {
                "actor_id": "vehicle1",
                "action_type": "speed",
                "speed_value": 30,
                "trigger_type": "time",
                "trigger_value": 2.0
            }
        ],
        "success_distance": 200
    }
    
    try:
        print("\nTesting enhanced spawn selection...")
        xosc_content = converter.convert(test_scenario)
        print("✓ Conversion successful!")
        
        # Write output file
        with open('/home/user/Desktop/Rajiv/test_output.xosc', 'w') as f:
            f.write(xosc_content)
        print("✓ Output written to test_output.xosc")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def test_fallback_behavior():
    """Test fallback when no road intelligence is available"""
    
    # Create converter
    converter = JsonToXoscConverter()
    
    # Remove road intelligence data to test fallback
    original_data = converter.road_intelligence.copy()
    converter.road_intelligence = {}
    
    test_scenario = {
        "map_name": "Town01",
        "ego_vehicle_model": "vehicle.tesla.model3",
        "weather": "clear",
        "ego_spawn": {
            "criteria": {
                "lane_type": "Driving"
            }
        },
        "actors": [
            {
                "id": "vehicle1", 
                "type": "vehicle",
                "model": "vehicle.audi.a2",
                "spawn": {
                    "criteria": {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": 20, "max": 50}
                    }
                }
            }
        ],
        "actions": [],
        "success_distance": 100
    }
    
    try:
        print("\nTesting fallback behavior...")
        xosc_content = converter.convert(test_scenario)
        print("✓ Fallback conversion successful!")
        
        # Restore original data
        converter.road_intelligence = original_data
        
        return True
        
    except Exception as e:
        print(f"✗ Fallback test failed: {e}")
        converter.road_intelligence = original_data
        return False

if __name__ == "__main__":
    print("=== Road Intelligence Integration Test ===")
    
    success1 = test_road_intelligence_integration()
    success2 = test_fallback_behavior()
    
    if success1 and success2:
        print("\n🎉 All tests passed! Road intelligence integration is working.")
    else:
        print("\n❌ Some tests failed. Check the implementation.")