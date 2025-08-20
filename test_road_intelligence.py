#!/usr/bin/env python3
"""
Demonstration of the improved road intelligence-based spawn generation system.
This shows how spawn points are now generated directly from road geometry data,
which is more reliable than using pre-computed spawn points.
"""

import json
import xosc_json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Create converter
converter = xosc_json.JsonToXoscConverter()

# Complex scenario that benefits from road intelligence
scenario = {
    'name': 'complex_urban_scenario',
    'description': 'Complex urban scenario using road intelligence for accurate spawn generation',
    'map_name': 'Town01',
    'weather': 'cloudy',
    'ego_spawn': {
        'criteria': {
            'lane_type': 'Driving',
            'speed_limit': {'min': 20, 'max': 30}
        }
    },
    'actors': [
        {
            'id': 'lead_vehicle',
            'type': 'vehicle',
            'model': 'vehicle.tesla.model3',
            'spawn': {
                'criteria': {
                    'lane_type': 'Driving',
                    'road_relationship': 'same_road',  # On same road as ego
                    'distance_to_ego': {'min': 15, 'max': 25}
                }
            },
            'actions': [
                {
                    'type': 'speed',
                    'target_speed': 20,
                    'trigger': {'type': 'simulation_start'}
                }
            ]
        },
        {
            'id': 'side_vehicle',
            'type': 'vehicle',
            'model': 'vehicle.audi.a2',
            'spawn': {
                'criteria': {
                    'lane_type': 'Driving',
                    'road_context': 'urban',
                    'road_relationship': 'different_road',  # On different road
                    'distance_to_ego': {'min': 30, 'max': 50}
                }
            }
        },
        {
            'id': 'parked_vehicle',
            'type': 'vehicle',
            'model': 'vehicle.bmw.grandtourer',
            'spawn': {
                'criteria': {
                    'lane_type': ['Parking', 'Shoulder'],  # Try parking lanes first
                    'distance_to_ego': {'min': 40, 'max': 60}
                }
            }
        }
    ]
}

print("=" * 60)
print("ROAD INTELLIGENCE-BASED SPAWN GENERATION DEMO")
print("=" * 60)
print("\nThis system now:")
print("1. Uses actual road geometry from road intelligence data")
print("2. Calculates spawn points mathematically from road segments")
print("3. Properly handles lane types, road contexts, and relationships")
print("4. Falls back to enhanced spawn files only when necessary")
print("\nConverting scenario...")

try:
    xosc = converter.convert(scenario)
    print("\n✅ CONVERSION SUCCESSFUL!")
    
    # Save the output
    output_file = '/tmp/complex_urban_scenario.xosc'
    with open(output_file, 'w') as f:
        f.write(xosc)
    print(f"\nScenario saved to: {output_file}")
    
    print("\nKey improvements over the old system:")
    print("- Spawn points are ALWAYS valid (from actual road geometry)")
    print("- Lane type accuracy (knows exact lane definitions)")
    print("- Better distance calculations along road paths")
    print("- Supports all road contexts and relationships")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
